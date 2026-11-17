# Procedure: measure the N101VTF V2F input impedance on MonC's channel

**Why:** the SR570 output has 50 Ω source impedance (manual). The V2F input resistance R_in loads it, so the V2F sees
V_in = V_SR570 × R_in / (R_in + 50). That is −0.5 % at 10 kΩ and −50 ppm at 1 MΩ. R_in is not on the datasheet
(`references/`). This procedure measures it with MonC's own electronics, without a DVM.

**Method (series-resistor ratio):** hold the SR570 output steady (the SR570's calibrated offset current is the source). Count the
V2F rate with and without a known series resistor R_s between the SR570 OUTPUT and the V2F input, interleaved
A/B/A/B/A. With f0 the V2F's own zero rate:

  r = (f_with − f0) / (f_without − f0) = (R_in + 50) / (R_in + 50 + R_s)
  R_in = R_s · r / (1 − r) − 50

Why this source: measured 2026-11-12 (`data/sweeps/monc_sweep1_results.md`), at 50 nA/V with a CAL 50 nA offset:
- the output is 100.2 kHz, and the 50 nA/V range's dark is stable to ±2 Hz (±2e-5);
- count noise is ~0.5 Hz per 1 s count;
- the absolute accuracy of the source doesn't matter, only its stability across the swaps.

## What you need
- One BNC in-line resistor, or a small BNC box with a series resistor. **R_s = 1.000 kΩ, 0.1 %** (measure it with an ohmmeter and write the value down). Optional: a second, 10 kΩ, for a cross-check.
- A BNC barrel (the "without" configuration), so that both configurations have the same number of connectors.
- MonC only; MonP is not touched. The SR570 writes (step 2) need your OK at the time.

## Expected ratios (R_s = 1 kΩ)
| R_in | r | rate change at 100 kHz |
|---|---|---|
| 10 kΩ | 0.9095 | −9.0 kHz |
| 100 kΩ | 0.99010 | −990 Hz |
| 1 MΩ | 0.99900 | −100 Hz |
| 10 MΩ | 0.99990 | −10 Hz |

- With 60 s per configuration, the resolution in r is about ±2e-5. That gives R_in to ~2 % at 1 MΩ, and better at lower R_in. Above ~10 MΩ, use R_s = 10 kΩ.
- R_s's own tolerance enters R_in directly (0.1 %).

## Steps
1. **Check the logger is running** (1 s counts of S4). The agent confirms this; the file is under `xray_fluxor-data\ca_logger\`.
2. **Set the source** (agent, with your OK). MonC SR570: 50 nA/V, offset CAL, sign +, 50 nA, ON. Expect S4 ≈ 100.2 kHz. Wait ≥ 60 s for it to settle.
3. **In the hutch, at the V2F end of MonC's cable**, so the SR570 side isn't disturbed. Note the time of each swap to the nearest ~5 s:

   | # | Configuration | Hold |
   |---|---|---|
   | A1 | barrel (without) | 60 s |
   | B1 | R_s (with) | 60 s |
   | A2 | barrel | 60 s |
   | B2 | R_s | 60 s |
   | A3 | barrel | 60 s |

   The rate jumps during each swap, because the input is briefly open. Those seconds are discarded.
4. **Zero point f0** (optional; ~8 Hz, negligible at 100 kHz): with the barrel in, set the SR570 offset OFF at 50 nA/V for 60 s, then with R_s for 60 s. This also shows any V2F input-bias effect through R_s; expect ≤ a few Hz.
5. **Restore MonC** (agent): baseline settings, read back.
6. **Repeat on MonP's channel only if you decide to.** It would mean moving the same source cable, or doing it on MonP's own SR570, which needs your separate approval. The V2F channels are probably identical, but that's an assumption.

## Analysis (agent)
- From the logger file, take each configuration's counts, excluding the 12 s after each swap (the near-zero recovery rule doesn't apply at 100 kHz, but the cable transient does).
- Compute the means f_A1…f_A3, f_B1, f_B2.
- Interpolate A to the B times to remove slow drift: r_k = f_Bk / mean(f_A(k), f_A(k+1)).
- Report r ± spread, R_in ± uncertainty (including R_s tolerance), and the loading factor R_in / (R_in + 50) for the physics note.
- If the two r_k disagree by more than 5e-5, the source drifted or a connector is intermittent: repeat.

## What could fool it
- **A connector that changes contact resistance.** The barrel in "without" keeps the connector count the same. Reseat each connection once and look for a step.
- **The 50 Ω output impedance itself is assumed** (manual). R_in is quoted as (R_in + 50) − 50, so an output impedance of 60 Ω would make R_in 10 Ω low: irrelevant above 1 kΩ.
- **A V2F input that isn't purely resistive at DC** (bias current): step 4 checks it.
