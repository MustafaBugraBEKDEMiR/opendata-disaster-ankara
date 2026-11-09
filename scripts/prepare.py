#!/usr/bin/env python3
"""
Turn the raw downloads into small, load-ready files for one area.

    python scripts/prepare.py              # study area (Ankara) and validation area (Kadıköy)
    python scripts/prepare.py ankara

For each area, data/work/<key>/ receives:

    area.geojson        the districts of the area (from geoBoundaries)
    clip.geojson        the same, buffered; used to cut the OSM extract
    extract.osm.pbf     OpenStreetMap cut to clip.geojson           (osmium extract)
    edges.tsv           routable road segments for walking and driving (built here, see build_edges)
    facilities.geojsonl hospitals, fire stations, schools, parks, assembly points (osmium export)
    admin.geojsonl      administrative boundaries (neighbourhoods = mahalle)        (osmium export)
    cells.tsv           WorldPop 100 m cells with population > 0 inside the clip box

Needs osmium-tool on PATH and the Python packages in requirements.txt.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
from array import array
from collections import Counter
from pathlib import Path

import osmium
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds
from shapely.geometry import mapping, shape
import shapely
from shapely.ops import unary_union

from config import DRIVE_SPEED_DEFAULT, RAW, SOURCES, STUDY, VALIDATION, WORK

AREAS = {a["key"]: a for a in (STUDY, VALIDATION)}

WALK_HIGHWAYS = {
    "footway", "path", "pedestrian", "steps", "living_street", "residential", "service",
    "unclassified", "tertiary", "tertiary_link", "secondary", "secondary_link", "primary",
    "primary_link", "track", "cycleway", "corridor", "road", "trunk", "trunk_link",
}
NO = {"no", "private"}
YES = {"yes", "designated", "permissive"}


# --------------------------------------------------------------------------- tag rules
def walkable(t) -> bool:
    hw = t.get("highway")
    if hw not in WALK_HIGHWAYS:
        return False
    foot = t.get("foot")
    if foot == "no":
        return False
    if foot in YES:
        return True
    if t.get("access") in NO:
        return False
    if hw in ("trunk", "trunk_link"):      # dual carriageways: only with a mapped sidewalk
        return any(t.get(k) in ("both", "left", "right", "yes", "separate")
                   for k in ("sidewalk", "sidewalk:both", "sidewalk:left", "sidewalk:right"))
    return True


def drive_direction(t) -> tuple[bool, bool]:
    """(forward allowed, backward allowed) for a motor vehicle."""
    hw = t.get("highway")
    if hw not in DRIVE_SPEED_DEFAULT:
        return False, False
    for key in ("motor_vehicle", "motorcar", "vehicle", "access"):
        v = t.get(key)
        if v in NO:
            return False, False
        if v in YES:
            break
    ow = t.get("oneway")
    if ow in ("yes", "true", "1"):
        return True, False
    if ow in ("-1", "reverse"):
        return False, True
    if ow == "no":
        return True, True
    if t.get("junction") in ("roundabout", "circular") or hw in ("motorway", "motorway_link"):
        return True, False
    return True, True


def speed_kmh(t) -> float:
    hw = t.get("highway")
    v = (t.get("maxspeed") or "").strip().lower()
    named = {"tr:urban": 50, "tr:rural": 90, "tr:motorway": 120, "tr:living_street": 20}
    if v in named:
        return float(named[v])
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(km/h|kmh)?$", v)
    if m and 5 <= float(m.group(1)) <= 140:
        return float(m.group(1))
    return float(DRIVE_SPEED_DEFAULT.get(hw, 30))


# --------------------------------------------------------------------------- helpers
def run(*cmd: str) -> None:
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def write_geojson(path: Path, features: list[dict]) -> None:
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features},
                               ensure_ascii=False), "utf-8")


def area_polygons(area: dict, districts_file: Path, provinces_file: Path) -> list[dict]:
    """The districts of `area`, chosen inside the right province (names like Gölbaşı repeat)."""
    provs = json.loads(provinces_file.read_text("utf-8"))["features"]
    prov = next(f for f in provs if f["properties"]["shapeName"] == area["province"])
    P = shape(prov["geometry"]).buffer(0.01)
    out = []
    for f in json.loads(districts_file.read_text("utf-8"))["features"]:
        name = f["properties"]["shapeName"]
        g = shape(f["geometry"])
        if name in area["districts"] and P.contains(g.representative_point()):
            out.append({"type": "Feature", "properties": {"district": name},
                        "geometry": mapping(g)})
    missing = set(area["districts"]) - {f["properties"]["district"] for f in out}
    if missing:
        sys.exit(f"{area['key']}: districts not found in the boundary file: {sorted(missing)}")
    return out


# --------------------------------------------------------------------------- road graph
def build_edges(pbf: Path, out: Path) -> dict:
    """
    Read every highway way, keep those usable on foot or by car, and split them at
    junctions (nodes shared by two or more kept ways). Vertex ids are OSM node ids,
    so the graph can be traced back to the map.
    """
    ways = []                      # (way_id, walk, fw, bw, speed, highway, name, refs, lons, lats)
    use = Counter()
    for w in osmium.FileProcessor(str(pbf)).with_locations().with_filter(osmium.filter.KeyFilter("highway")):
        if not w.is_way():
            continue
        t = dict(w.tags)
        walk = walkable(t)
        fw, bw = drive_direction(t)
        if not (walk or fw or bw) or t.get("area") == "yes" and t.get("highway") != "pedestrian":
            continue
        refs, lons, lats = array("q"), array("d"), array("d")
        try:
            for n in w.nodes:
                refs.append(n.ref); lons.append(n.lon); lats.append(n.lat)
        except osmium.InvalidLocationError:
            continue                   # a node outside the extract; the way is cut at the border
        if len(refs) < 2:
            continue
        ways.append((w.id, walk, fw, bw, speed_kmh(t), t["highway"], (t.get("name") or "").replace("\t", " "),
                     refs, lons, lats))
        use.update(refs)
        use[refs[0]] += 1              # endpoints are always vertices
        use[refs[-1]] += 1

    stats = Counter()
    with open(out, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f, delimiter="\t", lineterminator="\n")
        wr.writerow(["way_id", "source", "target", "walk", "drive_fw", "drive_bw",
                     "speed_kmh", "highway", "name", "wkt"])
        for way_id, walk, fw, bw, spd, hw, name, refs, lons, lats in ways:
            start = 0
            for i in range(1, len(refs)):
                if use[refs[i]] > 1 or i == len(refs) - 1:
                    if refs[start] != refs[i]:     # skip zero-length self loops
                        pts = ",".join(f"{lons[j]:.7f} {lats[j]:.7f}" for j in range(start, i + 1))
                        wr.writerow([way_id, refs[start], refs[i], int(walk), int(fw), int(bw),
                                     spd, hw, name, f"LINESTRING({pts})"])
                        stats["edges"] += 1
                        stats["walk"] += walk
                        stats["drive"] += fw or bw
                    start = i
    stats["ways"] = len(ways)
    return dict(stats)


# --------------------------------------------------------------------------- facilities
FACILITY_FILTER = [
    "nwr/amenity=hospital,fire_station,school",
    "nwr/leisure=park",
    "nwr/emergency=assembly_point",
]


def export_layer(pbf: Path, filters: list[str], out: Path, tmpdir: Path) -> None:
    sub = tmpdir / (out.stem + ".osm.pbf")
    run("osmium", "tags-filter", pbf, *filters, "-o", sub, "--overwrite")
    run("osmium", "export", sub, "-f", "geojsonseq", "-a", "type,id",
        "--geometry-types=point,polygon", "-o", out, "--overwrite")


# --------------------------------------------------------------------------- population
def export_cells(tif: Path, bbox: tuple[float, float, float, float], out: Path) -> dict:
    """Centre point and population of each 100 m WorldPop cell with people in it."""
    with rasterio.open(tif) as src:
        win = from_bounds(*bbox, transform=src.transform).round_offsets().round_lengths()
        band = src.read(1, window=win, masked=True)
        tr = src.window_transform(win)
        row0, col0 = int(win.row_off), int(win.col_off)
    vals = band.filled(0).astype("float64")
    rows, cols = np.nonzero(vals > 0)
    with open(out, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f, delimiter="\t", lineterminator="\n")
        wr.writerow(["cell_id", "lon", "lat", "pop"])
        for r, c in zip(rows, cols):
            lon, lat = tr * (c + 0.5, r + 0.5)
            # stable id from the cell's position in the national raster
            wr.writerow([(row0 + r) * 1_000_000 + (col0 + c), f"{lon:.6f}", f"{lat:.6f}",
                         f"{vals[r, c]:.6g}"])
    return {"cells": int(len(rows)), "population": round(float(vals.sum()), 1)}


# --------------------------------------------------------------------------- main
def prepare(area: dict, pbf: Path, tif: Path, districts: Path, provinces: Path,
            work: Path = WORK) -> dict:
    key = area["key"]
    wd = work / key
    wd.mkdir(parents=True, exist_ok=True)
    print(f"[{key}] {area['label']}")

    feats = area_polygons(area, districts, provinces)
    write_geojson(wd / "area.geojson", feats)
    to_m = Transformer.from_crs(4326, area["epsg"], always_xy=True)
    to_ll = Transformer.from_crs(area["epsg"], 4326, always_xy=True)
    reproject = lambda g, tr: shapely.transform(g, lambda xy: np.column_stack(tr.transform(xy[:, 0], xy[:, 1])))
    union_m = reproject(unary_union([shape(f["geometry"]) for f in feats]), to_m)
    clip = reproject(union_m.buffer(area["network_buffer_m"]).simplify(20), to_ll)
    write_geojson(wd / "clip.geojson", [{"type": "Feature", "properties": {}, "geometry": mapping(clip)}])

    run("osmium", "extract", "-p", wd / "clip.geojson", pbf, "-o", wd / "extract.osm.pbf", "--overwrite")

    roads = wd / "roads.osm.pbf"
    run("osmium", "tags-filter", wd / "extract.osm.pbf", "w/highway", "-o", roads, "--overwrite")
    info = {"edges": build_edges(roads, wd / "edges.tsv")}
    roads.unlink()

    export_layer(wd / "extract.osm.pbf", FACILITY_FILTER, wd / "facilities.geojsonl", wd)
    export_layer(wd / "extract.osm.pbf", ["r/boundary=administrative"], wd / "admin.geojsonl", wd)
    for tmp in wd.glob("*.osm.pbf"):
        if tmp.name != "extract.osm.pbf":
            tmp.unlink()

    info["cells"] = export_cells(tif, clip.bounds, wd / "cells.tsv")
    (wd / "prepare.json").write_text(json.dumps(info, indent=2) + "\n", "utf-8")
    print(f"  {info}")
    return info


def main(keys: list[str]) -> None:
    if not shutil.which("osmium"):
        sys.exit("osmium-tool is required (apt install osmium-tool / brew install osmium-tool)")
    pbf = RAW / SOURCES["osm_pbf"]["file"]
    tif = RAW / SOURCES["worldpop"]["file"]
    for key in keys or AREAS:
        prepare(AREAS[key], pbf, tif, RAW / SOURCES["districts"]["file"], RAW / SOURCES["provinces"]["file"])


if __name__ == "__main__":
    main(sys.argv[1:])
