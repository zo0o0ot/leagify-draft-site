"""
Leagify NFL Draft Scorer

Reads fantasy draft CSVs and Sportradar draft data, computes scores,
and writes JSON data files into hugo/data/ for the static site.
"""

import csv
import json
import os
import sys
import tomllib
from datetime import datetime, timezone

from scoring import get_leagify_points
from sportradar import get_draft, get_prospects

SCORER_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.dirname(SCORER_DIR)
HUGO_DATA_DIR = os.path.join(REPO_ROOT, "hugo", "data")
FANTASY_DIR = os.path.join(SCORER_DIR, "fantasy-draft")
INFO_DIR = os.path.join(SCORER_DIR, "info")
CONFIG_PATH = os.path.join(SCORER_DIR, "config.toml")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_fantasy_draft(year: int) -> list[dict]:
    path = os.path.join(FANTASY_DIR, str(year), f"{year}FantasyDraft.csv")
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_school_info() -> dict[str, dict]:
    """Returns dict keyed by school name -> {state, conference}"""
    path = os.path.join(INFO_DIR, "SchoolStatesAndConferences.csv")
    result = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            result[row["School"]] = {
                "state": row["State"],
                "conference": row["Conference"],
            }
    return result


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_prospects(data: dict) -> dict[str, dict]:
    """Returns dict keyed by player ID -> prospect info."""
    result = {}
    for p in data.get("prospects", []):
        school = (p.get("team") or {}).get("market") or p.get("team_name", "")
        conference = (p.get("conference") or {}).get("name") or p.get("team_name", "")
        result[p["id"]] = {
            "player_id": p["id"],
            "name": p["name"],
            "school": school,
            "position": p.get("position", ""),
            "conference": conference,
            "experience": p.get("experience", ""),
        }
    return result


def parse_picks(data: dict, prospects: dict[str, dict], school_info: dict) -> list[dict]:
    """Parse all picks from draft JSON into enriched pick dicts."""
    picks = []
    for round_idx, round_data in enumerate(data.get("rounds", []), start=1):
        for pick in round_data.get("picks", []):
            prospect_data = pick.get("prospect")
            if not prospect_data:
                continue

            player_id = prospect_data.get("id")
            prospect = prospects.get(player_id, {})

            # Use verified school from prospects list; fall back to draft JSON
            school = prospect.get("school") or prospect_data.get("team_name", "")
            info = school_info.get(school, {"state": "", "conference": ""})

            traded = pick.get("traded") is True

            picks.append({
                "pick": pick.get("overall"),
                "round": round_idx,
                "pick_in_round": pick.get("number"),
                "player": prospect_data.get("name", ""),
                "school": school,
                "position": prospect.get("position") or prospect_data.get("position", ""),
                "experience": prospect.get("experience") or prospect_data.get("experience", ""),
                "traded": traded,
                "points": get_leagify_points(round_idx, pick.get("number", 0), traded),
                "state": info["state"],
                "conference": info["conference"],
                "player_id": player_id,
            })
    return picks


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def assign_owners(picks: list[dict], fantasy: list[dict]) -> list[dict]:
    """Join picks to fantasy draft by school name."""
    school_to_owner = {row["Player"]: row for row in fantasy}
    owned = []
    for pick in picks:
        owner_row = school_to_owner.get(pick["school"])
        if owner_row:
            owned.append({**pick, "owner": owner_row["Owner"]})
    return owned


def assign_owners_all(picks: list[dict], fantasy: list[dict]) -> list[dict]:
    """All picks with owner assigned; unowned schools get owner=''."""
    school_to_owner = {row["Player"]: row["Owner"] for row in fantasy}
    return [{**pick, "owner": school_to_owner.get(pick["school"], "")} for pick in picks]


def compute_owner_scores(owned_picks: list[dict]) -> list[dict]:
    totals: dict[str, int] = {}
    for pick in owned_picks:
        totals[pick["owner"]] = totals.get(pick["owner"], 0) + pick["points"]
    sorted_owners = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    return [
        {"owner": owner, "points": points, "rank": rank + 1}
        for rank, (owner, points) in enumerate(sorted_owners)
    ]


