"""Cross-check the MonP counts->photons conversion against every reachable existing tool.

Quantity compared: photons/s in the plate region per net Hz of scaler rate, for MonP
(plate length l = 6 cm), SR570 S = 0.5 uA/V (500 nA/V), N101VTF x1 = 1e5 Hz/V.

  A  the physics note as written (W = 35 eV, e = 1.6e-19, its mu_en table, rho implied 1.165e-3)
  B  this project: NIST Hubbell-Seltzer mu_en/rho, W = 34.8 eV, exact e, rho from P,T
  C1 xraydb.ionchamber_fluxes default (both_carriers=True, with_compton=True)
  C2 xraydb.ionchamber_fluxes(both_carriers=False)
  D  CHESS web calculator algorithm, ported verbatim from its JS (saved in web_calculators/)
     with the 'Mass-energy absorption coefficient' option, W = 34.6 eV, rho = 1.131e-3, no Kapton
  (SSRL photonfluxcalc.pl returned 503 on 2026-11-12; Hephaestus is a Perl/Tk app, not installed.)

Run:  <bluesky venv>\\Scripts\\python.exe -I -X utf8 crosscheck_calculators.py
"""
import csv
import math
import sys
from pathlib import Path

import xraydb

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))   # -I drops the script dir; our own sibling module only
from query_cross_sections import parse_nist, loglog_interp  # noqa: E402
OUT = HERE / "out"

L_CM = 6.0
S_A_PER_V = 0.5e-6
HZ_PER_V = 1e5
E_CHARGE = 1.602176634e-19          # C, exact (SI 2019)
M_N2 = 28.0134                      # g/mol
R = 8.314462618                     # J/(mol K)
# Site means: P from LOT ASOS 2025 (analysis/out/pressure_climatology.txt),
# T from 15ID:Sensor2:Temperature 2024-06..2026-11 (analysis/out/hutch_temperature.txt)
SITE_P_KPA = 98.99      # 2025 LOT mean (99.26 kPa at 205 m) carried to the hutch at 228 m (user, 2026-11-12)
SITE_T_C = 24.9

NIST_N = parse_nist(HERE / "nist_hubbell_seltzer" / "z07_nitrogen.html")


def rho_n2(p_kpa, t_c):
    """Ideal-gas N2 density, g/cm^3 (real-gas compressibility Z ~ 0.9997 at 1 atm, ignored)."""
    return p_kpa * 1e3 * M_N2 / (R * (t_c + 273.15)) / 1e6


def current_per_hz():
    return S_A_PER_V / HZ_PER_V     # A per Hz


def flux_generic(e_kev, muen_lin, w_ev, e_charge=E_CHARGE):
    """photons/s in plate region per Hz: i W / (e E (1-exp(-mu_en l)))."""
    i = current_per_hz()
    return i * w_ev / (e_charge * e_kev * 1e3 * (1 - math.exp(-muen_lin * L_CM)))


# ---- A: the note -------------------------------------------------------------------
NOTE_TABLE = {5: 0.03595, 10: 0.004130, 15: 0.001132, 20: 0.0004505, 30: 0.0001280}  # cm^-1


def note_A(e):
    if e not in NOTE_TABLE:
        return None
    return flux_generic(e, NOTE_TABLE[e], 35.0, 1.6e-19)


# ---- B: this project ----------------------------------------------------------------
def ours_B(e, p_kpa=101.325, t_c=20.0, w_ev=34.8):
    muen = loglog_interp(e / 1e3, NIST_N, 2) * rho_n2(p_kpa, t_c)
    return flux_generic(e, muen, w_ev)


# ---- C: xraydb -----------------------------------------------------------------------
def xraydb_C(e, both):
    volts = 1.0 / HZ_PER_V          # 1 Hz -> 1e-5 V
    fl = xraydb.ionchamber_fluxes(gas="nitrogen", volts=volts, length=L_CM, energy=e * 1e3,
                                  sensitivity=S_A_PER_V, both_carriers=both)
    return fl.incident


# ---- D: CHESS JS port ----------------------------------------------------------------
CHESS_E = [4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0, 60.0, 80.0, 100.0]
CHESS_MUEN_N = [6.094E+01, 3.086E+01, 1.759E+01, 7.170E+00, 3.545E+00, 9.715E-01, 3.867E-01,
                1.099E-01, 5.051E-02, 3.217E-02, 2.548E-02, 2.211E-02, 2.231E-02]


def chess_D(e, counts=1.0, eion=34.6, rho=1.131e-3):
    # current=counts*10/1e6*range, with 'range' the amplifier gain in A/V (10 V <-> 1e6 Hz)
    current = counts * 10 / 1e6 * S_A_PER_V
    flux_arr = [current * eion / 1.602e-19 / (Ej * 1000) / (1 - math.exp(-L_CM * mu * rho))
                for Ej, mu in zip(CHESS_E, CHESS_MUEN_N)]
    i = next(k for k, Ej in enumerate(CHESS_E) if Ej >= e) - 1   # their loop, then i-1
    x0, x1, x2 = CHESS_E[i], CHESS_E[i + 1], CHESS_E[i + 2]
    f0, f1, f2 = flux_arr[i], flux_arr[i + 1], flux_arr[i + 2]
    c2 = ((f0 - f1) / (x0 - x1) - (f0 - f2) / (x0 - x2)) / (x1 - x2)
    c1 = (f0 - f1) / (x0 - x1) - c2 * (x0 + x1)
    c0 = f0 - c1 * x0 - c2 * x0 * x0
    return c0 + c1 * e + c2 * e * e


