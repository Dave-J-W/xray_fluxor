# Flux evaluation from ion chamber reading: the note, with replies

*The C-station note "Flux evaluation from ion chamber reading" (`references/Flux evaluation from ion chamber reading.docx`) is copied here in full, paragraph by paragraph, with its equations transcribed. After each paragraph comes a reply drawn from the calculation that runs live for MonP and MonC (`METHOD.md`, `RESULT.md`, `physics_note.md`). Reply written 2026-11-13. Its numbers are those in METHOD.md on that date, including the review's latest corrections (METHOD_REVIEW R1–R2). The long arithmetic is in the postscripts.*

**In short.**
- We agree with the note's structure, with one charge per ion pair, and with using $\mu_{\rm en}$ for the absorption and $\mu$ for the exit.
- At 10 keV the note's formula and ours give the same flux, within 0.01 %. That is a coincidence: two differences of about 0.9 % cancel at the site's mean density. One is in the constants, the other in density and length together (P.S. 2).
- Above about 18 keV the note's own second caveat, incomplete thermalization, dominates. At 30 keV the formula is low by **×1.76 on MonP** and **×1.37 on MonC**, and we correct for that.
- The note puts absolute accuracy at "no better than 10 %". Our stated bounds are tighter than that below ~15 keV (±3.6 %), and wider at 30 keV (+23 / −20 % on MonP).

---

> **Note.** Given an incoming photon flux $I_i$, the number of photons (per second) absorbed by the ion chamber is
> $$I_a = I_i\bigl(1-\exp(-\mu_{en}\,l)\bigr),$$
> where $l$ is the length of the beam's path within the charge collection region (roughly equal to the length of the charge collection plates, 6 cm for our standard ion chambers). $\mu_{en}$, here, is the energy-absorption coefficient, which is distinct from the standard absorption coefficient $\mu$ (more about this later).

**Reply.** We use the same relation, with three refinements.

1. **What $I_a$ counts.** With $\mu_{en}$, $I_a$ is not the number of photons absorbed. It is the photon-equivalent of the **energy** deposited: $I_aE$ is the power given to the gas. The number of photons that interact at all is $I_i(1-e^{-\mu l})$, which is 9 % larger at 10 keV and 2.8× larger at 30 keV. The note's later equations use $I_aE$ as an energy, so they are right; only the wording "number of photons absorbed" is not.
2. **$\mu_{en}$ is a density times a table value.** The note's table is in cm⁻¹, so it fixes the density. Dividing by NIST's $\mu_{en}/\rho$ gives $\rho$ = 1.1650 × 10⁻³ g/cm³: N₂ at 1 atm and 20 °C. At the hutch (228 m; site mean 98.99 kPa and 24.9 °C) the mean density is 1.1190 × 10⁻³ g/cm³, **4.1 % lower**. The weather moves it a further ±0.8 % (1σ) about that mean. We compute the density live from the airport pressure and the hutch temperature, good to ±0.2 % (METHOD §3).
3. **The length.** Our chambers' collector is 60.5 mm long, measured on 2026-11-13. It has grounded guards 1 mm beyond each end, set back 0.51 mm from its face. A 2-D field model of the measured chamber gives an effective collection length of **61.9 mm**, ±1.4 % over the measurement tolerances. Against the note's 6 cm, that lowers the flux by 3.1 %.

For a uniform beam, refinements 2 and 3 move the result in opposite directions. At the site-mean density they nearly cancel: the note's absorbed fraction is 0.9 % larger than ours (P.S. 2).

---

> **Note.** The number of electrons (per second) produced by the absorbed photons is given by
> $$n_e = \frac{I_a E}{E_I},$$
> where $E$ is the photons' energy and $E_I$ is the mean ionization energy, i.e. the mean energy needed to extract an electron from the material. $E_I$ is material dependent, of course; for nitrogen (which is used in our ion chambers) the value is $E_I = 0.035$ keV/e.

**Reply.** Agreed, with a name and a value change.
- **Name.** The quantity is the **W-value**, the mean energy spent per ion pair. It is not the ionization energy, which for N₂ is 15.6 eV. W is more than twice that, because much of the energy goes into excitation and sub-ionization electrons.
- **Value.** We use **W(N₂) = 34.8 eV ± 0.6 %** (`data/queries/W_values.md`). The ± is the full spread of five sources:
  - 34.8 eV from ICRU 31 and Knoll, from Jesse & Sadauskis, and from arXiv:1703.10032;
  - 34.6 eV from the SSRL and CHESS calculators;
  - 35.0 eV from this note.

  The note's value is at the top of the spread. It makes the flux 0.57 % higher than 34.8 eV does.