def compute_school_stats(owned_picks: list[dict], fantasy: list[dict]) -> list[dict]:
    fantasy_by_school = {row["Player"]: row for row in fantasy}
    school_points: dict[str, int] = {}
    school_owner: dict[str, str] = {}

    for pick in owned_picks:
        school = pick["school"]
        school_points[school] = school_points.get(school, 0) + pick["points"]
        school_owner[school] = pick["owner"]

    stats = []
    for school, actual in school_points.items():
        row = fantasy_by_school.get(school, {})
        projected = int(row.get("ProjectedPoints", 0))
        bid = int(row.get("Bid", 0))
        tier = row.get("Position", "")
        projected_for_ratio = projected if projected > 0 else 1
        stats.append({
            "school": school,
            "owner": school_owner[school],
            "tier": tier,
            "bid": bid,
            "projected": projected,
            "actual": actual,
            "difference": actual - projected,
            "performance_ratio": round(actual / projected_for_ratio, 3),
            "points_per_dollar": round(actual / bid, 3) if bid > 0 else None,
        })
    return sorted(stats, key=lambda x: x["actual"], reverse=True)


def compute_round_breakdown(owned_picks: list[dict]) -> list[dict]:
    totals: dict[tuple, dict] = {}
    for pick in owned_picks:
        key = (pick["owner"], pick["round"])
        if key not in totals:
            totals[key] = {"owner": pick["owner"], "round": pick["round"], "picks": 0, "points": 0}
        totals[key]["picks"] += 1
        totals[key]["points"] += pick["points"]
    return sorted(totals.values(), key=lambda x: (x["owner"], x["round"]))


def compute_flops(fantasy: list[dict], owned_picks: list[dict]) -> list[dict]:
    """Schools drafted in fantasy that had zero NFL picks."""
    schools_with_picks = {pick["school"] for pick in owned_picks}
    flops = []
    for row in fantasy:
        if row["Player"] not in schools_with_picks:
            flops.append({
                "school": row["Player"],
                "owner": row["Owner"],
                "bid": int(row["Bid"]),
                "projected": int(row["ProjectedPoints"]),
            })
    return sorted(flops, key=lambda x: x["projected"], reverse=True)


def compute_draft_roster(fantasy: list[dict], owned_picks: list[dict]) -> list[dict]:
    """Every school an owner drafted, with actual points (0 if none scored)."""
    school_actual: dict[str, int] = {}
    for pick in owned_picks:
        school_actual[pick["school"]] = school_actual.get(pick["school"], 0) + pick["points"]

    roster = []
    for row in fantasy:
        school = row["Player"]
        roster.append({
            "owner": row["Owner"],
            "school": school,
            "tier": row.get("Position", ""),
            "bid": int(row["Bid"]),
            "projected": int(row["ProjectedPoints"]),
            "actual": school_actual.get(school, 0),
        })
    return sorted(roster, key=lambda x: (x["owner"], -x["actual"]))


