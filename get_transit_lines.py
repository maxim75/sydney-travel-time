"""Extract train, metro, light rail and ferry lines and stations from Sydney GTFS for the map.

Reads the Transport for NSW "full Greater Sydney" GTFS static zip and writes a small JSON
file for build_travel_time_map.py. Route shapes overlap heavily (every service pattern has
its own shape), so shapes are drawn longest first and only the parts not already covered
by an earlier line are kept, then simplified.

Usage:
    uv run get_transit_lines.py [--gtfs ~/Downloads/full_greater_sydney_gtfs_static_0.zip]
"""

import argparse
import csv
import io
import json
import math
import time
import zipfile
from pathlib import Path

# GTFS route_type -> map layer. 106 is NSW TrainLink regional trains, which share Sydney's tracks.
LAYERS = {"2": "rail", "401": "rail", "106": "rail", "900": "light_rail", "4": "ferry"}
BBOX = (-34.45, 149.95, -32.85, 151.75)  # lat/lon box around Greater Sydney
SCALE = 100_000  # output coordinates are integers in 1e-5 degrees, like the map data
M_PER_DEG_LAT = 110_574
M_PER_DEG_LON = 111_320 * math.cos(math.radians(-33.87))
COVER_M = 40  # a point within about this distance of an existing line is already drawn
STEP_M = 20  # densify shapes so coverage is checked at least this often
SIMPLIFY_M = 8


def reader(z: zipfile.ZipFile, name: str) -> csv.DictReader:
    return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))


def to_m(lat: float, lon: float) -> tuple[float, float]:
    return lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT


def in_bbox(lat: float, lon: float) -> bool:
    return BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]


def densify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = points[:1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        n = max(1, math.ceil(math.hypot(x1 - x0, y1 - y0) / STEP_M))
        out += [(x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n) for t in range(1, n + 1)]
    return out


def simplify(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker, iterative."""
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = points[a], points[b]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1e-9
        best, best_d = -1, tolerance
        for i in range(a + 1, b):
            px, py = points[i]
            d = abs(dy * (px - ax) - dx * (py - ay)) / length
            if d > best_d:
                best, best_d = i, d
        if best >= 0:
            keep[best] = True
            stack += [(a, best), (best, b)]
    return [p for p, k in zip(points, keep) if k]


class Coverage:
    """Grid of cells already crossed by a drawn line."""

    def __init__(self, size: float):
        self.size = size
        self.cells: set[tuple[int, int]] = set()

    def key(self, x: float, y: float) -> tuple[int, int]:
        return math.floor(x / self.size), math.floor(y / self.size)

    def covered(self, x: float, y: float) -> bool:
        gx, gy = self.key(x, y)
        return any((gx + a, gy + b) in self.cells for a in (-1, 0, 1) for b in (-1, 0, 1))

    def add(self, points: list[tuple[float, float]]) -> None:
        self.cells.update(self.key(x, y) for x, y in points)


def new_runs(points: list[tuple[float, float]], coverage: Coverage) -> list[list[tuple[float, float]]]:
    """Parts of a line not already covered, each extended by one point to join the line it leaves."""
    flags = [coverage.covered(x, y) for x, y in points]
    runs, i = [], 0
    while i < len(points):
        if flags[i]:
            i += 1
            continue
        j = i
        while j < len(points) and not flags[j]:
            j += 1
        run = points[max(0, i - 1):min(len(points), j + 1)]
        if len(run) >= 2:
            runs.append(run)
        i = j
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gtfs", type=Path, default=Path("~/Downloads/full_greater_sydney_gtfs_static_0.zip").expanduser())
    parser.add_argument("--output", type=Path, default=Path("data/transit_lines.json"))
    args = parser.parse_args()
    started = time.monotonic()
    z = zipfile.ZipFile(args.gtfs)

    route_layer = {r["route_id"]: LAYERS[r["route_type"]] for r in reader(z, "routes.txt") if r["route_type"] in LAYERS}
    shape_layer, trip_layer = {}, {}
    for t in reader(z, "trips.txt"):
        if (layer := route_layer.get(t["route_id"])) is not None:
            shape_layer[t["shape_id"]] = layer
            trip_layer[t["trip_id"]] = layer
    print(f"{len(shape_layer):,} shapes on {len(route_layer):,} routes")

    # shapes.txt is ~1 GB; parse only the lines for the shapes we need.
    shapes: dict[str, list[tuple[int, float, float]]] = {}
    f = io.TextIOWrapper(z.open("shapes.txt"), encoding="utf-8-sig")
    next(f)
    for line in f:
        sid = line[1:line.index('"', 1)]
        if sid in shape_layer:
            _, lat, lon, seq, *_ = next(csv.reader([line]))
            shapes.setdefault(sid, []).append((int(seq), float(lat), float(lon)))

    lines: dict[str, list[list[int]]] = {layer: [] for layer in dict.fromkeys(LAYERS.values())}
    coverage = {layer: Coverage(COVER_M) for layer in lines}
    ordered = sorted(shapes, key=lambda s: -len(shapes[s]))
    for sid in ordered:
        layer = shape_layer[sid]
        pts = sorted(shapes[sid])
        # split where the shape leaves the Sydney box
        segments, current = [], []
        for _, lat, lon in pts:
            if in_bbox(lat, lon):
                current.append(to_m(lat, lon))
            elif current:
                segments.append(current)
                current = []
        segments.append(current)
        for segment in segments:
            if len(segment) < 2:
                continue
            dense = densify(segment)
            for run in new_runs(dense, coverage[layer]):
                flat = []
                for x, y in simplify(run, SIMPLIFY_M):
                    flat += [round(x / M_PER_DEG_LON * SCALE), round(y / M_PER_DEG_LAT * SCALE)]
                lines[layer].append(flat)
            coverage[layer].add(dense)

    # Stations: parent stops whose platforms are served by these routes.
    served: dict[str, str] = {}
    f = io.TextIOWrapper(z.open("stop_times.txt"), encoding="utf-8-sig")
    header = next(f).strip().split(",")
    trip_col, stop_col = header.index("trip_id"), header.index("stop_id")
    for line in f:
        cols = line.split(",", max(trip_col, stop_col) + 1)
        layer = trip_layer.get(cols[trip_col].strip('"'))
        if layer is not None:
            served.setdefault(cols[stop_col].strip('"'), layer)
    stops = {s["stop_id"]: s for s in reader(z, "stops.txt")}
    stations: dict[str, list] = {}
    for stop_id, layer in served.items():
        stop = stops.get(stop_id)
        if stop is None:
            continue
        parent = stops.get(stop["parent_station"]) or stop
        lat, lon = float(parent["stop_lat"]), float(parent["stop_lon"])
        if parent["stop_id"] not in stations and in_bbox(lat, lon):
            name = parent["stop_name"].split(",")[0]
            stations[parent["stop_id"]] = [name, round(lon * SCALE), round(lat * SCALE), layer]

    out = {"lines": lines, "stations": sorted(stations.values())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, separators=(",", ":")))
    counts = ", ".join(f"{layer} {len(v):,} lines / {sum(len(p) for p in v) // 2:,} points" for layer, v in lines.items())
    print(f"Wrote {args.output} ({args.output.stat().st_size / 1e3:.0f} kB) in {time.monotonic() - started:.0f}s: "
          f"{counts}; {len(stations):,} stations")


if __name__ == "__main__":
    main()
