#!/usr/bin/env python3
"""
Routes and street loads from the shortest-path trees built in sql/13_access.sql.

Every network node knows its next node towards the nearest facility (node_access.pred), so
the trees give, without any extra routing:

* edge_load  – how many residents' routes use each street segment. For the walking
               scenario this is the evacuation flow: the streets that would fill first.
* agents     – the full route of a sample of residents (weighted by population), with a
               time stamp at every vertex, for the animated map and the GIF.

    python scripts/simulate.py          # recompute edge loads for the built areas

build.py calls compute_loads(); export_web.py calls agents().
"""
from __future__ import annotations

import io
import json
import math
from collections import defaultdict

import numpy as np
import psycopg2

from config import SIM_AGENTS, SIM_SEED, SNAP_SPEED_KMH, STUDY, VALIDATION

SCENARIOS = {          # target in node_access → how the agent moves along the tree
    "walk_assembly_any": {"key": "walk", "outward": False,
                          "label": "Residents walk to the nearest assembly-area candidate"},
    "drive_hospital":    {"key": "hospital", "outward": False,
                          "label": "Residents are driven to the nearest hospital"},
    "drive_fire":        {"key": "fire", "outward": True,
                          "label": "Fire engines drive from the nearest station to each home"},
}


def _tree(cur, s: str, target: str) -> dict[int, tuple[float, int, int | None]]:
    cur.execute(f"SELECT vertex_id, cost_s, pred, edge_id FROM {s}.node_access WHERE target = %s", [target])
    return {v: (c, p, e) for v, c, p, e in cur.fetchall()}


# --------------------------------------------------------------------------- loads
def compute_loads(conn, s: str) -> None:
    """Sum the residents of every cell over the edges of its route (one pass per tree)."""
    cur = conn.cursor()
    cur.execute(f"""DROP TABLE IF EXISTS {s}.edge_load;
                    CREATE TABLE {s}.edge_load (target text, edge_id bigint, pop double precision,
                                                PRIMARY KEY (target, edge_id))""")
    for target in SCENARIOS:
        cur.execute(f"""SELECT vertex_id, pred, edge_id FROM {s}.node_access
                        WHERE target = %s ORDER BY cost_s DESC, depth DESC""", [target])
        order = cur.fetchall()                      # children before parents
        cur.execute(f"""SELECT t.via, sum(c.pop) FROM {s}.cell_time t JOIN {s}.cell c USING (cell_id)
                        WHERE t.target = %s AND t.via IS NOT NULL GROUP BY t.via""", [target])
        load = defaultdict(float, {v: float(p) for v, p in cur.fetchall()})
        edge_load = defaultdict(float)
        for v, pred, edge in order:
            l = load.get(v, 0.0)
            if l and pred != -1 and edge is not None:
                edge_load[edge] += l
                load[pred] += l
        rows = "".join(f"{target}\t{e}\t{p:.3f}\n" for e, p in edge_load.items())
        cur.copy_expert(f"COPY {s}.edge_load FROM STDIN", io.StringIO(rows))
        print(f"  edge_load {target:<20} {len(edge_load):>7,} edges")
    cur.execute(f"ANALYZE {s}.edge_load")
    conn.commit()


# --------------------------------------------------------------------------- agents
def _dist(a, b) -> float:
    """Metres between two lon/lat points (equirectangular; fine for a few hundred metres)."""
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((b[0] - a[0]) * k, b[1] - a[1]) * 111_320


def _spread(coords: list, t0: float, t1: float) -> list[tuple[float, float, float]]:
    """Time stamps along a polyline, proportional to distance."""
    d = [0.0]
    for a, b in zip(coords, coords[1:]):
        d.append(d[-1] + _dist(a, b))
    total = d[-1] or 1.0
    return [(t0 + (t1 - t0) * x / total, c[0], c[1]) for x, c in zip(d, coords)]


