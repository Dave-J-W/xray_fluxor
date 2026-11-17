"""What does MonP lose by not logging gas pressure? Weather statistics from a real barometer.

Input: hourly ASOS altimeter settings for LOT (Lewis University Airport, Romeoville IL, 205 m,
~12 km from the APS), calendar year 2025, from the Iowa Environmental Mesonet. The raw CSV
is saved in data/queries/weather/.

The station pressure comes from the altimeter setting by the standard NWS relation
  P_stn = (A^0.190284 - 8.4228807e-5 * H)^(1/0.190284)        [hPa, H in m]
N2 density goes as P/T, so the fractional pressure spread is the fractional density spread,
and through (1 - exp(-mu_en rho l)) ~ mu_en rho l it is the flux-conversion spread.
The hutch is assumed to share outdoor pressure (HVAC overpressure is a few Pa, 0.003 %).

Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 analysis/pressure_climatology.py
"""
import csv
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "queries" / "weather" / "iem_asos_LOT_2025.csv"
OUT = ROOT / "analysis" / "out"
OUT.mkdir(exist_ok=True)
INHG_TO_HPA = 33.8638866667


def main():
    t, p = [], []
    with SRC.open() as f:
        for r in csv.DictReader(f):
            if r["alti"] in ("M", ""):
                continue
            a = float(r["alti"]) * INHG_TO_HPA
            h = float(r["elevation"])
            t.append(datetime.strptime(r["valid"], "%Y-%m-%d %H:%M"))
            p.append((a ** 0.190284 - 8.4228807e-5 * h) ** (1 / 0.190284))
    p = np.array(p) / 10.0                      # kPa
    ts = np.array([x.timestamp() for x in t]) / 3600.0   # hours
    # guard: a few reports carry garbage altimeter values (e.g. 61 % off). Physical station
    # pressure here never leaves 95-104 kPa; drop and count anything outside.
    good = (p > 95.0) & (p < 104.0)
    n_bad = int((~good).sum())
    p, ts, t = p[good], ts[good], [x for x, g in zip(t, good) if g]

    mean = p.mean()
    rel = p / mean - 1
    lines = [
        f"source: {SRC.name}, n = {len(p)} reports kept, {n_bad} rejected (outside 95-104 kPa), {t[0]} .. {t[-1]} UTC",
        f"station pressure mean = {mean:.3f} kPa (vs 101.325: {100*(mean/101.325-1):+.2f} %)",
        f"1 sigma = {100*rel.std():.2f} %   min/max = {100*rel.min():+.2f} % / {100*rel.max():+.2f} %",
        f"1st..99th percentile = {100*np.percentile(rel,1):+.2f} % .. {100*np.percentile(rel,99):+.2f} %",
    ]
    for hours in (1, 3, 12, 24, 72, 168):
        # change over the lag: pair each report with the first one at least `hours` later
        j = np.searchsorted(ts, ts + hours)
        ok = j < len(ts)
        d = 100 * (p[j[ok]] - p[ok]) / mean
        lines.append(f"change over {hours:4d} h: |median| = {np.median(np.abs(d)):.2f} %   95th pct = {np.percentile(np.abs(d),95):.2f} %   max = {np.abs(d).max():.2f} %")
    text = "\n".join(lines)
    print(text)
    (OUT / "pressure_climatology.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
