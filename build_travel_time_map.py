"""Build a self-contained HTML map of travel times to and from the QVB from --sample-hex results.

Reads the hexagon results written by get_sydney_building_travel_time.py --sample-hex, the
Saturday night trips home written by get_qvb_night_travel_time.py (a second overlay, if
present), and data/sydney_buildings.csv (to draw every built-up hexagon, including ones not
yet processed, and to label suburbs), and writes one HTML file with the data embedded.

Usage:
    uv run build_travel_time_map.py [--results data/travel_times_hex9] [--output data/qvb_travel_map.html]
"""

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import h3

TEMPLATE = Path(__file__).parent / "map_template.html"
SCALE = 100_000  # coordinates are stored as integers in 1e-5 degrees (~1 m)
STATUS_CODES = {"ok": 1, "no_journey": 2, "not_found": 3}
QVB_LAT, QVB_LON = -33.87173827, 151.20669221  # GANSW706029353

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


def hhmm(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%H:%M") if value else ""


def when(value: datetime) -> str:
    return value.strftime("%-H:%M on %a %-d %b %Y")


def load_results(results_dir: Path) -> dict[str, dict]:
    """Latest result row per H3 cell."""
    results: dict[str, dict] = {}
    for path in sorted(results_dir.glob("travel_times_*.csv")):
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                results[row["h3_cell"]] = row
    return results


def overlay(cells: list[str], results: dict[str, dict], night: bool) -> dict:
    """Column arrays for one overlay, in `cells` order. Column-oriented arrays keep the JSON small.

    `minutes` is what the map colours by: the trip time for journeys to the QVB, and the
    time from the requested departure to arrival (so including the wait) for night trips.
    """
    names = ["status", "minutes", "trip", "wait", "morning", "walkMin", "walkM", "transports", "modes",
             "depart", "arrive", "address"]
    out: dict[str, list] = {name: [] for name in names}
    for cell in cells:
        row = results.get(cell)
        ok = row is not None and row["status"] == "ok"
        num = (lambda key: int(row[key]) if ok and row.get(key) else None)
        values = {
            "status": STATUS_CODES[row["status"]] if row else 0,
            "minutes": num("total_minutes" if night else "journey_minutes"),
            "trip": num("journey_minutes"),
            "wait": num("wait_minutes") if night else None,
            "morning": int(ok and row.get("next_morning") == "True"),
            "walkMin": num("walking_minutes"), "walkM": num("walking_distance_m"), "transports": num("transports"),
            "modes": sum(bit for bit, key in ((1, "has_bus"), (2, "has_train"), (4, "has_ferry"), (8, "has_tram"))
                         if ok and row[key] == "True"),
            "depart": hhmm(row["departure"]) if ok else "",
            "arrive": hhmm(row["arrival"]) if ok else "",
            "address": (row["address"] if night else row["depart_building_address"]) if row else "",
        }
        for name in names:
            out[name].append(values[name])
    if not night:  # these only apply to night trips
        for name in ("trip", "wait", "morning"):
            del out[name]
    out["computed"] = sum(1 for s in out["status"] if s)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--buildings", type=Path, default=Path("data/sydney_buildings.csv"))
    parser.add_argument("--results", type=Path, default=Path("data/travel_times_hex9"))
    parser.add_argument("--night-results", type=Path, default=Path("data/night_from_qvb_hex9"),
                        help="Output of get_qvb_night_travel_time.py (overlay skipped if missing)")
    parser.add_argument("--output", type=Path, default=Path("data/qvb_travel_map.html"))
    parser.add_argument("--transit", type=Path, default=Path("data/transit_lines.json"),
                        help="Rail, light rail and ferry lines from get_transit_lines.py (skipped if missing)")
    parser.add_argument("--resolution", type=int, default=9, help="H3 resolution used for --sample-hex (default: 9)")
    parser.add_argument("--arrive-by", type=datetime.fromisoformat, default=datetime(2026, 10, 12, 9, 0),
                        help="Arrival time the results were computed for (for the page subtitle)")
    args = parser.parse_args()

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

    overlays = {"to": {**overlay(cells, load_results(args.results), night=False), "when": when(args.arrive_by)}}
    if args.night_results.exists():
        night = load_results(args.night_results)
        requested = next((r["requested"] for r in night.values()), None)
        if requested:
            overlays["night"] = {**overlay(cells, night, night=True), "when": when(datetime.fromisoformat(requested))}

    labels = []
    for tier, names in LABELS.items():
        for name in names:
            points = locality_points.get(name)
            if points:
                lat = statistics.median(p[0] for p in points)
                lon = statistics.median(p[1] for p in points)
                labels.append([name.title(), round(lon * SCALE), round(lat * SCALE), tier])

    data = {
        "scale": SCALE,
        "total": len(cells),
        "qvb": [round(QVB_LON * SCALE), round(QVB_LAT * SCALE)],
        "localities": [name.title() for name in localities],
        "center": center, "verts": verts, "loc": loc, "labels": labels, "overlays": overlays,
        "transit": json.loads(args.transit.read_text()) if args.transit.exists() else None,
    }
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    args.output.write_text(TEMPLATE.read_text().replace("/*__DATA__*/null", payload))
    done = ", ".join(f"{name} {o['computed']:,}" for name, o in overlays.items())
    print(f"Wrote {args.output} ({args.output.stat().st_size / 1e6:.1f} MB): {len(cells):,} hexagons; computed: {done}")


if __name__ == "__main__":
    main()
