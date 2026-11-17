#!/usr/bin/env python3
"""Feed the live barometric pressure into the MonP flux calc on utilioc.

Every run (cron, every 15 min on the production host):
  1. Fetch the newest LOT altimeter setting (Lewis University Airport, 205 m, ~14 km from the
     APS): the IEM current-observation JSON first, the NOAA Aviation Weather Center METAR as a
     fallback. stdlib HTTP only.
  2. Convert it to station pressure (the standard NWS relation),
     and sanity-check it (95-104 kPa, report at most 2 h old).
  3. If it is good: write it to 15IDC:util:userTran1.G (kPa, the N2 pressure input of the flux
     calc), and write 0 to 15IDC:util:userTran3.H (the age counter, which counts seconds up
     by itself).
     If it is not good: write nothing. G keeps its last value, H keeps counting, and after
     2 h the status slot shows MINOR ("always a number, with a warning").

Assumptions (physics_note.md §3.3; analysis/asos_intercompare.py):
  - The chamber N2 is at hutch pressure. The exhaust is an open outlet through 3" of
    ~0.16" ID tube (user, 2026-11-12): ~0.3 Pa at 100 sccm, i.e. 0.0003 %.
  - The hutch is at outdoor pressure.
  - Elevation: LOT is at 205 m and the ion chambers at 228 m (user, 2026-11-12). The reported
    pressure is carried to 228 m along the standard atmosphere (≈ -0.27 %, ±0.01 % for real
    temperatures).
  - LOT represents the APS: stations 12-42 km apart agree to 0.05 % (1σ) in 2025.

Writes only to 15IDC:util: (the user's slot grant). Prints one log line per run.

Usage:  python3 asos_pressure.py [--dry-run]
Env:    EPICS_CA_ADDR_LIST=<subnet broadcast>  EPICS_CA_AUTO_ADDR_LIST=NO
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

STATION = "LOT"
INHG_TO_HPA = 33.8638866667
MAX_AGE_S = 7200
P_MIN_KPA, P_MAX_KPA = 95.0, 104.0     # sanity guard on the pressure written (2025 range 95.9-101.4 kPa at LOT)
CRON_SCHEDULE = "7,22,37,52 * * * *"   # as installed by the user (service-account crontab); documentation only
PV_PRESSURE = "15IDC:util:userTran1.G"
PV_AGE = "15IDC:util:userTran3.H"
UA = "xray_fluxor-pressure/1.0"


LOT_ELEV_M = 205.0          # LOT field elevation (IEM station metadata, 2025 archive pulls)
HUTCH_ELEV_M = 228.0        # ion chambers in the C hutch (user, 2026-11-12)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def obs_iem():
    """Primary: IEM current observation (JSON): altimeter [inHg] and its UTC time."""
    j = json.loads(_get("https://mesonet.agron.iastate.edu/json/current.py?station=LOT&network=IL_ASOS"))
    ob = j["last_ob"]
    t = datetime.strptime(ob["utc_valid"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return t, float(ob["altimeter[in]"]), "IEM"


def obs_awc():
    """Fallback: NOAA Aviation Weather Center raw METAR; altimeter group Annnn (hundredths inHg)."""
    line = _get("https://aviationweather.gov/api/data/metar?ids=KLOT&format=raw&hours=3").splitlines()[0]
    m = re.search(r"\bKLOT (\d{2})(\d{2})(\d{2})Z\b.*\bA(\d{4})\b", line)
    if not m:
        raise ValueError(f"cannot parse METAR: {line!r}")
    now = datetime.now(timezone.utc)
    t = now.replace(day=int(m.group(1)), hour=int(m.group(2)), minute=int(m.group(3)), second=0, microsecond=0)
    if t > now + timedelta(minutes=10):        # report from the previous month
        t = (t.replace(day=1) - timedelta(days=1)).replace(day=int(m.group(1)))
    return t, int(m.group(4)) / 100.0, "AWC"


def station_kpa(alti_inhg, elev_m=HUTCH_ELEV_M):
    """Pressure at elev_m implied by an altimeter setting: the standard NWS relation, which carries the
    altimeter setting along the standard atmosphere. At elev_m = LOT_ELEV_M it is LOT's station pressure;
    at HUTCH_ELEV_M it is that reduced by 23 m (≈ -0.27 %)."""
    a = alti_inhg * INHG_TO_HPA
    return (a ** 0.190284 - 8.4228807e-5 * elev_m) ** (1 / 0.190284) / 10.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    errors = []
    obs = None
    for src in (obs_iem, obs_awc):
        try:
            obs = src()
            break
        except Exception as e:  # network, HTTP, parse
            errors.append(f"{src.__name__}: {type(e).__name__}: {e}")
    if obs is None:
        print(f"{stamp} FETCH-FAILED {'; '.join(errors)}; nothing written")
        return 1
    t, alti, source = obs
    p = station_kpa(alti)
    age = (now - t).total_seconds()
    if not (P_MIN_KPA < p < P_MAX_KPA) or age > MAX_AGE_S:
        print(f"{stamp} REJECTED {source} obs {t:%H:%MZ} alti {alti} -> {p:.3f} kPa, age {age:.0f} s; nothing written")
        return 1
    if a.dry_run:
        print(f"{stamp} DRY-RUN {source} obs {t:%H:%MZ} alti {alti} inHg -> {p:.3f} kPa (age {age:.0f} s)")
        return 0
    import epics
    ok1 = epics.caput(PV_PRESSURE, round(p, 3), wait=True, timeout=5)
    ok2 = epics.caput(PV_AGE, 0, wait=True, timeout=5)
    back = epics.caget(PV_PRESSURE, timeout=5)
    good = ok1 == 1 and ok2 == 1 and back is not None and abs(back - round(p, 3)) < 1e-6
    print(f"{stamp} {'WROTE' if good else 'WRITE-FAILED'} {PV_PRESSURE}={p:.3f} kPa "
          f"({source} LOT obs {t:%H:%MZ}, alti {alti} inHg, age {age:.0f} s); readback {back}")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
