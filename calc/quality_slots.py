"""Warnings and stated uncertainty for the MonP flux, as utilioc slots: definitions, mirrors, test.

The governing rule (user, 2026-11-12): "an imperfect number with an EPICS warning and/or stated
uncertainty is better than no number". Nothing here blocks, zeroes or freezes the flux. It only
adds alarm severity and bounds.

Slots (all in 15IDC:util:, with no links outside utilioc):
  STATUS   userCalcOut1  the lane's status code, carried as alarm severity. VAL = the flags slot's code
           (FLAG_BITS below: the sum of the set bits, 0-63). code 0 NO_ALARM; > 0.5 MINOR; > 15.5 MAJOR
           (bit 16: E outside 4.9-30.5 keV, bit 32: scaler not counting). calc/lanes.py sets the links.
  DARKFEED userCalcOut2  the background estimate (userTran2.L), with STATUS's severity attached
           through an MS link. userTran1.H reads it through MS, so the flux record itself
           (userTran1, including .P) carries the warning.
  BOUNDS   userTran3     wall-loss-corrected best estimate and stated low/high flux:
           C    = Lw, the fraction of the SIGNAL lost to the plates: the Monte Carlo loss per photoabsorption
                  (analysis/wall_loss_mc.py, validated against Grün 1957) times the photoelectric share f_pe of
                  mu_en (Compton electrons are too slow to reach a plate; finding M1). Fitted PER LANE as
                  Lw = 1 - exp(-((E-E0)/s)^p) above E0, else 0, at E = E_eff (WALL_FITS, clcc(lane);
                  analysis/wall_loss_fit.py), for each chamber as mounted.
           L    = BEST ESTIMATE = P / (1 - Lw)         (P = userTran1.P, the standard formula)
           low  = P x LOW_FACTOR / (1 - max(0.9 Lw - 0.07, 0))
                  LOW_FACTOR = 1 - sigma_s (0.964): the symmetric terms in quadrature, including the guarded
                  collection length (SYMMETRIC_TERMS). The Lw lower edge allows for range -10 %,
                  elastic sigma +20 % (singly and combined) and plate backscatter.
           high = P x HIGH_FACTOR / (1 - Lw - min(0.09, 2 Lw + 0.05 [E_eff>13]))
                  HIGH_FACTOR = 1 + sigma_s (1.036). The Lw upper edge
                  covers range +10 %, elastic sigma ±20 %, a 1 mm beam offset, density ±3 %, and range +10 %
                  combined with sigma -20 % (BAND; analysis/wall_loss_fit.py).
           F/G  = +% / -% of high/low relative to the best estimate L
"""
import math
import sys

