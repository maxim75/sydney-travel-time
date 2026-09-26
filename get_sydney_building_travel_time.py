"""Fastest public transport journey from every Greater Sydney building to the QVB.

Reads building IDs from data/sydney_buildings.csv (see get_sydney_buildings.py) and,
for each, finds the fastest journey arriving at the Queen Victoria Building by 9:00
on the first Monday of November 2026 (override with --arrive-by). Output files do
not record the arrival time, so use a fresh --output-dir when changing it.

Results go to numbered CSV files of --batch-size rows in --output-dir. After a file
is written, its building IDs are appended to processed.log in the same directory,
so a restarted run skips them. Buildings with no journey or unknown to the API are
recorded too (status "no_journey" or "not_found"); buildings whose requests fail are
not, so they are retried next run.

With --sample-hex RES, buildings are grouped into H3 hexagons of that resolution and
only one row is written per hexagon: the building nearest the hexagon's centre, or
the next nearest (up to --hex-candidates) when it has no journey or is not found.

Usage:
    uv run get_sydney_building_travel_time.py --workers 8 [--limit 100] [--sample-hex 9]
"""

import argparse
import csv
import itertools
import math
import os
import sys
import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, fields
from datetime import date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import TypeVar

import h3

from fastest_journey import JourneySummary, fastest_journey
from main import SYDNEY_TZ, ApiError

QVB = "GANSW706029353"  # 429-481 George Street, Sydney NSW 2000
LOG_NAME = "processed.log"
BATCH_PREFIX = "travel_times_"
MAX_ATTEMPTS = 4
T = TypeVar("T")
COLUMNS = ["address_detail_pid", "status", "h3_cell", *(f.name for f in fields(JourneySummary))]


def first_monday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(7 - first.weekday()) % 7)


ARRIVE_BY = datetime.combine(first_monday(2026, 11), datetime.min.time().replace(hour=9), SYDNEY_TZ)


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def batch_files(output_dir: Path) -> list[Path]:
    return sorted(output_dir.glob(f"{BATCH_PREFIX}*.csv"))


def load_processed(output_dir: Path) -> set[str]:
    """IDs in processed.log, plus any batch file written just before a crash but not yet logged."""
    log_path = output_dir / LOG_NAME
    processed = set(log_path.read_text().split()) if log_path.exists() else set()
    missing = []
    for path in batch_files(output_dir):
        with path.open(newline="") as f:
            missing += [row["address_detail_pid"] for row in csv.DictReader(f) if row["address_detail_pid"] not in processed]
    if missing:
        log(f"Recovering {len(missing):,} IDs from batch files missing in {LOG_NAME}")
        append_log(log_path, missing)
        processed.update(missing)
    return processed


def append_log(log_path: Path, ids: list[str]) -> None:
    with log_path.open("a") as f:
        f.write("".join(f"{pid}\n" for pid in ids))
        f.flush()
        os.fsync(f.fileno())


class BatchWriter:
    """Writes rows to numbered CSV files, then records their IDs in the process log."""

    def __init__(self, output_dir: Path, batch_size: int, columns: list[str] = COLUMNS):
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.columns = columns
        existing = batch_files(output_dir)
        self.next_index = int(existing[-1].stem.removeprefix(BATCH_PREFIX)) + 1 if existing else 1
        self.rows: list[dict] = []
        self.written = 0
        self.started = time.monotonic()

    def add(self, row: dict) -> None:
        self.rows.append(row)
        if len(self.rows) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self.rows:
            return
        path = self.output_dir / f"{BATCH_PREFIX}{self.next_index:05d}.csv"
        tmp = path.with_suffix(".csv.tmp")
        with tmp.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.columns)
            writer.writeheader()
            writer.writerows(self.rows)
        tmp.replace(path)
        append_log(self.output_dir / LOG_NAME, [row["address_detail_pid"] for row in self.rows])
        self.written += len(self.rows)
        self.next_index += 1
        self.rows = []
        rate = self.written / (time.monotonic() - self.started)
        log(f"Wrote {path.name}: {self.written:,} rows this run ({rate:.1f}/s)")


