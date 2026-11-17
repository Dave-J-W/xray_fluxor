r"""Export the flux dashboard's model (parameters, budget, flags, slot map, expected expressions) as JSON.

Run: <bluesky venv>\Scripts\python.exe -I -X utf8 tools/export_dashboard_model.py [out.json]
(default out: docs/dashboard_model.json). OFFLINE: no EPICS. The 15IDC HA repo keeps a committed copy
(ioc/utilioc/screens/flux_dashboard_model.json) that its generator and its live currency check read; the copy
carries the xray_fluxor commit it was made from. Sources: fluxor/parameters.toml (via fluxor.params) and
calc/estation_lane.py for the E-station; calc/monp_transform.py, calc/quality_slots.py, calc/background_transform.py,
calc/lanes.py for the C-station lanes. Nothing is typed twice: values come from those modules.

C-station constants are not in the registry; their tags and sources below are written here from the comments in
the calc modules (physics_note.md, CHAMBER_FACTS.md) and are the one place a tag is assigned by hand.
"""
import datetime
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "calc"))

import background_transform as bt  # noqa: E402
import estation_lane as el  # noqa: E402
import lanes as ln  # noqa: E402
import monp_transform as mt  # noqa: E402
import quality_slots as qs  # noqa: E402
from fluxor import params  # noqa: E402

P = "15IDC:util:"


def _git():
    try:
        sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "calc", "fluxor"],
                               capture_output=True, text=True).stdout.strip()
        return sha + ("+uncommitted calc/fluxor changes" if dirty else "")
    except OSError:
        return "unknown"


def prow(name, value, unit, tag, source, sigma=None, closes="", date=""):
    return dict(name=name, value=value, unit=unit, tag=tag, source=source, sigma=sigma, closes_with=closes, date=date)


def registry_rows():
    reg = params.default()
    return [prow(p.name, p.value, p.unit, p.tag, p.source, p.sigma, p.closes_with, p.date) for p in (reg.param(n) for n in reg.names())]


# ---- E-station -----------------------------------------------------------------------------
def estation():
    reg = params.default()
    G = el.G
    rows = registry_rows()
    kept = {"CHOICE", "DERIVED"}
    rows += [
        prow("lane.k_flux", el.G["k_flux"], "photons/s per A per keV", "DERIVED", "W_EV/(E_CHARGE*1e3) from fluxor.constants"),
        prow("lane.flag1_energy", qs.FLAG1_E_KEV, "keV", "DERIVED", "calc/quality_slots.FLAG1_E_KEV: wall-loss band widens above 12.5 keV at the lowest density seen (informational, bit 1)"),
        prow("lane.flag2_recomb", el.RECOMB_FLAG_FRACTION, "fraction", "CHOICE", "calc/estation_lane.RECOMB_FLAG_FRACTION: bit 2, central recombination above 5 %"),
        prow("lane.flag4_pressure_age", 7200, "s", "CHOICE", "bit 4: pressure not updated for 2 h (same rule as the C-station lanes)"),
        prow("lane.flag8_low_current", el.LOW_CURRENT_NA, "nA", "CHOICE", "calc/estation_lane.LOW_CURRENT_NA: bit 8, net current below 50 nA (the TetrAMM noise term is not in the bounds; this flag covers it)"),
        prow("lane.flag16_energy_range", list(G["e_range"]), "keV", "GIVEN", "mono range the fit and tables are valid for: 4.9 to 30.5 keV (bit 16, alarm)"),
        prow("lane.flag32_raw_neg_margin", el.RAW_NEG_MARGIN_NA, "nA", "CHOICE", "calc/estation_lane.RAW_NEG_MARGIN_NA: bit 32, raw sum below -5 nA"),
        prow("lane.flag32_full_scale_fraction", el.FULL_SCALE_FRACTION, "fraction of 120 uA", "CHOICE", "calc/estation_lane.FULL_SCALE_FRACTION: bit 32, a channel at or above 99 %% of full scale (%.0f nA)" % G["fs_na"]),
        prow("lane.wall_band", G["band"], "a,b,cap,k,floor,e_widen", "DERIVED", "calc/quality_slots.BAND, shared with the C-station lanes (analysis/wall_loss_fit.py)"),
        prow("lane.recomb_k_per_A", list(G["k_per_a"]), "1/A (low, central, high aspect)", "DERIVED", "fluxor recombination at 1 uA, linear in current, capped at 0.5 (calc/estation_lane._generate)"),
        prow("lane.noise_threshold", G["noise_na"], "nA", "DERIVED", "3 sigma of the two-channel current from the TetrAMM chain, rounded up to 0.1 nA (not in the live bounds)"),
    ]
    terms = [
        dict(name="mu_en/rho tables", rel=G["terms"]["mu_en/rho tables"], tag=reg.param("terms.mu_en_tables_rel").tag, source="terms.mu_en_tables_rel: spread of NIST vs Chantler/Elam"),
        dict(name="W", rel=G["terms"]["W"], tag=reg.param("terms.w_rel").tag, source="terms.w_rel: spread of the W sources, carried as 1 sigma"),
        dict(name="density", rel=G["terms"]["density (P, T from the caller)"], tag=reg.param("terms.density_rel").tag, source="terms.density_rel"),
        dict(name="gas stand-in P,T", rel=G["terms"]["gas stand-in P,T"], tag=reg.param("gas.p_kpa").tag, source="gas.p_kpa sigma 1.0 kPa and gas.t_c sigma 2.0 C (stand-ins: no E-station P or T sensor)"),
        dict(name="collection length", rel=G["terms"]["collection length (l_eff)"], tag=reg.param("ic500.l_eff_cm").tag, source="ic500.l_eff_cm sigma (relative 3 %: fringe-field allowance)"),
        dict(name="TetrAMM range gain", rel=G["terms"]["TetrAMM range gain"], tag=reg.param("tetramm.gain_rel").tag, source="tetramm.gain_rel (placeholder)"),
        dict(name="energy readback", rel=G["terms"]["energy readback"], tag=reg.param("terms.energy_readback_rel").tag, source="terms.energy_readback_rel (assumed 0.1 % dE/E times the largest dlnF/dlnE)"),
    ]
    expected = {}
    for role, recname in (("flux", "userTran9"), ("bounds", "userTran10"), ("flags", "userTran11")):
        expected[recname] = {f"CLC{k}": v for k, v in el.EXPR[role].items()}
    return dict(
        name="E-station IC-500-50", chamber="IC-500-50",
        slots=dict(flux="userTran9", bounds="userTran10", flags="userTran11", status="userCalcOut9"),
        flags=[dict(bit=b, letter=k, text=t) for b, k, t in el.FLAG_BITS],
        params=rows, terms=terms, quad_total=G["sigma_s"], low_factor=G["lf"], high_factor=G["hf"],
        asymmetric=dict(wall_loss="userTran10.C", recombination=["userTran10.E", "userTran10.F", "userTran10.G"]),
        not_in_budget=["TetrAMM noise term (the low-current flag covers it)", "per-channel split"],
        expected_clc=expected, wall_fit=list(G["wall_fit"]))


