# MonP: scaler counts to photons/s

*Physics and hardware note, phase 1, written 2026-11-12. The scope is MonP only. Software comes later.*

**Evidence tags.** Every quantitative claim carries one.
- **[MEASURED]** comes from C-station hardware. None exist yet.
- **[SOURCE]** is quoted from a saved database query or reference in this repo.
- **[DERIVED]** is computed here from tagged inputs.
- **[PROVISIONAL]** is from memory, or from a user statement not yet checked. Treat it as a hypothesis.

**Terms.**
- **CMC-custom**: C-station's custom-built ion chambers (MonP, and presumably MonC). Every geometry statement in this note refers to CMC-custom chambers. Other chamber types come in a later addendum.
- **Site mean**: 98.99 kPa and 24.9 °C, the long-term mean hutch conditions at the chambers' 228 m (§3.3). The 2025 LOT station mean (99.26 kPa at 205 m), carried up 23 m.

---

## 1. Reference plane and result

Photons/s are referred to the **MonP exit**: after the collection plates, before the Kapton exit window (user, 2026-11-12). The Kapton windows and the air path to the sample are a later step.

Signal chain:
- **Ion chamber:** flowing N2, CMC-custom and **guarded**, measured by the user on 2026-11-13 (MonC in hand; MonP is the same design). The facts are listed in `CHAMBER_FACTS.md` §1, and defined in `analysis/cmc_chamber_geometry.py`.
  - The collector (upper plate, 60.5 mm, F1.4) faces the HV plate (75.5 mm, F1.6) across a 10.85 mm gap (F1.5). Grounded guard blocks sit beside the collector (F1.1, F1.9, F1.10).
  - MonP's plates are **vertical**, so its field is horizontal (F1.2). MonC's are horizontal (F1.3).
  - HV is 2.7 kV from the supply readout, not verified (F3.1).
  - (The provisional description used until 2026-11-13, an unguarded chamber of 6 cm plates 1 cm apart, is superseded.)
- **Beam:** horizontal FWHM ~1 mm, vertical FWHM 20–40 µm [user] (F2.7, F2.8).
- **SR570:** sensitivity S, currently 500 nA/V for MonP at 10 keV.
  - Maximum output is **+5 V** [user, confirmed; manual: "±5 V into a high impedance load (50 Ω output impedance)"].
- **N101VTF V2F:** gain x1, **0–10 V input range** (the user confirms this is the current and historical setting), so 10 V → 1 MHz, i.e. 1e5 Hz/V [SOURCE: datasheet].
  - The SR570's 5 V therefore gives 500 kHz. Only half the V2F range is used.
- **VME scaler:** Joerger VSC16 [SOURCE: `references/vsc16man-A.pdf`].
  - 16 channels, 32 bit, up to 40 MHz.
  - TTL inputs into 50 Ω by default (500 Ω optional), which matches the N101VTF's 50 Ω-capable outputs.
  - It has an on-board 10 MHz crystal output (±0.01 %) for timing.
- **Operating rule** [user]: the SR570 gain is reduced when the count rate goes above 400 kHz (4 V), to stay clear of saturation.

**Conversion** (net rate N = N_meas − N_dark, in Hz):

```
i      = N · S / (1e5 Hz/V)                                        SR570 + V2F
I_p    = i · W / ( e · E · (1 − exp(−(μ_en/ρ)·ρ·l)) )              flux entering the plate region
I_exit = I_p · exp( −(μ/ρ)·ρ·(l + l_gap) )                         flux at the reference plane
```

The terms:
- **ρ** is the N2 density from the chamber's pressure and temperature (§3.3).
- **l = l_eff = 6.19 cm** (CHAMBER_FACTS F4.2): the guarded collector's effective collection length, from a 2-D field model of the measured chamber, ±1.4 % (F4.4; §3.1). Since the chamber was measured, μ_en/ρ (±3 %) is the dominant uncertainty.
- **l_gap** is the N2 path from the plate end to the exit window. It is not yet measured, so 0 is used.
- **W = 34.8 eV** (§2.1) and **e = 1.602176634e-19 C** (exact).
- **μ_en/ρ and μ/ρ** are NIST Hubbell–Seltzer values for N, log-log interpolated (§2.2).

Gas and windows *upstream* of the plates do not enter, because the reference plane is downstream.

**Photons/s at the MonP exit per net Hz, at S = 500 nA/V and l_gap = 0** [DERIVED; `data/queries/out/monp_exit_table.csv`]. The ph/s-per-Hz value scales linearly with S.

| E (keV) | absorbed in plates | ph/s per Hz, site mean (98.99 kPa, 24.9 °C) | ph/s per Hz, 101.325 kPa & 20 °C | N2 loss per cm of l_gap |
|---|---|---|---|---|
| 5  | 18.7 % | 9.40e5 | 8.99e5 | 3.5 % |
| 8  | 4.70 % | 2.75e6 | 2.64e6 | 0.85 % |
| 10 | 2.35 % | **4.50e6** | 4.32e6 | 0.43 % |
| 12 | 1.32 % | 6.75e6 | 6.48e6 | 0.26 % |
| 15 | 0.65 % | 1.10e7 | 1.06e7 | 0.14 % |
| 20 | 0.26 % | 2.09e7 | 2.00e7 | 0.07 % |
| 30 | 0.074 % | 4.90e7 | 4.71e7 | 0.034 % |

The CSV has the full grid from 5 to 30 keV in 1 keV steps. The physics note's own conditions (1 atm, 20 °C) read 3.8 % low against the site mean.

**Operating points at 10 keV and 500 nA/V, site mean** [DERIVED]:

| Point | Rate | Flux at MonP exit |
|---|---|---|
| Dark offset | 50–100 Hz | ≈ 2–4e8 ph/s equivalent. Negligible at full beam; it matters for attenuated or detuned beam (§3.5) |
| Typical full beam | 224 kHz (2.24 V, 1.1 µA) | ≈ 1.0e12 ph/s |
| Gain-change threshold | 400 kHz (4 V) | **1.8e12 ph/s**: above this, the SR570 goes to 1 µA/V |
| SR570 output limit | 500 kHz (5 V) | 2.2e12 ph/s; saturates beyond this |

The V2F's own 1 MHz full scale is never reached with the 0–10 V setting.

**The V2F's 0–5 V range: one extra bit, and when it is worth having.**
- Switching the internal range to 0–5 V makes the conversion 2e5 Hz/V. The SR570's 5 V then gives 1 MHz, and every count is worth half as many photons. That is exactly one extra bit (a factor of 2) of counting resolution.
- **It only helps when the counting quantization (±1 count per gate) is the limiting noise.** It rarely is:
  - At 1 s gates and ~2e5 Hz, quantization is 5e-6, far below the SR570 and beam noise.
  - It starts to matter for short gates. At 10 ms and 200 kHz, ±1 count is 0.05 %, and it would become 0.025 %.
  - It also matters for very low rates.