- **Counting.** $n_e$ must be the number of ion **pairs**, with one elementary charge per pair in the external circuit. The note does this. The electron and the ion together induce exactly $e$, wherever the pair is made (Shockley–Ramo). Counting both carriers would halve the flux, and xraydb's default does exactly that (`references/xraydb_two_carrier/CASE.md`).

---

> **Note.** This number of electrons represents a current (in microampere units) of
> $$J(\mu A) = 10^6 \times 1.6\times10^{-19}\, n_e = 1.6\times10^{-13}\, n_e.$$

**Reply.** Agreed. With the exact $e$ = 1.602176634 × 10⁻¹⁹ C the constant is 1.6022 × 10⁻¹³. The rounding makes the flux 0.14 % high.

---

> **Note.** The current is, in turn, converted by the amplifier to voltage, according to
> $$V(\text{volt}) = \frac{J(\mu A)}{S(\mu A/\text{volt})},$$
> where $S$ is the amplifier's sensitivity (in units of µA/volt, as shown).

**Reply.** Agreed. Two practical conditions apply.
- $S$ must be the gain actually set. The SR570's serial port is listen-only, so a front-panel change is invisible to EPICS. We change gains only from EPICS for that reason.
- The SR570 output must stay below 5 V, which is 500 kHz at the scaler. We lower the gain above 400 kHz.

The gain accuracy (SR570 × V2F × scaler) is **±0.7 %**. That is the manual's ±0.5 %, widened because MonC's ranges, measured end to end, reach +0.6 % (`ELECTRONICS_CONCLUSIONS.md`).

---

> **Note.** Finally, the voltage is digitized with a standard conversion rate of $10^5$ (cts/sec/volt). Thus, the measured scaler count rate is
> $$N(\text{cts/sec}) = 10^5\,V = 10^5\,\frac{J}{S} = 10^5\times1.6\times10^{-13}\,\frac{n_e}{S} = 1.6\times10^{-8}\,\frac{I_aE}{E_IS} = 1.6\times10^{-8}\,\frac{I_iE\bigl(1-\exp(-\mu_{en}l)\bigr)}{E_IS}.$$

**Reply.** Agreed, under two conditions.
- **The V2F range.** $10^5$ counts/s per volt holds for the N101VTF on its ×1 gain and 0–10 V range, which the user confirmed. On the 0–5 V range the factor is $2\times10^5$, and every flux would be 2× too high.
- **The background.** $N$ should be the **net** rate. With no beam the scaler still counts 182–227 Hz on MonP at 500 nA/V (SR570 offsets and the V2F zero). We subtract a running no-beam estimate. Its effect is 0.09 % at a 224 kHz reading, but it would be 2 % at 10 kHz and 20 % at 1 kHz.

---

> **Note.** Reversing (the last equation) we get
> $$I_i(\text{ph/sec}) = \frac{E_I(\text{keV})\,S(\mu A/\text{volt})\,N(\text{cts/sec})}{1.6\times10^{-8}\bigl(1-\exp(-\mu_{en}l)\bigr)E(\text{keV})}.$$
> Using the value for nitrogen, i.e. $E_I = 0.035$ keV/e, we get
> $$I_i(\text{ph/sec}) \approx 2.19\times10^{6}\,\frac{S(\mu A/\text{volt})\,N(\text{cts/sec})}{\bigl(1-\exp(-\mu_{en}l)\bigr)E(\text{keV})}.$$

**Reply.** Our constant, for the same units, is **2.1721 × 10⁶**. The note's is 0.83 % higher:
- +0.57 % from W (35 against 34.8 eV);
- +0.14 % from $e$ (1.6 against 1.6022);
- +0.11 % from rounding 2.1875 to 2.19.

Our full formula, before the wall-loss correction, is the same as the note's with those constants, the live density and $l$ = 6.19 cm (METHOD §4). **Worked through for one reading** (MonP, 10 keV, 224.0 kHz at 500 nA/V):

| | Note's formula | Ours |
|---|---|---|
| Photons/s entering the collection region | 1.002 × 10¹² | 1.002 × 10¹² |
| Photons/s at the exit | 0.975 × 10¹² | 0.975 × 10¹² (NIST); 0.978 × 10¹² with the live cross-section fits |