# ---- named constants: the single source for the slot expressions below and their Python mirrors ----
RHO0 = 1.1221e-3            # g/cm3, reference density of the wall-loss Monte Carlo (CLCB)
RANGE_EXP = 0.568           # 1/1.76: CSDA range ~ T^1.76 / rho (CLCB)
# Signal wall loss per lane, Lw = 1 - exp(-((E-E0)/s)^p) above E0 (CLCC): f_pe x the MC of that chamber as mounted
# (analysis/wall_loss_families.py -> analysis/wall_loss_fit.py, which gates these against the rounded fits).
# MonP: plates vertical, E toward the plates, beam centred (ASSUMED). MonC: plates horizontal, E along the plates.
# Both: the measured 10.85 mm gap. Before 2026-11-13 both lanes used one fit for a 10 mm vertical-plate chamber.
WALL_FITS = {"MonP": (17.9, 19.7, 1.17), "MonC": (18.1, 27.0, 1.41)}
WALL_FIT = WALL_FITS["MonP"]    # default lane for the module-level BOUNDS expressions
# Wall-loss band around the fit (CLCD, CLCE): lo = max(a*C - b, 0), hi = C + min(cap, k*C + floor*[E_eff > e_widen]).
# Covers every single MC variant and the two combined corners (reach +10 % with elastic sigma -20 %, reach -10 % with
# sigma +20 %) within 2 MC standard errors (analysis/wall_loss_fit.py; finding M4, 2026-11-13).
# Before 2026-11-13: b 0.06, cap 0.065, floor 0.04 (floor 0.05 for the measured 10.85 mm gap: MonP corner at 18 keV).
BAND = {"a": 0.9, "b": 0.07, "cap": 0.09, "k": 2, "floor": 0.05, "e_widen": 13}
# Symmetric terms on the flux, in quadrature (physics_note §3.7; finding M5, 2026-11-13)
SYMMETRIC_TERMS = {
    "mu_en/rho tables": 0.03,           # spread of NIST vs Chantler/Elam
    "W": 0.006,                         # full spread of five sources, carried as 1 sigma
    "electronics": 0.007,               # SR570 gain x V2F scale incl. loading, type B (ELECTRONICS_CONCLUSIONS.md; user 2026-11-13)
    "density (live P, T)": 0.002,
    "cross-section fit": 0.009,         # calc fit vs log-log NIST, worst at 25 keV (monp_transform self-test)
    # guarded chamber as measured (2026-11-13): l_eff is in the formula (monp_transform.L_CM); what remains is the spread
    # of analysis/collection_length_cmc.py over the dimension tolerances, in quadrature, plus 0.5 % for the 2-D model
    # (checked against the model CSV by the test below, COLLECTION_GROUPS)
    "collection length (guarded)": 0.014,
    # mono energy readback (user 2026-11-17, "Add the term"): an ASSUMED 0.1 % energy error (dE/E; no edge scan yet)
    # times the largest d ln(flux)/d ln E over 5-30 keV, 3.7 (MonP best estimate at 29.5 keV; 2.2 below 15 keV),
    # rounded up. CHAMBER_FACTS F9.7; UNCERTAINTY.md.
    "energy readback": 0.004,
}
COLLECTION_MODEL_2D = 0.005
# case groups of analysis/out/collection_length_cmc.csv: one tolerance each (largest |delta - nominal| in the group)
COLLECTION_GROUPS = {"guard gap +-0.5 mm": ("guard_gap_0.5", "guard_gap_1.5"),
                     "guard recess +-0.25 mm": ("guard_recess_0.25", "guard_recess_0.75"),
                     "collector length +-0.5 mm": ("coll_len_-0.5", "coll_len_+0.5"),
                     "beam height +-1 mm": ("beam_z_+1", "beam_z_-1"),
                     "HV plate length -2 mm": ("hv_len_-2",),
                     "guard to end wall": ("guard_touches_wall",),
                     "plate gap +-0.2 mm at the beam track": ("gap_+0.2", "gap_-0.2")}
OTHER_TERMS = math.sqrt(sum(v * v for v in SYMMETRIC_TERMS.values()))     # 0.0358 (0.0356 before the energy term, 2026-11-17)
HIGH_FACTOR = math.ceil((1 + OTHER_TERMS) * 1000) / 1000                  # 1.036 (CLCE)
# The collection length is now a symmetric term (the chamber is guarded and measured; finding M2 closed 2026-11-13),
# so the low side mirrors the high side. Before: LOW_FACTOR 0.86 (one-sided allowance for an unguarded chamber).
LOW_FACTOR = math.floor((1 - OTHER_TERMS) * 1000) / 1000                  # CLCD
# Lowest gas density seen, relative to rho0: site mean 0.9972 x LOT 2025 minimum pressure (-3.43 %) x hutch maximum
# temperature (29.0 vs 24.9 C) = 0.950 (analysis/out/pressure_climatology.txt, hutch_temperature.txt)
RHO_MIN_OVER_RHO0 = 0.95
# Bit 1 is designed for a density below the lowest seen, so one more year of weather has margin (finding N2; user
# 2026-11-13 "Yes, both"): 0.934 rho0 gives 13 x 0.934^0.568 = 12.505 -> 12.5 keV (was 12.6, no margin below 0.95)
RHO_FLAG1_OVER_RHO0 = 0.934
# Status bit 1 threshold on the raw energy: below it E_eff <= e_widen at every density down to RHO_FLAG1 (M7, N2)
FLAG1_E_KEV = math.floor(BAND["e_widen"] * RHO_FLAG1_OVER_RHO0 ** RANGE_EXP * 10) / 10   # 12.5


def _n(x):
    """Number as written in a calc expression: shortest form, no leading zero."""
    t = f"{x:g}"
    return t[1:] if t.startswith("0.") else t


