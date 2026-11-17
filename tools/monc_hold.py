"""Put the MonC SR570 (15IDC:A3) into a named hold configuration and leave it there (no restore).

WRITES HARDWARE SETTINGS: only with the user's OK for that configuration. Only 15IDC:A3 fields in
monc_sweep.ALLOWED are written; each is read back. MonP (15IDC:A2) is never written.

Usage: monc_hold.py <name> [--dry-run]     names: see CONFIGS
"""
import os, sys, time

CONFIGS = {
    # dark-drift monitoring, chosen 2026-11-12 (user: "Move above zero"): calibrated 1 nA offset at
    # 50 nA/V gives ~2055 Hz (2000 nominal + ~55 Hz dark), far from the V2F clip. dark = f - 2000 Hz.
    "dark_monitor_cal1nA": [("sens_num", "50"), ("offset_on", "OFF"), ("offset_cal", "CAL"), ("offset_unit", "nA"),
                            ("offset_num", "1"), ("offset_sign", "+"), ("offset_on", "ON")],
    # interim operation (user 2026-11-12: "set MonC to 5uA/V and set the offset such that counts are less than
    # 120 Hz"): 5 uA/V offset-off dark ~18 Hz (set 4/5) + calibrated +2 nA (= 40 Hz) -> ~58 Hz, clear of both
    # the 120 Hz limit and the V2F clip. Old software, no background subtraction.
    "interim_5uA_cal2nA": [("offset_on", "OFF"), ("sens_unit", "uA/V"), ("sens_num", "5"), ("offset_cal", "CAL"),
                           ("offset_unit", "nA"), ("offset_num", "2"), ("offset_sign", "+"), ("offset_on", "ON")],
    # the 2026-11-12 baseline (restore point)
    "baseline": [("sens_num", "50"), ("offset_cal", "UNCAL"), ("offset_unit", "nA"), ("offset_num", "20"),
                 ("offset_sign", "+"), ("off_u_put", "6"), ("offset_on", "ON")],
}
ALLOWED = ("sens_unit", "sens_num", "offset_num", "offset_unit", "offset_sign", "offset_on", "offset_cal",
           "off_u_put")


def main():
    name = sys.argv[1]
    writes = CONFIGS[name]
    assert all(f in ALLOWED for f, _ in writes)
    if "--dry-run" in sys.argv:
        print(name, writes); return
    os.environ.setdefault("PYEPICS_ENCODING", "utf-8")
    import epics
    for field, value in writes:
        pv = epics.PV(f"15IDC:A3{field}")
        pv.wait_for_connection(3); pv.get_ctrlvars()
        target = pv.enum_strs.index(value) if pv.enum_strs else int(value)
        pv.put(target, wait=True, timeout=5); time.sleep(0.3)
        rb = pv.get(use_monitor=False)
        if rb != target:
            raise SystemExit(f"readback {pv.pvname} = {rb}, wanted {value}")
    print(time.strftime("%H:%M:%S"), name, "set:",
          [(f, epics.caget(f"15IDC:A3{f}", as_string=True)) for f, _ in writes])


if __name__ == "__main__":
    main()