def agents(conn, s: str, n: int = SIM_AGENTS, seed: int = SIM_SEED) -> dict:
    """Routes of n residents per scenario, drawn with probability proportional to population."""
    cur = conn.cursor()
    snap_mps = SNAP_SPEED_KMH / 3.6
    out = {}
    for target, sc in SCENARIOS.items():
        tree = _tree(cur, s, target)
        cur.execute(f"""SELECT t.cell_id, c.pop FROM {s}.cell_time t JOIN {s}.cell c USING (cell_id)
                        WHERE t.target = %s ORDER BY t.cell_id""", [target])
        ids, pops = zip(*cur.fetchall()) if cur.rowcount else ((), ())
        if not ids:
            continue
        rng = np.random.default_rng(seed)
        w = np.asarray(pops, dtype=float)
        pick = rng.choice(len(ids), size=min(n, len(ids)), replace=False, p=w / w.sum())
        chosen = [int(ids[i]) for i in sorted(pick)]

        cur.execute(f"""
            SELECT c.cell_id, t.via, t.minutes * 60, sn.dist_m,
                   ST_AsGeoJSON(ST_Transform(c.geom_m, 4326), 6),
                   ST_AsGeoJSON(ST_Transform(
                     CASE WHEN t.via = e.source THEN ST_Reverse(ST_LineSubstring(e.geom_m, 0, sn.frac))
                          ELSE ST_LineSubstring(e.geom_m, sn.frac, 1) END, 4326), 6)
            FROM {s}.cell c
            JOIN {s}.cell_time t ON t.cell_id = c.cell_id AND t.target = %s
            JOIN {s}.cell_snap sn ON sn.cell_id = c.cell_id AND sn.mode = %s
            JOIN {s}.edges e ON e.id = sn.edge_id
            WHERE c.cell_id = ANY (%s)""",
                    [target, "walk" if target.startswith("walk") else "drive", chosen])
        starts = cur.fetchall()

        paths, need = {}, set()
        for cell_id, via, total_s, dist_m, pt, partial in starts:
            edges, v = [], via
            while v in tree and tree[v][1] != -1:
                edges.append((v, tree[v][1], tree[v][2]))
                v = tree[v][1]
            paths[cell_id] = edges
            need.update(e for _, _, e in edges)
        cur.execute(f"""SELECT id, source, ST_AsGeoJSON(ST_Transform(geom_m, 4326), 6)
                        FROM {s}.edges WHERE id = ANY (%s)""", [list(need)])
        geom = {i: (src, json.loads(g)["coordinates"]) for i, src, g in cur.fetchall()}

        routes = []
        for cell_id, via, total_s, dist_m, pt, partial in starts:
            p0 = json.loads(pt)["coordinates"]
            g = json.loads(partial) if partial else None      # a Point when the cell sits on a node
            part = [] if g is None else (g["coordinates"] if g["type"] == "LineString" else [g["coordinates"]])
            conn_s = dist_m / snap_mps
            node_s = tree[via][0]
            seq = [(0.0, p0[0], p0[1])]
            if part:
                seq += _spread(part, conn_s, max(conn_s, total_s - node_s))
            for v, pred, e in paths[cell_id]:
                src, coords = geom[e]
                coords = coords if src == v else coords[::-1]
                t0 = total_s - tree[v][0]
                t1 = total_s - tree[pred][0]
                seq += _spread(coords, t0, t1)[1:]
            if sc["outward"]:                      # fire engine: station → home
                seq = [(total_s - t, x, y) for t, x, y in reversed(seq)]
            flat, last = [], None
            for t, x, y in seq:
                key = (round(x, 5), round(y, 5))
                if key == last:
                    continue
                last = key
                flat += [round(t, 1), key[0], key[1]]
            routes.append(flat)
        out[sc["key"]] = {"label": sc["label"], "target": target, "agents": routes,
                          "max_s": max((r[-3] for r in routes), default=0)}
        print(f"  agents {sc['key']:<9} {len(routes):>5}")
    return out


if __name__ == "__main__":
    c = psycopg2.connect("")
    for area in (STUDY, VALIDATION):
        cur = c.cursor()
        cur.execute("SELECT to_regclass(%s)", [f"{area['key']}.node_access"])
        if cur.fetchone()[0]:
            compute_loads(c, area["key"])
