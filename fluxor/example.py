r"""Worked example: the E-station IC-500-50 read by the TetrAMM (channels 3 and 4) and, later, the FX4.

Run: <bluesky venv>\Scripts\python.exe -I -X utf8 fluxor/example.py
Currents are an illustration (2.4 + 1.6 uA, the size of the archived E-station beam-on plateaus), not a measurement.
P and T are left out of the calls, so the registry's flagged stand-ins are used (rows gas.p_kpa and gas.t_c): there is no
E-station gas sensor. Pass p_kpa= and t_c= to evaluate() once you have real values.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fluxor.chains.fx4 import Fx4  # noqa: E402
from fluxor.chains.tetramm import TetraMM
from fluxor.chambers.ic500_50 import Ic500_50
from fluxor.core import evaluate


def show(label, r):
    print(f"{label}")
    print(f"  flux best {r.flux_best:.4g} ph/s  [{r.flux_low:.4g}, {r.flux_high:.4g}]   sigma {100 * r.sigma_rel:.2f} %")
    print(f"  per channel: " + ", ".join(f"{n} {v:.3g}" for n, v in r.per_channel.items()))
    d = r.detail["chamber"]
    print(f"  recombination loss: low {100 * d['recomb_low']:.2f} %, central {100 * d['recomb_central']:.2f} %, "
          f"high {100 * d['recomb_high']:.2f} %  (beam height {10 * d['beam_h_cm']:.3f} mm)")
    print(f"  flags: {', '.join(r.flags)}")


def main():
    chamber = Ic500_50()
    tet = TetraMM(("Current3", "Current4"), rng=0, darks={"Current3": 0.0, "Current4": 0.0}, dark_age_h=1.0)
    for e in (10.0, 20.0, 30.0):
        r = evaluate(chamber, tet, {"channels": {"Current3": 2400.0, "Current4": 1600.0}}, e)
        show(f"TetrAMM, {e:g} keV", r)
    fx = Fx4(("c3", "c4"), rng=4, sample_hz=10.0, darks={"c3": 0.0, "c4": 0.0}, dark_age_h=1.0)
    r = evaluate(chamber, fx, {"channels": {"c3": 2.4e-6, "c4": 1.6e-6}}, 10.0, temp_c=22.0)
    show("FX4 (range 4 = 10 uA, provisional), 10 keV", r)


if __name__ == "__main__":
    main()
