#!/usr/bin/env python3
"""
End-to-end test of the pipeline on a tiny, hand-made street grid.

The grid is a TEST FIXTURE, not data: 5 × 5 junctions about 111 m apart, written out
below so every expected travel time can be checked by hand. It exercises the real code
path (osmium → prepare.py → build.py → all SQL files) and then checks the numbers.

    python tests/run_tests.py          # needs PG* variables, osmium-tool, requirements.txt

The test uses the schema "testgrid" and the src/report schemas of the target database,
so point it at a scratch database, not at a finished build.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import psycopg2
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build                                     # noqa: E402
import prepare                                   # noqa: E402
import simulate                                  # noqa: E402
from config import SOURCES, WALK_SPEED_KMH       # noqa: E402

LON0, LAT0 = 32.80, 39.90            # grid origin (south-west junction)
DLON, DLAT = 0.0013, 0.0010          # ≈ 111 m in both directions at this latitude
N = 5                                # 5 × 5 junctions
AREA = {"key": "testgrid", "label": "test grid", "province": "Testil",
        "districts": ["Testilce"], "epsg": 5255, "network_buffer_m": 200}


def node_id(r: int, c: int) -> int:
    return 1000 + 10 * r + c


def ll(r: float, c: float) -> tuple[float, float]:
    return LON0 + c * DLON, LAT0 + r * DLAT


# --------------------------------------------------------------------------- fixture
def osm_xml() -> str:
    nodes, ways, rels = [], [], []

    def node(i, lon, lat, tags=None):
        t = "".join(f'<tag k="{k}" v="{v}"/>' for k, v in (tags or {}).items())
        nodes.append(f'<node id="{i}" version="1" lat="{lat:.7f}" lon="{lon:.7f}">{t}</node>')

    def way(i, refs, tags):
        nd = "".join(f'<nd ref="{r}"/>' for r in refs)
        t = "".join(f'<tag k="{k}" v="{v}"/>' for k, v in tags.items())
        ways.append(f'<way id="{i}" version="1">{nd}{t}</way>')

    for r in range(N):
        for c in range(N):
            node(node_id(r, c), *ll(r, c))
    wid = 1
    for r in range(N):                                   # east-west streets
        way(wid, [node_id(r, c) for c in range(N)], {"highway": "residential", "name": f"Row {r}"})
        wid += 1
    for c in range(N):                                   # north-south streets; column 4 one-way north
        tags = {"highway": "residential", "name": f"Col {c}"}
        if c == 4:
            tags["oneway"] = "yes"
        way(wid, [node_id(r, c) for r in range(N)], tags)
        wid += 1
    way(50, [node_id(2, 2), node_id(3, 3)], {"highway": "footway"})          # walk only
    node(2001, *ll(-1, 0)); node(2002, *ll(-1, 4))
    way(51, [2001, 2002], {"highway": "motorway"})                           # not walkable, isolated

    def square(first_id, r0, c0, r1, c1, inset):
        pts = [ll(r0, c0), ll(r0, c1), ll(r1, c1), ll(r1, c0)]
        sx, sy = inset * DLON, inset * DLAT
        pts = [(pts[0][0] + sx, pts[0][1] + sy), (pts[1][0] - sx, pts[1][1] + sy),
               (pts[2][0] - sx, pts[2][1] - sy), (pts[3][0] + sx, pts[3][1] - sy)]
        ids = list(range(first_id, first_id + 4))
        for i, (x, y) in zip(ids, pts):
            node(i, x, y)
        return ids + [ids[0]]

    way(60, square(3000, 3, 0, 4, 1, 0.09), {"leisure": "park", "name": "Test Park"})     # ≈ 8,200 m²
    way(61, square(3010, 0, 2, 0.2, 2.2, 0.0), {"leisure": "park", "name": "Tiny"})     # ≈ 490 m², dropped
    way(62, square(3020, 1, 3, 2, 4, 0.09), {"amenity": "school", "name": "Test School"})
    node(4001, *ll(0, 4), {"amenity": "hospital", "name": "Test Hospital"})
    node(4002, *ll(4, 0), {"amenity": "fire_station", "name": "Test Fire Station"})
    node(4003, *ll(2, 2), {"emergency": "assembly_point", "name": "Test Assembly"})

    # neighbourhood "Batı" = columns 0–2
    x0, x1 = LON0 - 0.004, LON0 + 2.5 * DLON
    y0, y1 = LAT0 - 0.004, LAT0 + 4 * DLAT + 0.004
    for i, (x, y) in enumerate([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]):
        node(5000 + i, x, y)
    way(70, [5000, 5001, 5002, 5003, 5000], {})
    rels.append('<relation id="80" version="1"><member type="way" ref="70" role="outer"/>'
                '<tag k="type" v="boundary"/><tag k="boundary" v="administrative"/>'
                '<tag k="admin_level" v="8"/><tag k="name" v="Batı Mahallesi"/></relation>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6" generator="test">\n'
            + "\n".join(nodes + ways + rels) + "\n</osm>\n")


def write_fixture(raw: Path) -> tuple[Path, Path]:
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "grid.osm").write_text(osm_xml(), "utf-8")
    pbf = raw / "grid.osm.pbf"
    subprocess.run(["osmium", "cat", str(raw / "grid.osm"), "-o", str(pbf), "--overwrite"], check=True)

    m = 0.006
    box = [[LON0 - m, LAT0 - m], [LON0 + 4 * DLON + m, LAT0 - m],
           [LON0 + 4 * DLON + m, LAT0 + 4 * DLAT + m], [LON0 - m, LAT0 + 4 * DLAT + m]]
    poly = {"type": "Polygon", "coordinates": [box + [box[0]]]}
    for key, name in (("districts", "Testilce"), ("provinces", "Testil")):
        fc = {"type": "FeatureCollection",
              "features": [{"type": "Feature", "properties": {"shapeName": name}, "geometry": poly}]}
        (raw / SOURCES[key]["file"]).write_text(json.dumps(fc), "utf-8")

    # population: 3 arc-second cells (as WorldPop), aligned so one cell centre sits on junction (0,0)
    px = 1 / 1200
    west, north = LON0 - 0.5 * px - 10 * px, LAT0 + 0.5 * px + 20 * px
    pop = np.zeros((40, 40), dtype="float32")
    pop[20, 10] = 50.0                          # centre exactly on junction (0,0)
    far_col = 10 + int(round((4 * DLON + 0.0045) / px))
    pop[20, far_col] = 7.0                      # ≈ 380 m east of the grid: too far from any road
    tif = raw / SOURCES["worldpop"]["file"]
    with rasterio.open(tif, "w", driver="GTiff", height=40, width=40, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(west, north, px, px), nodata=-99999) as dst:
        dst.write(pop, 1)

    (raw / SOURCES["tuik_districts"]["file"]).write_text(json.dumps({"data": [{
        "il_adi": "Testil", "ilceler": [{"il_adi": "TESTİL", "ilce_adi": "TESTİLCE", "nufus": "60"}]}]}), "utf-8")
    (raw / SOURCES["kadikoy_areas"]["file"]).write_text(
        "Mahalle;Adet;Toplanma_Alani_(m²)\nBATI MAHALLESİ;2;9.000\nYok Mahallesi;1;500\n", "utf-8")
    return pbf, tif


# --------------------------------------------------------------------------- checks
FAILS = []


def check(label: str, ok: bool, detail="") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILS.append(label)


def near(a, b, tol) -> bool:
    return a is not None and abs(float(a) - float(b)) <= tol


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="eat-test-"))
    try:
        raw, work = tmp / "raw", tmp / "work"
        pbf, tif = write_fixture(raw)
        info = prepare.prepare(AREA, pbf, tif, raw / SOURCES["districts"]["file"],
                               raw / SOURCES["provinces"]["file"], work=work)

        conn = psycopg2.connect("")
        build.psql("00_init.sql")
        build.load_src(conn, raw)
        build.psql("10_area.sql", s=AREA["key"], epsg=AREA["epsg"])
        build.load_area(conn, AREA, work)
        for f in build.AREA_SQL:
            build.psql(f, **build.area_vars(AREA))
        simulate.compute_loads(conn, AREA["key"])
        build.psql("20_validation.sql", s=AREA["key"])
        cur = conn.cursor()

        def one(sql, *args):
            cur.execute(sql, args)
            row = cur.fetchone()
            return row[0] if row and len(row) == 1 else row

        print("checks")
        # network ------------------------------------------------------------
        # 5 rows × 4 + 5 cols × 4 segments + footway + motorway = 42
        check("edges split at every junction", info["edges"]["edges"] == 42, info["edges"])
        check("motorway is not walkable",
              one("SELECT bool_or(walk) FROM testgrid.edges WHERE highway = 'motorway'") is False)
        check("footway is walk-only",
              one("SELECT walk AND NOT (drive_fw OR drive_bw) FROM testgrid.edges WHERE highway = 'footway'"))
        check("one-way street: backward driving forbidden",
              one("SELECT bool_and(drive_fw AND NOT drive_bw AND drive_bw_s = -1) FROM testgrid.edges "
                  "WHERE way_id = 10"))
        check("isolated motorway left out of the main driving network",
              one("SELECT bool_or(drive_main) FROM testgrid.edges WHERE highway = 'motorway'") is False)
        seg = one("SELECT avg(length_m) FROM testgrid.edges WHERE highway = 'residential'")
        check("block length ≈ 111 m", near(seg, 111.0, 1.0), f"{seg:.2f} m")

        # facilities ---------------------------------------------------------
        kinds = dict(cur.execute("SELECT kind, count(*) FROM testgrid.facility GROUP BY kind") or cur.fetchall())
        check("park < 1000 m² dropped, one of each kind kept",
              kinds == {"park": 1, "school": 1, "hospital": 1, "fire_station": 1, "assembly_point": 1}, kinds)
        check("park entered from its 4 corner junctions",
              one("SELECT count(*) FROM testgrid.facility_node n JOIN testgrid.facility f USING (facility_id) "
                  "WHERE f.kind = 'park' AND n.mode = 'walk'") == 4)

        # travel times -------------------------------------------------------
        mps = WALK_SPEED_KMH / 3.6
        cell0 = one("SELECT cell_id FROM testgrid.cell WHERE pop = 50")
        t = dict(cur.execute("SELECT target, minutes FROM testgrid.cell_time WHERE cell_id = %s", [cell0])
                 or cur.fetchall())
        check("walk to park = 3 blocks", near(t.get("walk_park"), 3 * 111.0 / mps / 60, 0.05),
              f"{t.get('walk_park'):.2f} min")
        check("walk to assembly point = 4 blocks", near(t.get("walk_assembly_point"), 4 * 111.0 / mps / 60, 0.05))
        check("nearest candidate = min of the three",
              near(t.get("walk_assembly_any"),
                   min(t["walk_park"], t["walk_school"], t["walk_assembly_point"]), 1e-6))
        check("drive to hospital = 4 blocks at 30 km/h", near(t.get("drive_hospital"), 4 * 111.0 / (30 / 3.6) / 60, 0.02))
        check("fire engine to cell = 4 blocks at 30 km/h", near(t.get("drive_fire"), 4 * 111.0 / (30 / 3.6) / 60, 0.02))
        back = one("SELECT cost_s FROM testgrid.node_access WHERE target = 'drive_hospital' AND vertex_id = %s",
                   node_id(4, 4))
        check("one-way respected: (4,4) → hospital needs a 6-block detour",
              near(back, 6 * 111.0 / (30 / 3.6), 3), f"{back:.1f} s")
        fire44 = one("SELECT cost_s FROM testgrid.node_access WHERE target = 'drive_fire' AND vertex_id = %s",
                     node_id(4, 4))
        check("fire station → (4,4) along row 4 = 4 blocks", near(fire44, 4 * 111.0 / (30 / 3.6), 3))

        # routes & street loads --------------------------------------------
        col0 = [one("SELECT id FROM testgrid.edges WHERE (source, target) IN ((%s, %s), (%s, %s))",
                    node_id(r, 0), node_id(r + 1, 0), node_id(r + 1, 0), node_id(r, 0)) for r in range(3)]
        loads = [one("SELECT pop FROM testgrid.edge_load WHERE target = 'walk_assembly_any' AND edge_id = %s", e)
                 for e in col0]
        check("evacuation flow: the 50 residents walk north along column 0", loads == [50, 50, 50], loads)
        check("no load on streets nobody uses",
              one("SELECT count(*) FROM testgrid.edge_load WHERE target = 'walk_assembly_any'") == 3)
        sim = simulate.agents(conn, "testgrid", n=10)
        walk = sim["walk"]["agents"][0]
        check("walking route: starts at the home, ends at the park after 3 blocks",
              walk[1:3] == [round(LON0, 5), round(LAT0, 5)] and near(walk[-3], 3 * 111.0 / mps, 2)
              and near(walk[-1], LAT0 + 3 * DLAT, 1e-5), walk[-3:])
        fire = sim["fire"]["agents"][0]
        check("fire-engine route: starts at the station, ends at the home",
              fire[0] == 0 and near(fire[2], LAT0 + 4 * DLAT, 1e-5) and near(fire[-1], LAT0, 1e-5)
              and near(fire[-3], 4 * 111.0 / (30 / 3.6), 2), fire[:3] + fire[-3:])
        check("route times never go backwards",
              all(all(a <= b for a, b in zip(r[0::3], r[3::3])) for sc in sim.values() for r in sc["agents"]))

        # population & indicators -------------------------------------------
        check("population preserved", near(one("SELECT sum(pop) FROM testgrid.cell"), 57, 1e-6))
        check("cell 380 m from any road is not routed",
              one("SELECT count(*) FROM testgrid.cell_snap s JOIN testgrid.cell c USING (cell_id) WHERE c.pop = 7") == 0)
        unreached = one("SELECT pct_unreached FROM testgrid.summary WHERE level = 'area' AND target = 'walk_park'")
        check("unrouted population reported, not hidden", near(unreached, 100 * 7 / 57, 0.1), f"{unreached} %")
        within = one("SELECT pct_le_5 FROM testgrid.summary WHERE level = 'area' AND target = 'walk_assembly_any'")
        check("share within 5 min", near(within, 100 * 50 / 57, 0.1), f"{within} %")
        check("cell assigned to its neighbourhood",
              one("SELECT m.name FROM testgrid.cell c JOIN testgrid.mahalle m ON m.osm_id = c.mahalle_id "
                  "WHERE c.pop = 50") == "Batı Mahallesi")
        park_m2 = one("SELECT area_m2 FROM testgrid.facility WHERE kind = 'park'")
        cand = one("SELECT candidate_m2 FROM testgrid.mahalle_space")
        check("candidate surface = park inside the neighbourhood", near(cand, park_m2, 2), f"{cand} m²")

        # sources & validation logic ----------------------------------------
        check("name key", one("SELECT src.name_key('Fenerbahçe Mahallesi') = src.name_key('FENERBAHÇE MAH.')"))
        check("Turkish thousands separator", one("SELECT src.to_num('9.000') = 9000 AND src.to_num('12,5') = 12.5"))
        check("TÜİK district matched", one("SELECT tuik_2021 FROM report.district_population_check "
                                            "WHERE area = 'testgrid'") == 60)
        v = one("SELECT matched_mahalle, official_mahalle, official_m2 FROM report.kadikoy_validation_summary")
        check("official neighbourhoods matched by name", v == (1, 2, 9000), v)
        conn.close()
    finally:
        if "--keep" not in sys.argv:
            shutil.rmtree(tmp, ignore_errors=True)

    if FAILS:
        sys.exit(f"{len(FAILS)} check(s) failed: {FAILS}")
    print("all checks passed")


if __name__ == "__main__":
    main()
