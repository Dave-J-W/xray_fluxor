"""Ladder ratios (gain x CAL level x V2F) at MonC's operating ranges, from set 4 and set 5 step logs.

Usage: python -I analysis/monc_ladders.py <set4_steplog.csv> <set5_steplog.csv>
ratio = (f - dark) / (1e5 Hz/V * I / S), dark = mean of the offset-off steps bracketing the ladder.
"""
import csv, re, sys

K = 1e5
M = {"pA": 1e-12, "nA": 1e-9, "uA": 1e-6}


def load(p):
    return {r["step"]: float(r["mean_S4"]) for r in csv.DictReader(open(p))}


s4, s5 = load(sys.argv[1]), load(sys.argv[2])
rows = []
# set 4: 5 uA/V ladder, darks D5_c (before) and L5_off (after)
d = (s4["D5_c"] + s4["L5_off"]) / 2
for st, f in s4.items():
    m = re.fullmatch(r"L5_(\d+)(uA)", st)
    if m:
        rows.append((5, f"{m[1]} {m[2]}", f, d, K * float(m[1]) * M[m[2]] / 5e-6))
# set 4 lifts (~20-25 mV) per range, darks _d and _d2
for st, f in s4.items():
    m = re.fullmatch(r"G(\d+)([nu])_l", st)
    if m:
        S = float(m[1]) * (1e-9 if m[2] == "n" else 1e-6)
        lift = {"200n": 5e-9, "500n": 10e-9, "1u": 20e-9, "2u": 50e-9, "5u": 100e-9, "10u": 200e-9, "20u": 500e-9}[m[1] + m[2]]
        dd = (s4[f"G{m[1]}{m[2]}_d"] + s4[f"G{m[1]}{m[2]}_d2"]) / 2
        rows.append((S * 1e6, f"{lift*1e9:.0f} nA (lift)", f, dd, K * lift / S))
# set 5 ladders
for st, f in s5.items():
    m = re.fullmatch(r"S(\d+)u_(\d+)(nA|uA)", st)
    if m:
        S = float(m[1]) * 1e-6
        dd = (s5[f"S{m[1]}u_d"] + s5[f"S{m[1]}u_d2"]) / 2
        rows.append((float(m[1]), f"{m[2]} {m[3]}", f, dd, K * float(m[2]) * M[m[3]] / S))
print(" S (uA/V) | CAL level      | f (Hz)      | dark (Hz) | nominal (Hz) | output V | ratio")
for S, lev, f, dd, nom in sorted(rows, key=lambda r: (r[0], r[4])):
    print(f" {S:8g} | {lev:14s} | {f:11.1f} | {dd:9.1f} | {nom:12.0f} | {nom/K:8.3f} | {(f-dd)/nom:.5f}")
