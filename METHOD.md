# How we calculate photons/s from the ion chamber current

*Method note, written 2026-11-13. It applies to the C-station ion chambers MonP (upstream) and MonC (downstream), and describes the calculation that runs live in the utilioc slots. The physics evidence is in `physics_note.md`, the finished numbers in `RESULT.md`, the chamber and electronics facts in `CHAMBER_FACTS.md`, and the slot expressions in `calc/`. Where this note and the code differ, the code is what runs. The numbers are for the live constants as of commit 9fff096 (2026-11-13). The energy readback term added on 2026-11-17 (§7 (e′)) moved σ_s from 3.56 to 3.58 % and changed none of the worked numbers. A review of this method, with proposed corrections, is kept separately in `METHOD_REVIEW.md`.*

**What is calculated.** The photon flux $\Phi$ (photons/s) at the chamber's **exit plane**: at the downstream end of the collection region, before the Kapton exit window. The Kapton windows and the air path to the sample are not included.

**The chamber.** A CMC-custom chamber of flowing N₂ at hutch pressure, **guarded**. The user measured it by hand on 2026-11-13 (`analysis/cmc_chamber_geometry.py`):
- the collector is a 60.5 mm plate along the beam, and the HV plate opposite it is 75.5 mm long;
- grounded aluminium guards sit 1 mm beyond each end of the collector, set back 0.51 mm from its face;
- the gap is 10.85 mm at the beam track (±0.2 mm there; the plates are not quite parallel, ±0.5 mm across their 60 mm width);
- 2.7 kV across the gap.

The two lanes use the same chamber build, mounted differently:
- **MonP:** plates vertical, so the beam's horizontal polarization points at them. The beam is taken as centred in the gap [ASSUMED: not measured on MonP].
- **MonC:** plates horizontal, so the polarization lies along them. The beam is 4.90 mm from the collector and 5.95 mm from the HV plate (from the beam scar on the Kapton).

That MonP's chamber is built like the measured one is an assumption.

**Contents**
1. Counts to current
2. Current to ion pairs to absorbed energy
3. Absorbed energy to photons
4. To the exit plane
5. Background subtraction
6. Wall loss and the best estimate
7. Bounds
8. Status flags
9. Full worked examples at 10 and 30 keV

---

## Symbols

| Symbol | Meaning | Value or source |
|---|---|---|
| $C$, $t$ | scaler counts in one gate, and the gate time | `15IDC:scaler1.S3` (MonP), `.S4` (MonC); `.T` |
| $N_{\rm meas}$ | measured rate, $C/t$ | Hz |
| $\hat D$ | background (dark) rate estimate | Hz, §5 |
| $N$ | net rate | Hz |
| $g_V$ | V2F conversion gain | $10^5$ Hz/V (N101VTF, ×1, 0–10 V range) |
| $V$ | SR570 output voltage | V |
| $S$ | SR570 sensitivity | A/V |
| $i$ | chamber current | A |
| $e$ | elementary charge | $1.602176634\times10^{-19}$ C (exact) |
| $\dot n$ | ion pairs collected per second | s⁻¹ |
| $W$ | mean energy spent per ion pair in N₂ | 34.8 eV |
| $P_{\rm abs}$ | power deposited in the gas of the collection region | keV/s |
| $E$ | photon energy (monochromator readback) | keV |
| $\mu/\rho$, $\mu_{\rm en}/\rho$ | mass attenuation and mass energy-absorption coefficients of N | cm²/g, NIST Hubbell–Seltzer |
| $\rho$ | N₂ density | g/cm³ |
| $P$, $T$ | gas pressure and temperature | kPa, °C or K |
| $l$ | collection length: the modelled effective length $l_{\rm eff}$ of the guarded chamber, rounded | 6.19 cm (`calc/monp_transform.py` L_CM) |
| $\delta$ | relative error of $l$: true length $= l(1+\delta)$ | §7 |
| $x$ | absorption thickness for energy, $(\mu_{\rm en}/\rho)\,\rho\, l$ | dimensionless |
| $\eta$ | fraction of the beam energy deposited in the collection region, $1-e^{-x}$ | |
| $\tau$ | transmission over the collection length, $e^{-(\mu/\rho)\rho l}$ | |
| $\Phi_p$ | photons/s entering the collection region | |
| $\Phi_F$ | photons/s at the exit plane from the standard formula (no wall loss) | `userTran1.P` / `userTran4.P` |
| $\Lambda$ | photoelectron energy lost to the plates, per photoelectric absorption (the Monte Carlo) | §6 |
| $\Lambda_s$ | fraction of the **signal** lost to the plates, $f_{\rm pe}\Lambda$ | §6; `userTran3.C` / `userTran6.C` |
| $E_{\rm eff}$ | density-scaled energy at which $\Lambda_s$ is evaluated | §6 |
| $E_0$, $s$, $p$ | the lane's wall-loss fit constants | §6; `quality_slots.WALL_FITS` |
| $\hat\Phi$ | best estimate (wall-loss corrected) | `userTran3.L` / `userTran6.L` |
| $\Phi_{\rm lo}$, $\Phi_{\rm hi}$ | stated low and high bounds | `userTran3.D`, `.E` / `userTran6.D`, `.E` |

**The whole calculation in one line** (each factor is derived in §1–§6):

$$
\hat\Phi \;=\; \underbrace{\frac{(N_{\rm meas}-\hat D)\,S}{g_V}}_{\text{§1, §5: } i}\;\cdot\;\underbrace{\frac{W}{e\,E}}_{\text{§2}}\;\cdot\;\underbrace{\frac{1}{1-e^{-(\mu_{\rm en}/\rho)\rho l}}}_{\text{§3}}\;\cdot\;\underbrace{e^{-(\mu/\rho)\rho l}}_{\text{§4}}\;\cdot\;\underbrace{\frac{1}{1-\Lambda_s(E_{\rm eff})}}_{\text{§6}}
$$

The first four factors make the **standard formula** $\Phi_F$, which is the same for both lanes. The last factor is the wall-loss correction, which is each lane's own. It is exactly 1 for $E_{\rm eff}$ up to 17.9 keV (MonP) or 18.1 keV (MonC).

