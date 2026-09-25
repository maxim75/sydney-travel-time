"""Extract building IDs (G-NAF ADDRESS_DETAIL_PIDs) in Greater Sydney to a CSV.

A "building" is a current, principal G-NAF address that is not a secondary
address (unit, suite, shop...). Greater Sydney is the ABS Greater Capital City
Statistical Area 1GSYD, matched through each address's 2021 mesh block.

Needs the ABS mesh block allocation file MB_2021_AUST.xlsx; it is downloaded to
data/ on first run if missing.

Usage:
    uv run get_sydney_buildings.py [--gnaf PATH] [--output sydney_buildings.csv]
"""

import argparse
import csv
import io
import sys
import time
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import openpyxl

DEFAULT_GNAF = Path.home() / "Downloads" / "g-naf_aug26_allstates_gda2020_psv_110"
MB_ALLOCATION_URL = (
    "https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3"
    "/jul2021-jun2026/access-and-downloads/allocation-files/MB_2021_AUST.xlsx"
)
DEFAULT_MB_ALLOCATION = Path(__file__).parent / "data" / "MB_2021_AUST.xlsx"
GREATER_SYDNEY = "1GSYD"


class GnafSource:
    """Reads NSW PSV tables from an extracted G-NAF folder or straight from the zip."""

    def __init__(self, path: Path):
        path = path.expanduser()
        zip_path = path if path.suffix == ".zip" else path.with_name(path.name + ".zip")
        self.files: dict[str, Path | str] = {}
        if path.is_dir():
            for f in path.rglob("*_psv.psv"):
                self.files[f.name] = f
        if not self.files and zip_path.is_file():
            self.zip = zipfile.ZipFile(zip_path)
            for name in self.zip.namelist():
                if name.endswith("_psv.psv") and "/Standard/" in name:
                    self.files[name.rsplit("/", 1)[1]] = name
        if not self.files:
            raise SystemExit(f"No G-NAF PSV files found in {path} or {zip_path}")

    @contextmanager
    def _open(self, table: str):
        source = self.files[f"NSW_{table}_psv.psv"]
        if isinstance(source, Path):
            with source.open(encoding="utf-8", newline="") as f:
                yield f
        else:
            with self.zip.open(source) as raw:
                yield io.TextIOWrapper(raw, encoding="utf-8", newline="")

    def rows(self, table: str) -> Iterator[dict[str, str]]:
        """Yield current (not retired) rows of an NSW table."""
        with self._open(table) as f:
            for row in csv.DictReader(f, delimiter="|", quoting=csv.QUOTE_NONE):
                if not row.get("DATE_RETIRED"):
                    yield row


def load_sydney_mesh_blocks(path: Path) -> set[str]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        log(f"Downloading {MB_ALLOCATION_URL}")
        urllib.request.urlretrieve(MB_ALLOCATION_URL, path)
    workbook = openpyxl.load_workbook(path, read_only=True)
    rows = workbook.worksheets[0].iter_rows(values_only=True)
    header = next(rows)
    mb_col, gccsa_col = header.index("MB_CODE_2021"), header.index("GCCSA_CODE_2021")
    codes = {str(row[mb_col]) for row in rows if row[gccsa_col] == GREATER_SYDNEY}
    workbook.close()
    return codes


def format_address(detail: dict, street: dict | None, locality: str) -> str:
    def number(kind: str) -> str:
        return detail[f"{kind}_PREFIX"] + detail[kind] + detail[f"{kind}_SUFFIX"]

    house = number("NUMBER_FIRST")
    if detail["NUMBER_LAST"]:
        house += "-" + number("NUMBER_LAST")
    if not house and detail["LOT_NUMBER"]:
        house = "LOT " + number("LOT_NUMBER")
    street_parts = (street["STREET_NAME"], street["STREET_TYPE_CODE"], street["STREET_SUFFIX_CODE"]) if street else ()
    street_line = " ".join(filter(None, (house, *street_parts)))
    return ", ".join(filter(None, (street_line, f"{locality} NSW {detail['POSTCODE']}")))


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gnaf", type=Path, default=DEFAULT_GNAF, help="G-NAF folder or .zip")
    parser.add_argument("--mb-allocation", type=Path, default=DEFAULT_MB_ALLOCATION, help="ABS MB_2021_AUST.xlsx")
    parser.add_argument("--output", type=Path, default=Path("data/sydney_buildings.csv"))
    args = parser.parse_args()

    gnaf = GnafSource(args.gnaf)

    log("Loading Greater Sydney mesh blocks")
    sydney_mb_codes = load_sydney_mesh_blocks(args.mb_allocation)
    sydney_mb_pids = {r["MB_2021_PID"]: r["MB_2021_CODE"] for r in gnaf.rows("MB_2021") if r["MB_2021_CODE"] in sydney_mb_codes}
    log(f"{len(sydney_mb_codes):,} mesh blocks in Greater Sydney")

    log("Matching addresses to mesh blocks")
    address_mb = {
        r["ADDRESS_DETAIL_PID"]: sydney_mb_pids[r["MB_2021_PID"]]
        for r in gnaf.rows("ADDRESS_MESH_BLOCK_2021")
        if r["MB_2021_PID"] in sydney_mb_pids
    }
    log(f"{len(address_mb):,} addresses in Greater Sydney")

    log("Loading coordinates")
    coords = {
        r["ADDRESS_DETAIL_PID"]: (r["LATITUDE"], r["LONGITUDE"])
        for r in gnaf.rows("ADDRESS_DEFAULT_GEOCODE")
        if r["ADDRESS_DETAIL_PID"] in address_mb
    }

    log("Loading streets and localities")
    streets = {r["STREET_LOCALITY_PID"]: r for r in gnaf.rows("STREET_LOCALITY")}
    localities = {r["LOCALITY_PID"]: r["LOCALITY_NAME"] for r in gnaf.rows("LOCALITY")}

    log(f"Writing buildings to {args.output}")
    count = 0
    with args.output.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["address_detail_pid", "building_name", "address", "locality", "postcode", "latitude", "longitude", "mb_2021_code"])
        for d in gnaf.rows("ADDRESS_DETAIL"):
            pid = d["ADDRESS_DETAIL_PID"]
            if pid not in address_mb or d["ALIAS_PRINCIPAL"] != "P" or d["PRIMARY_SECONDARY"] == "S":
                continue
            locality = localities.get(d["LOCALITY_PID"], "")
            lat, lon = coords.get(pid, ("", ""))
            writer.writerow([
                pid, d["BUILDING_NAME"], format_address(d, streets.get(d["STREET_LOCALITY_PID"]), locality),
                locality, d["POSTCODE"], lat, lon, address_mb[pid],
            ])
            count += 1
    log(f"Done: {count:,} buildings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
