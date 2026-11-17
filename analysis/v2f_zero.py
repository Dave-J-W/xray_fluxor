"""V2F zero-input rate on MonC's channel, from the 1 s logger while the MonC SR570 was switched OFF.

Window: logger start (13:08:58) to the SR570 power-on (first S4 > 100, 13:29:56 on 2026-11-12). The SR570
being off was established afterwards (user switched it on; sweep 1 showed no response to any setting).
Usage: python -I analysis/v2f_zero.py <logger.csv>      Read-only.
"""
import csv, datetime as dt, statistics as st, sys
import numpy as np

rows = [(float(r["ioc_timestamp"]), float(r["value"])) for r in csv.DictReader(open(sys.argv[1], encoding="utf-8"))
        if r["pv"] == "15IDC:scaler1.S4" and r["value"] and r["ioc_timestamp"]]
rows.sort()
t_on = next(t for t, v in rows if v > 100)
off = [(t, v) for t, v in rows if t < t_on - 1]
t, v = np.array(off).T
print(f"window {dt.datetime.fromtimestamp(t[0]):%H:%M:%S} - {dt.datetime.fromtimestamp(t[-1]):%H:%M:%S}"
      f" ({(t[-1]-t[0])/60:.1f} min), n = {len(v)} one-second counts; power-on at {dt.datetime.fromtimestamp(t_on):%H:%M:%S}")
vals, cnt = np.unique(v, return_counts=True)
print("histogram:", dict(zip(vals.astype(int).tolist(), cnt.tolist())))
print(f"mean {v.mean():.4f} Hz, sd {v.std(ddof=1):.3f}, sem {v.std(ddof=1)/np.sqrt(len(v)):.4f}")
# drift: slope and thirds
a, b = np.polyfit((t - t[0]) / 60, v, 1)
print(f"linear drift {a:+.4f} Hz/min over the window")
for i, chunk in enumerate(np.array_split(v, 3)):
    print(f"  third {i+1}: mean {chunk.mean():.3f} (n {len(chunk)})")
# sweep-1 step windows are included: the SR570 was off, so its settings could not matter (checked: means per step 8.0-8.6)
