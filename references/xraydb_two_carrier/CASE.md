# The xraydb `ionchamber_fluxes` two-carrier default: evidence file

Kept so that a report to the xraydb maintainers can be made with everything in one place (user, 2026-11-12: "keep track of all the references on this, since we may need to make the case to them about their mistake"). Everything quoted is saved in this folder, except where marked *not held*.

## The claim
`xraydb.ionchamber_fluxes()` (xraydb 4.6.1, current on 2026-11-12) defaults to `both_carriers=True`. That sets `N_carriers = 2` and doubles the absorbed energy assigned to a given current, so the returned flux is **half** the correct value for a conventional parallel-plate ion chamber. With `both_carriers=False` the function agrees with the standard formula, and with the NIST μ_en calculation to within 0.2 % at 5–20 keV once densities are matched (`../../data/queries/out/crosscheck_MonP_ph_per_Hz.csv`, `../../PROGRESS.md`).

## Why one carrier is correct
1. **Charge induced in the external circuit (Shockley–Ramo theorem).** Take an ion pair created at position x in a gap d. The electron drifts to the anode and induces charge e·(d−x)/d. The ion drifts to the cathode and induces e·x/d. The total per pair is **e**, independent of x. The "electron current" and the "ion current" are the two halves of one charge e, not two charges. Counting both as separate e's double-counts.
   - W. Shockley, "Currents to conductors induced by a moving point charge", *J. Appl. Phys.* 9, 635 (1938). *Not held.*
   - S. Ramo, "Currents induced by electron motion", *Proc. IRE* 27, 584 (1939). *Not held.*
   - **Worked parallel-plate ion-chamber derivation, held:** K. A. Recine, "Understanding Current Signals Induced by Drifting Electrons", arXiv:1404.3802 (2014), §II.C, eqs. (9)–(10), https://arxiv.org/abs/1404.3802. File: `Recine2014_arXiv1404.3802_induced_current.pdf` (local copy only, not tracked: download it from the arXiv link). For N_e electron–ion pairs made a distance z from the anode, the electrons induce Q_e = −N_e e (z/D) and the ions Q_i = −N_e e (1 − z/D). Verbatim: *"the total induced charge on the anode is then Q_total = Q_e + Q_i = −N_e e, which is independent of the drift distance."* One pair gives one e in total, not 2e.
   - G. F. Knoll, *Radiation Detection and Measurement*, ion chamber chapter (Ch. 5): the saturated ion-chamber current is the ion-pair formation rate times e. This is the same book xraydb cites for its W table. *Not held; chapter and page to be confirmed against a copy.*
2. **How W is defined and measured.** W is defined from the charge of **one sign** collected per unit energy deposited. In dosimetry, D = (Q/m)·(W/e). ICRU Report 85 defines exposure with charge of one sign only. Verbatim, as reproduced in the journal summary of the report (S. M. Seltzer et al. / D. Thomas, "ICRU Report 85: fundamental quantities and units for ionizing radiation", 2012; file `Thomas2012_ICRU85_summary.pdf`, §5.1.3): *"The exposure, X, is the quotient of dq by dm, where dq is the absolute value of the mean total charge of the ions of one sign produced when all the electrons and positrons liberated or created by photons incident on a mass dm of dry air are completely stopped in dry air."* A W value measured that way, combined with an N_carriers = 2 current model, is internally inconsistent by exactly 2.
3. **Independent calculators and notes all count one carrier:**

   | Source | Formula | File here |
   |---|---|---|
   | C-station physics note ("Flux evaluation from ion chamber reading") | i = e·n_e, one carrier | `../Flux evaluation from ion chamber reading.docx` |
   | T. Gog, APS Sector 27, "Ion chambers and flux measurements" | N_abs = (i0/e)/n_e | `../../data/queries/web_calculators/gog_aps27_notes_ion_chambers.pdf` |
   | CHESS Ion Chamber Flux Calculator (JS) | `current*eIon/1.602e-19/(E)/(1-exp(...))` | `../../data/queries/web_calculators/chess_bundle_2.js` |
   | SSRL flux notes | 34.6 eV per electron, single carrier | `../../data/queries/web_calculators/ssrl_flux_notes.html` |
   | Hephaestus (DEMETER) `Ion.pm` | see `hephaestus_Ion.pm` and the note below | `hephaestus_Ion.pm` |

## Evidence inside xraydb itself
1. **History** (commit metadata and diffs saved here, from `gh api repos/xraypy/XrayDB/commits/<sha>`):
   - `d7a57637e` (2021-05-03), message: **"no factor of 2 -- energy is converted to electron/ion pairs"**. It removed a factor of 2 and doubled every expected flux in the tests; for example, nitrogen ic2 went from 3.771e11 to 7.5417e11. Files: `commit_d7a57637e.diff`, `commit_d7a57637e.meta.txt`.
   - `fefbc3954` (2023-04-03), message: "ionchamber_flux adds option to set ncarriers to 1, but defaults to 2 (count electron and ion)". This re-introduced the factor of 2 as the default. It changed only `xray.py`. Files: `commit_fefbc3954.*`.
   - Current tests (`test_xray_current.py`, `test_ionchamber_fluxes`) expect nitrogen ic2 = 3.75e11. That is the two-carrier value: half of what the 2021 commit set.
2. **Self-inconsistency in 4.6.1.** The docstring example states `In=3.20045e+11`. Run locally (`local_run_xraydb_4.6.1.txt`):

   | Call | Incident flux |
   |---|---|
   | default (`both_carriers=True`) | 1.60694e+11 |
   | `both_carriers=False` | 3.21388e+11 |

   The documented example matches the **one-carrier** result. The docstring was written before the 2023 default change and was not updated.
3. **Their stated rationale** (docstring note 4, and `xraydb_doc_examples.rst`): "The effective ionization potential generates an electron and ions pair, and normally both carriers will contribute to the current ... To consider the current from 1 carrier, for example if using a Frisch grid, use `both_carriers=False`." The Frisch-grid remark is back to front. A Frisch grid makes the *induced signal of a pulse* depend on the electron alone. In both cases the integrated DC current per pair is e, and a DC current measured by a current amplifier is the integrated case.

## Related upstream discussion
- xraypy/XrayDB issue #12, "For gas mixtures, the ionchamber_fluxes function gives incorrect results" (closed 2021-05-11). It is about Compton and mixtures, not carriers. It links Hephaestus `Ion.pm#L397`.
- xraypy/XrayDB issue #31, "Mass energy-absorption data" (open, 2025-11-17). It asks for μ_en support, which is relevant to the Compton treatment.
- No issue about the carrier count was found (`gh search issues --repo xraypy/XrayDB carriers`, 2026-11-12).

## Status
- Not reported upstream. Reporting is the user's decision; this file is the material for it.
- Collected 2026-11-12: the ICRU 85 exposure definition (verbatim) and a worked Shockley–Ramo derivation for a parallel-plate chamber (Recine 2014, verbatim).
- Still to collect before reporting:
  - a Knoll page quote (no copy held; optional, since Recine covers it);
  - a measured C-station absolute anchor, which would be the decisive evidence.
