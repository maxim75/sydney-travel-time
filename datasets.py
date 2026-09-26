"""Travel time datasets: one folder per building, date, direction and time.

A dataset is either onward (fastest journey from every sampled building, arriving at the
dataset's building by a time) or return (earliest journey from the dataset's building to
every sampled building, leaving at a time and waiting at most max_wait_hours for a departure).

    data/datasets/<id>/dataset.json

holds the parameters and metadata from creation. While collecting, results go to batch
CSVs of BATCH_SIZE rows and processed.log in the same folder, so an interrupted run
resumes. When every sampled building has a row, the rows are merged into dataset.json
("results", "counts", "finished") and the batch files are deleted.

Every dataset uses the same sample: one building per H3 resolution-9 hexagon, taken from
the results of SAMPLE_DATASET (the original weekday-morning run to the QVB).
"""

import csv
import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import partial
from pathlib import Path

import h3

from get_qvb_night_travel_time import COLUMNS as RETURN_COLUMNS
from get_qvb_night_travel_time import night_row
from get_sydney_building_travel_time import (
    COLUMNS as ONWARD_COLUMNS,
)
from get_sydney_building_travel_time import (
    LOG_NAME,
    BatchWriter,
    batch_files,
    journey_row,
    load_processed,
    log,
    run_parallel,
    with_retries,
)
from main import SYDNEY_TZ, api_get

DATASETS_DIR = Path("data/datasets")
SAMPLE_DATASET = "GANSW706029353_2026-10-12_arr0900"  # to the QVB, arriving by 9:00 on Mon 12 Oct 2026
BATCH_SIZE = 1000

INT_COLUMNS = {"journey_minutes", "walking_minutes", "walking_distance_m", "transports",
               "wait_minutes", "total_minutes", "searches"}
FLOAT_COLUMNS = {"depart_latitude", "depart_longitude"}
BOOL_COLUMNS = {"has_bus", "has_train", "has_ferry", "has_tram", "next_morning"}


def dataset_id(pid: str, day: date, arrive_by: time | None = None, depart_at: time | None = None,
               max_wait_hours: int | None = None) -> str:
    """<pid>_<date>_arr<HHMM> for onward datasets, <pid>_<date>_dep<HHMM>_w<max wait>h for return ones."""
    if (arrive_by is None) == (depart_at is None):
        raise ValueError("give exactly one of arrive_by or depart_at")
    if arrive_by:
        return f"{pid}_{day:%Y-%m-%d}_arr{arrive_by:%H%M}"
    if max_wait_hours is None:
        raise ValueError("a return dataset needs max_wait_hours")
    return f"{pid}_{day:%Y-%m-%d}_dep{depart_at:%H%M}_w{max_wait_hours}h"


@dataclass
class Dataset:
    meta: dict

    @property
    def id(self) -> str:
        return self.meta["id"]

    @property
    def dir(self) -> Path:
        return DATASETS_DIR / self.id

    @property
    def path(self) -> Path:
        return self.dir / "dataset.json"

    @property
    def onward(self) -> bool:
        return "arrive_by" in self.meta

    @property
    def at(self) -> datetime:
        """The arrival (onward) or departure (return) time, in Sydney time."""
        hhmm = self.meta["arrive_by"] if self.onward else self.meta["depart_at"]
        return datetime.combine(date.fromisoformat(self.meta["date"]), time.fromisoformat(hhmm), SYDNEY_TZ)

    @property
    def complete(self) -> bool:
        return "results" in self.meta

    def save(self) -> None:
        """Write dataset.json atomically, one result row per line."""
        head = {k: v for k, v in self.meta.items() if k != "results"}
        text = json.dumps(head, indent=2, ensure_ascii=False)
        if self.complete:
            rows = ",\n".join("    " + json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in self.meta["results"])
            text = text[:-2] + f',\n  "results": [\n{rows}\n  ]\n}}'
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(text + "\n")
        tmp.replace(self.path)


def now() -> str:
    return datetime.now(SYDNEY_TZ).isoformat(timespec="seconds")


def load(ds_id: str) -> Dataset:
    return Dataset(json.loads((DATASETS_DIR / ds_id / "dataset.json").read_text()))


def all_datasets() -> list[Dataset]:
    return [Dataset(json.loads(p.read_text())) for p in sorted(DATASETS_DIR.glob("*/dataset.json"))]


