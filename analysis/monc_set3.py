"""Analyse MonC experiment set 3 from its step log (per-step mean S4, counts per 1 s count = Hz).

Usage: python -I analysis/monc_set3.py <steplog.csv>   (prints a report; nothing is written to EPICS)

Model: f = K * I / S + d_S  for a positive SR570 output, with K = 1e5 Hz/V (V2F, 0-10 V range),
I the offset current, S the sensitivity in A/V and d_S the range's dark (output-referred). f <= 1
means clipped (output <= 0 V, unipolar V2F) and is excluded from every fit.
"""
import csv, sys
import numpy as np

K = 1e5
CLIP = 1.5


def load(path):
    return {r["step"]: (float(r["mean_S4"]), float(r["sd_S4"]), int(r["n"])) for r in csv.DictReader(open(path))}


def main():
    m = load(sys.argv[1])
    f = lambda s: m[s][0]
    print("== F baseline repeats (Hz):", {s: round(f(s), 1) for s in ("F0", "F1", "F2", "R") if s in m})

    print("\n== A: CAL offset linearity at 50 nA/V (sign +)")
    dark = np.mean([f("A0"), f("A9")])
    print(f"   offset-off dark before/after: {f('A0'):.1f} / {f('A9'):.1f} Hz -> mean {dark:.1f}")
    for n in (1, 2, 5, 10, 20, 50):
        nom = K * n * 1e-9 / 50e-9
        meas = f(f"A{n}nA") - dark
        print(f"   {n:>3} nA: f={f(f'A{n}nA'):9.1f}  f-dark={meas:9.1f}  nominal={nom:8.0f}  ratio={meas/nom:.5f}")

    print("\n== B: per range, two CAL points + offset off")
    lohi = {1: (0.2, 1), 2: (0.5, 2), 5: (1, 5), 10: (2, 10), 20: (5, 20), 50: (10, 50),
            100: (20, 100), 200: (50, 200), 500: (100, 500)}
    print("   S nA/V | dark(off) Hz | f_lo   f_hi | slope/nominal | intercept Hz | intercept - dark")
    for S, (lo, hi) in lohi.items():
        d, fl, fh = f(f"B{S}d"), f(f"B{S}l"), f(f"B{S}h")
        slope = (fh - fl) / (hi - lo)          # Hz per nA
        nom = K * 1e-9 / (S * 1e-9)            # Hz per nA
        icpt = fl - slope * lo
        dflag = " (clipped)" if d <= CLIP else ""
        print(f"   {S:>5} | {d:9.1f}{dflag:10s} | {fl:8.1f} {fh:9.1f} | {slope/nom:.5f} | {icpt:9.1f} | "
              f"{icpt - d:8.1f}")

    print("\n== C: UNCAL vernier transfer at 50 nA/V, 20 nA level")
    us = [-10, -4, 0, 2, 4, 6, 8, 10, 15, 20, 30, 50, 100, 200, 500, 1000]
    pts = [(u, f(f"C{u}")) for u in us if f"C{u}" in m]
    print("   " + "  ".join(f"u={u}:{v:.1f}" for u, v in pts))
    lin = [(u, v) for u, v in pts if v > 50 and u <= 200]   # clear of the knee and of full scale
    if len(lin) >= 3:
        u, v = np.array(lin).T
        a, b = np.polyfit(u, v, 1)
        res = v - (a * u + b)
        print(f"   fit {len(u)} pts (f>50 Hz, u<=200): {a:.3f} Hz/unit, intercept {b:.1f} Hz, zero at u={-b/a:.2f};"
              f" residuals {np.round(res, 1).tolist()}")
        for uu in (500, 1000):
            if f"C{uu}" in m:
                print(f"   u={uu}: measured {f(f'C{uu}'):.0f}, line {a*uu+b:.0f}, ratio {f(f'C{uu}')/(a*uu+b):.4f}")
        print(f"   implied input-referred: {a/K*50e-9*1e12:.2f} pA per unit (full scale u=1000 -> "
              f"{a*1000/K*50e-9*1e9:.2f} nA)")

    print("\n== D: UNCAL range groups at 50 nA/V")
    for n in (2, 20, 100, 200, 500):
        a50, a100 = m.get(f"D50_{n}nA"), m.get(f"D100_{n}nA")
        line = f"   {n:>3} nA: u=50 {a50[0]:9.1f}" if a50 else f"   {n:>3} nA:"
        if a50 and a100:
            sl = (a100[0] - a50[0]) / 50
            line += f"  u=100 {a100[0]:9.1f}  slope {sl:.2f} Hz/unit = {sl/K*50e-9*1e12:.2f} pA/unit"
        print(line)

    print("\n== E: UNCAL sign A/B at u=+100, 20 nA")
    for s in ("E0", "E1-", "E2+", "E3-", "E4+"):
        if s in m:
            print(f"   {s:4s} {f(s):9.1f} (sd {m[s][1]:.1f}, n {m[s][2]})")
    if all(s in m for s in ("E1-", "E2+", "E3-", "E4+")):
        neg, pos = np.mean([f("E1-"), f("E3-")]), np.mean([f("E2+"), f("E4+")])
        print(f"   mean(-) {neg:.1f}  mean(+) {pos:.1f}  diff {(neg-pos)/pos*100:+.2f} %")


if __name__ == "__main__":
    main()
