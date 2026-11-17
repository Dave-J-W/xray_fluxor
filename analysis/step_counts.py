"""Print the individual 1 s S4 counts inside chosen sweep steps, from the ca_logger file.

Usage: python -I analysis/step_counts.py <steplog.csv> <logger.csv> <step> [<step> ...]
Shows every count from the step's first write (t_start) to its end, with seconds since t_start,
so settling after a write can be seen directly. Read-only.
"""
import csv, sys

steplog, logger, *steps = sys.argv[1:]
win = {r["step"]: (float(r["t_start"]), float(r["t_settled"]), float(r["t_end"]))
       for r in csv.DictReader(open(steplog))}
s4 = [(float(r["ioc_timestamp"]), float(r["value"])) for r in csv.DictReader(open(logger, encoding="utf-8"))
      if r["pv"] == "15IDC:scaler1.S4" and r["value"] and r["ioc_timestamp"]]
for st in steps:
    t0, t1, t2 = win[st]
    vals = [(t - t0, v) for t, v in s4 if t0 - 1 <= t <= t2 + 1]
    print(f"{st:8s} settle at +{t1-t0:.1f}s: " + "  ".join(f"{dt:+.1f}:{v:.0f}" for dt, v in vals))
