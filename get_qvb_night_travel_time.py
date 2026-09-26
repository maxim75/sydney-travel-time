"""Earliest public transport trip from the QVB on a Saturday night to every sampled building.

The reverse of get_sydney_building_travel_time.py --sample-hex: for each hexagon in its
results (--targets), plans a trip from the Queen Victoria Building to the building sampled
there, leaving at --depart-at (default 21:00 on the first Saturday of November 2026). When
nothing runs, it keeps searching later, up to --until (default 10:00 the next morning), so
places only reachable by a morning service are included; they are flagged next_morning.
Hexagons with no journey in the targets run (no service there on a weekday morning either)
first get a single search two hours before --until, and the full overnight search only if
that finds something; unreachable searches are slow, and there are thousands of them.

Each row records the wait at the QVB, the trip itself, and the total time from --depart-at
to arrival. Results are written in batches to --output-dir with a process log, as in the
other script, so a restarted run skips buildings already done.

Usage:
    caffeinate -is uv run get_qvb_night_travel_time.py --workers 3 [--depart-at 2026-10-10T21:00] [--limit 100]
"""

import argparse
import csv
import itertools
import os
import sys
from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from functools import partial
from pathlib import Path

from fastest_journey import SEARCH_STEP, earliest_journey
from get_sydney_building_travel_time import QVB, BatchWriter, load_processed, log, run_parallel, with_retries
from main import SYDNEY_TZ, ApiError

MORNING = time(5, 0)  # a first service leaving after this, the day after --depart-at, is "next morning"
COLUMNS = [
    "address_detail_pid", "h3_cell", "status", "address", "requested", "departure", "arrival",
    "wait_minutes", "journey_minutes", "total_minutes", "walking_minutes", "walking_distance_m",
    "transports", "has_bus", "has_train", "has_ferry", "has_tram", "next_morning", "searches",
]


def first_weekday(year: int, month: int, weekday: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7)


DEPART_AT = datetime.combine(first_weekday(2026, 11, 5), time(21, 0), SYDNEY_TZ)  # Saturday


def sydney(value: datetime) -> datetime:
    """Naive values are Sydney local time."""
    return value.replace(tzinfo=SYDNEY_TZ) if value.tzinfo is None else value.astimezone(SYDNEY_TZ)


def next_morning_after(depart_at: datetime, at: time) -> datetime:
    """`at` on the morning after a night out leaving at `depart_at` (the same day if after midnight)."""
    day = depart_at.date() + timedelta(days=1 if depart_at.time() >= time(12) else 0)
    return datetime.combine(day, at, SYDNEY_TZ)


def load_targets(results_dir: Path, processed: set[str]) -> Iterator[tuple[str, str, str, bool]]:
    """(h3 cell, building ID, address, had a journey) for each hexagon of a --sample-hex run.

    The latest result for a hexagon wins. Nearest (by weekday trip time) first.
    """
    cells: dict[str, dict] = {}
    for path in sorted(results_dir.glob("travel_times_*.csv")):
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                cells[row["h3_cell"]] = row
    targets = [r for r in cells.values() if r["status"] != "not_found"]
    log(f"{len(targets):,} target hexagons in {results_dir}")
    # Places with the quickest weekday trip first, so a partial run covers the middle of the city
    for row in sorted(targets, key=lambda r: (r["status"] != "ok", int(r["journey_minutes"] or 0), r["h3_cell"])):
        if row["address_detail_pid"] not in processed:
            yield row["h3_cell"], row["address_detail_pid"], row["depart_building_address"], row["status"] == "ok"


def night_row(cell: str, pid: str, address: str, reachable: bool, depart_at: datetime, until: datetime) -> dict:
    base = {"address_detail_pid": pid, "h3_cell": cell, "address": address, "requested": depart_at.isoformat()}
    try:
        searches = 0
        if not reachable:
            probe = until - SEARCH_STEP
            stats, searches = with_retries(lambda: earliest_journey(QVB, pid, probe, probe))
            if stats is None:
                return {**base, "status": "no_journey", "searches": searches}
        stats, more = with_retries(lambda: earliest_journey(QVB, pid, depart_at, until))
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--targets", type=Path, default=Path("data/travel_times_hex9"),
                        help="Output folder of get_sydney_building_travel_time.py --sample-hex")
    parser.add_argument("--output-dir", type=Path, default=Path("data/night_from_qvb_hex9"))
    parser.add_argument("--workers", type=int, default=8, help="Parallel requests (default: 8)")
    parser.add_argument("--batch-size", type=int, default=1000, help="Rows per output CSV (default: 1000)")
    parser.add_argument("--depart-at", type=datetime.fromisoformat, default=DEPART_AT,
                        help=f"ISO date-time, Sydney local if no offset (default: {DEPART_AT:%Y-%m-%dT%H:%M})")
    parser.add_argument("--until", type=datetime.fromisoformat,
                        help="Latest departure to search for (default: 10:00 the next morning)")
    parser.add_argument("--limit", type=int, help="Process at most this many hexagons in this run")
    args = parser.parse_args()
    if "ADDRESS_INFO_API_KEY" not in os.environ:
        parser.error("set ADDRESS_INFO_API_KEY in .env or the environment")
    depart_at = sydney(args.depart_at)
    until = sydney(args.until) if args.until else next_morning_after(depart_at, time(10))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    processed = load_processed(args.output_dir)
    log(f"Leave the QVB at {depart_at:%a %d %b %Y %H:%M}, searching until {until:%a %H:%M}; "
        f"{len(processed):,} already processed")

    work = load_targets(args.targets, processed)
    if args.limit:
        work = itertools.islice(work, args.limit)
    writer = BatchWriter(args.output_dir, args.batch_size, COLUMNS)
    failed = run_parallel(
        ((cell, partial(night_row, cell, pid, address, reachable, depart_at, until))
         for cell, pid, address, reachable in work),
        writer, args.workers,
    )
    log(f"Done: {writer.written:,} written, {failed:,} failed (will be retried on the next run)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