def create_or_load(pid: str, day: date, arrive_by: time | None = None, depart_at: time | None = None,
                   max_wait_hours: int | None = None) -> Dataset:
    """The dataset for these parameters, creating its folder and dataset.json if new."""
    ds_id = dataset_id(pid, day, arrive_by, depart_at, max_wait_hours)
    if (DATASETS_DIR / ds_id / "dataset.json").exists():
        return load(ds_id)
    key = os.environ["ADDRESS_INFO_API_KEY"]
    address = with_retries(lambda: api_get(f"/v1/addresses/{pid}", {}, key))  # 404 if the API doesn't know it
    meta = {
        "id": ds_id,
        "building": {"id": pid, "name": address.get("building_name"), "address": address["full_address"],
                     "latitude": address["latitude"], "longitude": address["longitude"]},
        "date": day.isoformat(),
        **({"arrive_by": f"{arrive_by:%H:%M}"} if arrive_by
           else {"depart_at": f"{depart_at:%H:%M}", "max_wait_hours": max_wait_hours}),
        "created": now(),
    }
    ds = Dataset(meta)
    ds.save()
    log(f"Created dataset {ds_id}")
    return ds


@dataclass
class Target:
    cell: str
    pid: str
    address: str


def sample_targets() -> list[Target]:
    """The sampled building of every hexagon, from SAMPLE_DATASET's results."""
    sample = load(SAMPLE_DATASET)
    if not sample.complete:
        raise RuntimeError(f"sample dataset {SAMPLE_DATASET} is not complete")
    return [Target(r["h3_cell"], r["address_detail_pid"], r["depart_building_address"]) for r in sample.meta["results"]]


def collect(ds: Dataset, targets: list[Target], workers: int, limit: int | None = None) -> int:
    """Plan journeys for every target not yet processed; returns the number that failed."""
    processed = load_processed(ds.dir)
    b = ds.meta["building"]
    scale = math.cos(math.radians(b["latitude"]))

    def distance(t: Target) -> float:
        lat, lon = h3.cell_to_latlng(t.cell)
        return (lat - b["latitude"]) ** 2 + ((lon - b["longitude"]) * scale) ** 2

    # Nearest the dataset's building first, so a partial run covers the area around it
    work = sorted((t for t in targets if t.pid not in processed), key=distance)
    if limit is not None:
        work = work[:limit]
    what = f"Arrive at {b['address']} by" if ds.onward else f"Leave {b['address']} at"
    log(f"{ds.id}: {what} {ds.at:%a %d %b %Y %H:%M}; {len(processed):,} of {len(targets):,} done, {len(work):,} to do")
    if not work:
        return 0

    if ds.onward:
        columns = ONWARD_COLUMNS
        task = lambda t: partial(journey_row, t.cell, t.pid, t.address, b["id"], ds.at)
    else:
        columns = RETURN_COLUMNS
        until = ds.at + timedelta(hours=ds.meta["max_wait_hours"])
        task = lambda t: partial(night_row, t.cell, t.pid, t.address, b["id"], ds.at, until)
    writer = BatchWriter(ds.dir, BATCH_SIZE, columns)
    failed = run_parallel(((t.cell, task(t)) for t in work), writer, workers)
    log(f"{ds.id}: {writer.written:,} written, {failed:,} failed (retried on the next run)")
    return failed


def typed(row: dict) -> dict:
    """A batch CSV row with numbers and booleans converted, and empty values as null."""
    out = {}
    for key, value in row.items():
        if value == "" or value is None:
            out[key] = None
        elif key in INT_COLUMNS:
            out[key] = int(value)
        elif key in FLOAT_COLUMNS:
            out[key] = float(value)
        elif key in BOOL_COLUMNS:
            out[key] = value == "True"
        else:
            out[key] = value
    return out


def merge(ds: Dataset, cells: set[str]) -> bool:
    """Merge the batch CSVs into dataset.json once every cell has a row; True if complete."""
    if ds.complete:
        return True
    rows: dict[str, dict] = {}
    for path in batch_files(ds.dir):  # later batches win, e.g. a rerun of a cell
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                if row["h3_cell"] in cells:
                    rows[row["h3_cell"]] = typed(row)
    missing = len(cells) - len(rows)
    if missing:
        log(f"{ds.id}: {missing:,} of {len(cells):,} hexagons still to do; not merged yet")
        return False
    results = [rows[cell] for cell in sorted(rows)]
    statuses = [r["status"] for r in results]
    ds.meta.update(
        finished=now(),
        counts={"ok": statuses.count("ok"), "no_journey": statuses.count("no_journey"),
                "not_found": statuses.count("not_found"),
                "next_morning": sum(1 for r in results if r.get("next_morning"))},
        results=results,
    )
    ds.save()
    for path in batch_files(ds.dir):
        path.unlink()
    (ds.dir / LOG_NAME).unlink(missing_ok=True)
    log(f"{ds.id}: merged {len(results):,} rows into {ds.path}")
    return True
