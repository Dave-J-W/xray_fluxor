# Handoff: monitor counts or current → photons/s

*For an agent that has to turn ChemMatCARS ion-chamber readings into photons per second: scaler counts for MonP and MonC,
current for the E-station IC-500-50. Written 2026-11-18 against commit a5c4f0f (local; published as 67b70b0). Every
number below is reproduced by the commands shown. The source is https://github.com/Dave-J-W/xray_fluxor; clone it
(`RUNBOOK.md` §1).*

## Read this first
- **Read only.** Never write a PV, never change an SR570 gain or offset (always the user's), never touch MonP's
  electronics. Pulling archived data and `caget` are fine.
- **Always give a number.** A doubtful input gets a flag and wider bounds, not a refusal (user rule).
- The result is photons/s **at the chamber's exit plane**: the downstream end of the collection region, before the
  Kapton exit window. Windows and air to the sample are not included.
- Quote it as the **best estimate with its stated low and high bounds** (`UNCERTAINTY.md` §3.3: bounds, not a
  confidence interval).

## 1. Pick the route

| Situation | Route |
|---|---|
| Times since 2026-11-17, any lane | **A: read the live result from the archiver** |
| Earlier times, or other count times or gains than the live calc saw (spec scans, for example) | **B (MonP, MonC)** or **C (E-station)**: recompute from the raw inputs |
| A quick estimate | **D**: the per-Hz table |

Recompute (B, C) rather than trust archived lane values from **before 2026-11-13**. That day the collection length
changed from 6.0 to 6.19 cm, the wall-loss fits were redone, and the bounds became symmetric. Values archived earlier
used the old constants.

## 2. Route A: the live result (photons/s, already computed)
Archived since 2026-11-17 (prefix `15IDC:util:`; the `pv-retrieval` skill says how to pull raw, unresampled data):

| Lane | Best estimate | Low / high | Formula only (not the result) | Status code |
|---|---|---|---|---|
| MonP | `userTran3.L` | `userTran3.D` / `.E` | `userTran1.P` | `userCalcOut1` |
| MonC | `userTran6.L` | `userTran6.D` / `.E` | `userTran4.P` | `userCalcOut4` |
| E-station | `userTran10.L` | `userTran10.K` / `.M` | `userTran9.P` | `userCalcOut9` |

Archived inputs, the same prefix: `userTran1.J` (MonP net rate, Hz), `userTran1.E` (energy), `userTran1.G` (live
pressure, kPa), `userTran2.L` (MonP background), `userTran4.J` (MonC net rate), `userTran9.A`, `.B`, `.C`, `.G`.

The archiver stores the calcouts **without `.VAL`**: use `userCalcOut1`, not `userCalcOut1.VAL`.

**Status bits** (`calc/OPERATOR.md`, "Status code"):

| Bit | Meaning | Effect on the number |
|---|---|---|
| 1 | E above 12.5 keV | informational: the wall-loss band is in use |
| 2 | background stale | the dark may be wrong. At low rates that biases the number |
| 4 | pressure older than 2 h | the last pressure is used |
| 8 | no beam | the number is ~0 and the bounds mean nothing |
| 16 | energy outside 4.9–30.5 keV | MAJOR: the cross-section fits are extrapolated |
| 32 | count time ≤ 0 | MAJOR: there is no rate |

The E-station bits differ: 2 means recombination above 5 %, 8 means a current below 50 nA.

**MonC's chamber has been unplugged since 2026-11-13 10:13** (`CHAMBER_FACTS.md` F7.2). Its lane runs, but its number
is not a beam measurement until the chamber is reconnected.

## 3. Route B: MonP and MonC from counts (the live calc's own arithmetic)
**Inputs per reading:**

| Input | MonP | MonC |
|---|---|---|
| counts | `15IDC:scaler1.S3` | `15IDC:scaler1.S4` |
| count time | `15IDC:scaler1.T` | the same |
| SR570 sensitivity indices (`sens_num`, `sens_unit`) | `15IDC:A2sens_num`, `15IDC:A2sens_unit` | `15IDC:A3sens_num`, `15IDC:A3sens_unit` |

The A2/A3 settings have been archived as MONITOR since 2026-11-12.

The other inputs are shared:
- **Energy, keV:** `ID15A1:DCMM:XTAL:E.RBV` (the C-station DCM).
- **Hutch temperature, °C:** `15ID:Sensor2:Temperature`.
- **Pressure, kPa:** `15IDC:util:userTran1.G`, or the Lewis University Airport (LOT) hourly pressure carried to 228 m
  (`calc/PRESSURE.md`). With neither, use 98.99 kPa (the site mean) and expect ±0.8 % instead of ±0.2 %.
- **Dark rate, Hz:** the no-beam rate at the same SR570 setting, measured after the last gain change. MonP read 182–227
  Hz at 500 nA/V (F13.1).

**Sensitivity:** sens_num indices 0…8 are 1, 2, 5, 10, 20, 50, 100, 200, 500. sens_unit 0…3 is pA/V, nA/V, µA/V, mA/V.
So 500 nA/V is (8, 1), and 5 µA/V is (2, 2).

```python
import sys; sys.path.insert(0, "calc")                       # from the repository root
import monp_transform as mt, quality_slots as qs
v = mt.evaluate(A=224000, B=1.0, C=8, D=1, E=10.0, F=24.9, G=98.99, H=200.0)
#   A counts, B time s, C sens_num, D sens_unit, E keV, F hutch degC, G kPa, H dark Hz
b = qs.bounds(v["P"], 10.0, v["K"], lane="MonP")            # lane="MonC" for MonC
# v["P"] = formula photons/s; b["L"] best estimate; b["D"], b["E"] low, high; b["F"], b["G"] +%, -%
```
These are the Python mirrors of the slot expressions, checked against the strings that run. They give exactly the
live numbers:

| Case (500 nA/V, dark 200 Hz, 98.99 kPa, 24.9 °C) | best estimate, photons/s | low – high |
|---|---|---|
| MonP, 10 keV, 224.0 kHz | 9.776 × 10¹¹ | 9.424 – 10.128 × 10¹¹ (±3.6 %) |
| MonP, 30 keV, 75.2 kHz | 6.320 × 10¹² | 5.077 – 7.784 × 10¹² (+23.2 / −19.7 %) |
| MonC, 30 keV, 75.2 kHz | 4.916 × 10¹² | 4.182 – 5.811 × 10¹² (+18.2 / −14.9 %) |

These are the worked examples of `METHOD.md` §9.

A **spec scan** records counts and count time per point, but not the SR570 setting. Take the setting from the archive
at the scan's time, and check that it didn't change during the scan. The `monitor-uncertainty-from-spec-scans` skill
covers using monc/monp from spec files.

## 4. Route C: E-station IC-500-50 from current (the `fluxor` package)
```python
from fluxor.chains.tetramm import TetraMM
from fluxor.chambers.ic500_50 import Ic500_50
from fluxor.core import evaluate
chain = TetraMM(("Current3", "Current4"), rng=0, darks={"Current3": 0.0, "Current4": 0.0}, dark_age_h=1.0)
r = evaluate(Ic500_50(), chain, {"channels": {"Current3": 2400.0, "Current4": 1600.0}}, 10.0, p_kpa=98.99, t_c=22.2)
r.flux_best, r.flux_low, r.flux_high, r.sigma_rel, r.budget, r.flags
# -> 4.351e12, 4.117e12, 5.221e12 photons/s; sigma 4.42 %
```
- Readings are in **nA, per channel**. The signal is on TetrAMM channels 3 and 4 only. **Use the sum of those two
  channels, not the IOC's all-channel sum**, which adds the unused channels' dark.
- The E-station PV names (TetrAMM, energy, temperature) are not in the public repository. Ask the user.
- **The energy is the side-bounce mono, not the DCM.** A first run with the DCM readback was void.
- **Darks:** the reading with beam off and bias on, the same day. Without one, flag `dark_stale_or_age_unknown`; the
  dark moves ~1 nA from week to week.
- **The high bound is dominated by recombination.** The beam's height and width have never been measured. At 4 µA the
  loss is 0.43 / 1.42 / 14.2 % (low / central / high), and the best estimate carries the central value.
- Every assumed number raises an `assumed:<name>` flag. `fluxor/PARAMETERS.md` says what would replace it.
- The package also has the FX4 chain and MonP/MonC (`fluxor/chambers/cmc_guarded.py`, `fluxor/chains/sr570_v2f.py`). For
  MonP and MonC prefer route B:
  - the package interpolates NIST directly, so it differs from the live calc by up to 0.9 % (0.2 % at 10 keV);
  - it carries no cross-section-fit term;
  - its count noise is √N, which overstates the V2F's noise.

## 5. Route D: quick estimate
At 500 nA/V and the site mean gas, one net Hz of MonP is (`RESULT.md`):

| E (keV) | 5 | 8 | 10 | 12 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|---|---|---|
| photons/s per Hz, formula | 9.13e5 | 2.65e6 | 4.37e6 | 6.56e6 | 1.08e7 | 2.02e7 | 3.26e7 | 4.78e7 |
| MonP best estimate per Hz | 9.13e5 | 2.65e6 | 4.37e6 | 6.56e6 | 1.08e7 | 2.18e7 | 4.42e7 | 8.43e7 |

Scaling:
- Scale with the sensitivity: ×2 at 1 µA/V, ×10 at 5 µA/V.
- With the gas density: +0.34 % per K warmer, −1 % per kPa higher.
- MonC's wall-loss correction is smaller above 18 keV: ×1.02 at 20 keV, ×1.16 at 25, ×1.37 at 30.

The formula (`METHOD.md`):

Φ = (N − D)·S / g · W / (e·E) · 1 / (1 − exp(−(μ_en/ρ)·ρ·l)) · exp(−(μ/ρ)·ρ·l) · 1 / (1 − Λ_s(E_eff))

| Symbol | Value |
|---|---|
| g | 1e5 Hz/V |
| W | 34.8 eV, **one** charge per ion pair |
| l | 6.19 cm for MonP and MonC; 5.0 cm for the IC-500-50 |
| μ, μ_en | NIST Hubbell–Seltzer, nitrogen |
| Λ_s | the lane's wall-loss fit, 0 below ~18 keV (`METHOD.md` §6) |

For a current I, replace (N − D)·S/g with I − I_dark.

## 6. Traps (each one has produced a wrong number here)
- **xraydb's `ionchamber_fluxes` is 2× low by default** (`both_carriers=True`; evidence in
  `references/xraydb_two_carrier/CASE.md`). Use one carrier.