STATUS = {
    "rec": "15IDC:util:userCalcOut1",
    "DESC": "MonP flux status (xray_fluxor)",
    "fields": {
        "CALC": "A",                                   # A = the lane's flags code (flags slot .L; link set in calc/lanes.py)
        "SCAN": "1 second", "PREC": "0", "EGU": "code",
        "HIGH": 0.5, "HSV": "MINOR", "HIHI": 15.5, "HHSV": "MAJOR", "HYST": 0.0,
        "OUT": "", "OOPT": "Every Time", "DOPT": "Use CALC",
    },
}
DARKFEED = {
    "rec": "15IDC:util:userCalcOut2",
    "DESC": "MonP dark feed Hz (xray_fluxor)",
    "fields": {
        "INPA": "15IDC:util:userTran2.L NPP NMS",     # background estimate Hz
        "INPB": "15IDC:util:userCalcOut1.VAL NPP MS",  # status: its severity is carried along
        "CALC": "A",
        "SCAN": "1 second", "PREC": "2", "EGU": "Hz",
        "OUT": "", "OOPT": "Every Time", "DOPT": "Use CALC",
    },
}
FLUX_DARK_LINK = "15IDC:util:userCalcOut2.VAL NPP MS"     # -> userTran1.INPH
BOUNDS = {
    "rec": "15IDC:util:userTran3",
    "DESC": "MonP flux bounds ph/s (xray_fluxor)",
    # MonP links, for reference; calc/lanes.py builds each lane's links
    "links": {"INPA": "15IDC:util:userTran1.P NPP MS", "INPB": "15IDC:util:userTran1.E NPP NMS",
              "INPI": "15IDC:util:userTran1.K NPP NMS"},
    "expr": {
        # B arrives by link as the mono energy and is then replaced by the density-scaled
        # energy E_eff = E*(rho0/rho)^(1/1.76) (CSDA range ∝ T^1.76/rho). That makes the lane's wall-loss
        # fit, made at rho0 = 1.1221e-3 g/cm3 (the MC reference), follow the live gas density I.
        "CLCB": "B*(1.1221E-3/I)^.568",
        "CLCC": None,       # built from WALL_FIT below: B>E0?1-1/EXP(((B-E0)/s)^p):0
        "CLCD": f"A*{_n(LOW_FACTOR)}/(1-MAX({_n(BAND['a'])}*C-{_n(BAND['b'])},0))",
        "CLCE": f"A*{_n(HIGH_FACTOR)}/(1-C-MIN({_n(BAND['cap'])},{_n(BAND['k'])}*C+"
                f"{_n(BAND['floor'])}*(B>{_n(BAND['e_widen'])})))",
        "CLCF": "A>0?100*(E*(1-C)/A-1):0",
        "CLCG": "A>0?100*(1-D*(1-C)/A):0",
        "CLCL": "A/(1-C)",
        # H: seconds since the pressure updater (tools/asos_pressure.py) last wrote userTran1.G;
        # the updater writes 0, and every 1 s scan adds 1 (state held in the value itself)
        "CLCH": "H+1",
    },
    "comments": {"A": "MonP exit flux ph/s (userTran1.P)", "B": "E_eff keV (E x (rho0/rho)^.568)",
                 "C": "signal wall-loss fraction (MC fit)", "D": "flux LOW bound ph/s",
                 "E": "flux HIGH bound ph/s", "F": "uncertainty up %", "G": "uncertainty down %",
                 "H": "s since pressure update",
                 "L": "BEST flux ph/s (wall-loss corr.)"},
    "SCAN": "1 second", "PREC": "4", "EGU": "ph/s",
}


# Status flags: one bit per condition. The code is their sum. 16 and 32 are MAJOR, the rest MINOR.
FLAG_BITS = [
    (1, "F", f"A>{_n(FLAG1_E_KEV)}", f"1: E>{_n(FLAG1_E_KEV)} keV, wall-loss band in use"),
    (2, "G", "C>0", "2: background stale (other gain/none)"),
    (4, "H", "D>7200", "4: pressure not updated for 2 h"),
    (8, "I", "E>P", "8: no beam (bounds not meaningful)"),
    (16, "J", "A<4.9||A>30.5", "16: E outside 4.9-30.5 keV (MAJOR)"),
    (32, "K", "B<=0", "32: scaler not counting (MAJOR)"),
]
FLAGS_CODE = "F+2*G+4*H+8*I+16*J+32*K"


