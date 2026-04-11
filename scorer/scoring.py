"""
Core Leagify scoring logic. Ported from GetLeagifyPoints() in the original C# console app.

Points are awarded per NFL draft pick based on round and position within the round.
Traded picks earn a 10-point bonus on top of the base score.
"""


def get_leagify_points(round_num: int, pick_in_round: int, traded: bool) -> int:
    """
    Calculate Leagify fantasy points for a single NFL draft pick.

    Args:
        round_num:     NFL draft round (1-7)
        pick_in_round: Pick number within the round (1-indexed)
        traded:        Whether the pick was traded before being made

    Returns:
        Integer point value for this pick
    """
    bonus = 10 if traded else 0

    if round_num == 1:
        if pick_in_round == 1:
            return 40 + bonus
        if pick_in_round <= 10:
            return 35 + bonus
        if pick_in_round <= 20:
            return 30 + bonus
        return 25 + bonus

    if round_num == 2:
        if pick_in_round <= 16:
            return 20 + bonus
        return 15 + bonus

    round_base = {3: 10, 4: 8, 5: 7, 6: 6, 7: 5}
    return round_base.get(round_num, 0) + bonus
