# Design: freeze detector for the E-station lane (proposed; not built)

Date: 2026-11-17. Status: scoped at the user's request ("Yes, scope it", 2026-11-17); waiting for the user's go-ahead to build and reinstall. Related: `TODO.md` item "detect a FROZEN input"; the dashboard spec open item 0.

## The problem (verified 2026-11-17)
The TetrAMM IOC stayed connected and reported Acquiring, but its readings stopped changing (channel 3 constant at 0.6972573897461134 nA, channel 4 at 0.12490693844901432 nA over many seconds; every TetrAMM PV shares one last-update timestamp). The E-station lane keeps publishing the last value: the status stays at its no-beam state (code 9, MINOR) and RESULT shows NO_ALARM. The lane detects a dead link (RESULT goes INVALID), not a frozen source.

## Design
**Idea:** an exactly equal sum of the two channel currents on consecutive scans means the source did not update. Real readings are 0.1 s means of a 24-bit ADC with noise: two scans one second apart are never exactly equal while the instrument is live, so equality is a strong, cheap signature of a frozen source. After N identical scans the lane raises its existing MAJOR flag.

**Where:** the flags slot `userTran11` (free letters M, N, O, P; no other slot changes, the flux and bounds slots are untouched):
| Letter | Role | Expression or link |
|---|---|---|
| M | channel 3 current (nA), input | link `userTran9.A` (read-only, NPP NMS) |
| N | channel 4 current (nA), input | link `userTran9.B` |
| O | count of consecutive identical scans (state) | `M+N==P?O+1:0` |
| P | the previous sum (state) | `M+N` |
| K (bit 32) | raw current fault | `B>0||O>=10` (was `B>0`) |
State letters use the evaluator's rule: a letter referenced before it is computed holds its previous value (as in the background-estimate slot, `calc/background_transform.py`). K reads O from the previous scan (a one-scan lag, harmless). Every string is at most 39 characters.

**Meaning of bit 32 after the change** (still MAJOR): raw current fault = sum below -5 nA, or a channel at or above 99 % of the 120 uA full scale, or NaN (all computed in the flux slot, letter O of `userTran9`), **or the source frozen: the sum unchanged for 10 scans (10 s)**. The threshold is a named constant (`FREEZE_SCANS = 10`) feeding the expression, the comments and the tests. The flux and RESULT keep being published (user rule: a number with a warning beats none); the status goes MAJOR (code 41 when only bit 1 and bit 8 were set before: 1 + 8 + 32).

**Why 10 scans:** the two slots are 1 s scans on unsynchronised phases, so one flux update can occasionally be read twice (a count of 1, then reset); ten in a row cannot happen with a live source, while ten seconds of a frozen reading is a short enough delay to be useful. The user can change the constant.

**What it does not do:** it does not detect a source that is live but wrong, a slow drift, or a frozen reading that happens to equal zero (the sum of two dark channels is never exactly zero in practice). It is not applied to MonP and MonC (their inputs are integer scaler counts, and the same count twice is normal).

## Behaviour to expect
- A disconnected link: the flux slot's A and B keep their last values, the sum repeats, the detector fires after 10 s (MAJOR) while RESULT is INVALID: both warnings agree.
- A frozen source (today's case): bit 32, status MAJOR after about 10 s, RESULT unchanged and NO_ALARM (the number is shown with the warning; the dashboard draws ALARM).
- Recovery: the counter resets on the first changed sum; the flag clears within 1 to 2 s of the source resuming.
- Restart of the utilioc: the state letters are autosaved with the other letters; a counter saved at 10 or more clears on the first changed sum.

## Work (small; one subagent task plus review)
1. `calc/estation_lane.py`: the `FREEZE_SCANS` constant; the new expressions, comments (CMTM to CMTP) and links (INPM, INPN) of the flags slot; bit 32's `FLAG_BITS` text and CMTK; `check_letter_order()` to allow the two intentional state references (K reads O, O reads P) and nothing else; `evaluate_lane()` able to run a sequence of scans with state (the evaluator's `state` argument).
2. Tests: a sequence of identical sums sets bit 32 at the 10th identical scan and not before; a changing sequence never sets it; recovery clears it; NaN, negative and full-scale cases unchanged; a single repeated read does not trip it; the strings stay at most 39 characters; the letter-order test; the flags code and severity.
3. Installer (`calc/install_lane.py --lane EStn`): the flags verifier must handle the two state letters and the lagged K (verify M and N against the flux slot's A and B within one scan, and K against the slot's own O from the previous scan, or tolerate the one-scan lag explicitly); the offline fake IOC in `tests/test_install_estation.py` evaluates the new strings with `calc_eval` (state across scans). The reinstall uses the existing guarded procedure for a commissioned lane: all four slots are disabled, rewritten, verified and re-enabled; the TetrAMM links are kept; no test currents. **Do not re-run it during a measurement** (the E-station has no beam now).
4. Docs in the same commits: `calc/HANDOFF.md` (letter map, bit 32 text, known behaviour), `calc/OPERATOR.md` (bit 32 and what to do when it is set: check the TetrAMM IOC), the dashboard spec and brief (bit 32 legend text; the dashboard's ALARM state already covers bit 32), `docs/` model export note, `PLAN.md` row, `PROGRESS.md` entry.
5. Live check: `--compare` shows 0 differences afterwards; MonP and MonC `--compare` still 0; with the TetrAMM still frozen, bit 32 sets within about 12 s of the reinstall (a real test), and clears when the user fixes the TetrAMM (a second real test).

## Scope guard (stop and ask)
Writes only to `userTran11` (and the Enable of the four lane slots during the guarded reinstall), through the guarded installer; no change to the flux, bounds or status slots' content; no write to any TetrAMM or beamline PV; no restart. The reinstall is the user's approved procedure (the lane install, 2026-11-16) but this change needs the user's go-ahead (asked 2026-11-17).

## Risks
The detector would fire on a source that is legitimately constant to the last digit; the TetrAMM averaged readings are not (observed: the dark readings change every update). If a false trip ever occurs, raise `FREEZE_SCANS` and reinstall. The one-scan lag of K means the flag appears 11 s after the freeze, not 10.
