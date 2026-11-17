"""Shared helpers for xray_fluxor figures. Every figure module in this folder:

  - imports its numbers from the upstream code or data. It does not retype them:
      calc/lanes.py, calc/monp_transform.py, calc/quality_slots.py   (live-slot expressions + mirrors)
      analysis/wall_loss_mc.py, analysis/fringe_field.py            (models)
      analysis/out/*.csv, data/queries/out/*.csv                    (computed results)
  - exposes `main(outdir)` and writes PNG + SVG into figures/out/ (via save());
  - stamps each figure with its source files, through the `sources` argument of save().

Run all:  <bluesky venv>\\Scripts\\python.exe -I -X utf8 figures/make_all.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "out"
for p in (ROOT / "calc", ROOT / "analysis", ROOT / "data" / "queries"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

STYLE = {"figure.dpi": 110, "savefig.dpi": 150, "font.size": 10, "axes.grid": True, "grid.alpha": 0.3,
         "axes.spines.top": False, "axes.spines.right": False}
plt.rcParams.update(STYLE)


def save(fig, name, sources, outdir=OUT):
    """Write figures/out/<name>.png and .svg, with a small footer naming the upstream sources."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    fig.text(0.01, 0.005, "sources: " + "; ".join(sources), fontsize=6.5, color="0.4", ha="left", va="bottom")
    for ext in ("png", "svg"):
        fig.savefig(outdir / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    return outdir / f"{name}.png"
