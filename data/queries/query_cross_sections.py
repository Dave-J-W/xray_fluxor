"""Query every locally reachable photon cross-section source for the ion-chamber gases.

Writes verbatim-ish CSV outputs next to this script (data/queries/out/), one file per
source, plus a side-by-side comparison for nitrogen. Re-run safe; overwrites out/.

Sources
  nist_hs   NIST Hubbell & Seltzer, X-Ray Mass Attenuation Coefficients (NISTIR 5632),
            raw HTML saved in nist_hubbell_seltzer/ (downloaded 2026-11-12), log-log interpolated
  xraydb    xraydb (Elam, Ravel & Sieber 2002 tables; Chantler FFAST), via pip xraydb
  xraylib   xraylib (Schoonjans et al. 2011) CS_* functions

Run:  <bluesky venv>\\Scripts\\python.exe -I -X utf8 query_cross_sections.py
"""
import csv
import math
import re
import sys
from pathlib import Path

import numpy as np
import xraydb
import xraylib

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# keV grid of interest for C-station (Si(111) mono, plus harmonics up to 30 keV)
E_KEV = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 20, 22, 25, 30, 40]

NIST_FILES = {
    "N": "z07_nitrogen.html",
    "O": "z08_oxygen.html",
    "Ar": "z18_argon.html",
    "air": "air_dry.html",
}
Z = {"N": 7, "O": 8, "Ar": 18}

def versions():
    return {
        "python": sys.version.split()[0],
        "xraydb": getattr(xraydb, "__version__", "?"),
        "xraylib": getattr(xraylib, "__version__", "?"),
        "numpy": np.__version__,
    }


def parse_nist(path):
    """Return (E_MeV, mu_rho, muen_rho) arrays from a saved NIST Hubbell-Seltzer HTML table.

    Edge rows carry a label (e.g. 'K') before the energy; the energy column is the first
    number in scientific notation with 5 decimals. Duplicate energies at edges are kept
    (both sides of the edge) and handled by interpolating only within monotone segments.
    """
    text = re.sub(r"<[^>]+>", " ", path.read_text(encoding="latin-1"))
    nums = re.findall(r"\d\.\d{5}E[+-]\d\d\s+\d\.\d{3}E[+-]\d\d\s+\d\.\d{3}E[+-]\d\d", text)
    rows = [tuple(float(x) for x in n.split()) for n in nums]
    if not rows:
        raise RuntimeError(f"no rows parsed from {path}")
    return np.array(rows)


def loglog_interp(e_mev, rows, col):
    """NIST-recommended log-log interpolation, within the segment above the last edge below e."""
    E = rows[:, 0]
    y = rows[:, col]
    # pick the last segment start whose energy <= e (edges repeat an energy)
    idx = np.searchsorted(E, e_mev, side="right") - 1
    if idx < 0 or idx >= len(E) - 1:
        raise ValueError(f"{e_mev} MeV outside table")
    if E[idx + 1] == E[idx]:
        idx += 1
    lx = np.log([E[idx], E[idx + 1]])
    ly = np.log([y[idx], y[idx + 1]])
    return float(np.exp(np.interp(math.log(e_mev), lx, ly)))


def write_csv(name, header, rows, meta):
    p = OUT / name
    with p.open("w", newline="") as f:
        for k, v in meta.items():
            f.write(f"# {k}: {v}\n")
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("wrote", p.relative_to(HERE))


