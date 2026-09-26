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


TRANSIT_MODES = {"train", "metro", "light_rail", "ferry", "bus", "coach", "other"}


def fastest_journey(
    from_pid: str,
    to_pid: str,
    arrive_by: datetime | str,
    api_key: str | None = None,
) -> JourneySummary | None:
    """Fastest public transport journey between two G-NAF addresses arriving by `arrive_by`.

    Naive datetimes and strings without an offset are Sydney local time.
    Returns None when no journey is found.
    """
    api_key = api_key or os.environ["ADDRESS_INFO_API_KEY"]
    if isinstance(arrive_by, datetime):
        arrive_by = arrive_by.isoformat()
    response = plan_journey(from_pid, to_pid, api_key, arrive_by=arrive_by, limit=10)
    if not response["journeys"]:
        return None

    # Journeys come latest-departure first, so on a tie min() keeps the one leaving latest.
    journey = min(response["journeys"], key=lambda j: j["duration_s"])
    origin = response["origin"]
    return JourneySummary(
        depart_building_id=origin["id"],
        depart_building_address=origin["name"],
        depart_latitude=origin["latitude"],
        depart_longitude=origin["longitude"],
        **journey_stats(journey),
    )


def journey_stats(journey: dict) -> dict:
    """Times, walking and modes of one journey from the /v1/journeys response."""
    modes = {leg["mode"] for leg in journey["legs"]}
    return dict(
        departure=datetime.fromisoformat(journey["departure"]),
        arrival=datetime.fromisoformat(journey["arrival"]),
        journey_minutes=round(journey["duration_s"] / 60),
        walking_minutes=round(journey["walk_time_s"] / 60),
        walking_distance_m=round(sum(leg["distance_m"] for leg in journey["legs"] if leg["mode"] == "walk")),
        transports=sum(leg["mode"] in TRANSIT_MODES for leg in journey["legs"]),
        has_bus=bool(modes & {"bus", "coach"}),
        has_train=bool(modes & {"train", "metro"}),
        has_ferry="ferry" in modes,
        has_tram="light_rail" in modes,
    )


SEARCH_STEP = timedelta(hours=2)  # the API only looks about 2.5 h ahead of depart_at


def earliest_journey(
    from_pid: str,
    to_pid: str,
    depart_at: datetime,
    give_up_at: datetime,
    api_key: str | None = None,
) -> tuple[dict | None, int]:
    """Earliest-arriving journey leaving at or after `depart_at`, waiting overnight if need be.

    The API only searches a couple of hours ahead, so when nothing runs, the search moves
    forward in SEARCH_STEP steps until a journey is found or `give_up_at` is passed.
    Naive datetimes are Sydney local time. Returns the journey_stats() of the journey (or
    None) and the number of searches made.
    """
    api_key = api_key or os.environ["ADDRESS_INFO_API_KEY"]
    at, searches = depart_at, 0
    while at <= give_up_at:
        searches += 1
        response = plan_journey(from_pid, to_pid, api_key, depart_at=at.isoformat(), limit=10)
        if response["journeys"]:
            journey = min(response["journeys"], key=lambda j: (datetime.fromisoformat(j["arrival"]), j["duration_s"]))
            return journey_stats(journey), searches
        at += SEARCH_STEP
    return None, searches