- **Costs:**
  - The V2F must be recalibrated in that mode; the datasheet calls only x1 / 0–10 V the "accurate calibrated default".
  - Hz/V must become configuration in any software.
  - The 400 kHz gain-change rule becomes 800 kHz.
  - The SR570's maximum output would sit at the V2F's 1 MHz full scale, with no headroom.
- **Recommendation:** leave it at 0–10 V unless fast (≲0.1 s) gating or very low flux becomes a goal.

---

## 2. Constants we do not measure

### 2.1 W(N2), the mean energy per ion pair
| Value (eV) | Source | Tag |
|---|---|---|
| 34.8 | ICRU Report 31 (1979) and Knoll Table 5-1, as tabulated in xraydb `ionization_potential('N2')` | SOURCE (xraydb 4.6.1 docstring, saved in `data/queries/W_values.md`) |
| 34.8 | Jesse & Sadauskis, Phys. Rev. 98, 1828 (1955) (N2 34.8, air 33.9). Called "well established, 34.8 ± 0.2 eV" in arXiv:1703.10032 | SOURCE (search abstract; full text not retrieved) |
| 34.6 | SSRL flux notes; also used by the CHESS calculator | SOURCE (`data/queries/web_calculators/`) |
| 35.0 | the physics note in `references/` | SOURCE |
| 33.97 (dry air) | ICRU Report 90 | SOURCE (search result); needed only for air-contamination estimates |

- **Adopted value: W = 34.8 eV ± 0.6 %.** The ± is the full spread of N2 values.
- **Energy dependence** [PROVISIONAL]. W rises for electrons below ~1 keV. At 10 keV about 4 % of the deposited energy goes to N K-shell Auger electrons (~0.4 keV). If those have W ~10 % higher, the effective W rises by ~0.4 %. That is within the band.
- No photon-specific N2 measurement was found. The closest is a photon W for dry air at 2.2–3.9 keV with 0.84 % uncertainty (Kato et al.), which is consistent with electron data.

### 2.2 μ/ρ and μ_en/ρ for nitrogen
Four sources were queried. Raw outputs are in `data/queries/out/`, and the comparison is in `compare_N.csv`.

| Source | μ/ρ vs NIST | μ_en/ρ (or equivalent) vs NIST | Independent of NIST? |
|---|---|---|---|
| NIST Hubbell–Seltzer (NISTIR 5632), z07 table | reference | reference | n/a |
| xraydb Elam (Scofield photo + Compton electron energy) | 0 to −4 % between grid points (NIST log-log interpolation on a coarse 10/15/20 keV grid) | within ±0.2 % up to 20 keV; −1.5 % at 25 keV | no: both rest on Scofield 1973 |
| xraydb Chantler FFAST | −4 % (photo −5 %) at 5–12 keV | n/a | **yes**: independent theory |
| xraylib 4.3.0 `CS_Energy` | n/a | agrees ≤10 keV; **−10 % to −48 % at 11–30 keV** | **rejected**, see below |

- **Adopted:** NIST μ_en/ρ ± 3 %. That is half the Scofield–Chantler spread, and in line with NIST's own note that the databases mostly agree within 5 %.
- **xraylib 4.3.0 is wrong here.** Above 10 keV its `CS_Energy(7, E)` is *smaller than its own photoabsorption* `CS_Photo(7, E)`, which is unphysical. It agrees with NIST at the 5–10 keV grid points and diverges above. Do not use xraylib's energy-absorption coefficients for N without re-checking a later release.
- **μ_en is the right coefficient** for the deposited energy. That the photo + Compton-electron model agrees with μ_en to 0.2 % confirms it. Rayleigh scattering deposits nothing, and N K fluorescence escape is negligible.
- **Absorbed-fraction form (METHOD_REVIEW.md M9).** The formula uses 1 − exp(−μ_en ρ l). The local-deposition form, (μ_en/μ)(1 − exp(−μ ρ l)), is smaller by 0.2 % at 5 keV, 0.11 % at 10 keV and 0.07 % at 30 keV. The formula's flux is therefore low by that much, which is negligible against the ±3 % on μ_en.

### 2.3 Other inputs
- **e** = 1.602176634e-19 C, exact. The note's 1.6e-19 is +0.14 % on flux.
- **N2 density:** ideal gas, ρ = P·M/(R·T) with M = 28.0134 g/mol. Real-gas compressibility at 1 atm is ~0.03 %, ignored.
  - The note's table implies ρ = 1.165e-3 g/cm³, i.e. 1 atm and 20 °C [DERIVED: 0.004519 cm⁻¹ / 3.879 cm²/g].

---

## 3. Uncertainty and systematics, largest first
*Which of these terms matter for absolute flux, and which for normalising (relative flux at one energy, or across energies), is sorted in `UNCERTAINTY.md`.*

### 3.1 Effective collection length l_eff
**Status 2026-11-13:** the chamber was measured by hand and is GUARDED (the bullet "Measured 2026-11-13" below). The calc now uses l = l_eff = 6.19 cm, and the residual collection term is ±1.4 % and symmetric. The unguarded analysis that follows is kept as the record of how the term was carried before; it no longer applies to these chambers.

**Beam geometry [user].** The beam is ~1 mm FWHM horizontally and 20–40 µm vertically. With MonP's vertical plates 10.85 mm apart (CHAMBER_FACTS F1.5), the beam's horizontal edges sit ~4.9 mm from each plate. The ionization is a thin horizontal ribbon at mid-gap.

**Fringe fields at the plate ends (history: the unguarded model used until 2026-11-13; the measured chamber is guarded, see "Measured 2026-11-13" below).** As first described [user, 2026-11-12], MonP had no guard electrodes, so this applied in full.
- Ion pairs made in the N2 just beyond the plate ends drift along fringe field lines, and some of them are collected. The result is l_eff > l.
- With no guards, the excess is a fraction of the gap per end. For a 1 cm gap that is ~0.3–0.8 cm on 6 cm, i.e. **δ = +5 % to +13 % in l_eff**. The true flux is the formula / (1 + δ), so **the computed flux is 5–11.5 % too high** [PROVISIONAL, geometry estimate]. This convention, flux ∝ 1/(1 + δ), is used throughout.
- How much of the fringe charge reaches the collector, rather than the grounded chamber body, depends on the plate thickness and the wall and window distances.
- A 2-D electrostatic (Laplace) model of the real geometry has now been built (below); it needs the chamber's wall distances to give a number. Only the absolute anchor (§5) settles it.

**Collection-length model, 2026-11-13** [DERIVED, geometry PROVISIONAL; `analysis/fringe_field.py` → `analysis/out/fringe_field_scan.csv`].

