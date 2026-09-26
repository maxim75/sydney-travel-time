"""Build a self-contained HTML map of travel times to the QVB from --sample-hex results.

Reads the hexagon results written by get_sydney_building_travel_time.py --sample-hex
and data/sydney_buildings.csv (to draw every built-up hexagon, including ones not yet
processed, and to label suburbs), and writes one HTML file with the data embedded.

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--buildings", type=Path, default=Path("data/sydney_buildings.csv"))
    parser.add_argument("--results", type=Path, default=Path("data/travel_times_hex9"))
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
    pid_locality: dict[str, str] = {}
    with args.buildings.open(newline="") as f:
        for row in csv.DictReader(f):
            if not row["latitude"]:
                continue
            lat, lon = float(row["latitude"]), float(row["longitude"])
            cell = h3.latlng_to_cell(lat, lon, args.resolution)
            cell_localities[cell][row["locality"]] += 1
            locality_points[row["locality"]].append((lat, lon))
            pid_locality[row["address_detail_pid"]] = row["locality"]

    results: dict[str, dict] = {}
    for path in sorted(args.results.glob("travel_times_*.csv")):
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                results[row["h3_cell"]] = row

    cells = sorted(cell_localities)
    localities = sorted({max(counts, key=counts.get) for counts in cell_localities.values()})
    locality_index = {name: i for i, name in enumerate(localities)}

    # Column-oriented arrays keep the embedded JSON small.
    center, verts, loc = [], [], []
    status, minutes, walk_min, walk_m, transports, modes, depart, arrive, address = ([] for _ in range(9))
    for cell in cells:
        c_lat, c_lon = h3.cell_to_latlng(cell)
        cy, cx = round(c_lat * SCALE), round(c_lon * SCALE)
        center += [cx, cy]
        boundary = h3.cell_to_boundary(cell)
        verts.append([v for lat, lon in boundary for v in (round(lon * SCALE) - cx, round(lat * SCALE) - cy)])
        counts = cell_localities[cell]
        row = results.get(cell)
        loc.append(locality_index[max(counts, key=counts.get)])
        if row is None:
            status.append(0)
            minutes.append(None); walk_min.append(None); walk_m.append(None); transports.append(None)
            modes.append(0); depart.append(""); arrive.append(""); address.append("")
            continue
        ok = row["status"] == "ok"
        status.append(STATUS_CODES[row["status"]])
        minutes.append(int(row["journey_minutes"]) if ok else None)
        walk_min.append(int(row["walking_minutes"]) if ok else None)
        walk_m.append(int(row["walking_distance_m"]) if ok else None)
        transports.append(int(row["transports"]) if ok else None)
        modes.append(sum(bit for bit, key in ((1, "has_bus"), (2, "has_train"), (4, "has_ferry"), (8, "has_tram"))
                         if row[key] == "True"))
        depart.append(hhmm(row["departure"]))
        arrive.append(hhmm(row["arrival"]))
        address.append(row["depart_building_address"])

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
        "arriveBy": args.arrive_by.strftime("%-H:%M on %a %-d %b %Y"),
        "total": len(cells),
        "computed": sum(1 for s in status if s),
        "qvb": [round(QVB_LON * SCALE), round(QVB_LAT * SCALE)],
        "localities": [name.title() for name in localities],
        "center": center, "verts": verts, "loc": loc, "status": status, "minutes": minutes,
        "walkMin": walk_min, "walkM": walk_m, "transports": transports, "modes": modes,
        "depart": depart, "arrive": arrive, "address": address, "labels": labels,
        "transit": json.loads(args.transit.read_text()) if args.transit.exists() else None,
    }
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    args.output.write_text(TEMPLATE.read_text().replace("/*__DATA__*/null", payload))
    print(f"Wrote {args.output} ({args.output.stat().st_size / 1e6:.1f} MB): "
          f"{data['computed']:,} of {data['total']:,} hexagons computed")


if __name__ == "__main__":
    main()
