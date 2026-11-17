"""Cross-check any sweep step log against the raw 1 s logger record, per step.

For each step it prints: the EPICS readback of offset_sign and off_u_put during the count window
(not the plan), the runner's logged mean, the strict mean (only counts that started after
settling; loaders.step_window), the count(s) completed at t_settled that the runner also took,
and MISMATCH when the two means differ by more than max(1 count, 0.1 %, 3 sd/sqrt(n)).
It also lists counts in the S4 1400-1500 band (the re-send spike signature). Only hits whose
neighbours both sit at the baseline (~10-25 counts) are re-send spikes; hits between two step
levels are ordinary transition counts that straddled a setting change.

Read-only. Run:
    <bluesky venv>\\Scripts\\python.exe -I analysis/figures/check_steplog.py <steplog.csv> [--all]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

import loaders as L  # noqa: E402
from common import hms, say  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("steplog", type=Path)
    ap.add_argument("--logger", type=Path, default=L.DEFAULT_LOGGER)
    ap.add_argument("--all", action="store_true", help="print every step, not only flagged ones")
    a = ap.parse_args(argv)
    lg = L.load_logger(a.logger)
    rows = list(csv.DictReader(open(a.steplog, newline="", encoding="utf-8")))
    say(f"{a.steplog.name}: {hms(float(rows[0]['t_start']))}-{hms(float(rows[-1]['t_end']))}, {len(rows)} steps")
    for r in rows:
        st = L.Step(a.steplog.stem, r["step"], "", r["writes"], "", float(r["t_start"]),
                    float(r["t_settled"]), float(r["t_end"]), int(r["n"]), float(r["mean_S4"]), float(r["sd_S4"]))
        s = L.step_stats(lg, st)
        try:
            state = L.settings_during(lg, st.t_settled, st.t_end - 0.5)
            rb = f"sign={state['A3offset_sign'][1]} u={state['A3off_u_put'][0]:+.0f}"
            note = ""
        except ValueError as e:
            rb, note = "sign=? u=?", "CHANGE IN WINDOW: " + str(e)[:80]
        pre = lg.S4[(lg.scaler_t > st.t_settled - 1.05) & (lg.scaler_t <= st.t_settled + 0.05)]
        tol = max(1.0, 1e-3 * abs(st.mean_log), 3 * (s.sd if s.n > 1 else 0) / np.sqrt(max(s.n, 1)))
        bad = not abs(s.mean - st.mean_log) <= tol
        wants_minus = "offset_sign=-" in r["writes"]
        sign_note = "REQUESTED SIGN - NOT IN READBACK" if wants_minus and "sign=+" in rb else ""
        if a.all or bad or note or sign_note:
            say(f"{r['step']:10s} {rb:16s} log {st.mean_log:10.1f} (n{st.n_log})  strict {s.mean:10.1f} (n{s.n})  "
                f"count at settle {pre.astype(int).tolist()}  {'MISMATCH' if bad else ''} {sign_note} {note}")
    t0, t1 = float(rows[0]["t_start"]) - 5, float(rows[-1]["t_end"]) + 5
    m = (lg.scaler_t >= t0) & (lg.scaler_t <= t1) & (lg.S4 > 1400) & (lg.S4 < 1500)
    for t, v in zip(lg.scaler_t[m], lg.S4[m]):
        i = int(np.searchsorted(lg.scaler_t, t))
        nb = (lg.S4[i - 1], lg.S4[i + 1] if i + 1 < len(lg.S4) else np.nan)
        say(f"S4 {v:.0f} at {hms(t)} (neighbours {nb[0]:.0f}, {nb[1]:.0f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