- **Method.**
  - A finite-difference Laplace solution in the beam–gap plane: collector at 0 V, HV plate at 1 V, the chamber body (side and end walls) at 0 V.
  - Field lines are traced from points on the beam line.
  - By Shockley–Ramo, a pair contributes e to the collector current if its field line ends on the collector, and 0 if it ends on the body. HV polarity does not matter.
  - l_eff is the length of beam line that ends on the collector.
- **Convergence.** The grid converges to ~1 % (0.2 mm vs 0.1 mm cells).
- **What decides it:** the **end gap**, from the plate ends to the end walls (window flanges), and to a lesser extent the **side gap**, from the plates' outer faces to the body. Plate thickness (1–3 mm) matters little.

| end gap → | 0.5 cm | 1 cm | 2 cm | 4 cm |
|---|---|---|---|---|
| side gap 0.5 cm | −2.3 % | +2.7 % | +5.3 % | +5.3 % |
| side gap 1 cm | −2.3 % | +3.7 % | +8.7 % | +9.7 % |
| side gap 2 cm | −2.3 % | +4.3 % | +12 % | +16 % |
| side gap 4 cm | −2.0 % | +5.0 % | +14 % | +22 % |

The table gives l_eff/L − 1 for 1 mm plates. 3 mm plates give similar values, up to +26 % at 4/4 cm.

