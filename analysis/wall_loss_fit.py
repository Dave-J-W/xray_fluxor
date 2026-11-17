"""Per-chamber fit of the SIGNAL wall-loss fraction used by the live bounds slots (CLCC), and a check that the live
band (calc/quality_slots.py wall_loss_band) covers every Monte Carlo variant of that chamber.

Families (analysis/wall_loss_families.py, which runs the MC): one per lane, each with its own geometry:
  MonP  plates vertical, E-vector toward the plates (beam taken centred: not measured on MonP)
  MonC  plates horizontal, E-vector along the plates (beam offset from the Kapton scar)
  Both use the measured gap (aperture height minus the two ledge insets) and the MC reference density rho0.
Files: analysis/out/wall_loss/<family>/central.csv and one CSV per variant. Variants named "stress_*" are reported,
not gated (three changes at once). The rest (single changes and two-change corners) must lie inside the band.

Why a photoelectric share (finding M1). The MC gives the energy lost to the plates PER PHOTOELECTRIC ABSORPTION.
The signal also contains the Compton-electron energy (part of mu_en), deposited locally: Compton electrons carry
<= 3.2 keV at 30 keV and travel < 0.3 mm in N2. So the fraction of the SIGNAL lost is
    Lambda_sig(E) = f_pe(E) * Lambda_MC(E),   f_pe = photo / (photo + Compton-electron)   (xraydb, data/queries/out/xraydb_N.csv)
The fitted form is Lambda_sig = 1 - exp(-((E - E0)/s)^p) above E0, else 0, evaluated live at the density-scaled energy
E_eff (CLCB): minimax in absolute error (ties broken by a small RMS term), then rounded to the digits the calc expression carries and re-searched.

Coverage: each variant's target f_pe(E) * loss, at E_eff = E (rho0/rho)^0.568 for the density variants, must lie in
the band (lo, hi) the LIVE constants give, within N_SE MC standard errors.

Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 analysis/wall_loss_fit.py
Output: analysis/out/wall_loss_fit_<family>.txt (also printed). Exit status 1 if a lane's live WALL_FITS entry differs
from its rounded fit, or the band misses a gated point.
"""
import csv
import itertools
import math
import re
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "calc"))
import quality_slots as qs  # noqa: E402

OUT = ROOT / "analysis" / "out"
FAMILY_DIR = OUT / "wall_loss"
FAMILIES = ("MonP", "MonC")
XRAYDB_N = ROOT / "data" / "queries" / "out" / "xraydb_N.csv"
FIT_EMIN = 14.0          # keV: below this the MC loss is < 1e-5
N_SE = 2.0               # coverage tolerance, MC standard errors


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(r for r in f if not r.startswith("#")))


def f_pe_table():
    rows = read_csv(XRAYDB_N)
    E = np.array([float(r["E_keV"]) for r in rows])
    f = np.array([float(r["elam_photo"]) / float(r["muen_eff_photo_plus_compton"]) for r in rows])
    return E, f


_FE, _FF = f_pe_table()


def f_pe(E):
    """Photoelectric share of mu_en for N, log-log interpolation of the xraydb table."""
    return float(np.exp(np.interp(math.log(E), np.log(_FE), np.log(_FF))))


def model(E, e0, s, p):
    E = np.asarray(E, float)
    x = np.clip((E - e0) / s, 0, None)
    return np.where(E > e0, 1 - np.exp(-x ** p), 0.0)


def header(path):
    with open(path, encoding="utf-8") as f:
        return "".join(line for line in f if line.startswith("#"))


def load_mc(path):
    """E, loss per photoabsorption, its standard error, and the run's density factor (from the header)."""
    rows = read_csv(path)
    E = np.array([float(r["E_keV"]) for r in rows])
    loss = np.array([float(r["loss_frac"]) for r in rows])
    se = np.array([float(r["stat_err"]) for r in rows])
    m = re.search(r"= x([0-9.]+) of 99\.26 kPa", header(path))
    dens = float(m.group(1)) if m else 1.0
    return E, loss, se, dens


def family_files(fam):
    d = FAMILY_DIR / fam
    files = sorted(d.glob("*.csv"))
    central = d / "central.csv"
    return central, [p for p in files if p.name != "central.csv"]


def gated(path):
    return not path.stem.startswith("stress_")


def variant_label(path):
    """(label, kind) from the variant file name; kind: central, range, sigma, offset, rho, combined, stress."""
    s = path.stem
    if s == "central":
        return "central", "central"
    if s.startswith("stress_"):
        return s[len("stress_"):].replace("_", " & "), "stress"
    if s.startswith("combo_"):
        return s[len("combo_"):].replace("_", " & "), "combined"
    kind = {"range": "range", "sigma": "sigma", "offset": "offset", "density": "rho"}[s.split("_")[0]]
    return s.replace("_", " "), kind


