# MonP: the finished number

*The chamber and electronics facts behind these numbers are listed in `CHAMBER_FACTS.md`, and each is checked against its source by `analysis/check_chamber_facts.py`.*

**At 10 keV, with the MonP SR570 at 500 nA/V, one net hertz of MonP scaler rate is 4.37 × 10⁶ photons/s at the MonP exit.**
- The exit is the downstream end of the collection region (the collector plus its guard gaps), before the Kapton exit window.
- Conditions are the site mean at the hutch (228 m): 98.99 kPa and 24.9 °C. Live, the calc uses the current pressure and temperature.
- Uncertainty: **±3.6 %** (stated bounds). The chamber is guarded and was measured by hand on 2026-11-13, so the collection length is no longer the dominant, one-sided term (below). Until 2026-11-13 this read +3.3 % / −14 %.

At other settings, scale it:
- by the SR570 sensitivity (×2 at 1 µA/V, ×0.1 at 50 nA/V);
- by the energy (table below);
- for gas density: +0.34 % per kelvin warmer, −1 % per kPa higher.

Example: MonP reading 224 kHz at 10 keV and 500 nA/V means about 0.98 × 10¹² photons/s.

| E (keV) | 5 | 8 | 10 | 12 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|---|---|---|
| photons/s per Hz at 500 nA/V | 9.13e5 | 2.65e6 | **4.37e6** | 6.56e6 | 1.08e7 | 2.02e7 | 3.26e7 | 4.78e7 |
| MonP wall-loss correction (MC, plates vertical) | 1 | 1 | 1 | 1 | 1.00 | ×1.08 | ×1.36 | **×1.76** |
| MonP best estimate per Hz | 9.13e5 | 2.65e6 | 4.37e6 | 6.56e6 | 1.08e7 | 2.18e7 | 4.42e7 | 8.43e7 |
| MonC wall-loss correction (MC, plates horizontal) | 1 | 1 | 1 | 1 | 1.00 | ×1.02 | ×1.16 | **×1.37** |
| stated bounds (MonP) | ±3.6 % | ±3.6 % | ±3.6 % | ±3.6 % | +9 / −3.6 % | +15 / −11 % | +18 / −15 % | +23 / −20 % |