The agreement within 0.01 % comes from two differences cancelling, the constant (+0.83 %) and the density with the length (−0.90 %), plus the unsubtracted background (+0.09 %). On a day when the pressure is 2 % above the mean the note's number would be 2 % high, and the cancellation would not hold. See P.S. 2.

---

> **Note.** Note that this is the result for the incoming beam. For the outgoing beam (at the outlet of the ion chamber), the result needs to be multiplied by $\exp(-\mu l)$ (note, $\mu$ and not $\mu_{en}$, here).

**Reply.** Agreed. Every interaction removes a photon from the beam, so the exit transmission uses $\mu$. Over 6.19 cm it is 0.974 at 10 keV and 0.998 at 30 keV.

The reference planes need stating:
- **"Incoming"** is the flux entering the **collection region**: after the entrance window and the gas before the collector, not the flux upstream of the chamber.
- **"Outgoing"** is the flux at the end of the collection region. The gas between there and the exit window is not included (0.43 % per cm at 10 keV), nor the Kapton exit window, nor the air path to the sample.

We publish the exit-plane value.

---

> **Note.** Coming back to the issue of absorption coefficient, since what we are actually measuring is the photon energy absorbed in the ion chamber, what needs to be used in the calculation is not the usual absorption coefficient $\mu$ (properly called "attenuation coefficient") but the energy absorption coefficient $\mu_{en}$. The values are nearly the same at low energies but significantly different at higher energies. A representative table of the values for nitrogen is shown below.
>
> | Energy (keV) | Att. coef. $\mu$ (cm⁻¹) | Energy abs. coef. $\mu_{en}$ (cm⁻¹) |
> |---|---|---|
> | 1.00 | 3.857 | 3.851 |
> | 1.50 | 1.262 | 1.258 |
> | 2.00 | 0.5556 | 0.5540 |
> | 3.00 | 0.1696 | 0.1686 |
> | 5.00 | 0.03663 | 0.03595 |
> | 10.00 | 0.004519 | 0.004130 |
> | 15.00 | 0.001440 | 0.001132 |
> | 20.00 | 0.0007197 | 0.0004505 |
> | 30.00 | 0.0003572 | 0.0001280 |
> | 50.00 | 0.0002307 | 3.748 × 10⁻⁵ |
> | 100.00 | 0.0001781 | 2.599 × 10⁻⁵ |

**Reply.** Agreed: $\mu_{en}$ for the energy deposited, $\mu$ for the beam's attenuation.
- The difference is Rayleigh scattering, the scattered photon in Compton scattering, and escaping fluorescence, none of which deposit energy locally.
- For nitrogen, the photoelectric part plus the Compton-electron part reproduces NIST's $\mu_{en}$ to 0.2 % (`physics_note.md` §2.2).

The table matches NIST Hubbell–Seltzer at $\rho$ = 1.1650 × 10⁻³ g/cm³ (1 atm, 20 °C). For example, 0.004130 cm⁻¹ is 3.545 cm²/g, and 0.0001280 cm⁻¹ is 0.1099 cm²/g, the values we use.

"Nearly the same at low energies" holds below about 5 keV. At 10 keV, where most of our work is, $\mu$ is already **9.4 %** above $\mu_{en}$, so using $\mu$ there would under-state the flux by 9.3 %.

We carry **±3 %** on $\mu_{en}/\rho$: half the Scofield–Chantler spread. It is the largest symmetric term in our budget.

---

> **Note.** The values from the third column (i.e. $\mu_{en}$) are the ones to be used. Note that at 30 keV $\mu_{en}$ is nearly 3 times smaller than $\mu$ and at 50 keV it is about 6 times smaller.

**Reply.** Confirmed from the note's own table:

| E (keV) | 10 | 15 | 20 | 30 | 50 |
|---|---|---|---|---|---|
| $\mu/\mu_{en}$ | 1.094 | 1.272 | 1.598 | 2.791 | 6.155 |

At 30 keV, using $\mu$ instead of $\mu_{en}$ would give a flux 2.79× too low.

---

> **Note.** Regarding accuracy, there are two issues to consider.
> The assumption that the charge collection length equals the length of the charge collection plates is just an approximation. In reality there is a non-zero probability for electrons produced within this length to escape, as well as probability for electrons produced outside to be captured. Both probabilities are energy dependent.

