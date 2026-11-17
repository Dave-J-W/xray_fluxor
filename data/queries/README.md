# data/queries: every external lookup, saved

Everything here is either a verbatim download or the output of a script in this folder, so any number in `physics_note.md` can be traced back. Re-run the scripts to regenerate `out/`.

Interpreter: `<bluesky venv>\Scripts\python.exe -I -X utf8 <script>` (the reusable venv on the user's PC). Use xraydb 4.6.1 and xraylib 4.3.0 (versions are written into each CSV header).

| Path | What | How it was made (2026-11-12) |
|---|---|---|
| `nist_hubbell_seltzer/*.html` | NIST X-Ray Mass Attenuation Coefficients (Hubbell & Seltzer, NISTIR 5632) for N, O, Ar, dry air, Kapton, and tables 1/2 | `curl -L` of `physics.nist.gov/PhysRefData/XrayMassCoef/ElemTab/z07.html` and siblings |
| `nist_estar/estar_N_table.html` | NIST ESTAR electron stopping power and CSDA range in nitrogen | `curl -F matno=007 -F GraphType=None -F ShowDefault=on physics.nist.gov/cgi-bin/Star/e_table.pl` |
| `web_calculators/chess_*` | CHESS ion chamber calculator page and its JS bundle (the formula is in `chess_bundle_2.js`: `select_gas`, `CalculateDataPoints`, `ICFlux`) | `curl` of the page and its script URLs |
| `web_calculators/ssrl_*` | SSRL flux notes (W = 34.6 eV). The calculator form returned HTTP 503 | `curl` |
| `web_calculators/gog_aps27_notes_ion_chambers.pdf` | T. Gog, "Ion chambers and flux measurements", APS Sector 27 | `curl` (the IIT note failed on TLS and was not saved) |
| `query_cross_sections.py` → `out/nist_hs_*`, `out/xraydb_N.csv`, `out/xraylib.csv`, `out/compare_N.csv` | μ/ρ and μ_en/ρ from NIST (parsed, log-log interpolated), xraydb Elam and Chantler, xraylib | script |
| `crosscheck_calculators.py` → `out/crosscheck_MonP_ph_per_Hz.csv`, `out/monp_exit_table.csv` | MonP ph/s per Hz: the note, ours, xraydb (1 and 2 carriers), CHESS port; exit-plane table | script |
| `out/xraydb_ionization_potential.txt` | xraydb's W table and its docstring | one-liner, recorded in PROGRESS.md |
| `W_values.md` | W(N2) by source | hand-compiled from the above |
| `weather/iem_asos_LOT_2025.csv` | Hourly altimeter settings for 2025 at Lewis University Airport (LOT, Romeoville IL, 205 m), from the Iowa Environmental Mesonet | `curl "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=LOT&data=alti&data=mslp&data=tmpf&year1=2025&month1=1&day1=1&year2=2026&month2=1&day2=1&tz=Etc%2FUTC&format=onlycomma&latlon=yes&elev=yes&missing=M&trace=T&direct=no&report_type=3"` |

Analyses that use these inputs live in `../../analysis/`:
- `wall_loss_bound.py` (ESTAR)
- `pressure_climatology.py` (ASOS)

Ion chamber references that may support an upstream report are in `../../references/xraydb_two_carrier/`.

Known data problem: xraylib 4.3.0 `CS_Energy(7, E)` falls below `CS_Photo(7, E)` above 10 keV, which is unphysical. It is rejected as a μ_en source (see `out/compare_N.csv`).