def flags(E, count_time, bkg_stale, p_age, no_beam_s, settle_s):
    """Python mirror of the flags slot. Returns the six bits and the code (letter L)."""
    bits = {"F": E > FLAG1_E_KEV, "G": bkg_stale > 0, "H": p_age > 7200, "I": no_beam_s > settle_s,
            "J": E < 4.9 or E > 30.5, "K": count_time <= 0}
    code = sum(b for b, k, _, _ in FLAG_BITS if bits[k])
    return {**{k: float(v) for k, v in bits.items()}, "L": float(code)}


def status(code):
    return code


def severity(code):
    return "MAJOR" if code > 15.5 else ("MINOR" if code > 0.5 else "NO_ALARM")




def e_eff(E, rho=RHO0):
    """Density-scaled energy at which the wall-loss fit is evaluated (CLCB)."""
    return E * (RHO0 / rho) ** RANGE_EXP


def collection_term(path=None):
    """Quadrature of the largest |delta - nominal| in each COLLECTION_GROUPS group of the model CSV, plus the 2-D
    allowance (analysis/out/collection_length_cmc.csv; delta in %)."""
    import csv
    from pathlib import Path
    path = path or Path(__file__).resolve().parents[1] / "analysis" / "out" / "collection_length_cmc.csv"
    with open(path, newline="", encoding="utf-8") as f:
        rows = {r["case"]: float(r["delta_pct"]) / 100 for r in csv.DictReader(x for x in f if not x.startswith("#"))}
    nom = rows["nominal"]
    parts = [max(abs(rows[c] - nom) for c in cases) for cases in COLLECTION_GROUPS.values()]
    return math.sqrt(sum(x * x for x in parts) + COLLECTION_MODEL_2D ** 2)


def clcc(lane="MonP"):
    """The lane's CLCC expression, built from its WALL_FITS entry."""
    return "B>{0:g}?1-1/EXP(((B-{0:g})/{1:g})^{2:g}):0".format(*WALL_FITS[lane])


BOUNDS["expr"]["CLCC"] = clcc("MonP")     # calc/lanes.py sets each lane's own


def wall_loss_band(E_eff, lane="MonP"):
    """(low, central, high) wall-loss fraction used by the lane's bounds slot (CLCC, CLCD, CLCE)."""
    e0, s, p = WALL_FITS[lane]
    b = BAND
    C = 1 - math.exp(-((E_eff - e0) / s) ** p) if E_eff > e0 else 0.0
    lo = max(b["a"] * C - b["b"], 0)
    hi = C + min(b["cap"], b["k"] * C + b["floor"] * (E_eff > b["e_widen"]))
    return lo, C, hi


def bounds(P, E, rho=RHO0, lane="MonP"):
    """Python mirror of the lane's BOUNDS expressions (same order, same constants). Returns B = E_eff too."""
    E = e_eff(E, rho)
    lo, C, hi = wall_loss_band(E, lane)
    D = P * LOW_FACTOR / (1 - lo)
    Eh = P * HIGH_FACTOR / (1 - hi)
    F = 100 * (Eh * (1 - C) / P - 1) if P > 0 else 0
    G = 100 * (1 - D * (1 - C) / P) if P > 0 else 0
    return dict(B=E, C=C, D=D, E=Eh, F=F, G=G, L=P / (1 - C))


