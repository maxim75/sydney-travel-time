"""Create travel time datasets and build the static map site from them.

With dataset parameters, creates (or resumes) the dataset for that building, date and
time, collects its journeys for every sampled hexagon, merges the results into its
dataset.json when complete, then rebuilds the site. Without them, only rebuilds the site.

The site (default docs/, served by GitHub Pages) is index.html, with the hexagons, suburb
labels, transit lines and the list of complete datasets embedded, plus one compact
map_data/<id>.json per complete dataset that the page fetches when it is selected.

Usage:
    uv run build_travel_time_map.py
    caffeinate -is uv run build_travel_time_map.py --building GANSW706029353 --date 2026-10-12 --arrive-by 09:00
    caffeinate -is uv run build_travel_time_map.py --building GANSW706029353 --date 2026-10-10 --depart-at 21:00
"""

import argparse
import csv
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, time
from pathlib import Path

import h3

import datasets
from datasets import Dataset

TEMPLATE = Path(__file__).parent / "map_template.html"
SCALE = 100_000  # coordinates are stored as integers in 1e-5 degrees (~1 m)
STATUS_CODES = {"ok": 1, "no_journey": 2, "not_found": 3}

# Suburb labels: tier 1 shows at every zoom, tier 2 once zoomed in.
LABELS = {
    1: ["PARRAMATTA", "PENRITH", "LIVERPOOL", "CAMPBELLTOWN", "HORNSBY", "CHATSWOOD", "BONDI BEACH",
        "MANLY", "CRONULLA", "BLACKTOWN", "GOSFORD", "KATOOMBA", "RICHMOND", "CAMDEN", "SUTHERLAND",
        "CASTLE HILL", "BANKSTOWN", "HURSTVILLE", "MONA VALE", "PICTON", "WYONG", "WINDSOR"],
    2: ["STRATHFIELD", "BURWOOD", "RYDE", "EPPING", "MACQUARIE PARK", "ROUSE HILL", "ST MARYS", "FAIRFIELD",
        "CABRAMATTA", "MIRANDA", "KOGARAH", "MASCOT", "RANDWICK", "MAROUBRA", "DEE WHY", "BROOKVALE",
        "NORTH SYDNEY", "NEWTOWN", "LEICHHARDT", "GLADESVILLE", "BAULKHAM HILLS", "NARELLAN", "ORAN PARK",
        "LEPPINGTON", "SPRINGWOOD", "BLAXLAND", "ENGADINE", "HELENSBURGH", "TERRIGAL", "WOY WOY",
        "THE ENTRANCE", "TOUKLEY", "KELLYVILLE", "SCHOFIELDS", "MARSDEN PARK", "AUBURN", "LIDCOMBE",
        "ASHFIELD", "MARRICKVILLE", "BOTANY", "COOGEE", "MOSMAN", "LANE COVE", "PYMBLE", "WAHROONGA",
        "BEROWRA", "AVALON BEACH", "PALM BEACH", "BLACKHEATH", "GLENBROOK", "MENAI", "PADSTOW",
        "BELMORE", "ROCKDALE", "CARINGBAH", "GREGORY HILLS", "AUSTRAL", "MOUNT DRUITT", "QUAKERS HILL"],
}


def hhmm(value: str | None) -> str:
    return datetime.fromisoformat(value).strftime("%H:%M") if value else ""


def building_label(ds: Dataset) -> str:
    b = ds.meta["building"]
    return (b.get("name") or b["address"]).title()


def describe(ds: Dataset) -> dict:
    """What the page needs to list a dataset and label it."""
    b = ds.meta["building"]
    verb = "arrive by" if ds.onward else "leave at"
    return {
        "id": ds.id,
        "direction": "onward" if ds.onward else "return",
        "when": ds.at.strftime("%-H:%M on %a %-d %b %Y"),
        "label": f"{building_label(ds)} · {'to' if ds.onward else 'from'}, {verb} {ds.at:%-H:%M} · {ds.at:%a %-d %b %Y}",
        "building": {"name": building_label(ds), "address": b["address"],
                     "xy": [round(b["longitude"] * SCALE), round(b["latitude"] * SCALE)]},
        "counts": ds.meta["counts"],
        "finished": ds.meta["finished"],
    }


def overlay(cells: list[str], ds: Dataset) -> dict:
    """Column arrays for one dataset, in `cells` order. Column-oriented arrays keep the JSON small.

    `minutes` is what the map colours by: the trip time for onward datasets, and the time
    from the requested departure to arrival (so including the wait) for return datasets.
    """
    night = not ds.onward
    results = {r["h3_cell"]: r for r in ds.meta["results"]}
    names = ["status", "minutes", "trip", "wait", "morning", "walkMin", "walkM", "transports", "modes",
             "depart", "arrive", "address"]
    out: dict[str, list] = {name: [] for name in names}
    for cell in cells:
        row = results.get(cell)
        ok = row is not None and row["status"] == "ok"
        get = (lambda key, row=row, ok=ok: row.get(key) if ok else None)
        values = {
            "status": STATUS_CODES[row["status"]] if row else 0,
            "minutes": get("total_minutes" if night else "journey_minutes"),
            "trip": get("journey_minutes"),
            "wait": get("wait_minutes"),
            "morning": int(bool(get("next_morning"))),
            "walkMin": get("walking_minutes"), "walkM": get("walking_distance_m"), "transports": get("transports"),
            "modes": sum(bit for bit, key in ((1, "has_bus"), (2, "has_train"), (4, "has_ferry"), (8, "has_tram"))
                         if get(key)),
            "depart": hhmm(get("departure")),
            "arrive": hhmm(get("arrival")),
            "address": (row["address"] if night else row["depart_building_address"]) if row else "",
        }
        for name in names:
            out[name].append(values[name])
    if not night:  # these only apply to return trips
        for name in ("trip", "wait", "morning"):
            del out[name]
    out["computed"] = sum(1 for s in out["status"] if s)
    return {**describe(ds), **out}


