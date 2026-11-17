#!/usr/bin/env python3
"""Log a list of slow-changing PVs (instrument settings) whenever any value changes. Read-only CA gets.

For settings the site archiver does not hold (picoammeter range, bias, offsets...), so a later reader
can date a change to within one cron interval. One JSON line per change, plus the first run:
    {"t": "<UTC ISO>", "v": {"<pv>": "<text value>", ...}}
A PV that cannot be read is recorded as "NC" (never a stale value).

Usage:  python3 pv_config_log.py --names FILE --out FILE.jsonl
        FILE: one PV name per line (blank lines and # comments ignored); kept on the host, not in the repo.
Env:    EPICS_CA_ADDR_LIST=<subnet broadcast>  EPICS_CA_AUTO_ADDR_LIST=NO
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import epics


def last_values(path):
    if not os.path.exists(path):
        return None
    last = None
    with open(path) as f:
        for line in f:
            if line.strip():
                last = line
    return json.loads(last)["v"] if last else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    names = [l.strip() for l in open(a.names) if l.strip() and not l.lstrip().startswith("#")]
    pvs = {n: epics.PV(n, auto_monitor=False) for n in names}
    vals = {}
    for n, p in pvs.items():
        v = None
        if p.wait_for_connection(timeout=5):
            v = p.get(as_string=True, timeout=5)
        vals[n] = "NC" if v is None else str(v)
    if vals == last_values(a.out):
        print("unchanged (%d PVs)" % len(vals))
        return 0
    rec = {"t": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "v": vals}
    with open(a.out, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print("logged change (%d PVs)" % len(vals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
