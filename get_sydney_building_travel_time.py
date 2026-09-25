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

Usage:
    uv run get_sydney_building_travel_time.py --workers 8 [--limit 100]
"""

import argparse
import csv
import itertools
import os
import sys
import time
from collections.abc import Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, fields
from datetime import date, datetime, timedelta
from pathlib import Path

from fastest_journey import JourneySummary, fastest_journey
from main import SYDNEY_TZ, ApiError

QVB = "GANSW706029353"  # 429-481 George Street, Sydney NSW 2000
LOG_NAME = "processed.log"
BATCH_PREFIX = "travel_times_"
MAX_ATTEMPTS = 4
COLUMNS = ["address_detail_pid", "status", *(f.name for f in fields(JourneySummary))]


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

    def __init__(self, output_dir: Path, batch_size: int):
        self.output_dir = output_dir
        self.batch_size = batch_size
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
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)
        tmp.replace(path)
        append_log(self.output_dir / LOG_NAME, [row["address_detail_pid"] for row in self.rows])
        self.written += len(self.rows)
        self.next_index += 1
        self.rows = []
        rate = self.written / (time.monotonic() - self.started)
        log(f"Wrote {path.name}: {self.written:,} buildings this run ({rate:.1f}/s)")


def journey_row(pid: str, address: str, arrive_by: datetime) -> dict:
    """Fastest journey from a building to the QVB, retrying rate limits and transient errors."""
    # Address from the input CSV, so rows without a journey still show it.
    base = {"address_detail_pid": pid, "depart_building_address": address}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            journey = fastest_journey(pid, QVB, arrive_by)
            break
        except ApiError as e:
            if e.status == 404:  # Address missing from the API's copy of G-NAF
                return {**base, "status": "not_found"}
            if (e.status is not None and e.status < 500 and e.status != 429) or attempt == MAX_ATTEMPTS:
                raise
            time.sleep(2**attempt)
    if journey is None:
        return {**base, "status": "no_journey"}
    return {**base, "status": "ok", **asdict(journey)}


def pending_buildings(input_path: Path, processed: set[str]) -> Iterator[tuple[str, str]]:
    with input_path.open(newline="") as f:
        for row in csv.DictReader(f):
            if row["address_detail_pid"] not in processed:
                yield row["address_detail_pid"], row["address"]


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
    parser.add_argument("--limit", type=int, help="Process at most this many buildings in this run")
    args = parser.parse_args()
    if "ADDRESS_INFO_API_KEY" not in os.environ:
        parser.error("set ADDRESS_INFO_API_KEY in .env or the environment")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    processed = load_processed(args.output_dir)
    log(f"Arrive by {args.arrive_by:%a %d %b %Y %H:%M}; {len(processed):,} buildings already processed")

    buildings = pending_buildings(args.input, processed)
    if args.limit:
        buildings = itertools.islice(buildings, args.limit)

    writer = BatchWriter(args.output_dir, args.batch_size)
    executor = ThreadPoolExecutor(max_workers=args.workers)
    in_flight: dict[Future, str] = {}
    failed = 0

    def collect(futures) -> None:
        nonlocal failed
        for future in futures:
            pid = in_flight.pop(future)
            try:
                writer.add(future.result())
            except ApiError as e:
                failed += 1
                log(f"Failed {pid}: {e}")

    try:
        # Keep a bounded queue of requests instead of submitting all 1.7M at once.
        for pid, address in buildings:
            in_flight[executor.submit(journey_row, pid, address, args.arrive_by)] = pid
            if len(in_flight) >= args.workers * 2:
                collect(wait(in_flight, return_when=FIRST_COMPLETED).done)
        collect(list(in_flight))
    except KeyboardInterrupt:
        log("Interrupted; saving completed results")
        executor.shutdown(wait=False, cancel_futures=True)
        collect([f for f in in_flight if f.done() and not f.cancelled()])
    finally:
        writer.flush()
        executor.shutdown(wait=False, cancel_futures=True)

    log(f"Done: {writer.written:,} written, {failed:,} failed (will be retried on the next run)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
