#!/usr/bin/env python3
"""Loopback caproto simulator of the lane PVs the flux dashboard reads, to render it in states the beam does not give.

    python3 op/tests/dashboard_sim.py <state.json>      serves 127.0.0.1:5076 (CA), prefix 15IDC:util:; never the network

<state.json> is re-read every 0.5 s: {"E": {...}, "P": {...}, "C": {...}} for the E-station, MonP and MonC lanes, each
{"bits": [1, 8, ...], "beam": true, "energy": 10.0, "invalid": false}. The values are made up (a rendering test, not
physics); the PV names are the screen's own, read from the generated display, so a screen change needs no edit here.
Needs caproto (the bluesky venv). SIMULATED: nothing here touches the real IOC.
"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("EPICS_CA_SERVER_PORT", "5076")
os.environ.setdefault("EPICS_CAS_INTF_ADDR_LIST", "127.0.0.1")
os.environ.setdefault("EPICS_CAS_AUTO_BEACON_ADDR_LIST", "NO")
os.environ.setdefault("EPICS_CAS_BEACON_ADDR_LIST", "127.0.0.1")

from caproto import AlarmSeverity, AlarmStatus
from caproto import ChannelDouble, ChannelString
from caproto.server import run

HERE = Path(__file__).resolve().parent
OP = HERE.parent
sys.path.insert(0, str(HERE.parent / "tools"))
import gen_dashboard as gd

P = "15IDC:util:"
MODEL = json.loads((OP.parent / "docs" / "dashboard_model.json").read_text(encoding="utf-8"))
KEY = {"E": "estation", "P": "monp", "C": "monc"}
LANE = {"E": gd.LANES[0], "P": gd.LANES[1], "C": gd.LANES[2]}
STRING_FIELDS = re.compile(r"\.(DESC|CLC[A-P]|SEVR)$")


def pv_names():
    text = (OP / "bob" / "flux_dashboard.bob").read_text(encoding="utf-8")
    names = set(re.findall(r"<pv_name>([^<]+)</pv_name>", text)) | set(re.findall(r"<pv_name>([^<]+)</pv_name>", text))
    for m in re.finditer(r"<(?:pv_name|y_pv)>(\$\(P\)[^<]+)</(?:pv_name|y_pv)>", text):
        names.add(m.group(1))
    for m in re.finditer(r"=`(\$\(P\)[^`]+)`\*1e6", text):                   # formula PVs: serve the record they scale
        names.add(m.group(1))
    return sorted(n.replace("$(P)", P) for n in names if n.startswith("$(P)"))


def lane_values(tag, st):
    """{pv: value} for one lane in state st."""
    L = LANE[tag]
    bits = set(st.get("bits", []))
    beam = st.get("beam", True)
    e = st.get("energy", 10.0)
    scale = 1.0 if beam else 2e-5
    res = 1.2e13 * scale * (1.0 if tag != "E" else 0.4)
    v = {}
    for items in (L["inputs"], L["corr"]):
        for _t, rec, fld, _u, _f, _p in items:
            if rec:
                v[f"{P}{rec}.{fld}"] = 1.0
    v.update({f"{P}{L['result'][0]}.{L['result'][1]}": res, f"{P}{L['low'][0]}.{L['low'][1]}": res * 0.85,
              f"{P}{L['high'][0]}.{L['high'][1]}": res * 1.15, f"{P}{L['up'][0]}.{L['up'][1]}": 15.0, f"{P}{L['down'][0]}.{L['down'][1]}": 15.0})
    for _t, rec, fld, *_ in L["inputs"]:
        if rec:
            lab = _t.lower()
            val = {"energy": e}.get(next((k for k in ("energy",) if k in lab), ""), None)
            if val is not None:
                v[f"{P}{rec}.{fld}"] = val
    for k, b, _c, _t in L["flags"]:
        v[f"{P}{L['flagrec']}.{k}"] = 1.0 if b in bits else 0.0
    code = sum(bits)
    v[f"{P}{L['code'][0]}.{L['code'][1]}"] = float(code)
    v[f"{P}{L['status']}.SEVR"] = "MAJOR" if code > 15.5 else ("MINOR" if code > 0.5 else "NO_ALARM")
    return v


def main(argv):
    state_file = Path(argv[1])
    names = pv_names()
    m = MODEL["lanes"]
    strings = {}
    for tag, key in KEY.items():
        for role, rec in m[key]["slots"].items():
            strings[f"{P}{rec}.DESC"] = f"{m[key]['name']} {role} (SIMULATED)"
        for rec, exprs in m[key]["expected_clc"].items():
            for fld, ex in exprs.items():
                strings[f"{P}{rec}.{fld}"] = ex
    pvdb = {}
    for n in names:
        if n == P + "HEARTBEAT":
            pvdb[n] = ChannelDouble(value=0.0)
        elif STRING_FIELDS.search(n):
            pvdb[n] = ChannelString(value=strings.get(n, "NO_ALARM"))
        else:
            pvdb[n] = ChannelDouble(value=0.0, precision=3)

    async def startup(async_lib, *a, **k):
        beat = 0
        last = None
        while True:
            beat += 1
            await pvdb[P + "HEARTBEAT"].write(float(beat))
            try:
                st = json.loads(state_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                st = {}
            if st != last or beat % 20 == 0:
                for tag in "EPC":
                    s = st.get(tag, {})
                    for pv, val in lane_values(tag, s).items():
                        if pv in pvdb:
                            sev = AlarmSeverity.NO_ALARM
                            L = LANE[tag]
                            if s.get("invalid") and pv in (f"{P}{L['result'][0]}.{L['result'][1]}", f"{P}{L['low'][0]}.{L['low'][1]}", f"{P}{L['high'][0]}.{L['high'][1]}"):
                                sev = AlarmSeverity.INVALID_ALARM
                                val = val * 1.01     # a changed value, so the alarm is posted to monitors
                            elif s.get("bits") and not isinstance(val, str) and pv.split(".")[0] in (P + L["bounds"], P + L["flux"]):
                                c = sum(s["bits"])
                                sev = AlarmSeverity.MAJOR_ALARM if c > 15.5 else (AlarmSeverity.MINOR_ALARM if c > 0.5 else AlarmSeverity.NO_ALARM)
                            await pvdb[pv].write(val)
                            await pvdb[pv].alarm.write(severity=sev, status=AlarmStatus.LINK if sev == AlarmSeverity.INVALID_ALARM else AlarmStatus.NO_ALARM)
                last = st
            await asyncio.sleep(0.5)

    print(f"serving {len(pvdb)} PVs on 127.0.0.1:{os.environ['EPICS_CA_SERVER_PORT']}", flush=True)
    run(pvdb, interfaces=["127.0.0.1"], startup_hook=startup, log_pv_names=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