- **xraylib 4.3.0 `CS_Energy` for N is wrong above 10 keV** (10–48 % low). Use NIST.
- **The gas density is not 1 atm and 20 °C.** That makes the flux 3.8 % low. Use the live P and T, or the site mean.
- **√N is not the error bar of V2F counts.** The counts are periodic, not Poisson. The electronics noise is
  0.001–0.003 % per 1 s count, about 190× below √N.
- **Gain changes and state errors.** Across an SR570 gain change the normaliser steps (MonC up to +0.62 % at the nominal
  ratio, F5.6). EPICS shows what was sent, not what the unit holds: a front-panel change or a switched-off unit is a
  factor of 2–10, invisible in EPICS. Cross-check MonP/MonC continuity.
- **Low rates need the dark.** The dark error is δD/N: 1 % at 10 kHz, 10 % at 1 kHz.
- **Above ~13 keV the wall loss dominates.** The formula alone (`userTran1.P`) is 0.57 of the result at 30 keV, by
  design. Use the best estimate.
- **The E-station TetrAMM can freeze** with no alarm (readings stop changing). Check that the input changes.

## 7. How good is it
Absolute, below 13 keV: ±3.6 % for MonP and MonC. Above 13 keV it is asymmetric, up to +23 / −20 % at 30 keV on MonP.
At E-station: −5.5 / +20 % at 10 keV and 4 µA.

None of these has been checked against an independent flux measurement.

For **normalising** (relative error), most terms cancel. At one energy, using the live photons/s and one gain, it is
≲0.2 %. Across energies it is ~1–2 % below 13 keV, and the wall-loss band above. The full sort is in `UNCERTAINTY.md`.

## 8. Check your setup before using it
```bash
python -I -X utf8 -m unittest discover -s tests -t .
```
```bash
python -I -X utf8 calc/monp_transform.py
```
```bash
python -I -X utf8 fluxor/example.py
```
Then reproduce the three rows of the table in §3. If they match, your inputs are wired the way the live calc's are.
