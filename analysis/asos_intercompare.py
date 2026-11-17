"""How well does one nearby airport barometer predict the pressure at another?

The pressure correction assumes that LOT's hourly station pressure, shifted to the APS elevation,
is the hutch pressure. This script tests the spatial part of that assumption. It compares LOT
(Romeoville, ~12 km from the APS) with ARR (Aurora), JOT (Joliet), MDW (Midway) and ORD (O'Hare),
2025, at matched hours. All stations are reduced to a common 210 m height using the
standard-atmosphere scale (dP/P = -dh / 8434 m, adequate for the <40 m differences here).

The residual scatter of (station - LOT) is an empirical upper bound on the error of transferring
LOT to a site ~12 km away. It includes both stations' barometer errors and real gradients.
APS sits between these stations, closer to LOT than to any other.

Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 analysis/asos_intercompare.py
"""
import csv
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "data" / "queries" / "weather"
OUT = ROOT / "analysis" / "out"
INHG = 33.8638866667
H_REF = 210.0
SCALE_H = 8434.0


def load(station):
    rows = {}
    meta = None
    with (W / f"iem_asos_{station}_2025.csv").open() as f:
        for r in csv.DictReader(f):
            if r["alti"] in ("M", ""):
                continue
            h = float(r["elevation"])
            meta = (float(r["lat"]), float(r["lon"]), h)
            a = float(r["alti"]) * INHG
            p = (a ** 0.190284 - 8.4228807e-5 * h) ** (1 / 0.190284)   # station pressure hPa
            p_ref = p * np.exp(-(H_REF - h) / SCALE_H)                  # reduce to 210 m
            if not 950 < p_ref < 1040:
                continue
            t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M")
            rows[(t.year, t.month, t.day, t.hour)] = p_ref   # one report per clock hour
    return rows, meta


def dist_km(a, b):
    la1, lo1 = np.radians(a[:2])
    la2, lo2 = np.radians(b[:2])
    return 6371 * np.arccos(np.sin(la1) * np.sin(la2) + np.cos(la1) * np.cos(la2) * np.cos(lo1 - lo2))


def main():
    ref, mref = load("LOT")
    aps = (41.703, -87.988, 0)   # APS, approximate [PROVISIONAL]
    lines = [f"reference LOT at {mref}, {dist_km(mref, aps):.1f} km from APS; heights reduced to {H_REF:.0f} m"]
    for s in ("ARR", "JOT", "MDW", "ORD"):
        other, m = load(s)
        keys = sorted(set(ref) & set(other))
        d = np.array([other[k] - ref[k] for k in keys])            # hPa
        dm = d - np.median(d)                                       # remove constant offset (calibration/height)
        lines.append(
            f"{s}: {dist_km(m, mref):5.1f} km from LOT, n={len(d)}, median offset {np.median(d):+.2f} hPa, "
            f"scatter about it: 1 sigma(robust) {1.4826*np.median(np.abs(dm)):.2f} hPa "
            f"= {100*1.4826*np.median(np.abs(dm))/990:.3f} %, 95th |d| {np.percentile(np.abs(dm),95):.2f} hPa "
            f"= {100*np.percentile(np.abs(dm),95)/990:.3f} %, max {np.abs(dm).max():.2f} hPa")
    text = "\n".join(lines)
    print(text)
    (OUT / "asos_intercompare.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
