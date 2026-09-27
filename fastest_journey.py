"""Fastest public transport journey between two buildings (G-NAF addresses)."""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta

from main import plan_journey


@dataclass
class JourneySummary:
    depart_building_id: str
    depart_building_address: str
    depart_latitude: float
    depart_longitude: float
    departure: datetime
    arrival: datetime
    journey_minutes: int
    walking_minutes: int
    walking_distance_m: int
    transports: int
    has_bus: bool
    has_train: bool
    has_ferry: bool
    has_tram: bool
    access_walk_m: int
    egress_walk_m: int
    legs: list[dict]


TRANSIT_MODES = {"train", "metro", "light_rail", "ferry", "bus", "coach", "other"}
MAX_END_WALK_M = 1200  # longest walk to the first stop, or from the last stop, that counts as covered


def end_walks(journey: dict) -> tuple[float, float]:
    """Walk from the start to the first stop, and from the last stop to the end (0 if none)."""
    legs = journey["legs"]
    access = legs[0]["distance_m"] if legs and legs[0]["mode"] == "walk" else 0
    egress = legs[-1]["distance_m"] if legs and legs[-1]["mode"] == "walk" else 0
    return access, egress


def within_walk_limit(journey: dict) -> bool:
    """Walk to the first stop and from the last stop each within MAX_END_WALK_M.

    Walk-only journeys always pass: the planner only offers them alone when walking is
    fastest (e.g. 1.5 km from Pyrmont to the QVB), which is not a lack of coverage.
    """
    if not any(leg["mode"] in TRANSIT_MODES for leg in journey["legs"]):
        return True
    return max(end_walks(journey)) <= MAX_END_WALK_M


def fastest_journey(
    from_pid: str,
    to_pid: str,
    arrive_by: datetime | str,
    api_key: str | None = None,
) -> tuple[JourneySummary | None, bool]:
    """Fastest journey between two G-NAF addresses arriving by `arrive_by`, within the walking limit.

    Naive datetimes and strings without an offset are Sydney local time. Returns the journey
    (None if no journey is within the walking limit) and whether any journey was found at all.
    """
    api_key = api_key or os.environ["ADDRESS_INFO_API_KEY"]
    if isinstance(arrive_by, datetime):
        arrive_by = arrive_by.isoformat()
    response = plan_journey(from_pid, to_pid, api_key, arrive_by=arrive_by, limit=10)
    journeys = [j for j in response["journeys"] if within_walk_limit(j)]
    if not journeys:
        return None, bool(response["journeys"])

    # Journeys come latest-departure first, so on a tie min() keeps the one leaving latest.
    journey = min(journeys, key=lambda j: j["duration_s"])
    origin = response["origin"]
    return JourneySummary(
        depart_building_id=origin["id"],
        depart_building_address=origin["name"],
        depart_latitude=origin["latitude"],
        depart_longitude=origin["longitude"],
        **journey_stats(journey),
    ), True


def journey_stats(journey: dict) -> dict:
    """Times, walking, modes and legs of one journey from the /v1/journeys response."""
    modes = {leg["mode"] for leg in journey["legs"]}
    access, egress = end_walks(journey)
    return {
        "departure": datetime.fromisoformat(journey["departure"]),
        "arrival": datetime.fromisoformat(journey["arrival"]),
        "journey_minutes": round(journey["duration_s"] / 60),
        "walking_minutes": round(journey["walk_time_s"] / 60),
        "walking_distance_m": round(sum(leg["distance_m"] for leg in journey["legs"] if leg["mode"] == "walk")),
        "transports": sum(leg["mode"] in TRANSIT_MODES for leg in journey["legs"]),
        "has_bus": bool(modes & {"bus", "coach"}),
        "has_train": bool(modes & {"train", "metro"}),
        "has_ferry": "ferry" in modes,
        "has_tram": "light_rail" in modes,
        "access_walk_m": round(access),
        "egress_walk_m": round(egress),
        "legs": [
            {"mode": leg["mode"], "route": leg.get("route"), "minutes": round(leg["duration_s"] / 60),
             "distance_m": round(leg["distance_m"]), "from": leg.get("from_name"), "to": leg.get("to_name")}
            for leg in journey["legs"]
        ],
    }


SEARCH_STEP = timedelta(hours=2)  # the API only looks about 2.5 h ahead of depart_at


def earliest_journey(
    from_pid: str,
    to_pid: str,
    depart_at: datetime,
    give_up_at: datetime,
    api_key: str | None = None,
) -> tuple[dict | None, int, bool]:
    """Earliest-arriving journey leaving between `depart_at` and `give_up_at`, within the walking limit.

    The API only searches a couple of hours ahead, so while nothing suitable runs, the search
    moves forward in SEARCH_STEP steps until a journey is found or `give_up_at` is passed.
    Journeys leaving after `give_up_at` are ignored. Naive datetimes are Sydney local time.
    Returns the journey_stats() of the journey (or None), the number of searches made, and
    whether any journey leaving in time was found at all (even beyond the walking limit).
    """
    api_key = api_key or os.environ["ADDRESS_INFO_API_KEY"]
    at, searches, found_any = depart_at, 0, False
    while at <= give_up_at:
        searches += 1
        response = plan_journey(from_pid, to_pid, api_key, depart_at=at.isoformat(), limit=10)
        in_time = [j for j in response["journeys"] if datetime.fromisoformat(j["departure"]) <= give_up_at]
        found_any = found_any or bool(in_time)
        journeys = [j for j in in_time if within_walk_limit(j)]
        if journeys:
            journey = min(journeys, key=lambda j: (datetime.fromisoformat(j["arrival"]), j["duration_s"]))
            return journey_stats(journey), searches, True
        at += SEARCH_STEP
    return None, searches, found_any
