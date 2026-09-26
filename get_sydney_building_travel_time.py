"""Batched, resumable, parallel journey collection (library used by datasets.py).

Results go to numbered CSV files of a fixed number of rows. After a file is written,
its building IDs are appended to processed.log in the same directory, so a restarted
run skips them. Buildings with no journey or unknown to the API are recorded too
(status "no_journey" or "not_found"); buildings whose requests fail are not, so they
are retried next run.
"""

import csv
import os
import sys
import time
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path

from fastest_journey import JourneySummary, fastest_journey
from main import ApiError

LOG_NAME = "processed.log"
BATCH_PREFIX = "travel_times_"
MAX_ATTEMPTS = 4
COLUMNS = ["address_detail_pid", "status", "h3_cell", *(f.name for f in fields(JourneySummary))]


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


def with_retries[T](call: Callable[[], T]) -> T:
    """Run an API call, retrying rate limits and server errors with exponential backoff."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return call()
        except ApiError as e:
            if (e.status is not None and e.status < 500 and e.status != 429) or attempt == MAX_ATTEMPTS:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def journey_row(cell: str, pid: str, address: str, anchor: str, arrive_by: datetime) -> dict:
    """Fastest journey from a sampled building to the `anchor` building, arriving by `arrive_by`."""
    # Address from the sample, so rows without a journey still show it.
    base = {"address_detail_pid": pid, "h3_cell": cell, "depart_building_address": address}
    try:
        journey = with_retries(lambda: fastest_journey(pid, anchor, arrive_by))
    except ApiError as e:
        if e.status == 404:  # Address missing from the API's copy of G-NAF
            return {**base, "status": "not_found"}
        raise
    if journey is None:
        return {**base, "status": "no_journey"}
    return {**base, "status": "ok", **asdict(journey)}


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
            except Exception as e:  # noqa: BLE001 - one bad task shouldn't stop a run of hours
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