- **Consequence (history, before the chamber was measured).** The low bound then, `LOW_FACTOR` 0.86, allowed l_eff up to +15.8 % (flux ×0.864), after the ±3.27 % symmetric terms then carried were taken out in quadrature. That covers chambers whose end walls sit within ~1–2 cm of the plate ends, but not one with distant walls (up to +26 %, flux ×0.79). Near end walls (≤0.5 cm) shorten l_eff slightly instead (−2 %).
- **Measured 2026-11-13 (user, MonC in hand; MonP is the same design): the chamber is GUARDED.** This supersedes the unguarded model above for the real chamber.
  - Wiring, by meter: the upper plate (60.5 mm) is the collector (BNC centre pin) and the lower plate (75.5 mm) is HV. Aluminium blocks beside the collector are grounded to the shell, so they are guard electrodes.
  - The blocks are ~1 mm from the collector ends, set back 0.51 mm from the collector plane (a larger clear aperture), 12.7 mm thick and mounted on the shell.
  - Shell: 95.16 × 101.4 × 44.5 mm outside. Aluminium plates, 1 mm thick (revised from 1/16"). The gap is 10.85 mm at the beam track (11.45 mm lower plate to guard face, minus ~0.6 mm), ±0.2 mm there and ±0.5 mm across the width, because the plates are not parallel. The upper plate's face is 0.6 mm inside the aperture's top ledge, so its 1 mm thickness straddles the ledge (confirmed by the user).
  - Windows: machined slots, 12.8 mm high with semicircular ends; about 64.5 mm long once the user's readings are reconciled with the exterior width held fixed (`slot_fit()`). They sit off-centre toward the inboard side, leaving ~30 mm on the outboard (electronics) side. The guards are ~63 mm wide (plate + a few mm inboard + 0.4 mm outboard).
  - All values and their tags are in `analysis/cmc_chamber_geometry.py`; the drawing is `figures/out/cmc_plates.png`.
  - **Result** (`analysis/collection_length_cmc.py`, 2-D Laplace + field lines, grid 0.05 mm): **l_eff = 61.925 mm**. The collection edge sits ~0.7 mm into each 1 mm guard gap; the 0.51 mm recess adds about 1.4 points over a flush guard.
  - **In the live calc since 2026-11-13: l = L_CM = 6.19 cm** in both the absorbed fraction and the exit transmission (`calc/monp_transform.py`).
  - Residual: one-at-a-time tolerances (guard gap ±0.5 mm, recess ±0.25 mm, collector length ±0.5 mm, beam height ±1 mm, HV plate −2 mm) move l_eff by −0.7 % to +0.8 %. In quadrature, plus 0.5 % for the 2-D model, that is **±1.36 %, carried as ±1.4 %** (`quality_slots.collection_term()`; `figures/out/leff_scan.png`).
- **Caveats.**
  - The model is 2-D. The plates are at least as wide as they are long, and the side walls in the third dimension would trim the far-wall extension somewhat.
  - It also neglects recombination in the weak far-fringe field. Collection there is slow but, at these ionization densities, should be complete. That is not verified.


**Photoelectron wall loss: the second big term, and it grows with energy.** This is the "full thermalization" caveat in the physics note, made quantitative [DERIVED; `analysis/wall_loss_bound.py` → `analysis/out/wall_loss_bound.csv`; NIST ESTAR ranges in `data/queries/nist_estar/`].
- Synchrotron light is polarized horizontally, and K-shell photoelectrons go preferentially along the E-vector (dN/du ∝ u², u = cos of the angle to E).
- At C-station the plates are vertical, so the E-vector points **straight at the plates**. This is the worst case, and the user's geometry confirms it.
**What "energy lost to plates" means, in plain words.**
- The ion chamber current comes from the photoelectron spending its energy making ion pairs in the gas, one pair per 34.8 eV. The flux formula assumes it spends **all** of it in the gas.
- If the photoelectron hits a plate while it still has energy, that leftover energy goes into the metal and makes no ion pairs. The current is then smaller than the formula expects.
- "Energy lost to plates" is that leftover as a fraction of the total. For example, 4.7 % at 15 keV means the current is 4.7 % below what the formula assumes. Ignoring it, the flux would be computed 4.7 % too low.
- "Upper bound" means the model lets every electron fly in a straight line. Real electrons zigzag, so they get less far from the beam and lose less. The true value lies between the two columns, or below the second.

**The model.**
- The model follows each photoelectron on a straight track whose length is k × its CSDA range (the total path length an electron of that energy travels before stopping), and counts the energy it still carries when it hits a plate.
  - k = 1 is an upper bound on reach.
  - Real tracks in N2 wander, so k = 0.5 is shown as an illustration, not a measurement.
  - The model uses a Gaussian beam of 1 mm FWHM in x, at 99 kPa and 22 °C.

| E (keV) | photoelectron CSDA range | signal lost to the plates, straight tracks (upper bound) | half-length tracks (illustrative) |
|---|---|---|---|
| 10 | 2.4 mm | 0 | 0 |
| 12 | 3.3 mm | 0 | 0 |
| 14 | 4.3 mm | 0.5 % | 0 |
| 15 | 4.9 mm | 4.7 % | 0 |
| 17 | 6.2 mm | 27 % | 0 |
| 20 | 8.3 mm | 41 % | 0.1 % |
| 25 | 12.4 mm | 59 % | 19 % |
| 30 | 17.1 mm | 71 % | 39 % |

Consequences:
- **At 10–13 keV, wall loss is zero** in every model. The 10 keV numbers above are unaffected.
- From ~15 keV upward the straight-track model alone gave anything from ~0 to tens of percent. **The Monte Carlo below replaces it.**
- **Harmonics:** a 30 keV photon from Si(333) is under-counted twice over: by the low μ_en, and by ~50 % wall loss (MC). MonP is nearly blind to third-harmonic contamination.
- **Energy scans:** across 15–30 keV, MonP's efficiency changes by up to ×2 from wall loss alone. Spectra normalized by MonP (or MonC) are distorted by that unless the corrected best estimate is used.
- Horizontal plates (E-vector parallel to the plates) would cut this loss substantially. The C-station chambers are vertical, so any comparison with another facility's chambers must check their orientation.

**Monte Carlo (2026-11-12): the wall loss, now computed** [DERIVED; `analysis/wall_loss_mc.py` → `analysis/out/wall_loss_mc*.csv`].
- **Method.** A single-scattering electron transport in N2 at ρ0 = 1.1221e-3 g/cm³ (99.26 kPa, 24.9 °C: the site mean before the 228 m correction; the live E_eff scaling accounts for the difference):
  - start: Sauter photoelectron angular distribution, E-vector toward the plates;
  - elastic scattering: screened-Rutherford (Wentzel/Molière);
  - energy loss: continuous slowing down from NIST ESTAR;
  - geometry: plates at ±5 mm, beam Gaussian 1 mm FWHM in x;
  - an electron reaching a plate gives it its remaining energy. Backscatter from the plate is not modelled, which makes the result slightly conservative.
- **Validation.** Normal-incidence pencil beams reproduce Grün's (1957) measured depth–dose curve for electrons in air (`analysis/out/wall_loss_mc_validation.csv`):
  - the depth holding 90 % of the energy is 0.74 R_G at 10, 20 and 30 keV (Grün: 0.74);
  - the dose peak sits deeper than Grün's 0.34 R_G: 0.39 R_G at 10 and 20 keV, 0.49 R_G at 30 keV.

| E (keV) | 15 | 16 | 17 | 18 | 20 | 22 | 25 | 28 | 30 |
|---|---|---|---|---|---|---|---|---|---|
| lost to the plates, per photoabsorption (MC) | 0.01 % | 0.16 % | 0.9 % | 2.8 % | 9.9 % | 19.0 % | 32.5 % | 44.1 % | 50.0 % |
| photoelectric share f_pe of μ_en | 0.996 | 0.994 | 0.993 | 0.990 | 0.986 | 0.979 | 0.964 | 0.939 | 0.925 |
| **signal** lost to the plates (f_pe × MC) | 0.01 % | 0.16 % | 0.9 % | 2.8 % | 9.7 % | 18.6 % | 31.4 % | 41.4 % | **46.2 %** |
| electrons reaching a plate | 0 | 0.7 % | 3.3 % | 8.6 % | 24 % | 38 % | 56 % | 68 % | 73 % |

(Statistical errors are ≤0.23 % absolute.)

- **Sensitivity** at 20 / 25 / 30 keV:

  | Variant | Loss at 20 / 25 / 30 keV |
  |---|---|
  | electron reach +10 % | 14.8 / 38.1 / 55.1 % |
  | electron reach −10 % | 5.2 / 26.3 / 45.0 % |
  | elastic σ ±20 % | 8.1–12.5 / 29.9–36.1 / 47.6–52.7 % |
  | beam 1 mm off-centre | 12.7 / 33.4 / 50.3 % |

  At 15 keV the 1 mm offset raises the loss to 0.5 %.
- **Why the signal loss is smaller (2026-11-13, METHOD_REVIEW.md M1).** The MC follows photoelectrons, so its loss is per photoelectric absorption. The signal also contains the Compton-electron energy, which is part of μ_en: f_pe = photo / (photo + Compton-electron), from xraydb (`data/queries/out/xraydb_N.csv`). Compton electrons carry ≤ 3.2 keV at 30 keV and travel < 0.3 mm in N2, so they never reach a plate 5 mm away.
- **Per chamber, as mounted (2026-11-13; supersedes the single 10 mm vertical-plate MC above for the live calc).**
  - `analysis/wall_loss_families.py` runs the MC for each chamber with the measured 10.85 mm gap. MonP: plates vertical, E toward them, beam taken as centred (ASSUMED, not measured), 1 mm FWHM. MonC: plates horizontal, E along them, beam 0.525 mm toward the collector (Kapton scar), 0.03 mm FWHM.
  - Signal loss (f_pe × MC) at 20 / 25 / 30 keV: MonP 6.2 / 26.9 / 42.8 %; MonC 2.1 / 13.9 / 26.7 % (`analysis/out/wall_loss/`). The MC energies include 18.5, 19, 19.5 and 21 keV, where the fits switch on (METHOD_REVIEW Q1).
  - With E along the plates, the photoelectrons start mostly parallel to the plates; only scattering carries them across the gap, so MonC loses much less.
- **Consequence:** the standard formula under-counts by 1/(1 − Lw). At the site density: MonP ×1.08 at 20 keV, ×1.36 at 25 keV, ×1.76 at 30 keV; MonC ×1.02, ×1.16, ×1.37.
- The bounds slot now publishes a **wall-loss-corrected best estimate** `L = P/(1 − Lw)`. Its band covers every variant above, and allows for plate backscatter on the low side.
  - Lw is fitted per lane as `1 − exp(−((E − E0)/s)^p)` above E0: MonP (17.9, 19.7, 1.17), max |fit − f_pe × MC| 0.009; MonC (18.1, 27.0, 1.41), 0.004 (`analysis/wall_loss_fit.py` → `analysis/out/wall_loss_fit_<lane>.txt`). Earlier fits: (18.7, 20.1, 1.01) / (18.6, 28.4, 1.28) on the coarser energy grid, (17.5, 19.1, 1.08) for the 10 mm chamber, and before M1, (17.2, 17.1, 1.22) to the per-absorption loss.
  - At 30 keV (MonP, site density) the best estimate is ×1.76 of P, range ×1.42–2.17 including the ±3.58 % symmetric terms.
  - The band covers each variant singly, and the two-change corners (reach +10 % with σ −20 %, reach −10 % with σ +20 %; finding M4, 2026-11-13). The three-change corner (adding a 1 mm offset) lies outside it and is reported as a stress case.
- **Still assumed:** MonP's beam position in its gap (centred), and the backscatter allowance (the plates are aluminium, per the user). The gap is measured (10.85 mm); its ±0.5 mm is inside the band's ±10 % reach variants.

### 3.2 μ_en/ρ: ±3 % (§2.2)

### 3.3 Gas density, and what is lost without pressure and temperature logging
**Real barometer data.** One year (2025) of hourly reports from the Lewis University Airport ASOS (LOT: Romeoville, 205 m, ~12 km from the APS), via the Iowa Environmental Mesonet [SOURCE: `data/queries/weather/iem_asos_LOT_2025.csv`; DERIVED: `analysis/pressure_climatology.py` → `analysis/out/pressure_climatology.txt`].

| Statistic | Value |
|---|---|
| Mean station pressure | **99.26 kPa**, i.e. 2.0 % below 1 atm |
| 1σ | 0.72 % |
| Extremes | −3.4 % / +2.1 % |
| 1st–99th percentile | −2.0 % / +1.7 % |
| Change over 1 h | median 0.03 %, 95th percentile 0.17 % |
| Change over 24 h | median 0.40 %, 95th percentile 1.6 %, max 3.0 % |
| Change over 72 h | median 0.54 %, 95th percentile 2.0 %, max 4.3 % |

Through ρ ∝ P/T, these are, one for one, changes in MonP's photons-per-Hz conversion.

**Hutch temperature, measured.** `15ID:Sensor2:Temperature` from the archiver, raw, 2024-06-26 to 2026-11-12, in two archiving regimes (10 s, then 60 s native spacing). It contains 1.63 M samples [SOURCE: archiver pull, kept outside the repo; DERIVED: `analysis/hutch_temperature.py` → `analysis/out/hutch_temperature.txt`]. Units assumed to be °C [PROVISIONAL].

| Statistic | Value | In density |
|---|---|---|
| Mean | **24.9 °C** (regime 1: 25.3; regime 2, since 2026-03: 23.5) | |
| 1σ | 1.18 K | 0.39 % |
| Extremes | 21.9 / 29.0 °C | |
| Change over 1 h | median 0.06 K, 95th percentile 0.20 K | 0.07 % |
| Change over 24 h | median 0.17 K, 95th percentile 0.62 K | 0.21 % |
| Change over 72 h | 95th percentile 0.85 K | 0.29 % |
| Daily range | median 0.63 K, 95th percentile 1.17 K | |

So the hutch is warmer than the 22 °C I had assumed. The site mean used throughout is **98.99 kPa and 24.9 °C**: the LOT mean carried to the chambers' 228 m (user, 2026-11-12). Temperature is a smaller term than pressure: 0.2 % per day against 0.4–1.6 %.

**What C-station loses today, with no pressure or temperature logging:**
1. **Absolute flux: almost nothing, provided the site-mean constants are used.**
   - Using 1 atm / 20 °C (the physics note's table) gives a density 3.7 % too high, so the flux comes out **3.8 % too low**: −2.0 % from pressure, −1.7 % from temperature. Using the site mean removes that bias.
   - What remains with fixed constants is the weather (pressure ±0.72 %, 1σ) and the hutch temperature (±0.39 %): ≈ ±0.8 % (1σ), against ±0.2 % when corrected.
   - In the budget (§3.7) this moved the total excluding l_eff from ±3.1 % to ±3.2 %, which is negligible against μ_en and l_eff. (Since 2026-11-13 the total carries electronics as ±0.7 %, the cross-section fit as ±0.9 % and the guarded collection length as ±1.4 %, and since 2026-11-17 the energy readback as ±0.4 %: ±3.58 %, CHAMBER_FACTS F9.5.)
2. **Relative normalization across days: this is the real loss.**
   - MonP's efficiency follows the weather. Within a scan of minutes to an hour it moves ≤0.03–0.2 %, which is invisible.
   - Between datasets taken a day apart it moves by a median of 0.4 % and up to 3 %. Over a 3-day beamtime it moves by up to 4 %.
   - That shift is a change in the *monitor*, not in the flux. Comparing normalized intensities across days, or across beamtimes, therefore carries a ~1–4 % weather systematic.
   - A ratio of two chambers on the same N2 supply (MonP and MonC share one) cancels it to first order. A sample signal divided by one chamber does not; see `normalization_proposal.md`.
   - The **MonP/BPM ratio does not cancel it** (the BPM does not depend on gas density). A MonP/BPM malfunction monitor (TODO) will see ±1–2 %/day of pure weather, so its error threshold must sit above that, or it must correct for it.
3. **Retroactive correction from the airport archive: yes, it works for CMC-custom chambers on gentle flow.**

**The airport-pressure correction: every assumption, and how each was checked.**

| # | Assumption | Size if wrong | Status |
|---|---|---|---|
| A1 | **The chamber gas is at hutch pressure.** The N2 flows in gently and exhausts to the hutch through an open outlet. The chamber then sits above ambient only by the pressure drop of the exhaust path. | Laminar (Poiseuille) drop, 2 m of 4 mm ID tube: **~10 Pa = 0.01 % at 100 sccm**, ~0.1 % at 1 L/min [DERIVED, μ(N2) = 1.78e-5 Pa·s]. **A bubbler or oil check valve on the exhaust adds ρgh: ~0.1 % per cm of liquid depth.** | **Confirmed (user, 2026-11-12):** both monitors exhaust through an open outlet at the end of ~3" (7.6 cm) of tubing, ~0.16" (4 mm) ID, the same as the input. Poiseuille: **~0.3 Pa = 0.0003 % at 100 sccm**, 0.02 % even at 5 L/min [DERIVED]. The chamber N2 is at hutch pressure. |
| A2 | **The hutch is at outdoor pressure.** | Building/HVAC pressurization is typically a few to ~25 Pa: ≤0.025 %. | PROVISIONAL; negligible either way |
| A3 | **LOT, about 14 km away, represents the APS.** | Measured over 2025 against JOT (12 km), ARR (37 km), MDW (35 km) and ORD (42 km), after reducing all to 210 m: **scatter 0.05 % (1σ), 0.07–0.10 % (95th percentile)**, about the same at every distance. That scatter is mostly the altimeter's 0.01 inHg (0.034 %) reporting resolution. Constant offsets between stations are 0.00 to −0.07 %. | **checked** [DERIVED: `analysis/asos_intercompare.py` → `analysis/out/asos_intercompare.txt`] |
| A4 | **The elevation difference LOT (205 m) vs the APS hutch is known.** | 0.012 % per metre; it is a *constant* offset. | PROVISIONAL (APS floor ~210–220 m). One handheld-barometer reading in the hutch calibrates it once. Matters only for absolute flux, not for relative corrections. |
| A5 | **Hourly reports are dense enough.** | The median change within 1 h is 0.03 %; interpolating linearly between reports leaves less than that. Rare outliers (thunderstorm jumps, bad reports up to ~7 hPa) need a guard, as in the scripts. | checked (`pressure_climatology.txt`) |
| A6 | **The gas temperature is the Sensor2 temperature.** At gentle flow the N2 has minutes in the chamber to reach wall temperature. | 0.34 % per K of difference between the sensor and the chamber. | PROVISIONAL: the sensor's location and accuracy relative to the chambers are unknown |
| A7 | **Ideal gas, constant composition.** | Compressibility is 0.03 %, and the flowing N2 is pure. | negligible |

**Result.** With ASOS pressure (A1–A5) and Sensor2 temperature (A6), the N2 density is known to about **±0.1 % (pressure) ⊕ ±0.17 % (temperature, if the sensor represents the chambers to ±0.5 K) ≈ ±0.2 %**. This is no worse than a dedicated gauge, it costs nothing, and it works **retroactively** on all archived data. It hinges on one check: the exhaust arrangement (A1). With an open outlet and gentle flow, ambient pressure can be used as is.

**Now live (2026-11-12):** the hourly LOT pressure feeds both flux calcs. See `calc/PRESSURE.md`.

**Absolute pressure controller, estimated payoff** (user asked):

| Scheme | Density uncertainty | Notes |
|---|---|---|
| Today, with 1 atm / 20 °C | +3.7 % bias, ±0.8 % (1σ), up to ~±3.5 % | |
| With the site mean (99.26 kPa / 24.9 °C) | ±0.8 % (1σ), −3.4 % / +2.1 % worst | free; just change the constants |
| + ASOS pressure + Sensor2 temperature | **≈ ±0.2 %** | free, software only, works retroactively. Needs A1 confirmed once. |
| Absolute pressure gauge at the chamber + temperature sensor | ≈ ±0.25 % | only adds a check of A1 and A6 |
| Absolute pressure controller | ≈ ±0.2–0.3 % | no gain over ASOS + Sensor2 |

- **Recommendation:** use the site mean now, and ASOS + Sensor2 in the software phase.
- Check A1 once with a differential gauge across the exhaust.
- Neither a gauge nor a controller is worth buying for density alone.

### 3.4 Gas purity: ≈ 0
- Air's μ_en/ρ is 34 % above N2's at 10 keV [DERIVED, NIST; mostly the 1.3 % argon by mass]. So 1 % residual air gives +0.34 % signal.
- With continuous flow and hours of purge after maintenance [user], this is negligible.
- It is a reason not to normalize to data taken in the first hour after a chamber is opened.

### 3.5 Electronics
| Item | Effect | Tag / check |
|---|---|---|
| SR570 gain accuracy | **±(0.5 % of output + 10 mV)** at 25 °C, for the 100 pA/V – 1 mA/V sensitivities; the offset term is **50 mV in High-BW mode**. The 10 mV is a worst-case output *offset* (1 kHz equivalent), part of what shows up as dark. C-station tunes the offset by hand to ~50–100 Hz (0.5–1 mV) at each gain change, so the real offset is the measured dark, not the 10 mV spec. That leaves **±0.5 %** on gain. | SOURCE (`references/SR570_manual.pdf`, Specifications); user |
| SR570 settings in EPICS | MonP (15IDC:A2): **Low Noise**, no filter, invert off, bias off; offset on, −, 200 nA range, **UNCAL**; 500 nA/V. MonC (15IDC:A3): Low Noise, no filter; offset on, +, 20 nA, UNCAL; 50 nA/V. Low Noise means the 10 mV term applies, not 50 mV. With the offset in UNCAL its value in amps is unknown, so **the dark must be measured, not computed**. | SOURCE: Experimenter session, EPICS last-sent values (`data/sweeps/monc_A3_baseline_2026-11-12.csv`). Front panel not yet read. Experimenter notes the IOC labels offset-sign index 0 "+" while the manual's IOSN 0 is negative. No PV exists for the sensitivity CAL/UNCAL state. **Caution [MEASURED, Experimenter MonC sweep 1, branch `monc-dark` commit 9f6c34f, `data/sweeps/monc_sweep1_results.md`]:** MonC's scaler channel (scaler1.S4) stayed at 8.0–8.6 Hz through *every* 15IDC:A3 change. That covered vernier ±100, both offset signs, offset 5–50 nA, gain 1–500 nA/V, offset on and off, and CAL; ~100 kHz was expected at one setting. The IOC processed every write. So for MonC, **EPICS SR570 values are demonstrably not a record of the hardware state**. **Resolved** (Experimenter, branch `monc-dark` commit 6d95ee3): the MonC SR570 was **switched off** during sweep 1. The user switched it on at 13:29:56 and A3init was re-run. The lesson stands: EPICS showed a full configuration for a unit that was off, so EPICS state is not proof of hardware state. Treat MonP's EPICS values with the same caution until the front panel is read. |
| **V2F + scaler gain, measured on the MonC channel** | At ~1 V output on every SR570 range 1–500 nA/V: **0.9998–1.0018 of the nominal 1e5 Hz/V**. The V2F is linear to 100 kHz. The CAL offset × gain × V2F chain at 50 nA/V agrees within ±0.3 % for 1–50 nA, except the 10 nA level (−1.16 %). This confirms the 1e5 Hz/V constant and the SR570 range accuracy to better than the ±0.5 % spec, on MonC's channel; MonP's channel is not yet measured. | MEASURED (Experimenter, `data/sweeps/monc_sweep1_results.md` on monc-dark, 6d95ee3) |
| **The offset-off dark is not one input current** | On MonC it is output-referred, depends on the range, and comes in both signs: 2 nA/V clips; 5–10 nA/V ≈ 5–12 Hz; 20/50/100 nA/V ≈ 57/54/31 Hz (stable ±2 Hz); 1/200/500 nA/V ≈ 450/410–430/150–180 Hz. It drifts by tens of Hz in the first hour after power-on. So the dark in Hz does **not** scale as 1/S. It must be measured per range, which is how the background slot (userTran2) treats it: tagged by gain, stale after a change. | MEASURED (same source) |
| **Dark subtraction: not done today. Is it negligible?** | **Yes, at the usual rates.** Unsubtracted, the normalizer is N + D instead of N, a relative error of D/N: **≤0.1 % at >100 kHz with D ≈ 100 Hz**. In a ratio of two such numbers within a scan it largely cancels. It stops being negligible when N falls: 1 % at 10 kHz, 10 % at 1 kHz. That happens with attenuated or detuned beam, narrow slits on MonC, or far from the operating energy. Subtracting costs only a shutter-closed reading, so it is recommended in software. Not urgent for normal >100 kHz operation. | DERIVED; the dark drift is under study by the Experimenter session |
| SR570 temperature coefficient (Low Drift mode, 11–28 °C) | ±(0.01 % of input + offset)/°C. Offset is 2 pA/°C at the 1e-7 A/V row and 20 pA/°C at the 1e-6 A/V row: **≈0.4–4 Hz/°C at 500 nA/V**. A lead for the dark-drift study (TODO). | SOURCE (manual, Table 1) |
| SR570 output | +5 V maximum into high impedance, 50 Ω output impedance. A V2F input impedance R_in loads it by 50/R_in, e.g. 0.5 % for 10 kΩ. **The N101VTF input impedance is not on the provisional datasheet.** The end-to-end check (CAL offset → SR570 → V2F → scaler, 0.9998–1.0018 of nominal on MonC) is a *product*: loading × V2F gain × SR570 gain × offset-level calibration. It is **consistent with loading ≤0.2 % (R_in ≳ 25 kΩ) if the offset and gain errors are below ~0.1 %; it does not separate them from the loading**. A uniform −0.4 % loading would be hidden by an offset generator running +0.5 % high, and level errors of that size exist (the 10 nA level reads −1.16 %) [DERIVED, with that assumption; caveat from Experimenter]. A direct R_in measurement (series-resistor ratio, Experimenter `procedures/v2f_input_impedance.md`, monc-dark 4e556b0) is written but not run. It needs the user in the hutch. | SOURCE (manual); user confirms +5 V; bound is DERIVED-with-assumption from Experimenter's MEASURED end-to-end ratio |
| SR570 UNCAL vernier | arbitrary gain if engaged. Settable over RS-232 (`SUCM 1`, `SUCV n`), so EPICS can set it too. | SOURCE (manual); check that EPICS and the front panel show "cal" |
| **SR570 RS-232 is listen-only** | "listen only, 9600 baud DCE". EPICS holds the last *sent* sensitivity, and a front-panel change silently breaks the conversion. | SOURCE (manual), user agrees. Operational rule: gain changes only through EPICS |
| SR570 input offset current | ±1 pA to ±5 mA. It is fixed in **amps**, so the dark rate in Hz changes with every sensitivity change: the 50 Hz offset at 500 nA/V becomes 25 Hz at 1 µA/V. C-station re-tweaks it by hand to ~50 Hz after each change [user]. | SOURCE (manual); DERIVED |
| SR570 polarity (INVERT; the default is off) vs the N101VTF polarity switch | wrong sign → V2F sits at 0 Hz | check once |
| N101VTF x1 gain | linearity ≤50 ppm FS (≈50 Hz at 1 MHz). x1 is the only calibrated gain; x2/x5/x10 are ±3 % | SOURCE (datasheet) |
| N101VTF internal switches | the 0–5 V range doubles Hz/V; the 2 MHz jumper doubles the output | SOURCE (datasheet); record their state once |
| Scaler (Joerger VSC16) | 40 MHz ≫ the 500 kHz maximum the V2F can reach here; pulses are periodic, so dead time is negligible. 32-bit capacity overflows only after ~2.4 h at 500 kHz. | SOURCE (`references/vsc16man-A.pdf`) |
| Scaler time base | rate = counts / gate time. If the time channel counts the VSC16's 10 MHz crystal, the time base is ±0.01 % (100 ppm), which is negligible. Which clock feeds the EPICS time channel (the VSC16's 10 MHz, or the N101VTF's 1 MHz output) is to be recorded. | SOURCE (manual); check the wiring once |
| Statistics | V2F output is periodic, not Poisson, so √N is **not** the error bar. Noise comes from the SR570 and the current; quantization is ±1 count per gate. | DERIVED |

### 3.6 Recombination: ≈ 0 [PROVISIONAL, user]
2.7 kV (F3.1) across the 10.85 mm gap (F1.5) is "well within the saturative regime." The HV readout itself is not verified. Its exact value matters only if it fell off the plateau.

### 3.7 Budget at 10 keV
| Term | Size on flux |
|---|---|
| l_eff (guarded chamber, measured; l_eff = 6.19 cm in the formula) | **±1.4 %** (model spread over the dimension tolerances, plus 0.5 % for the 2-D model). Before 2026-11-13: 0 to −13.6 %, one-sided |
| Photoelectron wall loss | 0 at 10 keV. Above ~18 keV it is corrected by each chamber's own MC: at 30 keV, MonP ×1.76 (band +23 % / −20 % including the other terms) and MonC ×1.37 (+18 % / −15 %) (§3.1) |
| μ_en/ρ | ±3 % |
| W | ±0.6 % |
| Density | ±0.8 % with the site-mean constants and no correction (±0.2 % with ASOS pressure + Sensor2 temperature) |
| SR570 gain × V2F scale, incl. V2F input loading | ±0.7 % (offset handled as dark). Until 2026-11-13 this was two rows: SR570 gain ±0.5 % (spec) and V2F x1 ±0.05 % plus an unknown loading term. Widened at the user's decision because MonC's chain, measured end to end, reaches +0.6 % on one range, and MonP's is unmeasured (`ELECTRONICS_CONCLUSIONS.md`). The loading is inside the end-to-end figure, for MonC's channel |
| Cross-section fit in the live calc | ±0.9 % (worst, vs log-log NIST at 25 keV) |
| Dark (subtracted live since 2026-11-12; this is the residual) | ≤0.1 % at >100 kHz; 1 % at 10 kHz |
| Mono energy readback (added 2026-11-17, user) | ±0.4 %: an ASSUMED 0.1 % energy error × d ln Φ / d ln E, which is 2.2 below 15 keV and at most 3.7 (MonP best estimate at 29.5 keV) (CHAMBER_FACTS F9.7) |
| **Total** | **±3.58 %**: μ_en 3, W 0.6, electronics 0.7, density 0.2 (live), fit 0.9, collection length 1.4, energy readback 0.4, in quadrature (`calc/quality_slots.py` SYMMETRIC_TERMS → LOW_FACTOR 0.964, HIGH_FACTOR 1.036) |

So the calculated MonP flux at 10 keV is good to ±3.6 % (stated bounds; it was +3.3 / −14 % before the chamber was measured). μ_en/ρ (±3 %) is now the dominant term.
- **An absolute anchor (§5) would test the whole chain**, including the modelled l_eff. After anchoring, the residual is about ±3 % at the anchor energy, set by μ_en's energy dependence.
- Transferring the anchor to other energies adds the energy dependence of μ_en. Above ~15 keV it also adds the MC wall-loss model's uncertainty. A second anchor energy (e.g. 25–30 keV) would test the MC directly.

---

## 4. Cross-check against existing tools
Comparison quantity: photons/s entering the MonP plates per Hz, at l = 6 cm and S = 500 nA/V [DERIVED; `data/queries/out/crosscheck_MonP_ph_per_Hz.csv`].

| Tool | at 10 keV | ratio to ours (same 1 atm, 20 °C) | Why it differs |
|---|---|---|---|
| **Ours** (NIST μ_en, W 34.8, ρ 1.165e-3) | 4.439e6 | 1 | |
| The physics note (W 35, e 1.6e-19, its table) | 4.469e6 | 1.007 | W +0.57 %, e +0.14 %; same density |
| CHESS calculator (JS ported verbatim) | 4.543e6 | 1.024 | W 34.6 (−0.6 %), ρ 1.131e-3 (+3.0 %). Its quadratic interpolation on a 10/15/20/30 keV grid adds +3.6 % at 25 keV |
| `xraydb.ionchamber_fluxes(both_carriers=False)` | 4.144e6 | 0.934 | xraydb's N2 density is 1.25e-3 (0 °C): ×1.073. After that, agreement is within 0.2 % up to 20 keV |
| **`xraydb.ionchamber_fluxes()` default** | 2.072e6 | **0.467** | **counts two carriers per ion pair, which halves the flux** |
| SSRL photonfluxcalc.pl | n/a | n/a | HTTP 503 on 2026-11-12. The notes page gives W = 34.6 eV |
| Hephaestus (DEMETER) `Ion.pm`, ported from its source | 3.447e6 | 0.777 | W = **30 eV for every gas** (×0.862) and ρ = 1.25e-3 (×0.932) give 0.80 at low E. It counts Compton scatter as *full-energy* absorption (photo + incoh), so the ratio falls to 0.58 at 20 keV and 0.33 at 30 keV. Single carrier. Not installed: the formula is read from the source file, `references/xraydb_two_carrier/hephaestus_Ion.pm` (last changed 2019-01-08) |
| T. Gog, APS-27 ion chamber notes | formula only | n/a | same single-carrier formula as the physics note (`references/` copy in `data/queries/web_calculators/`) |

**The two-carrier trap.** Per the Shockley–Ramo theorem, an electron–ion pair whose carriers drift to opposite plates induces a total charge *e* in the external circuit, not 2e. The physics note, Gog, CHESS, SSRL and Hephaestus all count one carrier. xraydb's default (`both_carriers=True`) is a factor 2 low for a standard parallel-plate chamber. If xraydb is used in the software phase, pass `both_carriers=False` and an explicit density.

The full evidence file, for a possible report upstream, is **`references/xraydb_two_carrier/CASE.md`**. It holds:
- the physics references;
- xraydb's own 2021 commit "no factor of 2 -- energy is converted to electron/ion pairs";
- its 2023 commit that re-introduced the factor as the default;
- the fact that its docstring example still prints the one-carrier value (3.20e11 documented; the default call returns 1.61e11).

All tools agree once W, density and the carrier count are aligned. The conversion itself is not in doubt; the inputs are.

---

## 5. Measurements to make (hardware, before software)
1. **V2F self-calibration.** Feed each channel the N101VTF's own 10 V reference and count it against the 1 MHz clock output. Record the internal 0–5 V switch, 2 MHz jumper and polarity switch states. Expect 1.000 MHz ± 50 Hz.
2. **SR570 state.** UNCAL off, INVERT state, filter, gain mode. Record the front-panel sensitivity against the EPICS value.
3. **Dark.** Shutter closed, HV on, at each SR570 sensitivity in use, as rate in Hz from the scaler clock channel. *Drift: see TODO.*
4. **Gas.** Read hutch P and T, or install a gauge and a sensor (§3.3).
5. **Geometry.** Done 2026-11-13: the user measured the chamber (MonC in hand; MonP is the same design), and it is guarded (CHAMBER_FACTS §1). Still open: l_gap (the N2 path from the plate end to the exit window; 0 used), MonP's beam position in its gap (F2.5, ASSUMED centred) and the HV at the chamber (F3.1).
6. **Linearity.** Beam fixed; step the SR570 one decade and check the rate scales by 10 within the gain accuracy.
7. **Absolute anchor: pixel detector + attenuators.** This yields l_eff.
   - Put the foils downstream of MonP, so MonP sees full beam.
   - Measure each foil's transmission with the ion-chamber pair at full flux; their relative accuracy is excellent.
   - Stack foils until the detector is in its linear range.
   - Correct for sensor quantum efficiency (Si 450 µm: ~95 % at 10 keV), threshold (~E/2), count-rate loss, and the air/window path from the MonP exit to the detector (the next phase; measurable to ~2 mm [user]).
8. **Current source: deferred.** The V2F self-cal plus the SR570 spec cover the electronics to ~0.5 % (budget term ±0.7 % since 2026-11-13; see §3.7). An injected current mainly catches gross configuration errors (the 0–5 V switch is ×2, UNCAL, wrong gain), which the anchor catches in aggregate. Buy one if the anchor and calculation disagree by more than ~10 %, to split electronics from physics. Interim option: a 1.000 V reference across a 1 % 1 GΩ resistor gives 1 nA.

---

## 6. Open questions for the user
**Answered 2026-11-12:**
- no guard electrodes (superseded 2026-11-13: the chamber is guarded, CHAMBER_FACTS F1.1);
- vertical plates;
- beam ~1 mm FWHM horizontally;
- SR570 maximum output +5 V;
- V2F on the 0–10 V range;
- gain reduced above 400 kHz.

The SR570 manual is now in `references/`.

**Answered, round 3 (2026-11-12):**
- hutch temperature PV `15ID:Sensor2:Temperature` (used in §3.3);
- SR570 gain mode Low Noise, from EPICS via the Experimenter session (front panel still to read);
- N2 flow is gentle and not monitored.

**Answered, round 4 (2026-11-12):**
- The N2 exhaust is an open outlet (A1, §3.3).
- The plates are at least as wide as they are long along the beam (≥6 cm) [user: assume this for now]. So the 1 mm wide beam sits far from the plates' side edges, and only the end fringes matter for l_eff.
- There is no need to read the SR570 front panels while they respond to commands (user). Experimenter's sweeps showed MonC responding once powered.
- MonC facts (user, via Experimenter):
  - MonC's gain is always ≥ MonP's, and the flux ratio is typically ≤4×;
  - MonC's standard gain is 5 µA/V;
  - the mapping is 15IDC:A2 ↔ scaler1.S3 (MonP) and 15IDC:A3 ↔ scaler1.S4 (MonC).
- Live pressure is now fed to the flux calc from the LOT airport observation (`tools/asos_pressure.py`).

**Still open:**
- **CMC-custom geometry** (user to provide; reminder in TODO):
  - which plate is the signal plate;
  - plate thickness;
  - distance from each plate to the chamber body;
  - distances from the plate ends to each window (l_gap);
  - whether MonC is the same design as MonP.
- **The exhaust arrangement on MonP/MonC** (open tube, bubbler, vent line?). It decides whether ambient pressure applies (§3.3, A1).
- **Where Sensor2 sits** relative to the chambers, and its accuracy (§3.3, A6).
- **N101VTF input impedance.** Not yet measured. The end-to-end calibration is consistent with ≤0.2 % loading only if the SR570 offset and gain are accurate to better than ~0.1 %, which is not established (gain spec ±0.5 %, no offset-accuracy spec). Experimenter's series-resistor A/B/A procedure (monc-dark 4e556b0) is the measurement that separates the loading. It needs the user in the hutch; MonP's channel needs its own approval.
- **SR570 front-panel state** (CAL/UNCAL sensitivity, gain mode, offset sign), to confirm the EPICS last-sent values.
