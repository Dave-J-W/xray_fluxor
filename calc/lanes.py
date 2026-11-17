"""Monitor "lanes": one identical set of utilioc slots per ion chamber (MonP, MonC).

Each lane is six slots:
  flux   (transform)  photons/s at the chamber exit (the formula); the physics is calc/monp_transform.py
  bkg    (transform)  running no-beam background estimate; calc/background_transform.py
  bounds (transform)  RESULT (wall-loss-corrected best estimate) and stated low/high flux; calc/quality_slots.py
  flags  (transform)  one status bit per condition, and their sum, the status code; calc/quality_slots.py
  status (calcout)    the status code with alarm severity (> 0.5 MINOR, > 15.5 MAJOR)
  dark   (calcout)    background fed to the flux, with the status severity attached (MS)

The expressions are identical in every lane: they are taken from the modules above. Only the
links, DESC, comments and slot numbers differ.

Shared inputs: mono energy, hutch temperature and the live pressure are common. The pressure
updater (tools/asos_pressure.py) writes the MonP lane's flux.G and resets its bounds.H age
counter. Other lanes read both from the MonP lane by internal links, so one updater serves all.

MonP and MonC are the same CMC-custom design (guarded; user, 2026-11-13; analysis/cmc_chamber_geometry.py), so the
conversion and the symmetric terms are shared. MonC is mounted with its plates horizontal, so each lane has its
own wall-loss fit (quality_slots.WALL_FITS, clcc(lane)).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from monp_transform import SLOT as FLUX, L_CM  # noqa: E402
from background_transform import SLOT as BKG  # noqa: E402
from quality_slots import STATUS, DARKFEED, BOUNDS, FLAG_BITS, FLAGS_CODE, clcc  # noqa: E402

P = "15IDC:util:"
LETTERS = "ABCDEFGHIJKLMNOP"

LANES = {
    "MonP": {"scaler": "S3", "sr570": "15IDC:A2",
             "slots": {"flux": 1, "bkg": 2, "bounds": 3, "status": 1, "dark": 2, "flags": 7},
             "pressure_owner": True, "plates": "vertical"},
    "MonC": {"scaler": "S4", "sr570": "15IDC:A3",
             "slots": {"flux": 4, "bkg": 5, "bounds": 6, "status": 4, "dark": 5, "flags": 8},
             "pressure_owner": False, "plates": "horizontal"},
}
# Plate orientation of each chamber as mounted (user, 2026-11-13; analysis/cmc_chamber_geometry.py monp_plates /
# monc_plates). Published as a constant in the bounds slot's letter M, for the screens: 0 vertical, 1 horizontal.
# The beam E-vector is horizontal, so vertical plates face it (MonP) and horizontal plates lie along it (MonC).
PLATE_CODES = {"vertical": 0, "horizontal": 1}
PLATES_LETTER = "M"
PRESSURE_LANE = "MonP"
# role -> (title, output field(s)) for documentation and figures
ROLE_OUTPUTS = {
    "flux": ("FLUX formula (photons/s at the exit, not wall-loss corrected)", ["P"]),
    "bkg": ("BACKGROUND estimate (Hz)", ["L"]),
    "bounds": ("RESULT and bounds (photons/s)", ["L", "D", "E"]),
    "flags": ("STATUS FLAGS (bits) and code", ["L"]),
    "status": ("STATUS code (alarm severity)", ["VAL"]),
    "dark": ("DARK FEED (background + severity)", ["VAL"]),
}


def rec(lane, role):
    n = LANES[lane]["slots"][role]
    return f"{P}{'userCalcOut' if role in ('status', 'dark') else 'userTran'}{n}"


def _short(r):
    return r[len(P):]


def build(lane):
    """Return [(record, DESC, fields, hand_values, kind)] in install order (dependencies first)."""
    L = LANES[lane]
    flux, bkg, bnd, st, dk, fl = (rec(lane, k) for k in ("flux", "bkg", "bounds", "status", "dark", "flags"))
    pflux, pbnd = rec(PRESSURE_LANE, "flux"), rec(PRESSURE_LANE, "bounds")
    sc, sr = L["scaler"], L["sr570"]
    out = []

    # flags: one 0/1 value per condition, and their sum as the status code (L)
    links = {"INPA": f"{flux}.E NPP NMS", "INPB": f"{flux}.B NPP NMS", "INPC": f"{bkg}.N NPP NMS",
             "INPD": f"{pbnd}.H NPP NMS", "INPE": f"{bkg}.H NPP NMS", "INPP": f"{bkg}.G NPP NMS"}
    expr = {f"CLC{k}": e for _, k, e, _ in FLAG_BITS}
    expr["CLCL"] = FLAGS_CODE
    cm = {"A": f"energy keV ({_short(flux)}.E)", "B": f"count time s ({_short(flux)}.B)",
          "C": f"background stale ({_short(bkg)}.N)", "D": f"s since P update ({_short(pbnd)}.H)",
          "E": f"s below no-beam level ({_short(bkg)}.H)", "P": f"no-beam settle s ({_short(bkg)}.G)",
          **{k: c for _, k, _, c in FLAG_BITS}, "L": "STATUS CODE = sum of the bits"}
    out.append((fl, f"{lane} status flags (xray_fluxor)",
                _transform(f"{lane} status flags (xray_fluxor)", links, expr, cm, "", "0"), {}, "transform"))

    # status: the flags code, with alarm severity (MINOR for any bit, MAJOR for 16 or 32)
    f = {"DESC": f"{lane} flux status code (xray_fluxor)"}
    links = {"INPA": f"{fl}.L NPP NMS"}
    for x in "ABCDEFGHIJKL":
        f[f"INP{x}"] = links.get(f"INP{x}", "")
    f.update({k: v for k, v in STATUS["fields"].items() if not k.startswith("INP")})
    out.append((st, f["DESC"], f, {}, "calcout"))

    # dark feed: this lane's background, with the status severity attached
    f = {"DESC": f"{lane} dark feed Hz (xray_fluxor)"}
    links = {"INPA": f"{bkg}.L NPP NMS", "INPB": f"{st}.VAL NPP MS"}
    for x in "ABCDEFGHIJKL":
        f[f"INP{x}"] = links.get(f"INP{x}", "")
    f.update({k: v for k, v in DARKFEED["fields"].items() if not k.startswith("INP")})
    out.append((dk, f["DESC"], f, {}, "calcout"))

    # flux
    links = {"INPA": f"15IDC:scaler1.{sc} NPP NMS", "INPB": "15IDC:scaler1.T NPP NMS",
             "INPC": f"{sr}sens_num NPP NMS", "INPD": f"{sr}sens_unit NPP NMS",
             "INPE": "ID15A1:DCMM:XTAL:E.RBV NPP NMS",
             "INPF": "15ID:Sensor2:Temperature NPP NMS",
             "INPH": f"{dk}.VAL NPP MS"}
    if not L["pressure_owner"]:
        links["INPG"] = f"{pflux}.G NPP NMS"
    cm = {"A": f"{lane} counts (scaler1.{sc})", "B": "count time s (scaler1.T)",
          "C": f"{lane} SR570 sens_num index", "D": f"{lane} SR570 sens_unit index",
          "E": "mono energy keV (DCMM RBV)", "F": "hutch T degC (Sensor2)",
          "G": "N2 kPa (live LOT, asos_pressure.py)" if L["pressure_owner"] else f"N2 kPa ({_short(pflux)}.G)",
          "H": f"dark Hz ({_short(bkg)} via {_short(dk)})",
          "I": "SR570 sensitivity A/V", "J": f"net {lane} rate Hz",
          "K": "N2 density g/cm3", "L": "ln(E/keV)",
          "M": "mu_en/rho N cm2/g (fit)", "N": "mu/rho N cm2/g (fit)",
          "O": f"fraction absorbed in {L_CM:g} cm (l_eff)", "P": f"formula, NOT result ({_short(bnd)}.L)"}
    out.append((flux, f"{lane} flux formula ph/s (xray_fluxor)",
                _transform(f"{lane} flux formula ph/s (xray_fluxor)", links, FLUX["expr"], cm, "ph/s", "4"),
                {"G": 98.99} if L["pressure_owner"] else {}, "transform"))

    # background estimate
    links = {f"INP{x}": f"{flux}.{x} NPP NMS" for x in "ABCD"}
    cm = {"A": f"{lane} counts ({_short(flux)}.A)", "B": f"count time s ({_short(flux)}.B)",
          "C": "SR570 sens_num idx", "D": "SR570 sens_unit idx",
          "E": f"raw {lane} rate Hz", "F": "no-beam threshold Hz", "G": "settle time s",
          "H": "s below threshold", "I": "averaging samples", "J": "gain code now",
          "K": "samples in estimate", "L": "BACKGROUND estimate Hz", "M": "gain code of estimate",
          "N": "1=stale (other gain/none)", "O": "s since estimate updated", "P": "background current A"}
    out.append((bkg, f"{lane} background Hz (xray_fluxor)",
                _transform(f"{lane} background Hz (xray_fluxor)", links, BKG["expr"], cm, "Hz", "3"),
                dict(BKG["values"]), "transform"))

    # bounds and RESULT
    links = {"INPA": f"{flux}.P NPP MS", "INPB": f"{flux}.E NPP NMS", "INPI": f"{flux}.K NPP NMS"}
    expr = dict(BOUNDS["expr"])
    expr["CLCC"] = clcc(lane)                    # this chamber's own wall-loss fit (quality_slots.WALL_FITS)
    if not L["pressure_owner"]:
        expr.pop("CLCH")                         # age counter lives in the pressure lane
        links["INPH"] = f"{pbnd}.H NPP NMS"
    cm = {"A": f"{lane} exit flux ph/s ({_short(flux)}.P)", "B": f"E_eff keV ({_short(flux)}.E density-scaled)",
          "I": f"N2 density g/cm3 ({_short(flux)}.K)",
          "C": "signal wall-loss fraction (MC fit)", "D": "flux LOW bound ph/s",
          "E": "flux HIGH bound ph/s", "F": "uncertainty up %", "G": "uncertainty down %",
          "H": "s since pressure update" if L["pressure_owner"] else f"s since P update ({_short(pbnd)}.H)",
          "L": "RESULT: best flux ph/s", PLATES_LETTER: "plates: 0 vertical, 1 horizontal"}
    f = _transform(f"{lane} flux RESULT ph/s (xray_fluxor)", links, expr, cm, "ph/s", "4")
    f[PLATES_LETTER] = PLATE_CODES[L["plates"]]      # a constant of the lane, re-asserted at every install
    out.append((bnd, f"{lane} flux RESULT ph/s (xray_fluxor)", f, {}, "transform"))
    return out


def _transform(desc, links, expr, comments, egu, prec):
    f = {"DESC": desc, "SCAN": "1 second", "PREC": prec, "COPT": "Always", "EGU": egu}
    for x in LETTERS:
        f[f"INP{x}"] = links.get(f"INP{x}", "")
    for x in LETTERS:
        f[f"CLC{x}"] = expr.get(f"CLC{x}", "")
    for x in LETTERS:
        f[f"CMT{x}"] = comments.get(x, "")
    return f


def check_lengths():
    bad = []
    for lane in LANES:
        for r, desc, fields, _, _ in build(lane):
            if len(desc) > 39:
                bad.append((r, "DESC", desc))
            for k, v in fields.items():
                if len(str(v)) > 39:
                    bad.append((r, k, v))
    return bad


def check_plates():
    """The lane orientations must match the geometry module (the user's record of the mountings)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    import cmc_chamber_geometry as cg
    want = {"MonP": cg.v("monp_plates"), "MonC": cg.v("monc_plates")}
    return [(lane, LANES[lane]["plates"], want[lane]) for lane in LANES if LANES[lane]["plates"] != want[lane]]


if __name__ == "__main__":
    bad = check_lengths() + check_plates()
    for lane in LANES:
        print(lane, [(_short(r), d) for r, d, *_ in build(lane)])
    print("too long:", bad or "none")
    print("PASS" if not bad else "FAIL")
    sys.exit(1 if bad else 0)