# ---- C-station -----------------------------------------------------------------------------
def cstation(lane):
    L = ln.LANES[lane]
    wf = qs.WALL_FITS[lane]
    orient = L["plates"]
    rows = [
        prow("W", mt.W_EV, "eV", "CHOICE", "physics_note.md 2.1: one of five sources; the spread is the W term (0.6 %)"),
        prow("collection length", mt.L_CM, "cm", "MEASURED", "analysis/collection_length_cmc.py, nominal case of the guarded CMC chamber, rounded (checked against the model CSV)"),
        prow("wall-loss fit E0, s, p", list(wf), "keV, keV, 1", "DERIVED", "fit of f_pe x the Monte Carlo of this chamber as mounted (analysis/wall_loss_families.py, wall_loss_fit.py)"),
        prow("plate orientation", orient, "", "ASSUMED" if lane == "MonP" else "GIVEN",
             "user 2026-11-13 (calc/lanes.py); MonP: vertical plates, E toward the plates, beam centred ASSUMED (quality_slots comment)" if lane == "MonP" else "user 2026-11-13 (calc/lanes.py): horizontal plates, E along them",
             closes="a check of the beam centring on the chamber" if lane == "MonP" else ""),
        prow("wall-loss band", dict(qs.BAND), "a,b,cap,k,floor,e_widen", "DERIVED", "covers every MC variant and two combined corners within 2 MC standard errors (finding M4, 2026-11-13)"),
        prow("reference density rho0", qs.RHO0, "g/cm3", "GIVEN", "density of the wall-loss Monte Carlo (CLCB)"),
        prow("range exponent", qs.RANGE_EXP, "1", "DERIVED", "1/1.76: CSDA range ~ T^1.76/rho (CLCB)"),
        prow("cross-section fit mu_en/rho", mt.MUEN, "calc expression, L = ln E", "DERIVED", "calc/fit_coefficients.py: minimax cubic over 5-30 keV of a NIST-anchored target, 4 significant figures, max error 0.6 %"),
        prow("cross-section fit mu/rho", mt.MU, "calc expression, L = ln E", "DERIVED", "calc/fit_coefficients.py, as above"),
        prow("V2F scale", 1e5, "Hz/V", "GIVEN", "calc/monp_transform.K_FLUX divisor (ELECTRONICS_CONCLUSIONS.md)"),
        prow("flux constant", mt.K_FLUX * 1e5, "photons/s per A per keV x ...", "DERIVED", "W/(e*1e3) = 2.17205e17 (CLCP uses 2.17205E12 with the 1e5 Hz/V V2F scale)"),
        prow("flag 1 energy", qs.FLAG1_E_KEV, "keV", "DERIVED", "quality_slots.FLAG1_E_KEV (informational)"),
        prow("flag 4 pressure age", 7200, "s", "CHOICE", "pressure not updated for 2 h"),
        prow("flag 16 energy range", [4.9, 30.5], "keV", "GIVEN", "validity range of the fit and tables (alarm)"),
        prow("background threshold", bt.SLOT["values"]["F"], "Hz", "CHOICE", "no beam while the raw rate stays below this (user dark/light split)"),
        prow("background settle", bt.SLOT["values"]["G"], "s", "CHOICE", "no-beam run length before the estimate updates"),
        prow("background averaging", bt.SLOT["values"]["I"], "samples", "CHOICE", "plain mean for the first 60 samples, then exponential"),
    ]
    sym_tags = {"mu_en/rho tables": "CHOICE", "W": "CHOICE", "electronics": "DERIVED", "density (live P, T)": "DERIVED",
                "cross-section fit": "DERIVED", "collection length (guarded)": "DERIVED", "energy readback": "ASSUMED"}
    sym_src = {"mu_en/rho tables": "spread of NIST vs Chantler/Elam", "W": "full spread of five sources, carried as 1 sigma",
               "electronics": "SR570 gain x V2F scale incl. loading, type B (ELECTRONICS_CONCLUSIONS.md; user 2026-11-13)",
               "density (live P, T)": "live pressure and temperature", "cross-section fit": "calc fit vs log-log NIST, worst at 25 keV",
               "collection length (guarded)": "spread of analysis/collection_length_cmc.py over the dimension tolerances plus 0.5 % for the 2-D model",
               "energy readback": "assumed 0.1 % energy error times the largest dlnF/dlnE (3.7), no edge scan yet (user 2026-11-17)"}
    terms = [dict(name=k, rel=v, tag=sym_tags[k], source=sym_src[k]) for k, v in qs.SYMMETRIC_TERMS.items()]
    s = L["slots"]
    bounds = dict(qs.BOUNDS["expr"])
    bounds["CLCC"] = qs.clcc(lane)
    if not L["pressure_owner"]:
        bounds.pop("CLCH")      # MonC's letter H is a link to the MonP lane's pressure age, not an expression (live check, 2026-11-17)
    expected = {f"userTran{s['flux']}": dict(mt.SLOT["expr"]), f"userTran{s['bounds']}": bounds,
                f"userTran{s['bkg']}": dict(bt.SLOT["expr"])}
    expected[f"userTran{s['flags']}"] = {f"CLC{k}": e for _, k, e, _t in qs.FLAG_BITS}
    expected[f"userTran{s['flags']}"]["CLCL"] = qs.FLAGS_CODE
    return dict(
        name=lane, chamber="CMC chamber (SR570 + V2F + scaler)",
        slots=dict(flux=f"userTran{s['flux']}", bkg=f"userTran{s['bkg']}", bounds=f"userTran{s['bounds']}",
                   flags=f"userTran{s['flags']}", status=f"userCalcOut{s['status']}", dark=f"userCalcOut{s['dark']}"),
        flags=[dict(bit=b, letter=k, text=t.split(": ", 1)[1]) for b, k, _e, t in qs.FLAG_BITS],
        params=rows, terms=terms, quad_total=qs.OTHER_TERMS, low_factor=qs.LOW_FACTOR, high_factor=qs.HIGH_FACTOR,
        asymmetric=dict(wall_loss=f"userTran{s['bounds']}.C", recombination=None),
        not_in_budget=["recombination (not applicable to the CMC chamber lane)"],
        expected_clc=expected, wall_fit=list(wf))


def build():
    lanes = {"estation": estation(), "monp": cstation("MonP"), "monc": cstation("MonC")}
    for k, v in lanes.items():
        tot = math.sqrt(sum(t["rel"] ** 2 for t in v["terms"]))
        assert abs(tot - v["quad_total"]) < 1e-9, (k, tot, v["quad_total"])
    return dict(prefix=P, xray_fluxor_commit=_git(), date=datetime.date.today().isoformat(), lanes=lanes)


def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "docs" / "dashboard_model.json"
    m = build()
    out.write_text(json.dumps(m, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for k, v in m["lanes"].items():
        print(f"{k}: {len(v['params'])} parameters, {len(v['terms'])} terms, total {100 * v['quad_total']:.2f} %, "
              f"factors {v['low_factor']} / {v['high_factor']}")
    print(f"wrote {out} (xray_fluxor {m['xray_fluxor_commit']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