**Worked-example inputs**, used in every section:

| | Example A | Example B |
|---|---|---|
| Energy $E$ | 10 keV | 30 keV |
| Measured rate $N_{\rm meas}$ (1 s gate) | 224.0 kHz (typical full beam) | 75.2 kHz (the first live reading, 2026-11-12) |
| Background $\hat D$ | 200 Hz | 200 Hz |
| SR570 sensitivity $S$ | 500 nA/V | 500 nA/V |
| Gas | site mean: $P$ = 98.99 kPa, $T$ = 24.9 °C | the same |

The 200 Hz background is typical of MonP's archived no-beam rate at 500 nA/V (182–227 Hz on 2026-11-12, `calc/OPERATOR.md`).

Both examples are worked for the **MonP** lane. §1–§5 are the same for MonC. Where the lanes differ (§6, §7), MonC's 30 keV result is given in a sentence.

---

## 1. Counts to current

The scaler counts the V2F's output pulses for a gate time $t$. The V2F produces a pulse rate proportional to the SR570's output voltage, and the SR570's output voltage is proportional to its input current:

$$
N = g_V\, V, \qquad V = \frac{i}{S} \qquad\Longrightarrow\qquad i = \frac{N\,S}{g_V}.
$$

Here $N$ is the **net** rate, after the background is removed (§5).

**Assumptions at this step.**
- **1a.** The V2F is on its ×1 gain and its 0–10 V input range, so $g_V = 10^5$ Hz/V: 10 V gives 1 MHz. This is the user-confirmed setting. On the 0–5 V range $g_V$ would double, and every result would be 2× too high.
- **1b.** $S$ is the sensitivity last sent from EPICS. The SR570's RS-232 is listen-only, so a change made on the front panel is invisible to the calculation. Gains are therefore changed only from EPICS.
- **1c.** The chain is linear: the SR570 output stays below its 5 V limit (500 kHz). The operating rule lowers the gain above 400 kHz.

The calc decodes the SR570's two EPICS menu indices, $c$ (the number 1, 2, 5, …, 500) and $d$ (pA, nA, µA, mA per volt):

$$
S = \bigl(1 + (c \bmod 3)^2\bigr)\cdot 10^{\lfloor c/3\rfloor + 3d - 12}\ \ \text{A/V}.
$$

For example, $c = 8$ and $d = 1$ give $5\times10^{-7}$ A/V, i.e. 500 nA/V.

**Uncertainty: electronics ±0.7 %** (SR570 gain × V2F scale, including V2F input loading; type B, from the MonC measurements in `ELECTRONICS_CONCLUSIONS.md`, user-approved 2026-11-13). It covers the SR570 gain, the V2F and the scaler.

**Worked example A (10 keV).**
- $N$ = 224 000 − 200 = 223 800 Hz.
- $V$ = 223 800 / 10⁵ = 2.238 V.
- $i$ = 2.238 V × 500 nA/V = **1.119 µA**.

Example B (30 keV): $N$ = 75 000 Hz, $V$ = 0.750 V, $i$ = **375.0 nA**.

---

## 2. Current to ion pairs to absorbed energy

**One charge per ion pair.** An ion pair is made at a distance $x_0$ from the collector, in a gap of width $d$. The electron drifts to one plate and the positive ion to the other. By the Shockley–Ramo theorem, a charge $q$ that moves across a fraction $\Delta x/d$ of the gap induces a charge $q\,\Delta x/d$ in the external circuit. The two carriers together therefore induce

$$
Q = e\,\frac{x_0}{d} + e\,\frac{d-x_0}{d} = e,
$$

which is one elementary charge per pair, wherever the pair was made. So

$$
\dot n = \frac{i}{e}.
$$

Counting both carriers ($2e$ per pair) is a known factor-2 error in some tools. The evidence is in `references/xraydb_two_carrier/CASE.md`.

**Energy per pair.** A photoelectron that stops completely in the gas makes on average one pair per $W$ of energy it deposits. So the power deposited in the gas is

$$
P_{\rm abs} = \dot n\, W = \frac{i\,W}{e}.
$$

**Assumptions at this step.**
- **2a. Saturation.** Every pair is collected: none is lost to recombination, and there is no gas gain. With 2.7 kV across 1.085 cm the chamber is well into the saturation plateau [PROVISIONAL: the HV readout is not verified].
- **2b. $W$ is constant.** $W$(N₂) = 34.8 eV ± 0.6 %, where ± is the full spread of five sources (`data/queries/W_values.md`). $W$ rises slightly for electrons below ~1 keV, such as N K-shell Auger electrons. That adds at most ~0.4 % at 10 keV and is inside the band.
- **2c. The electron spends all its energy in the gas.** This is the **full-thermalization** assumption. It fails above ~15 keV, where photoelectrons reach the plates; §6 corrects for it.
- **2d. The gas is pure N₂.** 1 % of residual air would raise the signal by 0.34 %. With continuous flow this is negligible, except in the first hour after a chamber is opened.

**Worked example A (10 keV).**
- $\dot n$ = 1.119 × 10⁻⁶ / 1.602 × 10⁻¹⁹ = 6.984 × 10¹² pairs/s.
- $P_{\rm abs}$ = 6.984 × 10¹² × 34.8 eV = **2.431 × 10¹¹ keV/s**, i.e. 39 µW.

Example B (30 keV): $\dot n$ = 2.341 × 10¹² pairs/s, and $P_{\rm abs}$ = **8.145 × 10¹⁰ keV/s**.

---

## 3. Absorbed energy to photons

**Energy balance.** $\Phi_p$ photons/s of energy $E$ enter the collection region. Of their energy, a fraction $\eta$ is deposited in the gas over the collection length $l$:

$$
P_{\rm abs} = \Phi_p\, E\, \eta, \qquad \eta = 1 - e^{-x}, \qquad x = \frac{\mu_{\rm en}}{\rho}\,\rho\, l.
$$

So

