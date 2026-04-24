"""
Sportradar NFL Draft API client with local file caching.

Trial API keys allow 1 request/second. Completed draft years use cached
JSON files and never hit the API again.
"""

import json
import os
import time

import requests

BASE_URL = "https://api.sportradar.us/draft/nfl/trial/v1/en"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "actual-draft")


def _cache_path(year: int, endpoint: str) -> str:
    return os.path.join(CACHE_DIR, str(year), f"{year}{endpoint}.json")


def _fetch_and_cache(url: str, path: str, api_key: str) -> dict:
    print(f"  Fetching {url}")
    for attempt in range(5):
        response = requests.get(url, params={"api_key": api_key}, timeout=30)
        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", 2 ** attempt * 30))
            print(f"  Rate limited (429), retrying in {wait}s...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        break
    data = response.json()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    # Sportradar trial rate limit: 1 request/second
    time.sleep(1.5)
    return data


def get_prospects(year: int, api_key: str, force_update: bool = False) -> dict:
    path = _cache_path(year, "Prospects")
    if os.path.exists(path) and not force_update:
        with open(path) as f:
            return json.load(f)
    url = f"{BASE_URL}/{year}/prospects.json"
    return _fetch_and_cache(url, path, api_key)


def get_draft(year: int, api_key: str, draft_complete: bool = False) -> dict:
    path = _cache_path(year, "Draft")
    if os.path.exists(path) and draft_complete:
        with open(path) as f:
            return json.load(f)
    url = f"{BASE_URL}/{year}/draft.json"
    return _fetch_and_cache(url, path, api_key)
