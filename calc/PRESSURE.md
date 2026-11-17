# How the N2 pressure is used

*Recorded 2026-11-12. Data flow, physics, sensitivities, failure behaviour and limits of the live pressure input to the MonP and MonC flux calculations.*

## 1. Why pressure matters
An ion chamber's response is set by how many photons the N2 between its plates absorbs. That is proportional to the gas density, ρ = P·M / (R·T). The chambers flow N2 to an open outlet, so the gas is at hutch pressure: the outlet tube adds ~0.3 Pa, i.e. 0.0003 % (physics_note §3.3, A1). Hutch pressure is outdoor pressure, which moves with the weather by ±0.72 % (1σ), and by up to −3.4 % / +2.1 % over 2025.

## 2. Data flow
```
LOT ASOS, Lewis University Airport, Romeoville, 205 m, ~14 km from the APS
   │   altimeter setting (inHg), reported about every hour (:45-:55)
   ▼
IEM current-observation JSON (primary)  ──or──  NOAA Aviation Weather Center METAR (fallback)
   ▼
tools/asos_pressure.py, on the production host in ~/xray_fluxor/
   cron: 7,22,37,52 * * * *, service account, installed by the user 2026-11-12
   • pressure at the chambers: P = (A^0.190284 − 8.4228807e-5·228)^(1/0.190284), A in hPa
     (the altimeter setting carried along the standard atmosphere to the hutch's 228 m [user];
      LOT itself is at 205 m, so this is 0.27 % below LOT's station pressure)
   • guards: 95 < P < 104 kPa and observation ≤ 2 h old; otherwise it writes nothing
   • log: ~/xray_fluxor/logs/pressure.log, one line per run
   ▼ writes (CA put, read back)
15IDC:util:userTran1.G   N2 pressure, kPa             ← the MonP flux slot's pressure input
15IDC:util:userTran3.H   0                            ← resets the "seconds since update" counter
   │
   ├─ userTran1  K = G · 3.369272e-3 / (F + 273.15)    N2 density, g/cm³ (F = 15ID:Sensor2:Temperature, °C)
   │             O = 1 − exp(−6.19·M·K)               fraction absorbed over l_eff = 6.19 cm (CHAMBER_FACTS F4.2; M = μ_en/ρ)
   │             P = J·I·2.17205e12/E / O · exp(−6.19·N·K)   photons/s at the exit (N = μ/ρ, exit transmission)
   │
   ├─ userTran4  (MonC) G is linked to userTran1.G (NPP NMS), and the same K, O, P follow
   │
   ├─ userTran3/6  I = userTran1/4.K (live density); B = E·(1.1221e-3/I)^0.568 (density-scaled energy)
   │             C = wall loss evaluated at B, so the wall-loss correction follows the live density
   │
   └─ userTran3.H counts +1 per 1 s scan; userTran6.H (MonC) reads it by link
                flags slots userTran7/8: H-bit = (userTran3.H > 7200) → status code bit 4 → MINOR
```
One updater serves both monitors. The constant 3.369272e-3 is M/R in g/cm³ per (kPa/K): 28.0134 / 8.314462618 / 1000.

## 3. Sensitivity of the published numbers to pressure
`calc/monp_transform.full_physics()` and the wall-loss Monte Carlo variants give:

| E (keV) | direct effect: d ln(flux)/d ln(P), **applied live** | wall-loss effect d ln(best)/d ln(P), MonP (live fit) | MonC (live fit) |
|---|---|---|---|
| 8 | −1.03 | 0 | 0 |
| 10 | −1.01 | 0 | 0 |
| 15 | −1.005 | 0 | 0 |
| 20 | −1.00 | −0.46 | −0.20 |
| 25 | −1.00 | −0.71 | −0.43 |
| 30 | −1.00 | −0.93 | −0.64 |

(Per lane since 2026-11-13: each lane has its own wall-loss fit for its chamber as mounted, 10.85 mm gap.)

- **Direct.** About −1 % in flux per +1 % in pressure. Denser gas absorbs more, so each count stands for fewer photons. The tiny extra above 1 at low energy is the exit-transmission term.
- **Through the wall loss.** Denser gas shortens the photoelectron tracks (CSDA range ∝ T^1.76/ρ), so less energy reaches the plates.
  - The bounds slots now evaluate the Monte Carlo fit at the **density-scaled energy** E_eff = E·(ρ₀/ρ)^(1/1.76). Here ρ₀ = 1.1221e-3 g/cm³ is the MC's reference density, and ρ is the live density `userTran1/4.K`.
  - Check against each lane's MC runs at ±3 % density (30 keV; `analysis/out/wall_loss/<lane>/density_0.97.csv`, `density_1.03.csv`):
    - MonP: the live fit gives −0.93, the MC −0.83.
    - MonC: the live fit gives −0.64, the MC −0.54.
    - The scaled fit overstates the MC's density dependence by ~0.1 on both lanes. At the live ±0.2 % density error that is below 0.03 % on the result. (Before 2026-11-13, with one 10 mm-gap fit, it understated it: −0.93 against −1.09; METHOD_REVIEW.md M6, Q3.)
  - With it, the 30 keV best estimate's total pressure sensitivity is ≈ −1.9 %/% on MonP and ≈ −1.6 %/% on MonC.