$$
\Phi_p = \frac{P_{\rm abs}}{E\,\bigl(1-e^{-(\mu_{\rm en}/\rho)\rho l}\bigr)} = \frac{i\,W}{e\,E\,\bigl(1-e^{-(\mu_{\rm en}/\rho)\rho l}\bigr)}.
$$

**Why $\mu_{\rm en}$, not $\mu$.** The coefficient $\mu$ counts every interaction. Some of them deposit nothing locally: Rayleigh scattering, the scattered photon in Compton scattering, and fluorescence that escapes. $\mu_{\rm en}$ counts only the energy handed to electrons. For nitrogen, the photoelectric part plus the Compton-electron part reproduces NIST's $\mu_{\rm en}$ to 0.2 % (`physics_note.md` §2.2).

**The thin-absorber limit.** For $x \ll 1$, $\eta \approx x$, and then

$$
\Phi_p \approx \frac{i\,W}{e\,E\,(\mu_{\rm en}/\rho)\,\rho\, l}.
$$

The flux is then inversely proportional to $\mu_{\rm en}$, $\rho$ and $l$, which is why those three are the leading uncertainties (§7). The calc keeps the exact exponential.

**Gas density.** For an ideal gas,

$$
\rho = \frac{P\,M}{R\,T}, \qquad \frac{M}{R} = \frac{28.0134\ \text{g/mol}}{8.314462618\ \text{J/(mol K)}} = 3.369272\times10^{-3}\ \ \frac{\text{g/cm}^3}{\text{kPa/K}}.
$$

- $T$ is the hutch temperature, `15ID:Sensor2:Temperature`, live.
- $P$ is the live airport pressure. The LOT altimeter setting $A$ is carried along the standard atmosphere to the hutch elevation $h$ = 228 m (`calc/PRESSURE.md`):

$$
P = \bigl(A^{0.190284} - 8.4228807\times10^{-5}\,h\bigr)^{1/0.190284} \qquad (A,\ P \text{ in hPa},\ h \text{ in m}).
$$

**Assumptions at this step.**
- **3a. Monochromatic beam.** Harmonics are not included. A third-harmonic photon is heavily under-counted (§6).
- **3b. $\mu_{\rm en}/\rho$ from NIST,** ± 3 % (half the Scofield–Chantler spread).
  - The live calc uses a cubic fit in $\ln E$ for 5–30 keV: `EXP(7.469-L*(1.833+L*(.5342-L*.06941)))`, with $L = \ln E$.
  - The fit is within 0.6 % of its NIST-anchored target, and within 0.9 % of log-log NIST (worst at 25 keV).
- **3c. The energy is deposited where the photon interacts,** and the secondary electrons stay in the collection region (2c).
  - Strictly, local deposition gives $\eta = (\mu_{\rm en}/\mu)\,(1-e^{-\mu\rho l})$.
  - The form used, $1-e^{-x}$, is 0.11 % larger at 10 keV and 0.07 % larger at 30 keV, which is negligible.
- **3d. The chamber gas is at hutch pressure, and hutch pressure is outdoor pressure.**
  - The open outlet adds 0.0003 %. HVAC adds ≤ 0.025 %.
  - LOT agrees with four other stations to 0.05 % (1σ).
- **3e. The N₂ is at the Sensor2 temperature.** The effect is 0.34 % per kelvin of difference. The sensor's position relative to the chambers is not known.
- **3f. The ideal gas law holds.** Compressibility is 0.03 %.
- **3g. The collection length is the modelled $l_{\rm eff}$, $l$ = 6.19 cm.** The guards end the collecting field within about a millimetre of the collector's ends. A 2-D Laplace and field-line model of the measured chamber gives 61.925 mm (`analysis/collection_length_cmc.py`), 1.4 mm longer than the 60.5 mm collector. The guards' set-back adds to it: flush guards would give 61.1 mm. Its uncertainty is ±1.4 % (§7a). Until 2026-11-13 the calc used the 6.0 cm plate length.

Together, 3d–3f give a live density good to about ±0.2 %: ±0.1 % from pressure, ±0.17 % from temperature if Sensor2 represents the gas to ±0.5 K.

**Worked example A (10 keV).**
- $\rho$ = 98.99 × 3.369272 × 10⁻³ / 298.05 = **1.1190 × 10⁻³ g/cm³**.
- $\mu_{\rm en}/\rho$ = 3.545 cm²/g (NIST).
- $x$ = 3.545 × 1.1190 × 10⁻³ × 6.19 = 0.02456.
- $\eta$ = 1 − e⁻⁰·⁰²⁴⁵⁶ = 0.02426. That is 1.2 % below $x$, so the exponential matters here.
- $\Phi_p$ = 2.431 × 10¹¹ / (10 × 0.02426) = **1.002 × 10¹² photons/s** entering the collection region.

Example B (30 keV):
- $\mu_{\rm en}/\rho$ = 0.1099 cm²/g, 32 times smaller.
- $x$ = 7.61 × 10⁻⁴, and $\eta$ = 7.61 × 10⁻⁴, only 0.04 % below $x$.
- $\Phi_p$ = 8.145 × 10¹⁰ / (30 × 7.61 × 10⁻⁴) = **3.568 × 10¹² photons/s**.

---

## 4. To the exit plane

Photons are removed from the beam by every interaction, so the attenuation uses $\mu$:

$$
\Phi_F = \Phi_p\,\tau, \qquad \tau = e^{-(\mu/\rho)\,\rho\, l}.
$$

Substituting §1–§3 gives the **standard formula**, exactly as the live slot computes it:

$$
\boxed{\;\Phi_F = \frac{N\,S}{g_V}\cdot\frac{W}{e\,E}\cdot\frac{e^{-(\mu/\rho)\rho l}}{1-e^{-(\mu_{\rm en}/\rho)\rho l}}\;}
\qquad\text{slot: } P = J\cdot I\cdot K_0/E/O\cdot \mathrm{EXP}(-6.19NK).
$$

In the slot, $J$ is the net rate, $I$ is $S$, $O$ is $\eta$, $N$ is $\mu/\rho$ and $K$ is $\rho$. The constant collects $W$, $e$, the eV-to-keV factor and $g_V$:

$$
K_0 = \frac{W}{e\cdot10^3\cdot g_V} = \frac{34.8}{1.602176634\times10^{-19}\cdot10^3\cdot10^5} = 2.17205\times10^{12}.
$$

**Assumptions at this step.**
- **4a. No gas between the end of the collection region and the exit window** ($l_{\rm gap} = 0$). This gap is not measured yet. Each cm of N₂ costs 0.43 % at 10 keV and 0.034 % at 30 keV.
- **4b.** $\mu/\rho$ is from NIST, through a cubic fit like 3b. Its uncertainty enters only through $1-\tau$, a few percent of a few percent.
- **4c.** Gas and windows **upstream** of the collection region do not enter, because the reference plane is downstream of them.

**Worked example A (10 keV).**
- $\mu/\rho$ = 3.879 cm²/g, so $\tau$ = e^(−3.879 × 1.1190 × 10⁻³ × 6.19) = 0.9735.
- $\Phi_F$ = 1.002 × 10¹² × 0.9735 = **0.975 × 10¹² photons/s** at the exit (NIST).
- The live slot's fits give **0.978 × 10¹²** (+0.2 %), or **4.37 × 10⁶ photons/s per net Hz** at 500 nA/V.
- With the 6.0 cm plate length used before 2026-11-13, the same reading gave 1.009 × 10¹². The longer $l$ lowers the formula by 3.1 %.

Example B (30 keV): $\tau$ = 0.9979, so $\Phi_F$ = **3.560 × 10¹²** photons/s (NIST), or **3.582 × 10¹²** with the live fits (+0.6 %). That is 4.78 × 10⁷ photons/s per Hz.

---

## 5. Background subtraction

With no beam, the scaler still counts a few tens to hundreds of Hz. This comes from the SR570's input offset (set by hand), its output offset, and the V2F's zero. The calc treats it as an additive rate and subtracts it:

$$
N = \begin{cases}\max\bigl(N_{\rm meas} - \hat D,\ 0\bigr) & t > 0\\ 0 & t \le 0.\end{cases}
$$

The clamp at 0 stops dark noise from producing a negative flux with no beam. The bounds then always bracket the result.

**The estimator** (the background slot `userTran2` / `userTran5`, scanned every 1 s):
- **When it updates.** A sample $k$ counts as no-beam when the raw rate has stayed below $r_{\rm th}$ = 400 Hz for longer than $t_s$ = 10 s. That covers both a closed shutter and a beam dump.
- **How it averages.** A running mean, which becomes an exponential average once $K_{\max}$ = 60 samples are in:

$$
\hat D_k = \hat D_{k-1} + \frac{r_k - \hat D_{k-1}}{K}, \qquad K = \min(k, K_{\max}).
$$

- **With beam on,** $\hat D$ holds its last value.
- **Gain tag.** Each estimate is tagged with the gain code $c + 10d$ it was taken at. If the gain has changed since, the estimate is **stale**: it is still subtracted, and status bit 2 is set (§8).

**Assumptions at this step.**
- **5a.** The dark rate at the current gain and offset settings has not changed since the last no-beam period. The dark is output-referred and range-dependent, and it drifts by tens of Hz in the first hour after power-on.
- **5b.** Only the gain is tagged, not the SR570 offset state. Re-tweaking the offset by hand at the same gain leaves an old estimate unflagged (`calc/HANDOFF.md`, Known traps).
- **5c.** A rate below 400 Hz means no beam. A very weak beam, such as a heavily detuned mono, would be taken as background.

**Its effect on the flux.** The error is $\delta\Phi/\Phi = \delta\hat D / N$:
- It is negligible at normal rates: 0.1 % for a 200 Hz error at 200 kHz.
- It matters when the rate is low: 2 % at 10 kHz, 20 % at 1 kHz.

**Worked example A (10 keV).**
- The subtraction is 200 / 224 000 = 0.09 % of the reading.
- The day's scatter of the dark, ±33 Hz, is ±0.015 % of the flux.

Example B (30 keV): the subtraction is 0.27 %, and the scatter ±0.04 %.

---

## 6. Wall loss and the best estimate

**The physics.**
- Above ~16 keV the N K-shell photoelectron, with kinetic energy $T_0 = E - 0.41$ keV, can travel farther than the distance from the beam to a plate: 5.4 mm on MonP (centred), and 4.9 mm to the collector on MonC.
- The beam is polarized horizontally, and photoelectrons are emitted preferentially along the polarization (Sauter: $d\sigma/d\Omega \propto \sin^2\theta\cos^2\varphi/(1-\beta\cos\theta)^4$).
- MonP's **vertical** plates face the polarization, so the electrons are aimed at them.
- MonC's **horizontal** plates lie along it, so most electrons run parallel to the plates and only the spread of the emission and scattering brings them to a plate. MonC's loss is therefore smaller, about 0.6 of MonP's at 30 keV.
- An electron that hits a plate with kinetic energy left over gives that energy to the metal, where it makes no ion pairs. Assumption 2c then fails, and the formula under-counts the photons.
- For scale, the CSDA ranges in the gas are 2.4 mm at 10 keV, 4.9 mm at 15 keV and 17 mm at 30 keV.

**Definition.** For each photoelectric absorption, $\Lambda$ is the mean energy carried into the plates, as a fraction of the photon energy $E$. The Auger electron (0.41 keV) deposits locally. The deposited power becomes

$$
P_{\rm abs} = \Phi_p\,E\,\eta\,\bigl[1 - f_{\rm pe}\,\Lambda\bigr],
$$

where $f_{\rm pe}$ is the photoelectric share of $\mu_{\rm en}$. Compton electrons carry at most 3 keV at 30 keV, travel ≲0.3 mm, and never reach a plate.

$f_{\rm pe}$ = photo / (photo + Compton-electron), from xraydb (Elam photoelectric cross section and mean Compton-electron energy; `data/queries/out/xraydb_N.csv`). It is 0.986 at 20 keV, 0.964 at 25 keV and 0.925 at 30 keV.

