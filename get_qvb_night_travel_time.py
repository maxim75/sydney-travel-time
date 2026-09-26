"""Earliest trips leaving a building at night, waiting overnight if need be (library used by datasets.py).

Each row records the wait at the departure building, the trip itself, and the total time
from the requested departure to arrival.
"""

from datetime import datetime, time, timedelta

from fastest_journey import SEARCH_STEP, earliest_journey
from get_sydney_building_travel_time import with_retries
from main import SYDNEY_TZ, ApiError

MORNING = time(5, 0)  # a first service leaving after this, the day after departure, is "next morning"
COLUMNS = [
    "address_detail_pid", "h3_cell", "status", "address", "requested", "departure", "arrival",
    "wait_minutes", "journey_minutes", "total_minutes", "walking_minutes", "walking_distance_m",
    "transports", "has_bus", "has_train", "has_ferry", "has_tram", "next_morning", "searches",
]


def sydney(value: datetime) -> datetime:
    """Naive values are Sydney local time."""
    return value.replace(tzinfo=SYDNEY_TZ) if value.tzinfo is None else value.astimezone(SYDNEY_TZ)


def next_morning_after(depart_at: datetime, at: time) -> datetime:
    """`at` on the morning after leaving at `depart_at` (the same day if leaving after midnight)."""
    day = depart_at.date() + timedelta(days=1 if depart_at.time() >= time(12) else 0)
    return datetime.combine(day, at, SYDNEY_TZ)


def night_row(cell: str, pid: str, address: str, reachable: bool, anchor: str, depart_at: datetime,
              until: datetime) -> dict:
    """Earliest trip from the `anchor` building to a sampled building, leaving at or after `depart_at`.

    If nothing runs, the search moves forward until `until`, so places only reachable by a
    morning service are included (next_morning). A building with no weekday journey in the
    sample (`reachable` false) first gets a single search two hours before `until`, and the
    full overnight search only if that finds something; unreachable searches are slow.
    """
    base = {"address_detail_pid": pid, "h3_cell": cell, "address": address, "requested": depart_at.isoformat()}
    try:
        searches = 0
        if not reachable:
            probe = until - SEARCH_STEP
            stats, searches = with_retries(lambda: earliest_journey(anchor, pid, probe, probe))
            if stats is None:
                return {**base, "status": "no_journey", "searches": searches}
        stats, more = with_retries(lambda: earliest_journey(anchor, pid, depart_at, until))
        searches += more
    except ApiError as e:
        if e.status == 404:
            return {**base, "status": "not_found"}
        raise
    if stats is None:
        return {**base, "status": "no_journey", "searches": searches}
    departure, arrival = stats["departure"], stats["arrival"]
    return {
        **base, **stats, "status": "ok", "searches": searches,
        "wait_minutes": round((departure - depart_at).total_seconds() / 60),
        "total_minutes": round((arrival - depart_at).total_seconds() / 60),
        "next_morning": departure >= next_morning_after(depart_at, MORNING),
    }
