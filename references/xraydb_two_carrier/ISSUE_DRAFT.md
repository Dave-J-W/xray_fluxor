<!--
DRAFT, not posted. For xraypy/XrayDB issues. Written 2026-11-12 from the evidence in CASE.md (same folder).
Whether and when to post is the user's decision. Before posting:
  - re-run the reproduction against the then-current xraydb release, and update the version and numbers;
  - check the repository for a newer issue or PR on the same point (`gh search issues --repo xraypy/XrayDB carriers`);
  - check that nothing in this text names people, hosts or the beamline beyond what you want public.
-->

# `ionchamber_fluxes()` defaults to `both_carriers=True`, which halves the flux for ordinary ion chambers

## Summary
`xraydb.ionchamber_fluxes()` (checked with xraydb 4.6.1) defaults to `both_carriers=True`. That sets `N_carriers = 2` and doubles the absorbed energy attributed to a measured current. For a conventional parallel-plate ion chamber read by a current amplifier, the returned incident flux is therefore **a factor of 2 too low**. One electron–ion pair produces a total charge of **e** in the external circuit, not 2e. This is also the convention under which W values (including the ones xraydb tabulates) are defined.

## Reproduction
```python
import xraydb
for both in (True, False):
    fl = xraydb.ionchamber_fluxes(gas='nitrogen', volts=1.25, length=20.0,
                                  energy=10e3, sensitivity=1.e-6, both_carriers=both)
    print(both, f"{fl.incident:g}")
# True  1.60694e+11      <- default
# False 3.21388e+11
```
The docstring example for this exact call states `In=3.20045e+11`. That is the **one-carrier** value: the documented example and the default behaviour disagree by 2×.

## Why one carrier is correct
- **Shockley–Ramo.** Consider a pair created a distance z from the anode in a gap D. The electron induces −e·z/D and the ion −e·(1 − z/D), so the total is −e, independent of z. A current amplifier integrates both contributions, but together they add up to one elementary charge per pair. A worked derivation for exactly this geometry: K. A. Recine, "Understanding Current Signals Induced by Drifting Electrons", arXiv:1404.3802, §II.C, eqs. (9)–(10): *"Q_total = Q_e + Q_i = −N_e e, which is independent of the drift distance."* (Original theorem: W. Shockley, J. Appl. Phys. 9, 635 (1938); S. Ramo, Proc. IRE 27, 584 (1939).)
- **The definition of W.** W is the mean energy expended per ion pair, and ion-chamber dosimetry uses D = (Q/m)·(W/e) with Q the charge **of one sign**. ICRU Report 85 defines exposure as *"the absolute value of the mean total charge of the ions of one sign produced …"* (§5.1.3). A W measured on that basis, combined with a current model that counts two carriers, is inconsistent by exactly 2.
- **The note in the docstring** says "to consider the current from 1 carrier, for example if using a Frisch grid, use `both_carriers=False`". A Frisch grid changes the shape and timing of a *pulse* signal (it removes the ion contribution to the induced pulse). It does not change the integrated DC charge per pair in a current-mode chamber, which is e in both cases.

## History (for context)
- `d7a57637e` (2021-05-03), "no factor of 2 -- energy is converted to electron/ion pairs". This removed a factor of 2, and the expected test fluxes doubled (e.g. nitrogen ic2 3.771e11 → 7.5417e11).
- `fefbc3954` (2023-04-03), "ionchamber_flux adds option to set ncarriers to 1, but defaults to 2 (count electron and ion)". This re-introduced the factor as the default. The current test (`test_ionchamber_fluxes`, nitrogen ic2 ≈ 3.75e11) encodes the two-carrier value; the docstring example still shows the one-carrier value.

## Cross-checks
With `both_carriers=False`, `ionchamber_fluxes()` agrees with an independent calculation (NIST Hubbell–Seltzer μ_en, W = 34.8 eV, one carrier) to within 0.2 % at 5–20 keV, once the gas density is matched. Several other implementations count one carrier:
- the CHESS ion-chamber flux calculator;
- the SSRL flux notes;
- the Hephaestus (DEMETER) ion-chamber tool;
- T. Gog's APS Sector 27 notes on ion chambers.

## Suggested change
1. Default `both_carriers=False`, or remove the option. If it stays, document it as a special case (it corresponds to no standard current-mode configuration we know of).
2. Update `test_ionchamber_fluxes` and the docstring example so that they agree.

A smaller, separate point: the gas density used for `'nitrogen'` (1.25e-3 g/cm³) is N2 at 0 °C and 1 atm. At typical room conditions (~22–25 °C, ~99–101 kPa) the density is ~7–10 % lower, and the flux scales almost inversely with it. A `density=` (or pressure/temperature) argument would help users get a few-percent result.

Thank you for xraydb. It made the cross-checks here easy.
