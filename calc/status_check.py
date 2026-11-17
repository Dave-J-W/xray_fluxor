"""Read-only snapshot of one or all xray_fluxor lanes on utilioc: values, severities, and whether
the alarm chain is consistent (the status severity reaches the dark feed, the flux and the bounds).

Usage: <bluesky venv>\\Scripts\\python.exe -X utf8 calc/status_check.py [--lane MonP|MonC]   (default: all lanes)
"""
import argparse
import sys
from pathlib import Path

import epics

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lanes import LANES, rec  # noqa: E402

ROWS = [("flux", "P", "exit flux ph/s"), ("flux", "J", "net rate Hz"), ("flux", "H", "background subtracted Hz"),
        ("flux", "E", "energy keV"), ("flux", "G", "N2 pressure kPa"),
        ("bkg", "L", "background estimate Hz"), ("bkg", "N", "background stale (1)"),
        ("bkg", "O", "s since background update"),
        ("flags", "L", "status code (sum of the bits)"),
        ("status", "VAL", "status code with severity"), ("dark", "VAL", "dark feed Hz"),
        ("bounds", "C", "signal wall-loss fraction"), ("bounds", "L", "RESULT best flux ph/s"),
        ("bounds", "D", "flux LOW bound ph/s"), ("bounds", "E", "flux HIGH bound ph/s"),
        ("bounds", "F", "uncertainty up %"), ("bounds", "G", "uncertainty down %"),
        ("bounds", "H", "s since pressure update")]
ORDER = {"NO_ALARM": 0, "MINOR": 1, "MAJOR": 2, "INVALID": 3}


def g(pv):
    return epics.caget(pv, as_string=True, timeout=3)


def check(lane):
    print(f"== {lane}")
    sev = {}
    for role, f, what in ROWS:
        r = rec(lane, role)
        s = g(r + ".SEVR")
        sev[role] = s
        print(f"  {r[11:] + '.' + f:18s} {str(g(r + '.' + f)):>14s}   {str(s):9s} {str(g(r + '.STAT')):8s} {what}")
    st = sev["status"]
    ok = all(ORDER.get(sev[x], -1) >= ORDER.get(st, 9) for x in ("dark", "flux", "bounds"))
    print(f"  status severity {st} reaches dark feed, flux and bounds: {'yes' if ok else 'NO'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", choices=sorted(LANES))
    a = ap.parse_args()
    ok = all([check(l) for l in ([a.lane] if a.lane else LANES)])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