def compute_nobody_schools(picks: list[dict], owned_picks: list[dict]) -> list[dict]:
    """Schools with NFL picks but no fantasy owner."""
    owned_schools = {pick["school"] for pick in owned_picks}
    unowned: dict[str, int] = {}
    for pick in picks:
        if pick["school"] not in owned_schools:
            unowned[pick["school"]] = unowned.get(pick["school"], 0) + pick["points"]
    return sorted(
        [{"school": s, "points": p} for s, p in unowned.items()],
        key=lambda x: x["points"],
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Draft status
# ---------------------------------------------------------------------------

def compute_draft_status(year: int, draft_data: dict, picks: list[dict], force_complete: bool = False) -> dict:
    draft_info = draft_data.get("draft", {})
    overall_status = draft_info.get("status", "")
    rounds = draft_data.get("rounds", [])

    if overall_status == "complete" or force_complete:
        status = "complete"
        current_round = 7
        current_day = 3
    elif not picks:
        status = "pre_draft"
        current_round = 0
        current_day = 0
    else:
        # Determine which rounds are closed
        closed_rounds = [
            i + 1 for i, r in enumerate(rounds)
            if r.get("status") == "closed"
        ]
        rounds_complete = closed_rounds
        max_closed = max(closed_rounds) if closed_rounds else 0

        # Day boundaries: Day 1=R1, Day 2=R2-3, Day 3=R4-7
        day1_done = max_closed >= 1 and (len(rounds) < 2 or rounds[1].get("status") != "inprogress")
        day2_done = max_closed >= 3 and (len(rounds) < 4 or rounds[3].get("status") != "inprogress")

        in_progress_rounds = [
            i + 1 for i, r in enumerate(rounds)
            if r.get("status") == "inprogress"
        ]

        if in_progress_rounds:
            status = "in_progress"
            current_round = in_progress_rounds[0]
        elif max_closed == 1:
            status = "between_days"
            current_round = 1
        elif max_closed == 3:
            status = "between_days"
            current_round = 3
        else:
            status = "in_progress"
            current_round = max_closed + 1 if max_closed < 7 else 7

        if current_round <= 1:
            current_day = 1
        elif current_round <= 3:
            current_day = 2
        else:
            current_day = 3

    return {
        "year": year,
        "status": status,
        "current_round": current_round,
        "current_day": current_day,
        "draft_complete": overall_status == "complete",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_picks_made": len(picks),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_json(data_dir: str, filename: str, data) -> None:
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Wrote {path}")


# ---------------------------------------------------------------------------
# Per-year pipeline
# ---------------------------------------------------------------------------

def score_year(year: int, draft_complete: bool, api_key: str) -> dict:
    print(f"\n=== Scoring {year} ===")

    fantasy = load_fantasy_draft(year)
    school_info = load_school_info()

    print("  Loading prospects...")
    update_prospects = not draft_complete
    prospects_data = get_prospects(year, api_key, force_update=update_prospects)
    prospects = parse_prospects(prospects_data)

    print("  Loading draft...")
    draft_data = get_draft(year, api_key, draft_complete=draft_complete)

    picks = parse_picks(draft_data, prospects, school_info)
    owned_picks = assign_owners(picks, fantasy)

    unmatched = [p for p in picks if p["school"] not in {o["school"] for o in owned_picks}]
    if unmatched:
        unmatched_schools = sorted({p["school"] for p in unmatched})
        print(f"  WARNING: {len(unmatched)} picks from schools with no fantasy owner: {unmatched_schools}")

    data_dir = os.path.join(HUGO_DATA_DIR, str(year))
    write_json(data_dir, "owner_scores.json", compute_owner_scores(owned_picks))
    write_json(data_dir, "school_stats.json", compute_school_stats(owned_picks, fantasy))
    write_json(data_dir, "draft_roster.json", compute_draft_roster(fantasy, owned_picks))
    write_json(data_dir, "round_breakdown.json", compute_round_breakdown(owned_picks))
    write_json(data_dir, "flops.json", compute_flops(fantasy, owned_picks))
    write_json(data_dir, "nobody_schools.json", compute_nobody_schools(picks, owned_picks))
    write_json(data_dir, "picks.json", assign_owners_all(picks, fantasy))

    return compute_draft_status(year, draft_data, picks, force_complete=draft_complete)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    api_key = os.environ.get("SPORTRADAR_API_KEY", "")
    if not api_key:
        print("ERROR: SPORTRADAR_API_KEY environment variable not set.")
        sys.exit(1)

    config = load_config()
    years = sorted(int(y) for y in config.keys())

    # Allow targeting a single year via CLI arg: python score.py 2025
    if len(sys.argv) > 1:
        try:
            years = [int(sys.argv[1])]
        except ValueError:
            print(f"ERROR: Invalid year argument: {sys.argv[1]}")
            sys.exit(1)

    latest_status = None
    for year in years:
        year_config = config.get(str(year), {})
        draft_complete = year_config.get("draft_complete", False)
        status = score_year(year, draft_complete, api_key)
        latest_status = status

    # Write draft status using the most recent year's data
    if latest_status:
        write_json(HUGO_DATA_DIR, "draft_status.json", latest_status)

    print("\nDone.")


if __name__ == "__main__":
    main()
