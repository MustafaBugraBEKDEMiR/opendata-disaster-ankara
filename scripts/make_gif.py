#!/usr/bin/env python3
"""
Animated GIF of the three scenarios in Ankara's urban core, for the README.

    python scripts/make_gif.py      # → docs/img/simulation.gif

Reads docs/data/sim.json (routes of sampled residents, see simulate.py),
flows.geojson (street loads) and districts.geojson.
"""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
import numpy as np                                   # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402
from matplotlib.collections import LineCollection    # noqa: E402

from config import DOCS_DATA, ROOT                   # noqa: E402

BBOX = (32.60, 39.84, 33.02, 40.04)    # lon/lat of the urban core shown in the GIF
T_END = 15 * 60                        # seconds shown
FRAMES, HOLD = 60, 10                  # animated frames + frames holding the last state
PANELS = [("walk", "On foot to an assembly-area candidate", "#2c5fa8"),
          ("hospital", "By car to the nearest hospital", "#d62728"),
          ("fire", "Fire engine to each home", "#ff7f0e")]
ARRIVED = "#1b9e77"


def lines(geom):
    return [geom["coordinates"]] if geom["type"] == "LineString" else geom["coordinates"]


def main() -> None:
    sim = json.loads((DOCS_DATA / "sim.json").read_text("utf-8"))
    flows = json.loads((DOCS_DATA / "flows.geojson").read_text("utf-8"))["features"]
    dist = json.loads((DOCS_DATA / "districts.geojson").read_text("utf-8"))["features"]
    meta = json.loads((DOCS_DATA / "meta.json").read_text("utf-8"))

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.5), dpi=80)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.78, bottom=0.08, wspace=0.03)
    title = fig.suptitle("", fontsize=15, fontweight="bold", y=0.97)
    state = []
    for ax, (key, label, col) in zip(axes, PANELS):
        ax.set_xlim(BBOX[0], BBOX[2]); ax.set_ylim(BBOX[1], BBOX[3])
        ax.set_aspect(1 / np.cos(np.radians(39.94)))
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color("#d0d4db")
        ax.set_facecolor("#f7f8fa")
        for f in dist:
            g = f["geometry"]
            for poly in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]):
                xs, ys = zip(*poly[0])
                ax.plot(xs, ys, color="#9aa1ad", lw=0.6, zorder=1)
        fl = [f for f in flows if f["properties"]["t"] == key]
        if fl:
            mx = max(f["properties"]["p"] for f in fl)
            segs, widths = [], []
            for f in fl:
                w = np.sqrt(f["properties"]["p"] / mx)
                for ln in lines(f["geometry"]):
                    segs.append(ln); widths.append(0.3 + 3.2 * w)
            ax.add_collection(LineCollection(segs, linewidths=widths, colors=col, alpha=0.28, zorder=2,
                                             capstyle="round"))
        ag = sim.get(key, {}).get("agents", [])
        tracks = [(np.array(a[0::3]), np.array(a[1::3]), np.array(a[2::3])) for a in ag]
        tracks = [t for t in tracks if BBOX[0] <= t[1][-1] <= BBOX[2] and BBOX[1] <= t[2][-1] <= BBOX[3]]
        moving = ax.scatter([], [], s=9, c=col, edgecolors="white", linewidths=0.4, zorder=4)
        done = ax.scatter([], [], s=4, c=ARRIVED, alpha=0.75, zorder=3)
        txt = ax.text(0.02, 1.02, "", transform=ax.transAxes, fontsize=10.5, va="bottom", color="#1d2433")
        ax.set_title(label, fontsize=12, pad=22, color=col, fontweight="bold")
        state.append((tracks, moving, done, txt))
    fig.text(0.01, 0.015, "Shortest street routes of residents sampled by population (WorldPop 2025) · lines: residents per "
             "street segment · OSM maps only part of the fire stations, so fire times are upper bounds · "
             f"© OpenStreetMap contributors · built {meta['generated']}", fontsize=8, color="#5b6475")

    def frame(i):
        t = min(i, FRAMES) / FRAMES * T_END
        title.set_text(f"Ankara, {int(t // 60)}:{int(t % 60):02d} min after the alarm")
        artists = [title]
        for tracks, moving, done, txt in state:
            mv, dn = [], []
            for ts, xs, ys in tracks:
                if t >= ts[-1]:
                    dn.append((xs[-1], ys[-1]))
                else:
                    mv.append((np.interp(t, ts, xs), np.interp(t, ts, ys)))
            moving.set_offsets(np.array(mv) if mv else np.empty((0, 2)))
            done.set_offsets(np.array(dn) if dn else np.empty((0, 2)))
            pct = 100 * len(dn) / max(len(tracks), 1)
            txt.set_text(f"arrived: {pct:.0f} % of {len(tracks):,} residents shown")
            artists += [moving, done, txt]
        return artists

    out = ROOT / "docs" / "img" / "simulation.gif"
    out.parent.mkdir(parents=True, exist_ok=True)
    FuncAnimation(fig, frame, frames=FRAMES + HOLD + 1, blit=False).save(out, writer=PillowWriter(fps=8))
    print(f"  {out.relative_to(ROOT)}  {out.stat().st_size / 2**20:.1f} MB")


if __name__ == "__main__":
    main()