def test():
    ok = True
    cases = [((10, 1, 0, 100, 0, 10), 0, "NO_ALARM"), ((30, 1, 0, 100, 0, 10), 1, "MINOR"),
             ((30, 1, 1, 100, 0, 10), 3, "MINOR"), ((30, 1, 1, 8000, 0, 10), 7, "MINOR"),
             ((30, 1, 0, 100, 60, 10), 9, "MINOR"), ((31, 1, 0, 100, 0, 10), 17, "MAJOR"),
             ((10, 0, 0, 100, 0, 10), 32, "MAJOR"), ((4, 0, 1, 9000, 60, 10), 62, "MAJOR")]
    for args, want, sev in cases:
        got = flags(*args)["L"]
        print(f"  flags{args} -> code {got:.0f} {severity(got)} (want {want} {sev})")
        ok &= got == want and severity(got) == sev
    for e in (10, 15, 18, 20, 25, 30):
        b = bounds(3.66e12, e)
        print(f"  {e:2d} keV: wall loss {b['C']:.3f}  best {b['L']:.3e}  low {b['D']:.3e}  high {b['E']:.3e}  (+{b['F']:.1f} % / -{b['G']:.1f} %)")
    ok &= abs(bounds(1, 10)["F"] - 100 * (HIGH_FACTOR - 1)) < 0.01 and abs(bounds(1, 10)["G"] - 100 * (1 - LOW_FACTOR)) < 0.01
    # M5: HIGH_FACTOR - 1 equals the quadrature sum of the listed terms to 0.1 %
    print(f"  symmetric terms {100 * OTHER_TERMS:.2f} % -> HIGH_FACTOR {HIGH_FACTOR}, LOW_FACTOR {LOW_FACTOR}; "
          f"status bit 1 at E > {FLAG1_E_KEV} keV")
    ok &= abs((HIGH_FACTOR - 1) - OTHER_TERMS) < 0.001
    ok &= abs((1 - LOW_FACTOR) - OTHER_TERMS) < 0.001
    # the collection-length term must equal the model's spread over the dimension tolerances (+ the 2-D allowance)
    term = collection_term()
    print(f"  collection length: model spread + 2-D allowance = {100 * term:.2f} % (SYMMETRIC_TERMS carries "
          f"{100 * SYMMETRIC_TERMS['collection length (guarded)']:.1f} %)")
    ok &= 0 <= SYMMETRIC_TERMS["collection length (guarded)"] - term < 0.001
    # each lane's CLCC is its own fit
    ok &= clcc("MonP") != clcc("MonC") and all(len(clcc(x)) <= 39 for x in WALL_FITS)
    # M7, N2: wherever the high bound is widened by the wall-loss band, status bit 1 is set (densities down to
    # RHO_FLAG1, below the lowest seen at the site)
    gap = [(round(e, 3), r) for r in (RHO_FLAG1_OVER_RHO0, RHO_MIN_OVER_RHO0, 0.97, 1.0, 1.03)
           for e in [12 + 0.005 * i for i in range(401)]
           if bounds(1, e, RHO0 * r)["F"] > 100 * (HIGH_FACTOR - 1) + 1e-9 and not flags(e, 1, 0, 0, 0, 10)["F"]]
    print("  band widened while status bit 1 is clear:", gap[:5] or "never")
    ok &= not gap
    b30 = bounds(1, 30)
    print(f"  30 keV best/formula: MonP x{b30['L']:.3f}, MonC x{bounds(1, 30, lane='MonC')['L']:.3f}")
    ok &= b30["D"] < b30["L"] < b30["E"]
    ok &= clcc("MonP") == "B>17.9?1-1/EXP(((B-17.9)/19.7)^1.17):0"
    ok &= clcc("MonC") == "B>18.1?1-1/EXP(((B-18.1)/27)^1.41):0"
    ok &= BOUNDS["expr"]["CLCD"] == "A*.964/(1-MAX(.9*C-.07,0))"
    ok &= BOUNDS["expr"]["CLCE"] == "A*1.036/(1-C-MIN(.09,2*C+.05*(B>13)))"
    ok &= FLAG_BITS[0][2] == "A>12.5"
    strings = list(STATUS["fields"].values()) + list(DARKFEED["fields"].values()) + \
        [x[2] for x in FLAG_BITS] + [x[3] for x in FLAG_BITS] + [FLAGS_CODE] + \
        list(BOUNDS["links"].values()) + list(BOUNDS["expr"].values()) + list(BOUNDS["comments"].values()) + \
        [FLUX_DARK_LINK]
    long = [s for s in map(str, strings) if len(s) > 39]
    descs = [STATUS["DESC"], DARKFEED["DESC"], BOUNDS["DESC"]]
    long += [d for d in descs if len(d) > 39]
    print("too long:", long or "none")
    ok &= not long
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(test())