**From here on, $\Lambda_s \equiv f_{\rm pe}\Lambda$ is the signal loss.** The live slot's C holds $\Lambda_s$, and the best estimate is

$$
\boxed{\;\hat\Phi = \frac{\Phi_F}{1-\Lambda_s(E_{\rm eff})}\;}
\qquad\text{slot: } L = A/(1-C).
$$

Until 2026-11-13 the live calc took $f_{\rm pe} = 1$, treating all of the deposited energy as photoelectron energy. That made the correction 7 % too large at 30 keV (1.7 % at 25 keV, 0.2 % at 20 keV). It was corrected on 2026-11-13.

**Where $\Lambda$ comes from.** A Monte Carlo of each chamber as mounted (`analysis/wall_loss_mc.py`, run per lane by `analysis/wall_loss_families.py`; `physics_note.md` §3.1):
- **Start:** a Sauter angular distribution, with the polarization toward the plates (MonP) or along them (MonC).
- **Scattering:** single elastic scattering (screened Rutherford, Molière screening).
- **Energy loss:** continuous slowing down from NIST ESTAR.
- **Geometry:** plates at ±5.425 mm from mid-gap (the 10.85 mm gap), infinite in width and length.
  - MonP: the beam is centred, Gaussian, 1 mm FWHM across the gap (the horizontal beam size).
  - MonC: the beam is 0.525 mm toward the collector, 0.03 mm FWHM across the gap (the vertical beam size, 20–40 µm).
  - The plates are 60 mm wide and the beam is 2 mm inboard of their centre, so at least 28 mm from a side edge. That is beyond the 17 mm range at 30 keV, so the infinite-width model holds for MonC's sideways electrons too.
- **At a plate:** the electron gives the plate its remaining energy. Backscatter from the plate is not modelled.
- **Validation:** the depth holding 90 % of the energy is 0.74 $R_G$ at 10, 20 and 30 keV, matching Grün's measured depth–dose curve for electrons in air.

Each lane's signal loss $f_{\rm pe}\Lambda_{\rm MC}$ is fitted as (`analysis/wall_loss_fit.py`)

$$
\Lambda_s(E) = \begin{cases} 1 - \exp\!\Bigl[-\Bigl(\dfrac{E-E_0}{s}\Bigr)^{p}\Bigr] & E > E_0\\[4pt] 0 & E \le E_0\end{cases}
$$

| Lane | $E_0$ (keV) | $s$ (keV) | $p$ | max \|fit − $f_{\rm pe}$ MC\| at the MC energies |
|---|---|---|---|---|
| MonP | 17.9 | 19.7 | 1.17 | 0.009, at 21 keV |
| MonC | 18.1 | 27.0 | 1.41 | 0.004, at 22 keV |

The MC energies are 8, 10, 12–18 (in 1 keV steps), 18.5, 19, 19.5, 20, 21, 22, 25, 28 and 30 keV. The 18.5–21 keV points were added on 2026-11-13 (METHOD_REVIEW Q1), because the onset of the fits lies there; the band is gated on them too.

**The fit follows the live density.** All electron path lengths scale as $1/\rho$, and the CSDA range goes as $R \propto T^{1.76}/\rho$. A chamber at density $\rho$ therefore behaves, to first order, like the Monte-Carlo chamber at its reference density $\rho_0$ with electrons of an equivalent energy:

$$
\frac{E_{\rm eff}^{1.76}}{\rho_0} = \frac{E^{1.76}}{\rho} \qquad\Longrightarrow\qquad E_{\rm eff} = E\,\Bigl(\frac{\rho_0}{\rho}\Bigr)^{1/1.76}, \quad \rho_0 = 1.1221\times10^{-3}\ \text{g/cm}^3.
$$

$\rho_0$ is the density the MC ran at (99.26 kPa, 24.9 °C). Two parts of the physics do not scale this way: the beam width, which is fixed in mm, and the energy dependence of the angular distribution. Checked against each lane's MC runs at ±3 % density at 30 keV, the scaled fit gives $\partial\ln[1/(1-\Lambda_s)]/\partial\ln\rho$ = −0.93 (MonP) and −0.64 (MonC), against −0.83 and −0.54 from the MC. The fit overstates the MC's density dependence by about 0.1; at the ±0.2 % live density error that is below 0.03 % on the result.

**Assumptions at this step.**
- **6a.** The geometry is as modelled (above), with the polarization fully horizontal. The gap varies by ±0.5 mm across the plate width, about ±5 % of the reach, which is inside the ±10 % reach variants of the band (§7f).
- **6b.** No plate backscatter. That makes $\Lambda$ slightly too large; the low edge of the band allows for it (§7).
- **6c.** Compton electrons deposit all their energy in the gas, so only the photoelectric share $f_{\rm pe}$ of the signal is exposed to wall loss (above).
- **6d.** MonP's beam is centred in its gap [ASSUMED], and MonP's chamber is built like the measured one [ASSUMED]. The band's 1 mm offset variant covers a beam off centre by up to 1 mm.
- **6e.** The fit is a single function of energy, so $f_{\rm pe}$ is in effect evaluated at $E_{\rm eff}$ rather than at $E$, although it does not depend on density. At 30 keV and ±3 % density this shifts $\Lambda_s$ by about ±0.002 or less, below the MC's statistical error.

**Worked example B (30 keV, MonP).**
- $E_{\rm eff}$ = 30 × (1.1221/1.1190)^0.568 = 30.05 keV. The site mean is 0.3 % less dense than the MC reference.
- $\Lambda_s$ = 0.4333.
  - The MC signal loss at 30 keV is $f_{\rm pe}\Lambda_{\rm MC}$ = 0.9245 × 0.4624 = 0.4275.
  - The fit sits 0.004 above it at 30.00 keV, and the density shift adds 0.0015.
- $\hat\Phi$ = 3.582 × 10¹² / (1 − 0.4333) = 3.582 × 10¹² × 1.765 = **6.32 × 10¹² photons/s**.

**MonC at 30 keV:** $\Lambda_s$ = 0.2715, so the correction is ×1.373, and the same reading would give $\hat\Phi$ = **4.92 × 10¹²** photons/s.

