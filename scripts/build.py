#!/usr/bin/env python3
"""
Build the database from data/work/ (see prepare.py) and run the analysis.

    python scripts/build.py                # study area + validation area
    python scripts/build.py ankara

Connection: the usual PG* environment variables (PGHOST, PGPORT, PGUSER, PGPASSWORD,
PGDATABASE). All analysis is SQL in sql/; this script only loads files and runs psql.
"""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psycopg2

import simulate

from config import (FACILITY_ENTRY_M, MAX_COST_S, MAX_SNAP_M, MIN_PARK_M2, RAW, ROOT,
                    SNAP_SPEED_KMH, SOURCES, STUDY, VALIDATION, WALK_SPEED_KMH, WORK)

SQL = ROOT / "sql"
AREAS = {a["key"]: a for a in (STUDY, VALIDATION)}
AREA_SQL = ["11_network.sql", "12_places.sql", "13_access.sql", "14_indicators.sql", "21_report.sql"]


def psql(file: str, **variables) -> None:
    t0 = time.time()
    cmd = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(SQL / file)]
    for k, v in variables.items():
        cmd += ["-v", f"{k}={v}"]
    env = dict(os.environ, PGOPTIONS="-c client_min_messages=warning")
    subprocess.run(cmd, check=True, env=env)
    print(f"  {file:<22} {time.time() - t0:6.1f} s")


def area_vars(area: dict) -> dict:
    return {
        "s": area["key"], "epsg": area["epsg"], "province": area["province"],
        "walk_mps": WALK_SPEED_KMH / 3.6, "snap_mps": SNAP_SPEED_KMH / 3.6,
        "max_snap_m": MAX_SNAP_M, "entry_m": FACILITY_ENTRY_M,
        "max_cost_s": MAX_COST_S, "min_park_m2": MIN_PARK_M2,
    }


# --------------------------------------------------------------------------- loading
JSON_COPY = "COPY {} (doc) FROM STDIN WITH (FORMAT csv, QUOTE e'\\x01', DELIMITER e'\\x02')"


def copy_json_lines(cur, table: str, lines) -> int:
    buf = io.StringIO()
    n = 0
    for line in lines:
        line = line.strip().lstrip("\x1e")          # geojsonseq record separator
        if line:
            buf.write(line + "\n")
            n += 1
    buf.seek(0)
    cur.copy_expert(JSON_COPY.format(table), buf)
    return n


def copy_tsv(cur, table: str, path: Path) -> None:
    with open(path, encoding="utf-8") as f:
        cur.copy_expert(f"COPY {table} FROM STDIN WITH (FORMAT csv, DELIMITER e'\\t', HEADER true)", f)


def read_table_file(path: Path) -> list[list[str]]:
    """Rows of a CSV (any common delimiter/encoding) or XLSX file, header included."""
    if path.suffix.lower() == ".xlsx":
        import openpyxl
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
        return [["" if v is None else str(v) for v in row] for row in ws.iter_rows(values_only=True)]
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1254", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    return [row for row in csv.reader(io.StringIO(text), dialect)]


def load_src(conn, raw: Path = RAW) -> None:
    with conn.cursor() as cur:
        doc = json.loads((raw / SOURCES["tuik_districts"]["file"]).read_text("utf-8"))
        cur.execute("INSERT INTO src.tuik_raw VALUES (%s)", [json.dumps(doc, ensure_ascii=False)])
        for key, table, ncols in (("kadikoy_areas", "src.kadikoy_areas_raw", 3),
                                  ("kadikoy_per_capita", "src.kadikoy_per_capita_raw", 4)):
            path = raw / SOURCES[key]["file"]
            if not path.exists():
                print(f"  (skipped {path.name}: not downloaded)")
                continue
            rows = [r[:ncols] for r in read_table_file(path)[1:] if any(c.strip() for c in r)]
            cur.executemany(f"INSERT INTO {table} VALUES ({','.join(['%s'] * ncols)})", rows)
            print(f"  {table}: {len(rows)} rows")
    conn.commit()


def load_area(conn, area: dict, work: Path = WORK) -> None:
    wd = work / area["key"]
    s = area["key"]
    with conn.cursor() as cur:
        copy_tsv(cur, f"{s}.edges_raw", wd / "edges.tsv")
        copy_tsv(cur, f"{s}.cells_raw", wd / "cells.tsv")
        with open(wd / "facilities.geojsonl", encoding="utf-8") as f:
            copy_json_lines(cur, f"{s}.facility_raw", f)
        with open(wd / "admin.geojsonl", encoding="utf-8") as f:
            copy_json_lines(cur, f"{s}.admin_raw", f)
        feats = json.loads((wd / "area.geojson").read_text("utf-8"))["features"]
        copy_json_lines(cur, f"{s}.district_raw", (json.dumps(x, ensure_ascii=False) for x in feats))
        for k, v in area_vars(area).items():
            if isinstance(v, (int, float)):
                cur.execute(f"INSERT INTO {s}.settings VALUES (%s, %s)", [k, v])
    conn.commit()


# --------------------------------------------------------------------------- main
def main(keys: list[str]) -> None:
    keys = keys or list(AREAS)
    conn = psycopg2.connect("")            # libpq reads the PG* variables
    psql("00_init.sql")
    load_src(conn)
    for key in keys:
        area = AREAS[key]
        print(f"[{key}] {area['label']}")
        psql("10_area.sql", s=key, epsg=area["epsg"])
        load_area(conn, area)
        for f in AREA_SQL:
            psql(f, **area_vars(area))
        simulate.compute_loads(conn, key)
    if VALIDATION["key"] in keys:
        psql("20_validation.sql", s=VALIDATION["key"])
    conn.close()


if __name__ == "__main__":
    if not os.environ.get("PGDATABASE"):
        sys.exit("Set PGHOST/PGUSER/PGPASSWORD/PGDATABASE first (see README).")
    main(sys.argv[1:])
