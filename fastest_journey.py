"""Fastest public transport journey between two buildings (G-NAF addresses)."""

import os
from dataclasses import dataclass
from datetime import datetime

from main import plan_journey


@dataclass
class JourneySummary:
    depart_building_id: str
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
    modes = {leg["mode"] for leg in journey["legs"]}
    origin = response["origin"]
    return JourneySummary(
        depart_building_id=origin["id"],
        depart_latitude=origin["latitude"],
        depart_longitude=origin["longitude"],
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