# ---- E: Hephaestus (DEMETER) Ion.pm flux_calc, ported -------------------------------------
# flux = (30/16) * 10**(20-gain) * V / E_eV / (1 - exp(-xsec*l)); gain g means 10**g V/A.
# i.e. W = 30 eV fixed for every gas, e = 1.6e-19, ONE carrier; xsec = (photo + incoherent)
# * rho with rho(N) = 0.00125 g/cm3. Demeter's Xray::Absorption default tables are Elam's, so the
# xraydb Elam photo+incoh values stand in for them. Source: references/xraydb_two_carrier/hephaestus_Ion.pm
def hephaestus_E(e):
    i = current_per_hz()
    mu = (float(xraydb.mu_elam("N", e * 1e3, kind="photo")) +
          float(xraydb.mu_elam("N", e * 1e3, kind="incoh"))) * 0.00125
    return i * 30.0 / (1.6e-19 * e * 1e3) / (1 - math.exp(-mu * L_CM))


def main():
    mat = xraydb.get_material("nitrogen")
    print("xraydb material 'nitrogen':", mat)
    hdr = ["E_keV", "A_note", "B_ours_1atm20C", "B_ours_site", "C1_xraydb_default",
           "C2_xraydb_1carrier", "D_CHESS", "E_Hephaestus", "B99_over_A", "C2_over_B1atm",
           "D_over_B1atm", "E_over_B1atm", "C1_over_C2"]
    rows = []
    for e in [5, 6, 8, 10, 12, 15, 17, 20, 25, 30]:
        a = note_A(e)
        b1 = ours_B(e)
        b2 = ours_B(e, SITE_P_KPA, SITE_T_C)
        c1 = xraydb_C(e, True)
        c2 = xraydb_C(e, False)
        d = chess_D(e)
        h = hephaestus_E(e)
        rows.append([e, f"{a:.4g}" if a else "", f"{b1:.4g}", f"{b2:.4g}", f"{c1:.4g}", f"{c2:.4g}",
                     f"{d:.4g}", f"{h:.4g}", f"{b2/a:.4f}" if a else "", f"{c2/b1:.4f}",
                     f"{d/b1:.4f}", f"{h/b1:.4f}", f"{c1/c2:.4f}"])
    with (OUT / "crosscheck_MonP_ph_per_Hz.csv").open("w", newline="") as f:
        f.write("# photons/s in MonP plate region per net Hz; l=6 cm, S=500 nA/V, 1e5 Hz/V\n")
        f.write(f"# rho_N2(101.325 kPa,20C)={rho_n2(101.325,20):.5g}  rho_N2(site {SITE_P_KPA} kPa,{SITE_T_C}C)={rho_n2(SITE_P_KPA,SITE_T_C):.5g} g/cm3\n")
        w = csv.writer(f)
        w.writerow(hdr)
        w.writerows(rows)
    print("  ".join(hdr))
    for r in rows:
        print("  ".join(str(x) for x in r))

    # ---- MonP exit-plane table (reference plane: after plates, before Kapton exit window) ----
    # I_exit = I_p * exp(-mu * rho * (l + l_gap)); l_gap (plate end -> exit window) unknown, 0 here.
    print("\nexit-plane table, l_gap = 0")
    hdr2 = ["E_keV", "absorbed_frac_site", "transmit_plates_site",
            "exit_ph_per_Hz_site", "exit_ph_per_Hz_1atm20C", "gap_loss_pct_per_cm_site"]
    rows2 = []
    for e in [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 20, 25, 30]:
        out = []
        for p, t in ((SITE_P_KPA, SITE_T_C), (101.325, 20.0)):
            rho = rho_n2(p, t)
            mu = loglog_interp(e / 1e3, NIST_N, 1) * rho
            muen = loglog_interp(e / 1e3, NIST_N, 2) * rho
            out.append((1 - math.exp(-muen * L_CM), math.exp(-mu * L_CM),
                        ours_B(e, p, t) * math.exp(-mu * L_CM), mu))
        rows2.append([e, f"{out[0][0]:.4%}", f"{out[0][1]:.4f}", f"{out[0][2]:.4g}", f"{out[1][2]:.4g}",
                      f"{100*(1-math.exp(-out[0][3])):.3f}"])
    with (OUT / "monp_exit_table.csv").open("w", newline="") as f:
        f.write("# MonP exit-plane photons/s per net Hz; l=6 cm, S=500 nA/V, 1e5 Hz/V, W=34.8 eV, NIST HS mu, mu_en\n")
        w = csv.writer(f)
        w.writerow(hdr2)
        w.writerows(rows2)
    print("  ".join(hdr2))
    for r in rows2:
        print("  ".join(str(x) for x in r))


if __name__ == "__main__":
    main()
