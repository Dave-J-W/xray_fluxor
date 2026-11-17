#!/usr/bin/env python3
"""Check the flux dashboard (op/bob/flux_dashboard.bob) and its model export (docs/dashboard_model.json).

    python3 op/tests/check_dashboard.py --static    no network
    python3 op/tests/check_dashboard.py --live      static, then the currency check against the real IOC (READ ONLY: caget only)
                                                 needs pyepics and EPICS_CA_ADDR_LIST / EPICS_CA_AUTO_ADDR_LIST=NO in the environment

Static:
  1. flux_dashboard.bob is what op/tools/gen_dashboard.py writes (no hand edits).
  2. Read-only: the only widgets with an action are action buttons whose actions are write_pv to the local
     selection loc://flux_sel (not a PV of the IOC); no execute/command action, no script, no input widget,
     no bool_button.
  3. Every PV is 15IDC:util: (via the macro P) or loc://flux_sel; no other host or private name.
  4. Optional records file (one record per line, or the IOC's `dbl` output): every record named exists.
  5. The model export is self-consistent: each lane's terms add in quadrature to quad_total, and the low/high
     factors are floor/ceil of 1 -/+ the total to 3 decimals.
Live (currency): every expected .CLC* string of the export (each slot of each lane) is read from the IOC and must
equal it exactly. That covers (a) the sigma terms: the quadrature total gives the factors found in the live bounds
expressions, (b) the wall-loss fit and other constants, (c) the slot map (each slot answers with the expected expressions).
A mismatch fails and names the slot, the field and the term involved.
"""
import json
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
OP = HERE.parent
BOB = OP / "bob" / "flux_dashboard.bob"
MODEL = OP.parent / "docs" / "dashboard_model.json"
GEN = OP / "tools" / "gen_dashboard.py"
P = "15IDC:util:"
fails = 0


def ok(m): print(f"PASS  {m}")


def bad(m):
    global fails
    fails += 1
    print(f"FAIL  {m}")


def static(records=None):
    gen = subprocess.run([sys.executable, str(GEN), str(BOB), "--check"], capture_output=True, text=True)
    (ok if gen.returncode == 0 else bad)(f"flux_dashboard.bob matches its generator ({gen.stdout.strip() or gen.stderr.strip()})")
    root = ET.parse(BOB).getroot()
    widgets = list(root.iter("widget"))
    bad_w = [w.get("type") for w in widgets if w.get("type") in ("textentry", "bool_button", "slider", "scrollbar", "spinner", "combo")]
    (ok if not bad_w else bad)(f"no input widgets ({len(widgets)} widgets)" + (f"; found {bad_w}" if bad_w else ""))
    writes, other = [], []
    for w in widgets:
        for a in (w.find("actions") if w.find("actions") is not None else []):
            if a.get("type") == "write_pv":
                writes.append(a.findtext("pv_name"))
            elif a.get("type") != "open_display":
                other.append(a.get("type"))
    (ok if not other and all(x == "loc://flux_sel(0)" or re.fullmatch(r"loc://flux_sel\(\d\)", x or "") for x in writes) else bad)(
        f"only write_pv actions are to loc://flux_sel ({len(writes)}); other actions: {other or 'none'}")
    (ok if not list(root.iter("scripts")) else bad)("no scripts")
    pvs = {e.text.strip() for e in root.iter("pv_name") if e.text and e.text.strip()}
    pvs |= {e.text.strip() for e in root.iter("y_pv") if e.text}          # strip-chart traces
    foreign = sorted(p for p in pvs if not (p.startswith("$(P)") or p.startswith("loc://flux_sel(") or re.fullmatch(r"=`\$\(P\)[A-Za-z0-9_.]+`\*1e6", p)))
    (ok if not foreign else bad)(f"every PV is $(P)... (15IDC:util:), a read-only `$(P)...`*1e6 formula, or loc://flux_sel ({len(pvs)} names)" + (f"; found {foreign[:5]}" if foreign else ""))
    text = BOB.read_text(encoding="utf-8")
    leak = re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text)
    (ok if not leak else bad)("no IP address in the screen" + (f"; found {leak[:3]}" if leak else ""))
    if records:
        raw = Path(records).read_text(errors="replace")
        if "epics> dbl" in raw:
            raw = raw.split("epics> dbl", 1)[1].split("epics> ", 1)[0]
        recs = {ln.strip() for ln in raw.splitlines() if ln.strip().startswith(P)}
        names = {re.sub(r"\.[A-Z0-9$]+$", "", re.sub(r"^=`|`\*1e6$", "", p).replace("$(P)", P)) for p in pvs if "$(P)" in p}
        miss = sorted(n for n in names if n not in recs)
        (ok if not miss else bad)(f"every record on the screen exists on the IOC ({len(names)})" + (f"; missing {miss}" if miss else ""))
    m = json.loads(MODEL.read_text(encoding="utf-8"))
    for k, lane in m["lanes"].items():
        tot = math.sqrt(sum(t["rel"] ** 2 for t in lane["terms"]))
        lo, hi = math.floor((1 - tot) * 1000) / 1000, math.ceil((1 + tot) * 1000) / 1000
        good = abs(tot - lane["quad_total"]) < 1e-9 and lo == lane["low_factor"] and hi == lane["high_factor"]
        (ok if good else bad)(f"model {k}: terms add to {100 * tot:.2f} %, factors {lo} / {hi}")
    return m


def live(m):
    try:
        import epics
    except ImportError:
        bad("pyepics not importable (use the bluesky venv)")
        return
    n = mism = 0
    for k, lane in m["lanes"].items():
        # the slot map: each slot's DESC answers
        for role, rec in lane["slots"].items():
            d = epics.caget(f"{P}{rec}.DESC", as_string=True, timeout=3)
            (ok if d else bad)(f"{lane['name']}: slot {role} = {rec} answers (DESC '{d}')")
        for rec, exprs in lane["expected_clc"].items():
            for fld, want in exprs.items():
                got = epics.caget(f"{P}{rec}.{fld}", as_string=True, timeout=3)
                n += 1
                if got != want:
                    mism += 1
                    hint = ""
                    if rec.endswith(tuple(str(x) for x in range(10))) and fld in ("CLCD", "CLCE", "CLCK", "CLCM"):
                        hint = f" (symmetric terms: model low x {lane['low_factor']}, high x {lane['high_factor']})"
                    elif fld == "CLCC":
                        hint = f" (wall-loss fit {lane['wall_fit']})"
                    bad(f"{lane['name']}: {rec}.{fld} live '{got}' != export '{want}'{hint}")
    (ok if not mism else bad)(f"currency: {n - mism} of {n} live .CLC strings equal the export")


def main(argv):
    rec = argv[argv.index("--records") + 1] if "--records" in argv else None
    if "--static" not in argv and "--live" not in argv:
        print(__doc__)
        return 2
    m = static(rec)
    if "--live" in argv:
        live(m)
    print("FAIL" if fails else "PASS", f"({fails} failures)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
