"""MonP photons/s for utilioc: the transform-slot design, its offline reference, and a self-test.

This file is the single source of truth for the slot. It holds:
  - SLOT: every field written to 15IDC:util:userTranN (links, expressions, DESC, SCAN)
  - evaluate(): a Python evaluation of the *same expression strings*, using the
    calc-language semantics they rely on (% integer modulo, ^ power, FLOOR, LN, EXP, ?:)
  - full_physics(): the physics-note conversion, computed independently (NIST tables, exact W, e)
  - main(): checks that every expression is <= 39 characters (the autosave/CA string limit), then
    compares evaluate() with full_physics() over 5-30 keV, several sensitivities, T and P

Letters (transform values A-P; evaluated in alphabetical order):
  inputs   A scaler counts (S3)   B elapsed time s (T)   C sens_num index   D sens_unit index
           E energy keV          F hutch T degC         G pressure kPa     H dark rate Hz
  computed I sensitivity A/V     J net rate Hz          K N2 density g/cm3 L ln(E)
           M mu_en/rho cm2/g     N mu/rho cm2/g         O absorbed fraction in l = L_CM
           P photons/s at the exit plane (end of the collection region, before the Kapton exit window)
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data" / "queries"))

# ---- constants and their provenance (physics_note.md) ------------------------------------------
W_EV = 34.8                 # §2.1
E_CHARGE = 1.602176634e-19  # exact
# Effective collection length (cm) of the guarded CMC-custom chamber: analysis/collection_length_cmc.py, nominal
# case at h = 0.05 mm (61.925 mm), rounded. Before 2026-11-13 the calc used the 6.0 cm plate length. The test below
# checks this constant against the model's CSV. The absorbed fraction and the exit transmission both use it.
L_CM = 6.19
L_EFF_CSV = ROOT / "analysis" / "out" / "collection_length_cmc.csv"
M_OVER_R = 28.0134 / 8.314462618 / 1000.0   # g/cm3 per (kPa/K): rho = P[kPa]*M_OVER_R/T[K]
K_FLUX = W_EV / (E_CHARGE * 1e3) / 1e5     # W/(e*1e3 eV/keV) / (1e5 Hz/V) -> 2.17205e12

# ln(mu/rho) = c0 + L*(c1 + L*(c2 + L*c3)), L = ln(E/keV). Coefficients from
# calc/fit_coefficients.py (calc/coefficients.json): a minimax cubic over 5-30 keV of a
# NIST-anchored target (equal to NIST at its grid points, Elam's shape in between), rounded to
# 4 significant figures to fit 39 characters. Max error 0.6 %.
MUEN = "EXP(7.469-L*(1.833+L*(.5342-L*.06941)))"
MU = "EXP(6.046+L*(.4546-L*(1.762-L*.2949)))"

SLOT = {
    "DESC": "MonP ph/s at exit (xray_fluxor)",
    "SCAN": "1 second",
    "PREC": "4",
    "links": {   # transform input links (read-only from outside PVs: NPP NMS, no processing)
        "INPA": "15IDC:scaler1.S3 NPP NMS",
        "INPB": "15IDC:scaler1.T NPP NMS",
        "INPC": "15IDC:A2sens_num NPP NMS",
        "INPD": "15IDC:A2sens_unit NPP NMS",
        "INPE": "ID15A1:DCMM:XTAL:E.RBV NPP NMS",   # mono energy keV (calc/lanes.py sets the same link)
        "INPF": "15ID:Sensor2:Temperature NPP NMS",
        "INPG": None,      # pressure kPa: written by tools/asos_pressure.py (MonP lane; MonC links to it)
        "INPH": "15IDC:util:userCalcOut2.VAL NPP MS",  # background Hz (userTran2 estimate) + status severity
    },
    "values": {"G": 98.99},   # fresh-install value of the pressure input (site mean at 228 m) until the updater writes
    "expr": {
        "CLCI": "(1+(C%3)^2)*10^(FLOOR(C/3)+3*D-12)",
        "CLCJ": "B>0?MAX(A/B-H,0):0",      # net rate, clamped at 0: no negative flux from dark noise
        "CLCK": "G*3.369272E-3/(F+273.15)",
        "CLCL": "LN(E)",
        "CLCM": MUEN,
        "CLCN": MU,
        "CLCO": f"1-EXP(-{L_CM:g}*M*K)",
        "CLCP": f"J*I*2.17205E12/E/O*EXP(-{L_CM:g}*N*K)",
    },
}


def evaluate(A, B, C, D, E, F, G, H):
    """Python mirror of SLOT['expr'], in transform order. Keep it literally in step with the strings."""
    v = dict(A=A, B=B, C=C, D=D, E=E, F=F, G=G, H=H)
    v["I"] = (1 + (int(C) % 3) ** 2) * 10 ** (math.floor(C / 3) + 3 * D - 12)
    v["J"] = max(A / B - H, 0.0) if B > 0 else 0.0
    v["K"] = G * 3.369272e-3 / (F + 273.15)
    v["L"] = math.log(E)
    L = v["L"]
    v["M"] = math.exp(7.469 - L * (1.833 + L * (.5342 - L * .06941)))
    v["N"] = math.exp(6.046 + L * (.4546 - L * (1.762 - L * .2949)))
    v["O"] = 1 - math.exp(-L_CM * v["M"] * v["K"])
    v["P"] = v["J"] * v["I"] * 2.17205e12 / E / v["O"] * math.exp(-L_CM * v["N"] * v["K"])
    return v


def full_physics(rate_hz, sens_a_per_v, e_kev, t_c, p_kpa):
    """Independent: NIST HS mu, mu_en (log-log), exact constants, physics_note.md §1."""
    from query_cross_sections import parse_nist, loglog_interp
    nist = parse_nist(ROOT / "data" / "queries" / "nist_hubbell_seltzer" / "z07_nitrogen.html")
    rho = p_kpa * 1e3 * 28.0134 / (8.314462618 * (t_c + 273.15)) / 1e6
    muen = loglog_interp(e_kev / 1e3, nist, 2) * rho
    mu = loglog_interp(e_kev / 1e3, nist, 1) * rho
    i = rate_hz * sens_a_per_v / 1e5          # V2F 1e5 Hz/V (0-10 V range)
    i_over_hz = i                              # amps
    flux_in = i_over_hz * W_EV / (E_CHARGE * e_kev * 1e3 * (1 - math.exp(-muen * L_CM)))
    return flux_in * math.exp(-mu * L_CM)


def main():
    ok = True
    print("expression lengths (limit 39):")
    for k, s in list(SLOT["expr"].items()) + [(k, s) for k, s in SLOT["links"].items() if s]:
        flag = "OK" if len(s) <= 39 else "TOO LONG"
        ok &= len(s) <= 39
        print(f"  {k}: {len(s):2d} {flag}  {s}")
    print(f"  DESC: {len(SLOT['DESC'])} (limit 40)")
    # The V2F factor 1e5 Hz/V is folded into CLCP's constant: 2.17205e12 = W/(e*1e3)/1e5.
    # (An earlier draft left it out, and this comparison caught the 1e5 error.)
    print("\nreference vs full physics (P is photons/s)")
    worst = 0.0
    worst_5_20 = 0.0
    for e in (5, 6, 8, 10, 12, 15, 20, 25, 30):
        for (c, d) in ((8, 1), (0, 2), (5, 1)):        # 500 nA/V, 1 uA/V, 50 nA/V
            for t, p in ((24.9, 99.26), (20.0, 101.325), (22.0, 97.0)):
                v = evaluate(A=2.0e5, B=1.0, C=c, D=d, E=e, F=t, G=p, H=50.0)
                ref = full_physics(2.0e5 - 50.0, v["I"], e, t, p)
                r = v["P"] / ref - 1
                worst = max(worst, abs(r))
                if e <= 20:
                    worst_5_20 = max(worst_5_20, abs(r))
        v = evaluate(A=2.0e5, B=1.0, C=8, D=1, E=e, F=24.9, G=99.26, H=0.0)
        print(f"  {e:4.0f} keV: sens {v['I']:.3g} A/V  P/rate = {v['P']/2e5:.4g} ph/s per Hz"
              f"  vs full {full_physics(2e5, 5e-7, e, 24.9, 99.26)/2e5:.4g}")
    print(f"\nworst |calc/full - 1|, 3 sensitivities x 3 (T,P): 5-20 keV {100*worst_5_20:.3f} %, "
          f"5-30 keV {100*worst:.3f} %")
    # gate: the calc must reproduce the full conversion within 1 % at 5-20 keV and 2 % to 30 keV,
    # well inside the 3 % mu_en uncertainty (physics_note.md §2.2)
    ok &= worst_5_20 < 0.01 and worst < 0.02
    # L_CM must be the modelled effective collection length (rounding only)
    import csv
    with open(L_EFF_CSV, newline='', encoding='utf-8') as f:
        nom = next(r for r in csv.DictReader(x for x in f if not x.startswith('#')) if r['case'] == 'nominal')
    rel = L_CM * 10 / float(nom['l_eff_mm']) - 1
    print(f"L_CM {L_CM} cm vs modelled l_eff {float(nom['l_eff_mm']):.3f} mm: {100 * rel:+.3f} %")
    ok &= abs(rel) < 0.001
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