(MonC's per-Hz values depend on its own SR570 gain; its wall-loss factor is the row above.)

## Where it comes from, step by step

| Step | Relation | Value at 10 keV | Source |
|---|---|---|---|
| 1. Counts to volts | V = N / (1e5 Hz/V) | N101VTF x1, 0–10 V range: 10 V = 1 MHz | N101VTF datasheet (`references/`); range confirmed by the user |
| 2. Volts to amps | i = V × S | S = 500 nA/V | SR570 setting (EPICS 15IDC:A2; front panel not yet read) |
| 3. Amps to ion pairs/s | n = i / e | e = 1.602176634e-19 C | exact (SI) |
| 4. Ion pairs to absorbed energy | energy/s = n × W, **one charge per ion pair** | W(N2) = 34.8 eV ± 0.6 % | ICRU 31 / Knoll / Jesse & Sadauskis; spread of 5 sources (`data/queries/W_values.md`) |
| 5. Absorbed energy to photons entering the collection region | ÷ [E × (1 − exp(−μ_en ρ l))] | 2.42 % of 10 keV photons deposit their energy in l = l_eff = 6.19 cm (the guarded collector's effective length, `analysis/collection_length_cmc.py`) | NIST Hubbell–Seltzer μ_en/ρ(N) = 3.545 cm²/g ± 3 % (spread vs Chantler) |
| 6. Gas density | ρ = P·M / (R·T) | 1.119e-3 g/cm³ at 98.99 kPa, 24.9 °C | LOT airport barometer, 2025 mean, carried to the hutch at 228 m; `15ID:Sensor2:Temperature` 2024–26 mean. Live: the current LOT pressure and Sensor2 |
| 7. To the exit plane | × exp(−μ ρ l) | 0.974 (l = 6.19 cm) | NIST μ/ρ(N) = 3.879 cm²/g |

**Cross-checked against every existing tool.**
- The C-station physics note agrees once its W (35 eV) and density (1 atm, 20 °C) are swapped for ours.
- So do the CHESS calculator, xraydb with one carrier and Hephaestus, once their inputs are aligned the same way.
- xraydb's default is 2× low; the evidence is in `references/xraydb_two_carrier/CASE.md`.
- Details: `physics_note.md` §4.

## What the uncertainty is made of
*Which of these terms matter for absolute flux, and which for normalising (relative flux at one energy, or across energies), is sorted in `UNCERTAINTY.md`.*

| Term | Size | Note |
|---|---|---|
| Effective collection length (guarded chamber, measured 2026-11-13) | **±1.4 %** | l_eff = 61.9 mm is now IN the formula (2-D field model of the measured chamber). What remains is the model's spread over the dimension tolerances (guard gap, guard recess, collector length, beam height, HV plate, plate gap at the beam track) plus 0.5 % for the 2-D approximation. Before 2026-11-13 this was a one-sided 0 to −13.6 % for an unknown, unguarded geometry. An absolute calibration (pixel detector + foils) would test it |
| μ_en/ρ tables | ±3 % | |
| W | ±0.6 % | |
| SR570 gain × V2F scale (incl. V2F input loading) | ±0.7 % | type B. The manual spec is ±0.5 %. Widened 2026-11-13 because MonC's SR570 ranges, measured end to end, reach +0.6 %, and MonP's own unit is unmeasured (`ELECTRONICS_CONCLUSIONS.md`) |
| Cross-section fit in the live calc | ±0.9 % | worst case, vs log-log NIST at 25 keV; 0.6 % vs its NIST-anchored target |
| Gas density with the site-mean constants | ±0.8 % (1σ) | ±0.2 % with hourly airport pressure + Sensor2 temperature |
| Dark offset (subtracted live since 2026-11-12; MonP's no-beam rate at 500 nA/V was 182–227 Hz) | ≤0.1 % above 100 kHz | the residual after subtraction |
| Mono energy readback (added 2026-11-17) | ±0.4 % | an ASSUMED 0.1 % energy error (no edge scan yet) × d ln Φ / d ln E: 2.2 below 15 keV, at most 3.7 (MonP best estimate near 30 keV) (CHAMBER_FACTS F9.7) |
| **Total** | **±3.58 %** | quadrature sum of μ_en 3, W 0.6, electronics 0.7, density 0.2 (live), fit 0.9, collection length 1.4, energy readback 0.4; the live bounds are × 0.964 / × 1.036 below ~13 keV. Not checked against an absolute reference: only the pixel-detector + foil anchor could test it |

Above ~17 keV photoelectrons can hit the plates before stopping, so the standard formula *under*-counts photons. A Monte Carlo of each chamber as mounted (10.85 mm gap), validated against Grün's measured electron depth–dose in air, gives the signal lost (photoelectric share only: Compton electrons are too slow to reach a plate):
- **MonP** (plates vertical, E-vector toward them; beam taken as centred): 0 at ≤15 keV, 6 % at 20 keV, 27 % at 25 keV, **43 % at 30 keV**.
- **MonC** (plates horizontal, E-vector along them): 0 at ≤15 keV, 2 % at 20 keV, 14 % at 25 keV, **27 % at 30 keV**.

Each lane publishes its own **wall-loss-corrected best estimate** with its own bounds (`physics_note.md` §3.1).

## Live calculation (installed 2026-11-12)
**`15IDC:util:userTran1.P` = MonP exit flux in photons/s, updated every second.** Operator guide: `calc/OPERATOR.md`. Maintainer notes: `calc/HANDOFF.md`.
- It is a utilioc transform: 16 short expressions, each ≤39 characters, using
  - live inputs: MonP counts and count time, the MonP SR570 gain, the mono energy readback, hutch temperature;
  - the background estimate (userTran2, subtracted), and the live pressure (LOT airport, carried to 228 m, every 15 min; `calc/PRESSURE.md`).
- **The result is `userTran3.L` (MonP) / `userTran6.L` (MonC)**, between its bounds `.D` and `.E`. `userTran1.P` / `userTran4.P` is the uncorrected formula, not the result.
- Every reading carries a status code (`userCalcOut1/4.VAL`, a sum of bits, each its own PV `userTran7/8.F–K`) with MINOR/MAJOR severity. See calc/OPERATOR.md, "Status code".
- Its energy formula is a minimax fit to NIST: within 0.6 % of its NIST-anchored target, and 0.9 % of log-log NIST (worst at 25 keV), over 5–30 keV. It agrees with the full NIST calculation on live inputs to 0.6 % (`calc/soak_check.py`).

**First live reading** (2026-11-12 13:50): mono at 30.0 keV, MonP 75.2 kHz at 500 nA/V, hutch 22.2 °C → **3.66 × 10¹² photons/s at the MonP exit.**
- At 30 keV that is the *uncorrected* formula. The wall-loss-corrected best estimate, live as `userTran3.L`, read 7.5 × 10¹² ph/s, range 5.3–8.9 × 10¹² (2026-11-12 ~16:05 local, after the MC).
- With the photoelectric-share fix (2026-11-13) the same reading gave 6.9 × 10¹² ph/s, range 4.9–8.6 × 10¹².
- **With the measured chamber (2026-11-13: l = 6.19 cm, MonP's own wall-loss fit for the 10.85 mm gap, symmetric bounds), the same reading gives a formula flux of 3.56 × 10¹² and a best estimate of 6.2 × 10¹² ph/s, range 5.0–7.7 × 10¹² (+23 % / −20 %).** (Recomputed after the 2026-11-13 refit; METHOD_REVIEW §1d.)
- The 10 keV numbers above do not have the wall-loss caveat.

**MonC (installed 2026-11-12):** a lane on `userTran4-6` / `userCalcOut4-5` (`calc/lanes.py`). Its exit flux is `15IDC:util:userTran4.P`. It has the same physics, status and symmetric terms, but **its own wall-loss fit**: MonC is the same chamber design mounted with its plates horizontal (since 2026-11-13). At install there was no beam at MonC: the scaler read ≈58 Hz, and the background estimate settled at 58.5 Hz, against 58.8 Hz measured independently by the Experimenter session.