def build_site(args: argparse.Namespace) -> None:
    # Every built-up hexagon, with the suburb most of its buildings are in.
    cell_localities: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    locality_points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    with args.buildings.open(newline="") as f:
        for row in csv.DictReader(f):
            if not row["latitude"]:
                continue
            lat, lon = float(row["latitude"]), float(row["longitude"])
            cell = h3.latlng_to_cell(lat, lon, args.resolution)
            cell_localities[cell][row["locality"]] += 1
            locality_points[row["locality"]].append((lat, lon))

    cells = sorted(cell_localities)
    localities = sorted({max(counts, key=counts.get) for counts in cell_localities.values()})
    locality_index = {name: i for i, name in enumerate(localities)}

    center, verts, loc = [], [], []
    for cell in cells:
        c_lat, c_lon = h3.cell_to_latlng(cell)
        cy, cx = round(c_lat * SCALE), round(c_lon * SCALE)
        center += [cx, cy]
        boundary = h3.cell_to_boundary(cell)
        verts.append([v for lat, lon in boundary for v in (round(lon * SCALE) - cx, round(lat * SCALE) - cy)])
        counts = cell_localities[cell]
        loc.append(locality_index[max(counts, key=counts.get)])

    labels = []
    for tier, names in LABELS.items():
        for name in names:
            points = locality_points.get(name)
            if points:
                lat = statistics.median(p[0] for p in points)
                lon = statistics.median(p[1] for p in points)
                labels.append([name.title(), round(lon * SCALE), round(lat * SCALE), tier])

    # One compact file per complete dataset; files of datasets that no longer exist are removed.
    map_dir = args.site / "map_data"
    map_dir.mkdir(parents=True, exist_ok=True)
    complete = [ds for ds in datasets.all_datasets() if ds.complete]
    for ds in complete:
        path = map_dir / f"{ds.id}.json"
        path.write_text(json.dumps(overlay(cells, ds), separators=(",", ":"), ensure_ascii=False))
        print(f"Wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")
    for path in map_dir.glob("*.json"):
        if path.stem not in {ds.id for ds in complete}:
            path.unlink()
            print(f"Removed {path}")

    data = {
        "scale": SCALE,
        "total": len(cells),
        "localities": [name.title() for name in localities],
        "center": center, "verts": verts, "loc": loc, "labels": labels,
        "datasets": sorted((describe(ds) for ds in complete), key=lambda d: d["label"]),
        "transit": json.loads(args.transit.read_text()) if args.transit.exists() else None,
    }
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    index = args.site / "index.html"
    index.write_text(TEMPLATE.read_text().replace("/*__DATA__*/null", payload))
    (args.site / ".nojekyll").touch()
    print(f"Wrote {index} ({index.stat().st_size / 1e6:.1f} MB): {len(cells):,} hexagons, {len(complete)} datasets")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    dataset = parser.add_argument_group("dataset (all of --building, --date and one of --arrive-by / --depart-at)")
    dataset.add_argument("--building", help="G-NAF building ID (ADDRESS_DETAIL_PID), e.g. GANSW706029353 for the QVB")
    dataset.add_argument("--date", type=date.fromisoformat, help="Travel date, YYYY-MM-DD")
    times = dataset.add_mutually_exclusive_group()
    times.add_argument("--arrive-by", type=time.fromisoformat, metavar="HH:MM",
                       help="Onward: arrive at the building by this time (Sydney time)")
    times.add_argument("--depart-at", type=time.fromisoformat, metavar="HH:MM",
                       help="Return: leave the building at this time (Sydney time), waiting overnight if need be")
    dataset.add_argument("--workers", type=int, default=3, help="Parallel requests (default: 3; the API slows beyond that)")
    dataset.add_argument("--limit", type=int, help="Testing: process at most this many more buildings in this run")
    parser.add_argument("--site", type=Path, default=Path("docs"), help="Output folder of the site (default: docs)")
    parser.add_argument("--buildings", type=Path, default=Path("data/sydney_buildings.csv"))
    parser.add_argument("--transit", type=Path, default=Path("data/transit_lines.json"),
                        help="Rail, light rail and ferry lines from get_transit_lines.py (skipped if missing)")
    parser.add_argument("--resolution", type=int, default=9, help="H3 resolution of the sample (default: 9)")
    args = parser.parse_args()

    failed = 0
    given = [args.building, args.date, args.arrive_by or args.depart_at]
    if any(given):
        if not all(given):
            parser.error("a dataset needs --building, --date and one of --arrive-by / --depart-at")
        if "ADDRESS_INFO_API_KEY" not in os.environ:
            parser.error("set ADDRESS_INFO_API_KEY in .env or the environment")
        ds = datasets.create_or_load(args.building, args.date, args.arrive_by, args.depart_at)
        if ds.complete:
            datasets.log(f"{ds.id} is already complete")
        else:
            targets = datasets.sample_targets()
            failed = datasets.collect(ds, targets, args.workers, args.limit)
            datasets.merge(ds, {t.cell for t in targets})

    build_site(args)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