**Reply.** We treat two separate effects here, and each now has a number.

1. **Where the field collects.** Ions and electrons drift along field lines, so the length that counts is the length over which the field lines end on the collector. It is not the plate length. In our guarded chamber this effective length is **61.9 mm**, against a 60.5 mm collector, from a 2-D Laplace and field-line model of the measured chamber (`analysis/collection_length_cmc.py`).
   - Its uncertainty is **±1.4 %**: collector length ±0.5 mm (0.81 %), guard set-back (0.73 %), guard gap (0.57 %), beam height (0.24 %), HV-plate length (0.16 %), and 0.5 % for the 2-D approximation, in quadrature.
   - This part does not depend on energy.
   - Without guards it would be much worse. Until the chamber was measured we carried a one-sided allowance of up to −13.6 % for it.
2. **Where the photoelectrons go.** Photoelectrons carry energy along the beam, both out of and into the collection region. With the beam passing through the gas on both sides of the collector, the exchange across the ends balances on average. Our Monte Carlo assumes that balance: it models the plates as infinitely long. The energy-dependent loss that does not balance is the energy carried sideways **into the plates**, which is the note's second issue (next reply).

---

> **Note.** The equation for $n_e$ assumes full "thermalization", i.e. subdivision of the energy of the initial photoionized electron among as many electrons as possible. For fixed ion chamber dimensions this becomes less and less likely when the beam energy goes up.

**Reply.** Agreed, and this is the dominant effect above ~18 keV. The mechanism is energy leaving the gas, not incomplete subdivision: W stays constant to within ±0.6 % across these energies.
- **The geometry.** The N K-shell photoelectron starts with $E$ − 0.41 keV. Its range in the gas (CSDA) is 2.4 mm at 10 keV, 4.9 mm at 15 keV and **17 mm at 30 keV**. The beam is 5.4 mm from each plate on MonP (centred) and 4.9 mm from the collector on MonC.
- **The polarization.** The beam is horizontally polarized, and photoelectrons go preferentially along the polarization (Sauter).
  - On **MonP** the plates are vertical, so the polarization points at them.
  - On **MonC** they are horizontal, so it lies along them.
- **The loss.** An electron that reaches a plate gives the metal its remaining energy and makes no more ion pairs. A Monte Carlo of each chamber as mounted (`analysis/wall_loss_mc.py`) gives the signal lost. It is validated against Grün's measured depth–dose curve in air: 90 % of the energy lies within 0.74 $R_G$, as Grün measured.

| E (keV) | ≤ 15 | 20 | 25 | 30 |
|---|---|---|---|---|
| MonP signal lost | 0 | 7 % | 26 % | **43 %** |
| MonP correction to the formula | ×1 | ×1.08 | ×1.36 | **×1.76** |
| MonC signal lost | 0 | 2 % | 14 % | **27 %** |
| MonC correction | ×1 | ×1.02 | ×1.16 | **×1.37** |

These are the live fits at the site-mean density. The Monte Carlo points themselves give 6, 27 and 43 % (MonP) and 2, 14 and 27 % (MonC).

- **Below the onset.** The correction is exactly 1 up to an effective energy of 17.9 keV (MonP) or 18.1 keV (MonC); the effective energy is the photon energy scaled for the gas density.
- **At 10 keV**, a straight 2.4 mm track from the beam's edge cannot reach a plate 4.9 mm away.
- **Compton electrons** (7.5 % of the signal at 30 keV) carry at most 3 keV. They travel ≲ 0.3 mm and never reach a plate.

So at 30 keV the note's formula is low by a factor of 1.76 on MonP. The worked reading is in P.S. 3.

---

> **Note.** The effects of both issues are difficult to quantify but the overall consensus is that absolute accuracy of ion chamber is no better than 10 % (and may be significantly worse).

**Reply.** With the chamber measured and the wall loss modelled, we can quantify both issues. The result is better than 10 % at low energy and worse at high energy. These are **stated bounds** (≈1σ of the symmetric terms, times the full edge of the wall-loss band on each side), not a confidence interval (P.S. 4).

| E (keV) | 5–12 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|
| MonP stated bounds | ±3.6 % | +9 / −3.6 % | +15 / −11 % | +18 / −15 % | **+23 / −20 %** |
| MonC stated bounds | ±3.6 % | +9 / −3.6 % | +14 / −6 % | +16 / −12 % | **+18 / −15 %** |

