# fluxor parameters (generated from parameters.toml: do not edit)

Every number the package uses that is not code. ASSUMED and PROVISIONAL rows raise an `assumed:<name>` flag in every result
that uses them. To improve one, edit its row in `parameters.toml` (new value, tag MEASURED, source, date), then run
`python -I -X utf8 fluxor/make_parameters_md.py`. `legacy` is the id in the old hand-written ASSUMPTIONS.md.

## ASSUMED

| name | value | sigma | unit | source (date) | closes with | legacy |
|---|---|---|---|---|---|---|
| `beam.aspect_central` | 0.1 |  | 1 | beam height / width; the symmetric 1x1 mm slits carry no ratio information; undulator beams are usually wider than tall (MonC's was 33:1) (2026-11-14) | the beam's real height and width, from a screen or a knife-edge scan | A29 |
| `beam.aspect_high` | 1.0 |  | 1 | upper end of the beam height / width range: the symmetric slits taken at face value, the conservative case (2026-11-14) | the beam's real height and width, from a screen or a knife-edge scan | A29 |
| `beam.aspect_low` | 0.03 |  | 1 | lower end of the beam height / width range for the recombination sensitivity (2026-11-14) | the beam's real height and width, from a screen or a knife-edge scan | A29 |
| `beam.width_mm` | 1.0 |  | mm | beam width along the plate from the white-beam slit set 2 (1.00 x 1.00 mm in every November window); the slits sit outside the Gaussian hot zone, so this is an upper bound on the beam (2026-11-14) | the slit distance and the real beam FWHM | A28 |
| `fx4.dark_sigma_a` | 1e-09 |  | A | residual dark offset after the caller's dark is subtracted, taken equal to the TetrAMM's (the E-station dark moved by about 1 nA from week to week) (2026-11-14) | a dark measured the same day | A11 |
| `fx4.gain_rel` | 0.01 |  | 1 | gain accuracy placeholder: the FX4 manual's text gives no figure (2026-11-14) | the order code and its accuracy table, or a calibration against a known current source | A10 |
| `gas.p_kpa` | 98.99 | 1.0 | kPa | stand-in: the C-station site-mean pressure; no E-station gas pressure sensor exists (user accepted, 2026-11-14) (2026-11-14) | a pressure reading on the chamber gas line | A7 |
| `gas.t_c` | 22.2 | 2.0 | C | the E-hutch air temperature (a degF PV; the live E-station lane reads this PV, user confirmed 2026-11-16: "Yes, keep it"); it is the hutch air, not the chamber body, and no chamber temperature sensor exists (TODO.md) (2026-11-14) | a temperature sensor on the chamber body | A7 |
| `ic500.plate_orientation` | horizontal |  |  | plates horizontal, E-vector along the plates (the MonC mounting); the wall-loss MC geometry (2026-11-14) | say how the chamber is mounted; rerun wall_loss_ic500.py and wall_loss_fit_ic500.py, update ic500.wall_fit | A2 |
| `terms.energy_readback_rel` | 0.004 |  | 1 | mono energy readback (user 2026-11-17, 'Add the term'): an assumed 0.1 % energy error (dE/E) times d ln(flux)/d ln E, which is at most 3.3 for this chamber (best estimate at 29.5 keV; 2.2 below 15 keV); carried as 0.4 %, the C-station value (calc/quality_slots.py SYMMETRIC_TERMS), which covers it. The E-station energy is the side-bounce mono (2026-11-17) | an edge scan (a foil K edge) at the working energy, giving the readback's real error |  |
| `tetramm.dark_sigma_nA` | 1.0 |  | nA | residual dark offset after the caller's dark is subtracted: the E-station dark moved by about 1 nA from week to week (Experimenter note 2026-11-13) (2026-11-14) | a dark measured the same day | A11 |
| `tetramm.gain_rel` | 0.01 |  | 1 | gain accuracy placeholder: neither the manual's text nor the order code gives a figure (2026-11-14) | the order code and its accuracy table, or a calibration against a known current source | A10 |
| `tetramm.unit_a` | 1e-09 |  | A | unit of the IOC values at the E-station: nA (CurrentScale 1e9, Experimenter 2026-11-13); the unit field is empty (2026-11-14) | confirm whether the IOC offsets are in use during a measurement | A14 |

## PROVISIONAL

| name | value | sigma | unit | source (date) | closes with | legacy |
|---|---|---|---|---|---|---|
| `tetramm.range` | 0 |  | index | range inferred as +-120 uA (RNG 0): signals of 0.2-6 uA were recorded unclipped; range, bias and offsets are not archived (2026-11-14) | the new settings log on the production host, from 2026-11-14 03:25 UTC | A24 |

## CHOICE

| name | value | sigma | unit | source (date) | closes with | legacy |
|---|---|---|---|---|---|---|
| `recomb.alpha_cm3_s` | 1.6e-06 |  | cm3/s | ion-pair recombination coefficient of air at 1 atm, a textbook value used for BOTH carriers, which overstates the loss in N2 where the negative carrier is a free electron (2026-11-14) |  | A8 |
| `recomb.apply_to_best` | True |  |  | whether the recombination correction is applied to the best estimate. True because an uncorrected recombination always understates the flux. Chosen in the 2026-11-14 plan; this reverses the earlier convention (old A19: the best estimate carries known, modelled corrections only, recombination goes to the high bound). Confirmed by the user on 2026-11-16 ("Yes, keep it") (2026-11-14) |  | A19 |
| `recomb.mobility_cm2_vs` | 1.8 |  | cm2/V/s | textbook ion mobility, used for BOTH carriers, which overstates the loss in N2 where the negative carrier is a free electron (2026-11-14) |  | A8 |
| `spectrum.fractions` | [[1.0, 1.0]] |  | photon fraction | user, 2026-11-14: monochromators are fairly good at monochromating (2026-11-14) |  | A27 |
| `terms.density_rel` | 0.002 |  | 1 | as MonP; the real P, T source for flowing N2 is open (A7) (2026-11-14) |  | A15 |
| `terms.mu_en_tables_rel` | 0.03 |  | 1 | spread of NIST vs Chantler/Elam (physics_note 3.7); the MonP term reused for this chamber (2026-11-14) |  | A15 |
| `terms.w_rel` | 0.006 |  | 1 | spread of five sources, as a 1-sigma; the MonP term reused for this chamber (2026-11-14) |  | A15 |

## DERIVED

| name | value | sigma | unit | source (date) | closes with | legacy |
|---|---|---|---|---|---|---|
| `ic500.wall_fit` | [17.7, 25.9, 1.36] |  | keV, keV, 1 | signal wall loss fitted to the MC of analysis/wall_loss_ic500.py (horizontal plates, centred beam, 0.1 mm FWHM); the rounded fit is checked by analysis/wall_loss_fit_ic500.py. Order: E0, s, p (2026-11-14) |  | A5 |
| `sr570.electronics_rel` | 0.007 |  | 1 | SR570 gain x V2F scale incl. loading, type B (ELECTRONICS_CONCLUSIONS.md; user 2026-11-13) (2026-11-14) |  |  |

## GIVEN

| name | value | sigma | unit | source (date) | closes with | legacy |
|---|---|---|---|---|---|---|
| `ic500.electrode_width_mm` | 63.0 |  | mm | electrode extent across the beam, 63 mm (user, 2026-11-16, vendor figure of the IC-400/IC-500 -50 split electrode). The wall-loss Monte Carlo assumes plates wide enough that only the gap matters, which holds for 63 mm (2026-11-16) |  |  |
| `ic500.gap_mm` | 10.0 |  | mm | user 2026-11-13: electrode gap 10 mm (2026-11-14) |  |  |
| `ic500.l_eff_cm` | 5.0 | 0.03 | cm | collection length along the beam = the electrode length, 50 mm (user, 2026-11-16, from the vendor figure of the split electrode: 50 mm along the beam, 63 mm across). The sigma is an allowance for fringe field and guard rings, which the figure does not show (the guarded CMC chamber's l_eff was 2.3 % longer than its plate); it stays at 3 % until a fringe-field run says otherwise. The sigma is relative (0.03 = 3 %), not in the row's unit (2026-11-16) |  | A3 |
| `ic500.split_band_mm` | 22.0 |  | mm | height of the zig-zag split between the two electrode halves, 22 mm (user, 2026-11-16, vendor figure). A beam inside this band shares its current between the two halves by its position; the SUM of the two channels does not depend on position, a single channel does (flag per_channel_flux_depends_on_beam_position) (2026-11-16) |  |  |
| `ic500.volts` | 1700.0 |  | V | user 2026-11-13: HV driven right now at 1.7 kV (2026-11-14) |  |  |

