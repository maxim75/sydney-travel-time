"""Plan a journey between two addresses using the Address Info API.

Usage:
    uv run main.py "1 Martin Pl, Sydney" "Bondi Beach" --arrive-by 2026-09-28T09:00

ADDRESS_INFO_API_KEY is read from the environment or a .env file.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("ADDRESS_INFO_BASE_URL", "https://address-info.d.imaxim.org")
SYDNEY_TZ = ZoneInfo("Australia/Sydney")


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def api_get(path: str, params: dict, api_key: str) -> dict:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    request = urllib.request.Request(
        f"{BASE_URL}{path}?{query}",
        headers={"X-API-Key": api_key, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise ApiError(f"{e.code} {e.reason} for {path}: {body}", status=e.code) from e
    except urllib.error.URLError as e:
        raise ApiError(f"Request to {path} failed: {e.reason}") from e


def resolve_address(text: str, api_key: str) -> dict:
    """Return the best-matching address for free text as {address_detail_pid, full_address, ...}."""
    results = api_get("/v1/addresses/search", {"q": text, "limit": 1}, api_key)["results"]
    if not results:
        raise ApiError(f"No address found for {text!r}")
    return results[0]["address"]


def plan_journey(
    from_pid: str,
    to_pid: str,
    api_key: str,
    mode: str = "transit",
    depart_at: str | None = None,
    arrive_by: str | None = None,
    limit: int = 3,
) -> dict:
    return api_get(
        "/v1/journeys",
        {
            "mode": mode,
            "from_address": from_pid,
            "to_address": to_pid,
            "depart_at": depart_at,
            "arrive_by": arrive_by,
            "limit": limit,
        },
        api_key,
    )


def format_time(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(SYDNEY_TZ).strftime("%a %H:%M")


def format_duration(seconds: int) -> str:
    hours, minutes = divmod(round(seconds / 60), 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes} min"


def format_leg(leg: dict) -> str:
    mode = leg["mode"].replace("_", " ")
    if leg["route"]:
        mode = f"{mode} {leg['route']}"
        if leg["headsign"]:
            mode += f" towards {leg['headsign']}"
    places = f"{leg['from_name'] or 'start'} -> {leg['to_name'] or 'end'}"
    return (
        f"    {format_time(leg['departure'])}-{format_time(leg['arrival'])[4:]}  "
        f"{mode}: {places} ({format_duration(leg['duration_s'])}, {leg['distance_m'] / 1000:.1f} km)"
    )


def print_response(response: dict) -> None:
    print(f"From: {response['origin']['name']}")
    print(f"To:   {response['destination']['name']}")
    print(f"Mode: {response['mode']}")
    if not response["journeys"]:
        errors = ", ".join(response["routing_errors"]) or "unknown reason"
        print(f"\nNo journeys found ({errors}).")
        return
    for i, journey in enumerate(response["journeys"], 1):
        print(
            f"\nJourney {i}: {format_time(journey['departure'])} -> {format_time(journey['arrival'])}, "
            f"{format_duration(journey['duration_s'])}, {journey['transfers']} transfer(s), "
            f"walk {format_duration(journey['walk_time_s'])}"
        )
        for leg in journey["legs"]:
            print(format_leg(leg))


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan a journey between two addresses.")
    parser.add_argument("origin", help="Origin address (free text)")
    parser.add_argument("destination", help="Destination address (free text)")
    parser.add_argument("--mode", choices=["transit", "car"], default="transit")
    when = parser.add_mutually_exclusive_group()
    when.add_argument("--depart-at", help="ISO date-time, Sydney local if no offset (default: now)")
    when.add_argument("--arrive-by", help="ISO date-time, Sydney local if no offset")
    parser.add_argument("--limit", type=int, default=3, choices=range(1, 11), metavar="1-10")
    parser.add_argument("--json", action="store_true", help="Print the raw JSON response")
    args = parser.parse_args()

    api_key = os.environ.get("ADDRESS_INFO_API_KEY")
    if not api_key:
        parser.error("set ADDRESS_INFO_API_KEY in .env or the environment")

    depart_at = args.depart_at
    if not depart_at and not args.arrive_by:
        depart_at = datetime.now(SYDNEY_TZ).replace(second=0, microsecond=0).isoformat()

    try:
        origin = resolve_address(args.origin, api_key)
        destination = resolve_address(args.destination, api_key)
        response = plan_journey(
            origin["address_detail_pid"],
            destination["address_detail_pid"],
            api_key,
            mode=args.mode,
            depart_at=depart_at,
            arrive_by=args.arrive_by,
            limit=args.limit,
        )
    except ApiError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(response, indent=2))
    else:
        print_response(response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
