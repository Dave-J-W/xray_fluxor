"""MonC at the interim setting after the overnight run: per-block statistics and any setting change. Read-only.

Usage: python -I analysis/monc_interim_watch.py <logger.csv> [from "YYYY-mm-dd HH:MM" CST] [block_s]
  default from 2026-11-13 08:12 CST (2 min after the runner restored the interim setting), block 300 s.
Prints every 15IDC:A3* setting change in the window (so a block can be trusted as "interim"), then per
block: n, mean, sd and max-min of S4 (1 s counts). A step in mean or sd marks a state change at the
input, e.g. the chamber being unplugged. Overnight reference (91 holds of 480 s): 60.2 +- 0.6 Hz.
"""
import csv, sys
from datetime import datetime, timedelta, timezone

import numpy as np

CST = timezone(timedelta(hours=-6))
path = sys.argv[1]
t_from = datetime.strptime(sys.argv[2] if len(sys.argv) > 2 else "2026-11-13 08:12", "%Y-%m-%d %H:%M").replace(tzinfo=CST).timestamp()
block = float(sys.argv[3]) if len(sys.argv) > 3 else 300.0
s4, changes = [], []
with open(path, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if not r["ioc_timestamp"]:
            continue
        t = float(r["ioc_timestamp"])
        if t < t_from:
            continue
        if r["pv"] == "15IDC:scaler1.S4" and r["value"]:
            s4.append((t, float(r["value"])))
        elif r["pv"].startswith("15IDC:A3"):
            changes.append((t, r["pv"], r["value"]))
fmt = lambda t: datetime.fromtimestamp(t, CST).strftime("%m-%d %H:%M:%S")
print(f"A3 setting events since {fmt(t_from)}: {len(changes)}")
for t, pv, v in changes:
    print(f"  {fmt(t)} {pv} = {v}")
a = np.array(s4)
print(f"S4 counts: {len(a)}, {fmt(a[0,0])} to {fmt(a[-1,0])}")
print(f"{'block start':15} {'n':>4} {'mean':>8} {'sd':>6} {'max-min':>8}")
for b0 in np.arange(a[0, 0], a[-1, 0], block):
    m = (a[:, 0] >= b0) & (a[:, 0] < b0 + block)
    y = a[m, 1]
    if len(y) > 10:
        print(f"{fmt(b0):15} {len(y):4d} {y.mean():8.1f} {y.std(ddof=1):6.2f} {y.max()-y.min():8.0f}")
