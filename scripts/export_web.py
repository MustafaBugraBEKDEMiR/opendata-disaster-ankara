#!/usr/bin/env python3
"""
Export the results for the web map (docs/data/) and write results/RESULTS.md.

    python scripts/export_web.py

Reads the database built by build.py (PG* variables).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import psycopg2

from config import (DOCS_DATA, FACILITY_ENTRY_M, FACILITY_KINDS, MAX_SNAP_M, MIN_PARK_M2, RAW,
                    RESULTS, SNAP_SPEED_KMH, STUDY, VALIDATION, WALK_SPEED_KMH, WEB_GRID_M)

TARGETS = {
    "walk_assembly_any":   ("w_any",  "Walk to the nearest assembly-area candidate (park, school or assembly point)"),
    "walk_assembly_point": ("w_pt",   "Walk to a mapped assembly point"),
    "walk_park":           ("w_park", f"Walk to a park ≥ {MIN_PARK_M2} m²"),
    "walk_school":         ("w_sch",  "Walk to school grounds"),
    "drive_hospital":      ("d_hosp", "Drive to the nearest hospital"),
    "drive_fire":          ("d_fire", "Fire engine from the nearest station"),
}


def rows(cur, sql: str, args=()) -> list[dict]:
    cur.execute(sql, args)
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def jnum(v):
    if v is None:
        return None
    f = float(v)
    return None if f != f or f in (float("inf"), float("-inf")) else (int(f) if f.is_integer() else f)


def feature_collection(cur, sql: str, args=()) -> dict:
    feats = []
    for r in rows(cur, sql, args):
        geom = json.loads(r.pop("geometry"))
        feats.append({"type": "Feature", "geometry": geom,
                      "properties": {k: (jnum(v) if not isinstance(v, str) else v) for k, v in r.items()}})
    return {"type": "FeatureCollection", "features": feats}


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), "utf-8")
    print(f"  {path.relative_to(path.parents[2])}  {path.stat().st_size / 1024:,.0f} kB")


# --------------------------------------------------------------------------- web data
def export_web(cur, s: str, epsg: int) -> None:
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    cols = ",\n".join(
        f"round((sum(pop * LEAST(coalesce(minutes, 61), 61)) FILTER (WHERE target = '{t}') / sum(pop) FILTER (WHERE target = '{t}'))::numeric, 1) AS {k}"
        for t, (k, _) in TARGETS.items())
    write_json(DOCS_DATA / "grid.geojson", feature_collection(cur, f"""
        WITH g AS (
          SELECT floor(ST_X(c.geom_m) / %(g)s)::int AS gx, floor(ST_Y(c.geom_m) / %(g)s)::int AS gy,
                 l.pop, l.target, l.minutes
          FROM {s}.cell c JOIN {s}.cell_long l USING (cell_id)
        )
        SELECT round(sum(pop) FILTER (WHERE target = 'drive_fire')) AS pop, {cols},
               ST_AsGeoJSON(ST_Transform(ST_MakeEnvelope(gx * %(g)s, gy * %(g)s, (gx + 1) * %(g)s,
                                                          (gy + 1) * %(g)s, %(epsg)s), 4326), 5) AS geometry
        FROM g
        GROUP BY gx, gy
        HAVING sum(pop) FILTER (WHERE target = 'drive_fire') >= 1
    """, {"g": WEB_GRID_M, "epsg": epsg}))

    metric = lambda t, col: (f"(SELECT {col} FROM {s}.summary x WHERE x.level = 'mahalle' "
                             f"AND x.key = m.osm_id::text AND x.target = '{t}')")
    write_json(DOCS_DATA / "mahalle.geojson", feature_collection(cur, f"""
        SELECT m.osm_id, m.name, m.district, sp.pop, sp.candidate_m2,
               round(sp.candidate_m2 / NULLIF(sp.pop, 0), 2) AS m2_per_person,
               {metric('walk_assembly_any', 'median_min')}  AS w_any_med,
               {metric('walk_assembly_any', 'pct_le_10')}   AS w_any_10,
               {metric('drive_hospital', 'median_min')}     AS d_hosp_med,
               {metric('drive_fire', 'median_min')}         AS d_fire_med,
               {metric('drive_fire', 'pct_le_10')}          AS d_fire_10,
               ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(m.geom_m, 15), 4326), 5) AS geometry
        FROM {s}.mahalle m JOIN {s}.mahalle_space sp USING (osm_id)
        WHERE sp.pop > 0
    """))

    write_json(DOCS_DATA / "facilities.geojson", feature_collection(cur, f"""
        SELECT kind, name, osm_ref,
               ST_AsGeoJSON(ST_Transform(ST_PointOnSurface(geom_m), 4326), 5) AS geometry
        FROM {s}.facility
        ORDER BY kind
    """))

    write_json(DOCS_DATA / "districts.geojson", feature_collection(cur, f"""
        SELECT name, ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(geom_m, 30), 4326), 5) AS geometry
        FROM {s}.district
    """))


# --------------------------------------------------------------------------- results
def med(v):
    """Median minutes; NULL/infinite means more than half the people are beyond 60 min."""
    return "> 60" if jnum(v) is None else jnum(v)


def md_table(header: list[str], body: list[list]) -> str:
    fmt = lambda v: "–" if v is None else (f"{v:,.0f}" if isinstance(v, (int, float)) and float(v).is_integer() and abs(float(v)) >= 1000
                                          else (f"{float(v):g}" if not isinstance(v, str) else v))
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(fmt(v) for v in r) + " |" for r in body]
    return "\n".join(lines)


def results_md(cur, s: str, v: str) -> tuple[str, dict]:
    sources = json.loads((RAW / "SOURCES.json").read_text("utf-8")) if (RAW / "SOURCES.json").exists() else {}
    area = {r["target"]: r for r in rows(cur, f"SELECT * FROM {s}.summary WHERE level = 'area'")}
    counts = dict((r["kind"], r["n"]) for r in rows(cur, f"SELECT kind, count(*) AS n FROM {s}.facility GROUP BY kind"))
    net = rows(cur, f"""SELECT count(*) FILTER (WHERE walk_main) AS walk_edges,
                               count(*) FILTER (WHERE drive_main) AS drive_edges,
                               round((sum(length_m) FILTER (WHERE walk_main) / 1000)::numeric) AS walk_km
                        FROM {s}.edges""")[0]
    pop = rows(cur, f"""SELECT round(sum(c.pop)::numeric) AS pop, count(*) AS cells,
                               round((sum(c.pop) FILTER (WHERE s.cell_id IS NULL))::numeric) AS off_network,
                               round((100 * sum(c.pop) FILTER (WHERE c.mahalle_id IS NOT NULL) / sum(c.pop))::numeric, 1) AS in_mahalle_pct
                        FROM {s}.cell c LEFT JOIN {s}.cell_snap s ON s.cell_id = c.cell_id AND s.mode = 'walk'""")[0]
    nmah = rows(cur, f"SELECT count(*) AS n FROM {s}.mahalle")[0]["n"]

    out = [f"# Results: {STUDY['label']}", "",
           f"*Generated {dt.date.today().isoformat()} by `scripts/export_web.py`. Do not edit by hand.*", ""]
    out += ["## Inputs", "",
            md_table(["", "value"], [
                ["Population (WorldPop 2025, 100 m cells)", float(pop["pop"])],
                ["Populated cells", pop["cells"]],
                ["Population with no road within " + f"{MAX_SNAP_M} m", float(pop["off_network"] or 0)],
                ["Walkable network (main component)", f"{net['walk_edges']:,} segments, {float(net['walk_km']):,.0f} km"],
                ["Drivable network (main component)", f"{net['drive_edges']:,} segments"],
                ["Neighbourhoods (OSM admin_level 8)", f"{nmah:,} (cover {pop['in_mahalle_pct']} % of the population)"],
            ] + [[FACILITY_KINDS[k]["label"], counts.get(k, 0)] for k in FACILITY_KINDS]), ""]
    if sources:
        out += ["Source files: " + "; ".join(f"`{x['file']}` ({x['downloaded']})" for x in sources.values()), ""]

    out += ["## Whole study area", "",
            "Share of the population that reaches the target within the given time, and the population-weighted median.", "",
            md_table(["Target", "≤ 5 min", "≤ 10 min", "≤ 15 min", "not reached ≤ 60 min*", "median (min)"],
                     [[label, f"{area[t]['pct_le_5']} %", f"{area[t]['pct_le_10']} %", f"{area[t]['pct_le_15']} %",
                       f"{area[t]['pct_unreached']} %", med(area[t]["median_min"])]
                      for t, (_, label) in TARGETS.items() if t in area]), "",
            "\\* includes population with no road within the snapping distance.", ""]

    d = rows(cur, f"""
        SELECT a.key AS district, a.pop,
               a.pct_le_10 AS w10, a.median_min AS wmed,
               h.pct_le_10 AS h10, h.median_min AS hmed,
               f.pct_le_10 AS f10, f.median_min AS fmed
        FROM {s}.summary a
        JOIN {s}.summary h ON h.level = 'district' AND h.key = a.key AND h.target = 'drive_hospital'
        JOIN {s}.summary f ON f.level = 'district' AND f.key = a.key AND f.target = 'drive_fire'
        WHERE a.level = 'district' AND a.target = 'walk_assembly_any'
        ORDER BY a.pct_le_10""")
    out += ["## Districts", "", "Sorted by the share of people within a 10-minute walk of an assembly-area candidate (worst first).", "",
            md_table(["District", "population", "walk ≤ 10 min", "walk median", "hospital ≤ 10 min (car)",
                      "hospital median", "fire engine ≤ 10 min", "fire median"],
                     [[r["district"], float(r["pop"]), f"{r['w10']} %", med(r["wmed"]), f"{r['h10']} %", med(r["hmed"]),
                       f"{r['f10']} %", med(r["fmed"])] for r in d]), ""]

    worst = rows(cur, f"""
        SELECT m.name, m.district, sp.pop, a.pct_le_10, a.median_min, f.median_min AS fire_med,
               round(sp.candidate_m2 / NULLIF(sp.pop, 0), 2) AS m2pp
        FROM {s}.mahalle m JOIN {s}.mahalle_space sp USING (osm_id)
        JOIN {s}.summary a ON a.level = 'mahalle' AND a.key = m.osm_id::text AND a.target = 'walk_assembly_any'
        JOIN {s}.summary f ON f.level = 'mahalle' AND f.key = m.osm_id::text AND f.target = 'drive_fire'
        WHERE sp.pop >= 1000
        ORDER BY a.pct_le_10, a.median_min DESC NULLS FIRST
        LIMIT 15""")
    out += ["## Neighbourhoods with the weakest walking access", "",
            "Neighbourhoods with at least 1,000 residents, sorted by the share within a 10-minute walk of an assembly-area candidate.", "",
            md_table(["Neighbourhood", "district", "population", "walk ≤ 10 min", "walk median", "fire median", "candidate m² / person"],
                     [[r["name"], r["district"], float(r["pop"]), f"{r['pct_le_10']} %", med(r["median_min"]),
                       med(r["fire_med"]), jnum(r["m2pp"])] for r in worst]), ""]

    chk = rows(cur, "SELECT * FROM report.district_population_check WHERE area = %s ORDER BY district", [s])
    out += ["## Check: WorldPop vs TÜİK district totals", "",
            "WorldPop is a 2025 model estimate, TÜİK ADNKS the 2021 register, so the ratio should be near 1, not exactly 1.", "",
            md_table(["District", "TÜİK 2021", "WorldPop 2025", "ratio"],
                     [[r["district"], r["tuik_2021"], float(r["worldpop_2025"]), jnum(r["ratio"])] for r in chk]), ""]

    val = {}
    cur.execute("SELECT to_regclass('report.kadikoy_validation_summary')")
    if cur.fetchone()[0]:
        val = rows(cur, "SELECT * FROM report.kadikoy_validation_summary")[0]
        vt = rows(cur, "SELECT * FROM report.kadikoy_validation ORDER BY mahalle")
        out += [f"## Validation: {VALIDATION['label']}", "",
                "Kadıköy Municipality publishes the number and surface of its official assembly areas per neighbourhood. "
                "The same pipeline derives the candidate surface from OpenStreetMap.", "",
                md_table(["", "official", "this pipeline"], [
                    ["Neighbourhoods", val["official_mahalle"], f"{val['matched_mahalle']} matched by name"],
                    ["Assembly areas / candidates", val["official_areas"], val["osm_candidates"]],
                    ["Surface (m²)", jnum(val["official_m2"]), jnum(val["osm_m2"])],
                    ["Rank correlation of surface (Spearman)", "", jnum(val["spearman_surface"])],
                    ["Population (official 2022 / WorldPop 2025)", val["official_pop_2022"], jnum(val["worldpop_2025"])],
                    ["Rank correlation of population (Spearman)", "", jnum(val["spearman_population"])],
                ]), "",
                "<details><summary>Per neighbourhood</summary>", "",
                md_table(["Neighbourhood", "official areas", "official m²", "OSM candidates", "OSM m²",
                          "official pop. 2022", "WorldPop 2025"],
                         [[r["mahalle"], r["official_count"], jnum(r["official_m2"]), r["osm_candidates"], jnum(r["osm_m2"]),
                           r["official_pop_2022"], jnum(r["worldpop_2025"])] for r in vt]), "", "</details>", ""]

    out += ["## Assumptions", "",
            f"* Walking speed {WALK_SPEED_KMH} km/h; the straight line from a cell centre to the nearest road "
            f"(≤ {MAX_SNAP_M} m) is walked at {SNAP_SPEED_KMH} km/h.",
            "* Driving at free-flow speed: OSM `maxspeed`, otherwise a default per road class (`scripts/config.py`). "
            "No traffic, no road damage.",
            f"* A park or school polygon can be entered from every road node within {FACILITY_ENTRY_M} m of it.",
            "* Routing stops at 60 minutes."]
    summary = {"area": {t: {k: jnum(vv) for k, vv in area[t].items() if k not in ("level", "key", "target")}
                        for t in area},
               "facilities": counts, "population": jnum(pop["pop"]), "mahalle": nmah,
               "validation": {k: jnum(x) for k, x in val.items()}}
    return "\n".join(out) + "\n", summary


def main() -> None:
    s, v = STUDY["key"], VALIDATION["key"]
    conn = psycopg2.connect("")
    cur = conn.cursor()
    export_web(cur, s, STUDY["epsg"])
    md, summary = results_md(cur, s, v)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "RESULTS.md").write_text(md, "utf-8")
    meta = {"generated": dt.date.today().isoformat(), "area": STUDY["label"],
            "targets": {k: label for _, (k, label) in TARGETS.items()},
            "walk_speed_kmh": WALK_SPEED_KMH, "grid_m": WEB_GRID_M, **summary}
    write_json(DOCS_DATA / "meta.json", meta)
    print("  results/RESULTS.md")
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
