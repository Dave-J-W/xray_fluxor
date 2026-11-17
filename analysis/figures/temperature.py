"""Hutch temperature for the MonC figures: RAW archiver pulls (no binning operator), saved outside git.

Pull (read-only HTTP GET to the archiver; host:port from the gitignored site.env, ARCHIVER_RETRIEVAL):
    <bluesky venv>\\Scripts\\python.exe -I analysis/figures/temperature.py pull [--from ISO] [--to ISO]
writes archiver-pulls/xray_fluxor/15ID_Sensor<n>_Temperature_RAW_60s-native_<from>_<to>.csv (no header:
epoch_s, value, severity, status, nanos). Figures then read every such file (load()), so make_figures.py
stays offline and reproducible.

Archiving (getPVDetails, 2026-11-12): 15ID:Sensor1..5:Temperature are SCAN, 60 s, config unchanged since
2026-03-09. Sensor2 is the C-station hutch sensor used in analysis/hutch_temperature.py. Sensor3 and
Sensor4 read 0.0 degC (no sensor connected), so they are refused by the value guard.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import loaders as L  # noqa: E402

PULLS = L.DATA_ROOT.parent / "archiver-pulls" / "xray_fluxor"
SENSORS = {1: "Sensor1", 2: "Sensor2 (C hutch)", 3: "Sensor3", 4: "Sensor4", 5: "Sensor5"}
COLOURS = {1: "#2a78d6", 2: "#eb6834", 3: "#1baf7a", 4: "#eda100", 5: "#1baf7a"}
VALID = (5.0, 45.0)        # degC; outside this a reading is not a hutch temperature (0.0 = no sensor)


def _site(key: str) -> str:
    for d in (L.ROOT, *L.ROOT.parents):
        f = d / "site.env"
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    raise SystemExit(f"{key} not set: copy site.env.template to site.env (gitignored) and fill it in")


def pull(frm: str, to: str):
    import urllib.parse
    import urllib.request
    host = _site("ARCHIVER_RETRIEVAL")
    PULLS.mkdir(parents=True, exist_ok=True)
    tag = f"{frm[:16].replace(':', '')}_{to[:16].replace(':', '')}"
    for n in SENSORS:
        pv = f"15ID:Sensor{n}:Temperature"
        q = urllib.parse.urlencode({"pv": pv, "from": frm, "to": to})
        out = PULLS / f"15ID_Sensor{n}_Temperature_RAW_60s-native_{tag}.csv"
        with urllib.request.urlopen(f"http://{host}/retrieval/data/getData.csv?{q}", timeout=120) as r:
            body = r.read()
        out.write_bytes(body)
        print(f"{pv}: {body.count(b'\n')} rows -> {out.name}")


def load(t0: float, t1: float):
    """[(label, t[], value[], colour)] for every sensor with valid readings in [t0, t1]."""
    out = []
    for n, lab in SENSORS.items():
        files = sorted(PULLS.glob(f"15ID_Sensor{n}_Temperature_RAW_*.csv"))
        rows = []
        for f in files:
            a = np.loadtxt(f, delimiter=",", usecols=(0, 1, 2), ndmin=2)
            if a.size:
                rows.append(a)
        if not rows:
            continue
        a = np.unique(np.concatenate(rows), axis=0)        # pulls overlap: one row per sample
        t, v, sev = a[:, 0], a[:, 1], a[:, 2]
        m = (t >= t0) & (t <= t1) & (sev == 0) & (v > VALID[0]) & (v < VALID[1])
        if m.sum() >= 3:
            out.append((f"15ID:{lab}:Temperature, °C (raw, 60 s SCAN)", t[m], v[m], COLOURS[n]))
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pull"])
    ap.add_argument("--from", dest="frm", default="2026-11-12T19:00:00.000Z")
    ap.add_argument("--to", dest="to",
                    default=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"))
    a = ap.parse_args()
    pull(a.frm, a.to)