Example A (10 keV): $E_{\rm eff}$ = 10.02 keV, so $\Lambda_s = 0$ exactly and $\hat\Phi = \Phi_F$. Even a straight-line 10 keV track (2.4 mm) cannot reach a plate from the beam edge, 4.9 mm away on either lane. Every gated MC variant is below 10⁻⁴ up to 13 keV; the three-change stress corner (§7f) reaches 3 × 10⁻⁴ there.

---

## 7. Bounds

*Which of these terms matter for absolute flux, and which for normalising (relative flux at one energy, or across energies), is sorted in `UNCERTAINTY.md`.*

The bounds are built from seven terms. Each one below gives what sets it and how it enters.

**(a) Collection length: ±1.4 %, symmetric.**
- If the true collection length is $l(1+\delta)$ instead of $l$, then, for the thin gas, $\eta \propto l$ and the true flux is

$$
\Phi_{\rm true} = \Phi_F\,\frac{1-e^{-x}}{1-e^{-x(1+\delta)}} \;\approx\; \frac{\Phi_F}{1+\delta}.
$$

- The guards make $\delta$ small and two-sided, so the term is symmetric: $|\partial\ln\Phi/\partial\ln l| \approx 1$.
- Its size is the model's spread over the measurement tolerances. Each tolerance contributes the largest change of $l_{\rm eff}$ from its nominal 61.925 mm (`analysis/out/collection_length_cmc.csv`):

| Tolerance | Largest change of $l_{\rm eff}$ |
|---|---|
| collector length ±0.5 mm | 0.81 % |
| guard set-back 0.51 ± 0.25 mm | 0.73 % |
| collector-to-guard gap 1 ± 0.5 mm | 0.57 % |
| beam height ±1 mm | 0.24 % |
| HV plate 2 mm shorter | 0.16 % |
| guard touching the end wall | 0 |
| 2-D model allowance (the chamber is 3-D) | 0.5 % |
| **quadrature sum** | **1.35 %, carried as 1.4 %** |

- `quality_slots.collection_term()` recomputes the sum from the CSV, and the self-test checks that the carried 1.4 % is not below it.
- Until 2026-11-13 the chamber was taken as unguarded, and this term was a one-sided allowance of up to −13.6 % on the flux.
- Only an absolute calibration (pixel detector plus foils) removes this term.

**(b) $\mu_{\rm en}/\rho$: ±3 %.**
- From §3, $\partial\ln\Phi_F/\partial\ln\mu_{\rm en} = -x e^{-x}/(1-e^{-x}) \approx -(1 - x/2)$. That is −0.988 at 10 keV and −1.000 at 30 keV.
- The cross-section fit (3b) adds up to 0.9 % (vs log-log NIST, worst at 25 keV). It is carried as its own term, ±0.9 %, in $\sigma_s$.

**(c) $W$: ±0.6 %.** $\Phi_F \propto W$ exactly.

**(d) Density: ±0.2 % (live).**
- Directly, $\partial\ln\Phi_F/\partial\ln\rho = -x e^{-x}/(1-e^{-x}) - (\mu/\rho)\rho l$. That is −1.01 at 10 keV and −1.00 at 30 keV.
- Above ~18 keV the best estimate also depends on density through $E_{\rm eff}$. The wall-loss part is