def with_retries(call: Callable[[], T]) -> T:
    """Run an API call, retrying rate limits and server errors with exponential backoff."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return call()
        except ApiError as e:
            if (e.status is not None and e.status < 500 and e.status != 429) or attempt == MAX_ATTEMPTS:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def journey_row(pid: str, address: str, arrive_by: datetime) -> dict:
    """Fastest journey from a building to the QVB."""
    # Address from the input CSV, so rows without a journey still show it.
    base = {"address_detail_pid": pid, "depart_building_address": address}
    try:
        journey = with_retries(lambda: fastest_journey(pid, QVB, arrive_by))
    except ApiError as e:
        if e.status == 404:  # Address missing from the API's copy of G-NAF
            return {**base, "status": "not_found"}
        raise
    if journey is None:
        return {**base, "status": "no_journey"}
    return {**base, "status": "ok", **asdict(journey)}


def first_ok_row(candidates: list[tuple[str, str]], arrive_by: datetime, h3_cell: str) -> dict:
    """Row for the first candidate building with a journey, or for the last one tried."""
    for pid, address in candidates:
        row = journey_row(pid, address, arrive_by)
        if row["status"] == "ok":
            break
    return {**row, "h3_cell": h3_cell}


Work = tuple[str, list[tuple[str, str]]]  # (h3 cell or "", candidate (pid, address) pairs)


def pending_buildings(input_path: Path, processed: set[str]) -> Iterator[Work]:
    with input_path.open(newline="") as f:
        for row in csv.DictReader(f):
            if row["address_detail_pid"] not in processed:
                yield "", [(row["address_detail_pid"], row["address"])]


def pending_hexes(input_path: Path, processed: set[str], resolution: int, max_candidates: int) -> Iterator[Work]:
    """One work item per hexagon not yet done, with its buildings nearest the centre first."""
    hexes: dict[str, list[tuple[str, str, float, float]]] = {}
    with input_path.open(newline="") as f:
        for row in csv.DictReader(f):
            if row["latitude"]:
                lat, lon = float(row["latitude"]), float(row["longitude"])
                cell = h3.latlng_to_cell(lat, lon, resolution)
                hexes.setdefault(cell, []).append((row["address_detail_pid"], row["address"], lat, lon))
    done = sum(any(b[0] in processed for b in hexes[cell]) for cell in hexes)
    log(f"{len(hexes):,} hexagons at resolution {resolution}, {done:,} already processed")

    for cell in sorted(hexes):
        buildings = hexes[cell]
        if any(pid in processed for pid, *_ in buildings):
            continue
        c_lat, c_lon = h3.cell_to_latlng(cell)
        scale = math.cos(math.radians(c_lat))
        buildings.sort(key=lambda b: (b[2] - c_lat) ** 2 + ((b[3] - c_lon) * scale) ** 2)
        yield cell, [(pid, address) for pid, address, *_ in buildings[:max_candidates]]


def run_parallel(tasks: Iterable[tuple[str, Callable[[], dict]]], writer: BatchWriter, workers: int) -> int:
    """Run (label, task) pairs on a thread pool, adding each result row to `writer`.

    Keeps a bounded queue instead of submitting everything at once. Failed tasks are logged
    and not written, so the next run retries them. On Ctrl-C, completed results are saved.
    Returns the number of failed tasks.
    """
    executor = ThreadPoolExecutor(max_workers=workers)
    in_flight: dict[Future, str] = {}
    failed = 0

    def collect(futures) -> None:
        nonlocal failed
        for future in futures:
            label = in_flight.pop(future)
            try:
                writer.add(future.result())
            except Exception as e:  # one bad task shouldn't stop a run of hours
                failed += 1
                log(f"Failed {label}: {e!r}")

    try:
        for label, task in tasks:
            in_flight[executor.submit(task)] = label
            if len(in_flight) >= workers * 2:
                collect(wait(in_flight, return_when=FIRST_COMPLETED).done)
        collect(list(in_flight))
    except KeyboardInterrupt:
        log("Interrupted; saving completed results")
        executor.shutdown(wait=False, cancel_futures=True)
        collect([f for f in in_flight if f.done() and not f.cancelled()])
    finally:
        writer.flush()
        executor.shutdown(wait=False, cancel_futures=True)
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--input", type=Path, default=Path("data/sydney_buildings.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/travel_times"))
    parser.add_argument("--workers", type=int, default=8, help="Parallel requests (default: 8)")
    parser.add_argument("--batch-size", type=int, default=1000, help="Rows per output CSV (default: 1000)")
    parser.add_argument(
        "--arrive-by", type=datetime.fromisoformat, default=ARRIVE_BY,
        help=f"ISO date-time, Sydney local if no offset (default: {ARRIVE_BY:%Y-%m-%dT%H:%M})",
    )
    parser.add_argument("--limit", type=int, help="Process at most this many buildings (or hexagons) in this run")
    parser.add_argument("--sample-hex", type=int, choices=range(0, 16), metavar="RES",
                        help="Process one building per H3 hexagon of this resolution (e.g. 9)")
    parser.add_argument("--hex-candidates", type=int, default=3,
                        help="With --sample-hex, buildings to try per hexagon until one has a journey (default: 3)")
    args = parser.parse_args()
    if "ADDRESS_INFO_API_KEY" not in os.environ:
        parser.error("set ADDRESS_INFO_API_KEY in .env or the environment")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    processed = load_processed(args.output_dir)
    log(f"Arrive by {args.arrive_by:%a %d %b %Y %H:%M}; {len(processed):,} buildings already processed")

    if args.sample_hex is None:
        work = pending_buildings(args.input, processed)
    else:
        work = pending_hexes(args.input, processed, args.sample_hex, args.hex_candidates)
    if args.limit:
        work = itertools.islice(work, args.limit)

    writer = BatchWriter(args.output_dir, args.batch_size)
    failed = run_parallel(
        ((cell or candidates[0][0], partial(first_ok_row, candidates, args.arrive_by, cell)) for cell, candidates in work),
        writer, args.workers,
    )

    log(f"Done: {writer.written:,} written, {failed:,} failed (will be retried on the next run)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
