"""Regenerate every MonC figure from the raw files.

Run (bare `python` is a broken stub on this PC):
    <bluesky venv>\\Scripts\\python.exe -I analysis/figures/make_figures.py [options]

Options:
    --logger PATH     raw ca_logger CSV (default: loaders.DEFAULT_LOGGER, outside git)
    --only NAME ...   build only these figures (names: see FIGURES below)
    --list            list the figures and exit

Read-only: this reads files and writes PNGs under analysis/figures/out/. It never touches EPICS.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # -I drops the script dir from sys.path

import loaders as L  # noqa: E402
from common import say  # noqa: E402


def _sweeps(lg):
    import fig_sweeps
    fig_sweeps.make(lg)


def _logger(lg):
    import fig_logger
    fig_logger.make(lg)


def _set3(lg):
    import fig_set3
    fig_set3.make(lg)


def _ranges(lg):
    import fig_ranges
    fig_ranges.make(lg)


def _night(lg):
    import fig_night
    fig_night.make(lg)


def _unc10(lg):
    import fig_unc10
    fig_unc10.make(lg)


def _electronics(lg):
    import fig_electronics
    fig_electronics.make(lg)


FIGURES = {
    "sweeps": (_sweeps, "sweep2_response.png: sweep 2 response by block, sweep 1 as control"),
    "set3": (_set3, "set3_response.png: set 3 + sweep-1 re-run (step logs from monc-dark)"),
    "ranges": (_ranges, "darks_by_range.png, cal_ladders.png: all live runs, one axis each, range as the series"),
    "night": (_night, "night_darks.png, night_hold.png: overnight program (growing step log outside git)"),
    "electronics": (_electronics, "elec1..5_*.png: MonC linearity, range/CAL factors, dark scatter, dark error (overnight grids and passes)"),
    "unc10": (_unc10, "unc10_*.png: MonC uncertainty at a fixed 10 keV: summary, against rate, coverage check"),
    "logger": (_logger, "logger_*.png: 1 s S4 time series with step/setting markers, warm-up, dark drift"),
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--logger", type=Path, default=L.DEFAULT_LOGGER)
    ap.add_argument("--only", nargs="+", choices=list(FIGURES))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--extra-sweeps-dir", type=Path,
                    help="TESTING ONLY: also read uncommitted step logs/plans from this folder (read-only); "
                         "figures then say UNCOMMITTED in their subtitle")
    a = ap.parse_args(argv)
    L.EXTRA_DIR = a.extra_sweeps_dir
    added = L.discover_sweeps()
    if added:
        say(f"[discover] step logs added: " + ", ".join(f"{k} = {L.SWEEP_FILES[k][0]} + {L.SWEEP_FILES[k][1]}"
                                                        for k in added))
    for u in L.UNMATCHED:
        say(f"[discover] NOT ADDED: {u}")
    if a.list:
        for k, (_, d) in FIGURES.items():
            say(f"{k:8s} {d}")
        return 0
    lg = L.load_logger(a.logger)
    say(f"[load] {lg.path.name}: {lg.n_rows} rows, {len(lg.scaler_t)} complete counts, "
        f"partial lines dropped {lg.n_partial_dropped}")
    for k in a.only or FIGURES:
        FIGURES[k][0](lg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
