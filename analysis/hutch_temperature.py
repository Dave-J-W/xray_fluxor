"""C-station hutch temperature (15ID:Sensor2:Temperature): how much does it move N2 density?

Input: RAW archiver pulls (no binning operator; see the pv-retrieval skill). They are kept
OUTSIDE this repo, in ../archiver-pulls/xray_fluxor/, per the archive-data convention.
Two regimes are split at the archival-config change of 2026-03-09.
Columns: epoch_s, value, severity, status, nanos (no header).

Reported, for density (rho ~ 1/T, so dT/T = 1 K / 295 K = 0.34 %):
  - overall statistics, and statistics per regime
  - the spread of changes over 1 h, 24 h and 72 h
  - the daily range
Values are assumed to be deg C (they read ~24-25). [PROVISIONAL: units not checked on the IOC]

Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 analysis/hutch_temperature.py [pull_dir]
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PULLS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "archiver-pulls" / "xray_fluxor"
OUT = ROOT / "analysis" / "out"


def load(path):
    a = np.loadtxt(path, delimiter=",", usecols=(0, 1, 2))
    t, v, sev = a[:, 0], a[:, 1], a[:, 2]
    ok = (sev == 0) & (v > 5) & (v < 45)          # guard: drop invalid / alarm-severity samples
    return t[ok], v[ok], int((~ok).sum())


def lag_stats(t, v, hours):
    j = np.searchsorted(t, t + 3600 * hours)
    ok = j < len(t)
    dt_real = t[j[ok]] - t[ok]
    good = dt_real < 3600 * hours * 1.5              # skip pairs that straddle archive gaps
    d = np.abs(v[j[ok]][good] - v[ok][good])
    return np.median(d), np.percentile(d, 95), d.max()


def main():
    files = sorted(PULLS.glob("15ID_Sensor2_Temperature_RAW_*.csv"))
    lines = [f"pull dir: {PULLS.name}/ ; files: {[f.name for f in files]}"]
    T_all, V_all = [], []
    for f in files:
        t, v, nbad = load(f)
        T_all.append(t)
        V_all.append(v)
        gaps = np.diff(t)
        lines.append(f"{f.name}: n={len(v)} (dropped {nbad}), median spacing {np.median(gaps):.0f} s, "
                     f"gaps >1 h: {(gaps > 3600).sum()}, mean {v.mean():.2f} C, sd {v.std():.2f} C, "
                     f"1..99 pct {np.percentile(v,1):.2f}..{np.percentile(v,99):.2f} C")
    t = np.concatenate(T_all)
    v = np.concatenate(V_all)
    o = np.argsort(t)
    t, v = t[o], v[o]
    lines.append(f"ALL: n={len(v)}, mean {v.mean():.2f} C, sd {v.std():.3f} C "
                 f"(= {100*v.std()/(v.mean()+273.15):.3f} % in density), "
                 f"min/max {v.min():.2f}/{v.max():.2f} C")
    for h in (1, 24, 72):
        med, p95, mx = lag_stats(t, v, h)
        lines.append(f"|change| over {h:3d} h: median {med:.3f} C, 95th {p95:.3f} C, max {mx:.2f} C "
                     f"(95th = {100*p95/(v.mean()+273.15):.3f} % in density)")
    day = np.floor((t - 6 * 3600) / 86400)           # local-ish days (UTC-6)
    rngs = np.array([np.ptp(v[day == d]) for d in np.unique(day) if (day == d).sum() > 100])
    lines.append(f"daily range: median {np.median(rngs):.3f} C, 95th {np.percentile(rngs,95):.3f} C, max {rngs.max():.2f} C")
    text = "\n".join(lines)
    print(text)
    (OUT / "hutch_temperature.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