def signal_points(path):
    """Signal-loss points of one file: E, E_eff (where the live band evaluates it), target = f_pe x loss, its s.e."""
    E, loss, se, dens = load_mc(path)
    fpe = np.array([f_pe(e) for e in E])
    return {"E": E, "E_eff": np.array([qs.e_eff(e, qs.RHO0 * dens) for e in E]), "target": fpe * loss,
            "se": fpe * se, "dens": dens}


def coverage(path, lane, n_se=N_SE, e_min=FIT_EMIN):
    """Per-point band test with the lane's LIVE constants: list of (E, target, lo, hi, inside)."""
    d = signal_points(path)
    res = []
    for e, ee, t_, s_ in zip(d["E"], d["E_eff"], d["target"], d["se"]):
        if e < e_min:
            continue
        lo, _, hi = qs.wall_loss_band(ee, lane)
        res.append((float(e), float(t_), lo, hi, bool(lo - n_se * s_ <= t_ <= hi + n_se * s_)))
    return res


TIE_BREAK = 0.05     # weight of the RMS residual added to the max residual, so the minimax optimum is unique
                     # (with a late onset, many fits share the same worst point; the RMS picks among them)


def fit(E, y, start):
    def objective(q):
        r = model(E, *q) - y
        return float(np.max(np.abs(r)) + TIE_BREAK * np.sqrt(np.mean(r * r)))

    def worst(q):
        return float(np.max(np.abs(model(E, *q) - y)))
    best = minimize(objective, x0=np.array(start, float), method="Nelder-Mead",
                    options={"xatol": 1e-4, "fatol": 1e-6, "maxiter": 4000}).x
    grid = itertools.product(np.round(best[0] + np.arange(-3, 4) * 0.1, 1),
                             np.round(best[1] + np.arange(-3, 4) * 0.1, 1),
                             np.round(best[2] + np.arange(-3, 4) * 0.01, 2))
    rounded = min(grid, key=objective)
    return tuple(float(v) for v in best), tuple(float(v) for v in rounded), worst(best), worst(rounded)


def run_family(fam):
    lines = []

    def out(s=""):
        print(s)
        lines.append(s)

    central, variants = family_files(fam)
    c = signal_points(central)
    m = c["E"] >= FIT_EMIN
    raw, rounded, err_raw, err_rounded = fit(c["E"][m], c["target"][m], qs.WALL_FITS[fam])
    live = qs.WALL_FITS[fam]
    out(f"== {fam}: signal wall loss = f_pe(E) x MC loss per photoabsorption ({central.relative_to(ROOT).as_posix()})")
    for line in header(central).splitlines():
        out("  " + line)
    out(f"  minimax fit   E0 {raw[0]:.3f}  s {raw[1]:.3f}  p {raw[2]:.4f}   max |fit - target| {err_raw:.4f}")
    out(f"  rounded fit   E0 {rounded[0]:.1f}  s {rounded[1]:.1f}  p {rounded[2]:.2f}   max |fit - target| {err_rounded:.4f}")
    out(f"  live WALL_FITS[{fam!r}] = {live}  (calc/quality_slots.py)")
    out("  E keV   f_pe    MC loss   target   live fit   live - target")
    lv = model(c["E"], *live)
    E, loss, _, _ = load_mc(central)
    for e, l_, t_, v_ in zip(c["E"], loss, c["target"], lv):
        out(f"  {e:5g}  {f_pe(e):.4f}   {l_:.4f}   {t_:.4f}   {v_:.4f}    {v_ - t_:+.4f}")
    ok = tuple(live) == rounded
    out(f"  live constants {'EQUAL' if ok else 'DIFFER FROM'} the rounded fit; live max |error| "
        f"{float(np.max(np.abs(lv[m] - c['target'][m]))):.4f}")
    out(f"  band coverage with the live constants (within {N_SE:g} MC s.e., from {FIT_EMIN:g} keV):")
    n_all = n_in = 0
    for p in [central] + variants:
        pts = coverage(p, fam)
        miss = [f"{e:g} keV {t_:.4f} not in [{lo:.4f}, {hi:.4f}]" for e, t_, lo, hi, ok_ in pts if not ok_]
        tag = "" if gated(p) else "  [stress case, not gated]"
        out(f"    {p.stem:38s} {'all covered' if not miss else 'MISSES: ' + '; '.join(miss)}{tag}")
        if gated(p):
            n_all += len(pts)
            n_in += len(pts) - len(miss)
    out(f"  covered {n_in} of {n_all} gated points")
    ok &= n_in == n_all
    out(f"  {fam}: {'PASS' if ok else 'FAIL'}")
    (OUT / f"wall_loss_fit_{fam}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ok, rounded


def main():
    results = {fam: run_family(fam) for fam in FAMILIES}
    ok = all(r[0] for r in results.values())
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
