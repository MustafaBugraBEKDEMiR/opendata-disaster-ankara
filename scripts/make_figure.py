#!/usr/bin/env python3
"""
Static figure for the README, drawn from the web-map data (docs/data/).

    python scripts/make_figure.py      # → docs/img/access_map.png
"""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.collections import PolyCollection    # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

from config import DOCS_DATA, ROOT, STUDY            # noqa: E402

BREAKS = [0, 5, 10, 15, 30, 60, 90]      # the last class (> 60 min) is drawn as 75
COLORS = ["#fcfdbf", "#feb078", "#f1605d", "#b73779", "#721f81", "#2c115f"]
PANELS = [("w_any", "Walk to the nearest assembly-area candidate"),
          ("d_fire", "Fire engine from the nearest station")]


def rings(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    return [p[0] for p in polys]


def main() -> None:
    grid = json.loads((DOCS_DATA / "grid.geojson").read_text("utf-8"))["features"]
    dist = json.loads((DOCS_DATA / "districts.geojson").read_text("utf-8"))["features"]
    meta = json.loads((DOCS_DATA / "meta.json").read_text("utf-8"))
    cmap, norm = ListedColormap(COLORS), BoundaryNorm(BREAKS, len(COLORS))

    fig, axes = plt.subplots(1, 2, figsize=(13, 6.6), constrained_layout=True)
    for ax, (key, title) in zip(axes, PANELS):
        polys = [f["geometry"]["coordinates"][0] for f in grid]
        vals = [75 if f["properties"][key] is None or f["properties"][key] > 60 else f["properties"][key] - 1e-6
                for f in grid]
        ax.add_collection(PolyCollection(polys, array=vals, cmap=cmap, norm=norm, linewidths=0))
        for f in dist:
            for r in rings(f["geometry"]):
                xs, ys = zip(*r)
                ax.plot(xs, ys, color="#1d2433", lw=0.6, alpha=0.7)
        s = meta["area"].get({"w_any": "walk_assembly_any", "d_fire": "drive_fire"}[key], {})
        ax.set_title(f"{title}\n{s.get('pct_le_10', '–')} % of residents within 10 minutes", fontsize=11)
        ax.autoscale_view()
        ax.set_aspect(1 / 0.766)          # cos(40°): keeps shapes undistorted at Ankara's latitude
        ax.set_axis_off()
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=axes, shrink=0.6, ticks=[2.5, 7.5, 12.5, 22.5, 45, 75])
    cb.ax.set_yticklabels(["≤ 5", "5–10", "10–15", "15–30", "30–60", "> 60"])
    cb.set_label("minutes")
    fig.suptitle(f"{STUDY['label']}: travel time on the street network (500 m squares, WorldPop 2025 residents)",
                 fontsize=12)
    fig.text(0.01, 0.01, "Data: © OpenStreetMap contributors (ODbL), WorldPop R2025A (CC BY 4.0). "
             f"Built {meta['generated']}.", fontsize=8, color="#5b6475")
    out = ROOT / "docs" / "img" / "access_map.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    print(f"  {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
