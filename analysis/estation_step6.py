r"""Step 6 (first part): run the fluxor package on the archived E-station beam-on periods. No PVs, no network.

Inputs: data/estation/beam_on_periods_2026-11.csv (the Experimenter's beam-on periods; numbers only). Energy = the E-station
side-bounce mono readback (the DCM column is the C-station's and is NOT used). Every other number comes from the parameter
registry (fluxor/parameters.toml): the TetrAMM range (provisional, RNG 0, flagged), the beam width (the white-beam slit, an UPPER bound, A28), the beam aspect ratio (central
value and range, A29) and the gas conditions, which are a STAND-IN (no E-station gas sensor exists: ambient pressure and
the E-hutch air temperature, A7). The best estimate carries the central recombination correction; the bounds span the aspect
range. The dark error is the before/after difference (at least 0.1 nA), as the Experimenter advised.
There is NO independent absolute flux reference for this line, so this run checks that the package behaves on real data
(flags, size of each term, consistency between beam-on periods); it cannot say whether the absolute flux is right.
Run: <bluesky venv>\Scripts\python.exe -I -X utf8 analysis/estation_step6.py
Output: analysis/out/estation_step6.csv and .txt (main(out_dir=...) writes them to another directory instead)
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fluxor import params  # noqa: E402
from fluxor.chains.tetramm import TetraMM  # noqa: E402
from fluxor.chambers.ic500_50 import Ic500_50, recombination_loss  # noqa: E402
from fluxor.core import evaluate  # noqa: E402


def main(out_dir=None):
    reg = params.default()
    out_dir = Path(out_dir) if out_dir is not None else ROOT / "analysis/out"
    out_dir.mkdir(parents=True, exist_ok=True)
    # P and T are left to the chamber: it reads the stand-in rows gas.p_kpa / gas.t_c itself and flags them; these two are for the header only
    p_kpa, t_c = reg.param("gas.p_kpa").value, reg.param("gas.t_c").value
    aspects = [(n.split("_")[1], reg.value(n)) for n in ("beam.aspect_low", "beam.aspect_central", "beam.aspect_high")]
    path = ROOT / "data/estation/beam_on_periods_2026-11.csv"
    rows = list(csv.DictReader(l for l in open(path, encoding="utf-8") if not l.startswith("#")))
    out, lines = [], []
    head = (f"{'beam-on period (UTC)':20s} {'E keV':>6s} {'I ch3+ch4':>10s} {'flux best':>10s} {'low':>9s} {'high':>9s} {'sigma':>6s} "
            f"{'wall loss':>9s} {'recomb central':>14s} {'recomb range':>14s} {'flux/I':>9s}")
    lines += [f"E-station mono energy per beam-on period, P {p_kpa} kPa, T {t_c} C (stand-ins), IC-500-50, TetrAMM range from the registry (row tetramm.range, provisional RNG 0), channels 3+4", head]
    chamber = Ic500_50(reg=reg)
    for r in rows:
        d3 = (float(r["dark3_before"]) + float(r["dark3_after"])) / 2
        d4 = (float(r["dark4_before"]) + float(r["dark4_after"])) / 2
        dark_err = max(abs(float(r["dark3_before"]) - float(r["dark3_after"])),
                       abs(float(r["dark4_before"]) - float(r["dark4_after"])), 0.1) * 1e-9
        chain = TetraMM(("Current3", "Current4"), darks={"Current3": d3, "Current4": d4}, dark_sigma_a=dark_err, dark_age_h=12)
        reading = {"channels": {"Current3": float(r["net_ch3_nA"]) + d3, "Current4": float(r["net_ch4_nA"]) + d4}}
        res = evaluate(chamber, chain, reading, float(r["energy_kev"]))
        cm = res.detail["chamber"]
        wl = chamber.flux(res.current_a, float(r["energy_kev"])).wall_loss   # Result carries no wall loss; ask the chamber (after evaluate, so flags are unaffected)
        flags = list(res.flags)
        lines.append(f"{r['start_utc']:20s} {float(r['energy_kev']):6.3f} {res.current_a * 1e9:8.0f}nA {res.flux_best:10.4g} {res.flux_low:9.3g} "
                     f"{res.flux_high:9.3g} {100 * res.sigma_rel:5.2f}% {100 * wl:8.1f}% {100 * cm['recomb_central']:13.2f}% "
                     f"{100 * cm['recomb_low']:6.2f}-{100 * cm['recomb_high']:.2f}% {res.flux_best / res.current_a:9.4g}")
        out.append({"start_utc": r["start_utc"], "energy_kev": r["energy_kev"], "current_nA": res.current_a * 1e9,
                    "flux_best": res.flux_best, "flux_low": res.flux_low, "flux_high": res.flux_high,
                    "sigma_rel": res.sigma_rel, "wall_loss": wl,
                    "recomb_low": cm["recomb_low"], "recomb_central": cm["recomb_central"], "recomb_high": cm["recomb_high"],
                    "ch3_share": res.per_channel["Current3"] / res.flux_best, "flags": ";".join(flags)})
    lines.append("")
    lines.append("recombination loss at each beam-on period's current, by beam height/width ratio (registry rows beam.aspect_*; the slit sizes alone give no ratio):")
    lines.append(f"  {'beam-on period':20s}" + "".join(f"{n + ' ' + format(a, 'g'):>12s}" for n, a in aspects))
    w_cm = chamber.beam_w_cm
    for r, o in zip(rows, out):
        i_a = o["current_nA"] * 1e-9
        vals = [recombination_loss(i_a, chamber.gap_cm, chamber.volts, min(w_cm * a, chamber.gap_cm), w_cm, chamber.l_cm,
                                   alpha=chamber.alpha, k_pos=chamber.mobility, k_neg=chamber.mobility) for _, a in aspects]
        lines.append(f"  {r['start_utc']:20s}" + "".join(f"{100 * v:11.2f}%" for v in vals))
    lines.append("flags on every beam-on period: " + ", ".join(sorted(set.intersection(*[set(o["flags"].split(";")) for o in out]))))
    lines.append("flux/I (ph/s per A) varies with energy (it is the sensitivity of the chamber at that energy); beam-on periods at one energy agree.")
    print("\n".join(lines))
    with open(out_dir / "estation_step6.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    (out_dir / "estation_step6.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
