# W(N2): mean energy per ion pair, by source

Collected 2026-11-12. Adopted value: **34.8 eV ± 0.6 %** (the full spread of the N2 values below).

| Value (eV) | Gas | Source | How we have it |
|---|---|---|---|
| 34.8 | N2 | ICRU Report 31 (1979); Knoll, *Radiation Detection and Measurement*, Table 5-1 | `out/xraydb_ionization_potential.txt` (xraydb 4.6.1 table and docstring, verbatim) |
| 34.8 | N2 | W. P. Jesse & J. Sadauskis, Phys. Rev. 98, 1828 (1955) (air 33.9) | web search abstract only; full text not retrieved |
| 34.8 ± 0.2 | N2 | described as "well established" in arXiv:1703.10032 (W in air, revisited) | `references/literature/arXiv-1703.10032_W-revisited.pdf` (the paper is about air; N2 value via search summary) |
| 34.6 | N2 | SSRL "Flux Calculations for SPEAR" page | `web_calculators/ssrl_flux_notes.html` |
| 34.6 | N2 | CHESS ion chamber calculator (cites SSRL) | `web_calculators/chess_bundle_2.js`, `select_gas()` |
| 35.0 | N2 | the physics note ("Flux evaluation from ion chamber reading") | `references/` |
| 33.97 | dry air | ICRU Report 90 (electrons) | web search result |
| 33.8 | air | xraydb table | `out/xraydb_ionization_potential.txt` |
| 41.3 | He | xraydb table; Gog APS-27 notes | for future He-filled chambers |

Not found: a photon-specific W measurement for pure N2 at 5–30 keV. The nearest is a photon W for dry air at 2.2–3.9 keV with 0.84 % uncertainty (Kato et al., ETDEWEB 21362918), which is consistent with electron data.

Still to retrieve: the ICRU 31 table itself, with its stated uncertainty for N2 and electrons, and Combecher (1980) on W for low-energy electrons in N2. A search on 2026-11-12 found only bibliographic records for ICRU 31 (IAEA INIS h6bzx-b7p74; GlobalSpec), no table text; the report is not freely available. The adopted ±0.6 % (the spread of five sources) stands. It is small next to the μ_en ±3 % and the collection-length term.