- **Below 13 keV** the budget is symmetric:
  - $\mu_{en}$ ±3 %;
  - collection length ±1.4 %;
  - cross-section fit ±0.9 %;
  - electronics ±0.7 %;
  - W ±0.6 %;
  - live density ±0.2 %;
  - energy readback ±0.4 % (added 2026-11-17).

  In quadrature that is ±3.58 %, carried as ±3.6 %.
- **Above 18 keV** the wall-loss band dominates. On MonP at 30 keV it alone is +18.9 / −16.7 %.

Two cautions:
- **No absolute check yet.** None of this has been compared with an absolute reference. Only a pixel detector with calibrated foils can do that, and until then the bounds are a budget, not a measurement.
- **One stress case falls outside the band.** Combining three Monte Carlo variants at once (longer reach, weaker scattering, and the beam 1 mm off centre) lies outside the band on MonP. It is up to ~3 % on the high bound near 18 keV, and ~1.5 % at 25 keV (METHOD §7f). No decision has yet accepted that.

---

> **Note.** On the other hand, relative accuracy, when comparing results obtained at same photon energy, is excellent.

**Reply.** Agreed **for one chamber** whose gain, density and background are tracked. Each of those still sets a floor:
- **Gain changes.** Ratios across SR570 ranges carry the gain error: up to +0.6 % between ranges, measured on MonC.
- **Gas density.** With fixed constants, the weather's ±0.8 % (1σ) passes straight into the flux at 10 keV, and doubles at 30 keV on MonP. There a denser gas absorbs more and also shortens the electron tracks, so the sensitivity is −1.93 % per % (±1.5 %). With the live pressure and temperature this drops to ±0.2 % and ±0.4 %.
- **Background at low rates.** A 200 Hz error in the dark rate is 0.1 % at 200 kHz but 2 % at 10 kHz.

It does **not** hold **between chambers mounted differently**, once the wall loss starts. At 30 keV the same reading on MonP and MonC means **6.32 × 10¹²** and **4.92 × 10¹²** photons/s: they differ by 28 %, only because the plates are turned 90° relative to the polarization. Below about 18 keV the two chambers agree to within the electronics (±0.7 %).

---

## Postscripts: the arithmetic

### P.S. 1. The constant

Note: $E_I/1.6\times10^{-8} = 0.035/1.6\times10^{-8} = 2.1875\times10^6$, quoted as $2.19\times10^6$.

Ours, in the note's units (S in µA/V, N in counts/s, E and W in keV). The current is $i = N\,S\times10^{-6}/10^5$ A, and $\Phi = iW/(eE\eta)$, so the constant is
$$\frac{W}{e\times10^{11}} = \frac{0.0348\ \text{keV}}{1.602176634\times10^{-19}\times10^{11}} = 2.17205\times10^{6}.$$
The note's $1.6\times10^{-8}$ is the same $e\times10^{11}$. With S in A/V this is METHOD §4's $K_0 = 2.17205\times10^{12}$.

Ratio: 2.19 / 2.17205 = 1.00826 = 1.00575 (W) × 1.00136 (e) × 1.00114 (rounding).

### P.S. 2. Worked reading at 10 keV, both ways (MonP, 224.0 kHz, 500 nA/V)

**Note's formula** (no background subtracted, table density, $l$ = 6 cm):
- $1-e^{-0.004130\times6} = 0.024476$;
- $I_i = 2.19\times10^6\times0.5\times224\,000\,/\,(0.024476\times10) = 1.0021\times10^{12}$;
- exit: $\times e^{-0.004519\times6} = \times0.97328 \Rightarrow 0.9753\times10^{12}$.