$$
\frac{\partial}{\partial\ln\rho}\,\ln\frac{1}{1-\Lambda_s(E_{\rm eff})} = -\frac{E_{\rm eff}}{1.76}\,\frac{\Lambda_s'(E_{\rm eff})}{1-\Lambda_s}.
$$

- At 30 keV that is −0.93 on MonP and −0.64 on MonC, so the totals there are −1.93 and −1.64. The ±0.2 % then becomes ±0.39 % and ±0.33 %, still small.

**(e) Electronics: ±0.7 %** (`ELECTRONICS_CONCLUSIONS.md`).

**(e′) Energy readback: ±0.4 %** (added 2026-11-17, user: "Add the term"; CHAMBER_FACTS F9.7).
- The flux depends on the energy the monochromator reports: $\partial\ln\hat\Phi/\partial\ln E$ = 2.2 below 15 keV, rising with the wall-loss correction to 3.7 on MonP (3.2 on MonC) at 29.5 keV.
- The readback error is ASSUMED to be 0.1 % ($\delta E/E$); no edge scan has measured it. 0.1 % × 3.7, rounded up, is 0.4 %, carried at every energy.

**(f) Wall-loss band: $[\Lambda_{\rm lo}, \Lambda_{\rm hi}]$ around $\Lambda_s$.** The same band formula is used on both lanes, around each lane's own $\Lambda_s$.
- For each lane, the band covers every one-at-a-time MC variant of that chamber, each scaled by $f_{\rm pe}$: electron reach ±10 %, elastic cross section ±20 %, beam 1 mm further off centre, density ±3 %.
- It also covers the two two-change corners: reach +10 % with σ −20 %, which is the upper edge, and reach −10 % with σ +20 %.
- That is 140 of 140 points per lane at 14–30 keV, within 2 MC standard errors (`analysis/out/wall_loss_fit_MonP.txt`, `_MonC.txt`). The check is made at the MC energies, which include 18.5, 19, 19.5 and 21 keV around the fits' onset; the reviewer's 0.05 keV interpolated grid also passes (METHOD_REVIEW §1d).
- One gated corner is covered only within the 2 s.e. allowance, not strictly: on MonP, reach +10 % with σ −20 % is up to 0.004 above $\Lambda_{\rm hi}$ at 23–27 keV (s.e. 0.002; METHOD_REVIEW R3). That is about 0.6 % on the high bound at 25 keV.
- The three-change corner (adding the 1 mm offset) is reported as a stress case and is not covered. The user accepted this on 2026-11-13 (PLAN.md; METHOD_REVIEW N1):
  - on MonP it is above the band at 18 keV (0.081 against 0.056), about 2.7 % on the high bound, and at 25 keV (0.361 against 0.351), about 1.5 %; on a fine grid the worst is +0.028 at 17.9 keV, about 3 %;
  - on MonC it is above at 18 and 18.5 keV, by 0.003.
- The lower edge also allows for plate backscatter, which the MC does not model:

$$
\Lambda_{\rm lo} = \max(0.9\,\Lambda_s - 0.07,\ 0), \qquad
\Lambda_{\rm hi} = \Lambda_s + \min\bigl(0.09,\ 2\Lambda_s + 0.05\,[E_{\rm eff} > 13\ \text{keV}]\bigr).
$$

- The $0.05\,[E_{\rm eff}>13]$ floor covers 13 keV up to the fit's start (17.9 keV MonP, 18.1 keV MonC). There the fit is zero, but the gated variants reach up to 0.017 (MonP) and 0.026 (MonC), both from the 1 mm offset variant.

**How they combine.** All the symmetric terms, (a)–(e′) and the cross-section fit, add in quadrature:

$$
\sigma_s = \sqrt{3^2 + 0.6^2 + 0.7^2 + 0.2^2 + 0.9^2 + 1.4^2 + 0.4^2}\ \% = 3.58\ \%.
$$

The wall-loss band (f) then **multiplies** both edges. It is stacked linearly, not in quadrature, and that is conservative:

$$
\boxed{\;
\Phi_{\rm hi} = \Phi_F\,\frac{c_{\rm hi}}{1-\Lambda_{\rm hi}}, \qquad
\Phi_{\rm lo} = \Phi_F\,\frac{c_{\rm lo}}{1-\Lambda_{\rm lo}}, \qquad
c_{\rm hi} = 1+\sigma_s \to 1.036,\quad
c_{\rm lo} = 1-\sigma_s \to 0.964
\;}
$$

$c_{\rm hi}$ is rounded up and $c_{\rm lo}$ down, to 3 decimals. The slot expressions are `D = A*.964/(1-MAX(.9*C-.07,0))` and `E = A*1.036/(1-C-MIN(.09,2*C+.05*(B>13)))`, with $A = \Phi_F$, $B = E_{\rm eff}$ and $C = \Lambda_s$. CLCC, which computes $C$, is the lane's own:
- MonP: `B>17.9?1-1/EXP(((B-17.9)/19.7)^1.17):0`;
- MonC: `B>18.1?1-1/EXP(((B-18.1)/27)^1.41):0`.

They are built from named constants in `calc/quality_slots.py` (SYMMETRIC_TERMS, HIGH_FACTOR, LOW_FACTOR, BAND, WALL_FITS).

Relative to the best estimate, the published percentages (`.F` and `.G`) are

$$
u = c_{\rm hi}\,\frac{1-\Lambda_s}{1-\Lambda_{\rm hi}} - 1, \qquad
d = 1 - c_{\rm lo}\,\frac{1-\Lambda_s}{1-\Lambda_{\rm lo}}.
$$

**What the bounds are.** They are stated bounds, not a confidence interval:
- each side is ~1σ of the symmetric terms, times the full edge of the wall-loss band on that side.

Below $E_{\rm eff}$ = 13 keV the bounds are therefore symmetric, ±3.6 %. Above it they are asymmetric, because the band is.

**Worked example A (10 keV).**
- $\Lambda_s = \Lambda_{\rm lo} = \Lambda_{\rm hi} = 0$, so $u$ = +3.6 % and $d$ = −3.6 %.
- Range **0.942 – 1.013 × 10¹²** photons/s around 0.978 × 10¹².

**Worked example B (30 keV, MonP).**
- $\Lambda_s$ = 0.4333, $\Lambda_{\rm lo}$ = 0.320, $\Lambda_{\rm hi}$ = 0.523.
- The wall-loss factors $1/(1-\Lambda_{\rm lo})$, $1/(1-\Lambda_s)$ and $1/(1-\Lambda_{\rm hi})$ are 1.471 / 1.765 / 2.098.
- $\Phi_{\rm lo}$ = 3.582 × 10¹² × 0.964 × 1.471 = **5.08 × 10¹²**.
- $\Phi_{\rm hi}$ = 3.582 × 10¹² × 1.036 × 2.098 ≈ **7.78 × 10¹²** (7.784 unrounded).
- So $u$ = +23.2 % and $d$ = −19.7 %.
- The wall-loss band alone is +18.9 % / −16.7 %. The rest comes from $c_{\rm hi}$ and $c_{\rm lo}$.

**MonC at 30 keV:** $\Lambda_s$ = 0.2715, $\Lambda_{\rm lo}$ = 0.174 and $\Lambda_{\rm hi}$ = 0.362, which gives **4.18 – 5.81 × 10¹²** around 4.92 × 10¹² (+18.2 / −14.9 %).

---

## 8. Status flags, briefly

Each lane publishes a **status code**: the sum of six bits, each also its own 0/1 PV. Any bit gives MINOR, and bits 16 or 32 give MAJOR. The flux is always published; the flags only add severity.

| Bit | Condition | What it means for the number |
|---|---|---|
| 1 | $E$ > 12.5 keV | wall loss is possible: the band is wider from $E_{\rm eff}$ > 13 keV, and the result is MC-corrected above $E_{\rm eff}$ = 17.9 keV (MonP) or 18.1 keV (MonC). 12.5 keV is $13 \times 0.934^{0.568}$ = 12.505, rounded down: down to 0.934 ρ₀ the bit is set wherever the band is widened. The lowest density seen at the site is 0.95 ρ₀, so there is a margin of 1.6 % (12.6 keV until 2026-11-13, which had none; METHOD_REVIEW N2) |
| 2 | background stale (another gain, or none yet) | the old $\hat D$ is still subtracted (§5) |
| 4 | pressure not updated for 2 h | the last $P$ is used; the weather moves it ~0.4 %/day |
| 8 | no beam for longer than the settle time | $N \approx 0$; the bounds are not meaningful |
| 16 | $E$ outside 4.9–30.5 keV (MAJOR) | the cross-section fits are extrapolated |
| 32 | count time ≤ 0 (MAJOR) | the scaler is not counting; there is no rate |

Example A gives code 0 (NO_ALARM), and example B gives code 1 (MINOR). The full table, with PV names, is in `calc/OPERATOR.md`.

---

## 9. Full worked examples at 10 and 30 keV

The inputs are as listed at the top: site-mean gas, 500 nA/V, 200 Hz background, MonP lane. The column "matters?" says whether the step's **uncertainty** moves the answer at that energy.

| Step | Quantity | A: 10 keV | matters? | B: 30 keV (MonP) | matters? |
|---|---|---|---|---|---|
| 1 | net rate $N$ | 223 800 Hz | | 75 000 Hz | |
| 1 | current $i$ | 1.119 µA | ±0.7 % electronics | 375.0 nA | ±0.7 %, minor next to (f) |
| 2 | pairs/s $\dot n$ | 6.98 × 10¹² | | 2.34 × 10¹² | |
| 2 | $P_{\rm abs}$ | 2.43 × 10¹¹ keV/s | $W$ ±0.6 % | 8.15 × 10¹⁰ keV/s | ±0.6 %, nugatory |
| 3 | $\rho$ | 1.1190 × 10⁻³ g/cm³ | ±0.2 % | the same | ±0.37 % with wall-loss coupling, nugatory |
| 3 | $\mu_{\rm en}/\rho$ | 3.545 cm²/g | **±3 %, leading term** | 0.1099 cm²/g | ±3 %, sub-dominant |
| 3 | $l$ | 6.19 cm | ±1.4 %, second term | the same | ±1.4 %, sub-dominant |
| 3 | $x$ → $\eta$ | 0.0246 → 0.0243 | exponential matters (1.2 %) | 7.61 × 10⁻⁴ → 7.61 × 10⁻⁴ | **nugatory**: $\eta = x$ to 0.04 % |
| 3 | $\Phi_p$ | 1.002 × 10¹² | | 3.568 × 10¹² | |
| 4 | $\tau$ | 0.974 | 2.7 % correction; its error is ~0.1 % | 0.998 | **nugatory** (0.2 %) |
| 4 | $\Phi_F$ (live fits) | 0.978 × 10¹² | | 3.582 × 10¹² | |
| 5 | dark share $\hat D/N_{\rm meas}$ | 0.09 % | nugatory | 0.27 % | nugatory |
| 6 | $E_{\rm eff}$, $\Lambda_s$ | 10.02 keV, **0** | **nugatory: exactly zero** | 30.05 keV, **0.433** | **dominant: ×1.76** |
| 6 | best estimate $\hat\Phi$ | **0.978 × 10¹²** | | **6.32 × 10¹²** | |
| 7 | **bounds** | **0.942 – 1.013 × 10¹² (±3.6 %)** | | **5.08 – 7.78 × 10¹² (+23 / −20 %)** | |

MonC differs only from step 6: at 30 keV it gives ×1.37, **4.92 × 10¹²**, with bounds 4.18 – 5.81 × 10¹² (+18 / −15 %).

**At 10 keV** the calculation is the textbook ion-chamber formula, and nothing about it is subtle.
- The photoelectrons stop in the gas, well short of the plates, so there is no wall loss and the result equals the formula, on both lanes.
- The band is symmetric, ±3.6 %. It is set by $\mu_{\rm en}$ (±3 %) and then the collection length (±1.4 %).
- Two corrections are real but small and well known: the absorption exponential (1.2 %) and the exit transmission (2.7 %).

**At 30 keV** three things change together.

1. **The gas is nearly transparent.**
   - $\mu_{\rm en}/\rho$ falls 32-fold from 10 keV. Only 0.076 % of the beam energy is absorbed, and $\mu/\rho$ falls 13-fold.
   - So the absorption exponential (3c) and the exit transmission (§4) become **nugatory**: the formula reduces to its thin-absorber limit, $\Phi_F \approx iW/(eE\,\mu_{\rm en}\, l)$.
   - Each count now stands for 11× more photons: 4.78 × 10⁷ per Hz against 4.37 × 10⁶.
2. **The photoelectrons reach the plates.**
   - The 17 mm CSDA range is three times the beam-to-plate distance.
   - On MonP, whose plates face the polarization, 46 % of the photoelectron energy goes into the metal. The Compton electrons (7.5 % of the signal) stay in the gas, so 43 % of the signal is lost and the formula is low by ×1.76.
   - On MonC, whose plates lie along the polarization, 27 % of the signal is lost (×1.37).
   - This one term, and its band (+18.9 / −16.7 % on MonP), sets the answer and its uncertainty.
   - Everything symmetric ($\mu_{\rm en}$, $l$, $W$, electronics, density) becomes **sub-dominant**. In quadrature with the wall-loss band it would move the high bound by only ~0.3 points. Stacked linearly, as the live calc does, it contributes about 4 points (+18.9 % becomes +23.2 %).
3. **Density enters twice.**
   - Denser gas absorbs more (−1 %/%), and it also shortens the electron tracks, which reduces the wall loss (another −0.93 %/% on MonP, −0.64 %/% on MonC).
   - The total is −1.93 %/% on MonP. That is still nugatory with the live ±0.2 % density, but it would matter (±1.5 %) with fixed site-mean constants.

The dark subtraction, gas purity, recombination and the $W$ energy dependence are nugatory at both energies.

**Consistency check.** The first live reading (MonP, 2026-11-12, 30.0 keV, 75.2 kHz at 500 nA/V, 22.2 °C) gave, live, a formula flux of 3.66 × 10¹² with the 6.0 cm length then in use (`RESULT.md`). With the calc as of a84c2ca, the same reading gives a formula flux of 3.56 × 10¹² and a best estimate of **6.23 × 10¹²**, range 5.01–7.66 × 10¹². That is evaluated at the reading's own 22.2 °C density, assuming the site-mean pressure and no dark subtraction. Example B differs from it in two ways:
- on the formula, example B is 0.6 % higher: +0.9 % because the reading's gas was denser, less 0.27 % for the 200 Hz dark that B subtracts;
- on the result, B is 1.4 % higher, because the denser gas also lowers $E_{\rm eff}$.