def main():
    meta = {"generated_by": "query_cross_sections.py", **versions(), "units": "cm^2/g, keV"}

    # ---------- NIST Hubbell & Seltzer: native grid + interpolated grid ----------
    nist = {}
    for sym, fn in NIST_FILES.items():
        rows = parse_nist(HERE / "nist_hubbell_seltzer" / fn)
        nist[sym] = rows
        write_csv(f"nist_hs_{sym}_native.csv", ["E_MeV", "mu_rho", "muen_rho"],
                  rows.tolist(), {**meta, "source": f"NIST XrayMassCoef {fn}, native grid"})
        interp = [[e, loglog_interp(e / 1e3, rows, 1), loglog_interp(e / 1e3, rows, 2)] for e in E_KEV]
        write_csv(f"nist_hs_{sym}_grid.csv", ["E_keV", "mu_rho", "muen_rho"], interp,
                  {**meta, "source": f"NIST XrayMassCoef {fn}, log-log interpolated"})

    # ---------- xraydb: Elam (by process), Chantler, Compton electron energy ----------
    rows = []
    for e in E_KEV:
        ev = e * 1e3
        tot = float(xraydb.mu_elam("N", ev, kind="total"))
        pho = float(xraydb.mu_elam("N", ev, kind="photo"))
        coh = float(xraydb.mu_elam("N", ev, kind="coh"))
        inc = float(xraydb.mu_elam("N", ev, kind="incoh"))
        ch_tot = float(xraydb.mu_chantler("N", ev))
        ch_pho = float(xraydb.mu_chantler("N", ev, photo=True))
        ce = xraydb.get_xraydb().compton_energies(ev)
        e_ce = float(ce.electron_mean)  # eV, mean Compton electron energy
        # energy-deposition coefficient implied by xraydb's ionchamber model
        muen_eff = pho + inc * e_ce / ev
        rows.append([e, tot, pho, coh, inc, ch_tot, ch_pho, e_ce, muen_eff])
    write_csv("xraydb_N.csv",
              ["E_keV", "elam_total", "elam_photo", "elam_coh", "elam_incoh",
               "chantler_total", "chantler_photo", "compton_e_mean_eV", "muen_eff_photo_plus_compton"],
              rows, {**meta, "source": "xraydb mu_elam / mu_chantler / compton_energies, element N"})

    # ---------- xraylib ----------
    rows = []
    for sym in ("N", "O", "Ar"):
        z = Z[sym]
        for e in E_KEV:
            rows.append([sym, e, xraylib.CS_Total(z, e), xraylib.CS_Photo(z, e), xraylib.CS_Rayl(z, e),
                         xraylib.CS_Compt(z, e), xraylib.CS_Energy(z, e)])
    air = xraylib.GetCompoundDataNISTByName("Air, Dry (near sea level)")
    for e in E_KEV:
        tot = sum(w * xraylib.CS_Total(z, e) for z, w in zip(air["Elements"], air["massFractions"]))
        en = sum(w * xraylib.CS_Energy(z, e) for z, w in zip(air["Elements"], air["massFractions"]))
        rows.append(["air", e, tot, "", "", "", en])
    write_csv("xraylib.csv", ["material", "E_keV", "CS_Total", "CS_Photo", "CS_Rayl", "CS_Compt", "CS_Energy"],
              rows, {**meta, "source": "xraylib CS_*; air from NIST compound 'Air, Dry (near sea level)' mass fractions",
                     "air_mass_fractions": dict(zip(air["Elements"], air["massFractions"]))})

    # ---------- side-by-side for nitrogen ----------
    xdb = {r[0]: r for r in (list(map(float, x)) for x in
           (csv.reader(l for l in (OUT / "xraydb_N.csv").open() if not l.startswith("#"))) if x[0] != "E_keV")}
    rows = []
    for e in E_KEV:
        mu_n = loglog_interp(e / 1e3, nist["N"], 1)
        en_n = loglog_interp(e / 1e3, nist["N"], 2)
        mu_xl = xraylib.CS_Total(7, e)
        en_xl = xraylib.CS_Energy(7, e)
        mu_el = xdb[e][1]
        en_el = xdb[e][8]
        mu_ch = xdb[e][5]
        en_air = loglog_interp(e / 1e3, nist["air"], 2)
        rows.append([e, f"{mu_n:.4g}", f"{mu_xl:.4g}", f"{mu_el:.4g}", f"{mu_ch:.4g}",
                     f"{en_n:.4g}", f"{en_xl:.4g}", f"{en_el:.4g}",
                     f"{100*(en_xl/en_n-1):+.2f}", f"{100*(en_el/en_n-1):+.2f}",
                     f"{en_air/en_n:.3f}"])
    write_csv("compare_N.csv",
              ["E_keV", "mu_NIST", "mu_xraylib", "mu_Elam", "mu_Chantler",
               "muen_NIST", "muen_xraylib", "muen_eff_xraydb",
               "muen_xraylib_vs_NIST_%", "muen_xraydb_vs_NIST_%", "muen_air_over_N2_NIST"],
              rows, {**meta, "source": "side-by-side, nitrogen (element N; N2 is the same per gram)"})
    for r in rows:
        print("  ".join(str(x) for x in r))


if __name__ == "__main__":
    main()