**Ours** (METHOD §1–§4, site mean 98.99 kPa and 24.9 °C):
- $N$ = 224 000 − 200 = 223 800 Hz, $i$ = 1.119 µA, $P_{\rm abs}$ = 2.431 × 10¹¹ keV/s;
- $\rho$ = 98.99 × 3.369272 × 10⁻³ / 298.05 = 1.1190 × 10⁻³ g/cm³;
- $x$ = 3.545 × 1.1190 × 10⁻³ × 6.19 = 0.02456, $\eta = 1-e^{-x}$ = 0.02426;
- $\Phi_p$ = 1.0020 × 10¹²; exit $\times e^{-3.879\times1.1190\times10^{-3}\times6.19} = \times0.9735 \Rightarrow 0.975\times10^{12}$ (0.978 × 10¹² with the live slot's fits).

**Why they agree.** Note/ours at the entrance = 1.00826 (constant) × 0.99104 (absorbed fraction: ours/note's, 0.02426/0.024476) × 1.00089 (no background, 224 000/223 800) = 1.0001.
- The absorbed fraction combines density ×1/1.0411 and length ×1.0317 (6.19/6), plus the exponential's curvature.
- On any day the density differs from the site mean, the note's fixed table moves the result by the same percentage, about −1 % per kPa.

### P.S. 3. Worked reading at 30 keV (MonP, 75.2 kHz, 500 nA/V: the first live reading's rate)

**Note's formula:**
- $1-e^{-0.0001280\times6} = 7.677\times10^{-4}$;
- $I_i = 2.19\times10^6\times0.5\times75\,200\,/\,(7.677\times10^{-4}\times30) = 3.575\times10^{12}$;
- exit $\times e^{-0.0003572\times6} = \times0.99786 \Rightarrow 3.568\times10^{12}$.

**Ours, standard formula:**
- $N$ = 75 000 Hz, $i$ = 375.0 nA, $P_{\rm abs}$ = 8.145 × 10¹⁰ keV/s;
- $x = \eta$ = 7.61 × 10⁻⁴, $\Phi_p$ = 3.568 × 10¹²;
- $\tau$ = 0.9979, so $\Phi_F$ = 3.560 × 10¹² (NIST), or 3.582 × 10¹² with the live fits.

The two formulas agree to 0.2 %.

**Wall loss (MonP):**
- effective energy for the density: $E_{\rm eff} = 30\times(1.1221/1.1190)^{1/1.76}$ = 30.05 keV;
- the fit: $\Lambda_s = 1-\exp[-((30.05-17.9)/19.7)^{1.17}]$ = 0.4333;
- $\hat\Phi = 3.582\times10^{12}/(1-0.4333) = 3.582\times10^{12}\times1.7646$ = **6.32 × 10¹²** photons/s.

The note's 3.57 × 10¹² is low by this factor of 1.76.

**MonC**, the same reading: $\Lambda_s$ = 0.2715, ×1.373, **4.92 × 10¹²**.

### P.S. 4. The bounds

Symmetric terms in quadrature:
$$\sigma_s = \sqrt{3^2+1.4^2+0.9^2+0.7^2+0.6^2+0.2^2+0.4^2}\ \% = 3.58\ \%,\qquad c_{\rm hi}=1.036,\ c_{\rm lo}=0.964.$$

The wall-loss band around $\Lambda_s$ multiplies both edges:
$$\Lambda_{\rm lo} = \max(0.9\Lambda_s-0.07,\ 0),\qquad \Lambda_{\rm hi} = \Lambda_s+\min\bigl(0.09,\ 2\Lambda_s+0.05\,[E_{\rm eff}>13\ \text{keV}]\bigr).$$
The band covers every one-at-a-time Monte Carlo variant (reach ±10 %, elastic cross section ±20 %, beam 1 mm off centre, density ±3 %) and both two-change corners. That is 140 of 140 gated points per lane, within 2 MC standard errors.

| | Formula $\Phi_F$ | Low | Best | High |
|---|---|---|---|---|
| 10 keV (both lanes) | 0.978 × 10¹² | 0.942 × 10¹² | 0.978 × 10¹² | 1.013 × 10¹² |
| 30 keV MonP ($\Lambda$ 0.320 / 0.433 / 0.523) | 3.582 × 10¹² | 3.582 × 0.964 × 1.471 = 5.08 × 10¹² | 6.32 × 10¹² | 3.582 × 1.036 × 2.098 ≈ 7.78 × 10¹² |
| 30 keV MonC ($\Lambda$ 0.174 / 0.272 / 0.362) | 3.582 × 10¹² | 4.18 × 10¹² | 4.92 × 10¹² | 5.81 × 10¹² |

### P.S. 5. The note's table as a density

$\mu_{en}(10\ \text{keV}) / (\mu_{en}/\rho)_{\rm NIST} = 0.004130 / 3.545 = 1.16502\times10^{-3}$ g/cm³. Ideal N₂ at 101.325 kPa and 20 °C gives 1.16455 × 10⁻³ g/cm³, the same to 0.04 %.

The site mean, $\rho = PM/RT$ with 98.99 kPa and 298.05 K, is 1.11902 × 10⁻³ g/cm³: lower by a factor of 1.0411.