Size of the live pressure effect, in practice:

| Interval | Typical change, 1σ or median | Extreme |
|---|---|---|
| Within a scan of minutes | <0.03–0.2 % | |
| Across a day | 0.4 % median | 3 % |
| Across a 3-day beamtime | | 4.3 % |

Before the live feed, all of this was a systematic error in absolute flux and in day-to-day comparisons. It is now removed, to the accuracy in §4.

## 4. Accuracy of the live value
| Term | Size | Status |
|---|---|---|
| Station-to-site transfer (LOT vs four stations 12–42 km away, 2025) | 0.05 % (1σ), ≤0.1 % (95 %) | measured (`analysis/out/asos_intercompare.txt`) |
| Elevation: chambers at 228 m vs LOT at 205 m | corrected, −0.27 %. Residual ≈ ±0.01 % from the real vs standard temperature lapse | user-given 228 m |
| Report resolution (0.01 inHg) and the ≤1 h age | ≤0.03 % + ≤0.03 % | |
| Chamber vs hutch (flow back-pressure) | 0.0003 % | confirmed open outlet (user) |
| Hutch vs outdoor (HVAC) | ≤0.025 % | assumed |
| **Pressure, total** | **≈ ±0.1 %** | |
| Temperature (Sensor2 vs the gas in the chambers) | 0.34 % per K | the sensor's placement relative to the chambers is not known |

Density overall: ≈ ±0.2 %, if Sensor2 represents the chambers to ±0.5 K.

## 5. When things go wrong
| Situation | What happens | What to do |
|---|---|---|
| A fetch fails (network, HTTP, a bad report) | the log says `FETCH-FAILED` / `REJECTED`; nothing is written; G keeps its last value; H keeps counting | nothing, unless it persists |
| No good update for 2 h | bit 4 (`userTran7.H`, `userTran8.H`) → 1, so the status of both lanes goes MINOR. The flux keeps using the last pressure | check `logs/pressure.log` and network access from the host |
| The updater or cron is gone | as above, indefinitely. The error grows with the weather, typically 0.4 %/day, up to ~3 %/day | reinstall the cron line (schedule in `tools/asos_pressure.py` CRON_SCHEDULE; full line in `calc/HANDOFF.md`), or set G by hand |
| utilioc restarts | G and H are restored by autosave; H resumes counting | nothing |
| Manual override | `caput 15IDC:util:userTran1.G <kPa>` is used until the next good update overwrites it. Site mean at 228 m: 98.99 kPa | to pin a value, disable the cron line first |

## 6. What uses pressure, and what does not
- **Uses it live:** MonP and MonC flux (`userTran1.P`, `userTran4.P`), and through them the best estimates and bounds (`userTran3/6.L, D, E`).
- **Not dependent on pressure:** the cross-section fits (they are per gram).
- **Follows live density through E_eff:** the wall-loss correction (§3).
- **Not affected:**
  - the background estimates (they are count rates);
  - the status code, except through the pressure-age flag.

## 7. Check it
```bash
tail -3 ~/xray_fluxor/logs/pressure.log                 # on the host: recent writes
```
On the PC (pyepics), read:
- `15IDC:util:userTran1.G` (kPa);
- `15IDC:util:userTran3.H` (seconds since the last update; below 900 after a :07/:22/:37/:52 run);
- `15IDC:util:userTran1.K` (density, g/cm³).

First live values, 2026-11-12:

| Time (UTC) | Pressure | LOT observation |
|---|---|---|
| 21:23Z | 98.948 kPa | 20:47Z obs |
| 21:52Z | 99.014 kPa | 21:45Z obs |
| 22:36Z | **98.743 kPa** | 21:45Z obs; first run with the 228 m elevation |

## 8. Direct test of the density correction (2026-11-17, first run)
`analysis/density_slope_test.py` (report `analysis/out/density_slope_test.txt`, figure `figures/out/density_slope_test.png`) regresses ln(MonP current / DBPM sum) on ln ρ in beam-on archiver data, 2026-11-12 18:42Z to 2026-11-17 15:01Z.
- **All archived data are at 30.001 keV** (no row below 15 keV), so this tests the combined direct + wall-loss correction. Expected slope at 30 keV: 1.93 (live fit) or 1.83 (MC), from §3. Absorption only would give 1.00.
- ρ moved 2.04 % over the window (P 2.05 %, Sensor2 T 0.32 %), but only 0.15–0.68 % within any one day.
- Headline (FX4 SumAll, quadrant-balance cut, per-day intercepts): **b = 2.14 ± 0.58** (hour-bootstrap SE; 95 % [1.12, 3.32]). ln P alone 1.75 ± 0.54; −ln T alone 4.2 ± 1.9 (T moved too little to say anything).
- Across the 8 analysis variants b runs 2.14–4.02, more than 2 SE, so the SE understates the systematic error. **Reading: b is positive and clearly above the absorption-only value of 1.0 in the headline, compatible with the live correction, but not a measurement of it.** A below-15 keV run is still needed for the clean test. Rerun when the beam is at another energy.
