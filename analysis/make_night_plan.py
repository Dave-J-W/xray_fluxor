"""Generate the overnight MonC program (2026-11-12/13, under the user's 17 h grant).

- grid: on each range 500 nA/V-20 uA/V, the offset-off dark, blanked, unblanked, then a CAL ladder over
  every level with output 0.1-4.5 V. Separates range gain, level error and V2F rate effects.
- pass (every ~10 min): offset-off dark on 200 nA/V-20 uA/V, blank/unblank at 5 uA/V, then a hold at the
  interim setting (5 uA/V, CAL +2 nA) for the rest of the 10 min. That is the dark-drift record per range.
- a grid every `grid_every` passes. The runner's --deadline stops the run and --restore puts back the
  interim setting.
Usage: python -I analysis/make_night_plan.py <out.csv> [n_passes] [--passes-only] [--hold=S]
  --passes-only: no grids (the 2026-11-13 leakage run used: <out> 5 --passes-only --hold=60)
"""
import csv, sys

K = 1e5
U = {"nA/V": 1e-9, "uA/V": 1e-6, "nA": 1e-9, "uA": 1e-6}
rows = []


def add(step, block, writes, dwell, exp="", q=""):
    rows.append(dict(step=step, block=block, writes=writes, dwell_s=str(dwell), expected_Hz=exp, question=q))


FULL_OFF = "blank_on=OFF;offset_on=OFF;offset_cal=CAL;offset_sign=+"
INTERIM = "blank_on=OFF;offset_on=OFF;sens_unit=uA/V;sens_num=5;offset_cal=CAL;offset_unit=nA;offset_num=2;offset_sign=+;offset_on=ON"
GRID_RANGES = [("500", "nA/V"), ("1", "uA/V"), ("2", "uA/V"), ("5", "uA/V"), ("10", "uA/V"), ("20", "uA/V")]
PASS_RANGES = [("200", "nA/V")] + GRID_RANGES
LEVELS = [("200", "nA"), ("500", "nA"), ("1", "uA"), ("2", "uA"), ("5", "uA"), ("10", "uA"), ("20", "uA"), ("50", "uA")]


def grid(g):
    for sn, su in GRID_RANGES:
        S = float(sn) * U[su]
        t = f"g{g}_{sn}{su[0]}"
        add(f"{t}_d", "grid_dark", f"blank_on=OFF;offset_on=OFF;sens_unit={su};sens_num={sn}", 14, "dark", "offset-off dark")
        add(f"{t}_b", "grid_blank", "blank_on=ON", 14, "", "blanked: V2F zero + post-front-end offset")
        add(f"{t}_ub", "grid_dark", "blank_on=OFF", 14, "dark", "unblanked again")
        first = True
        for ln, lu in LEVELS:
            V = float(ln) * U[lu] / S
            if not 0.1 <= V <= 4.5:
                continue
            w = f"offset_num={ln};offset_unit={lu}" + (";offset_on=ON" if first else "")
            first = False
            add(f"{t}_{ln}{lu}", "grid_ladder", w, 9, f"{K*V:.0f} + dark", f"output {V:.2f} V")
        add(f"{t}_off", "grid_dark", "offset_on=OFF", 14, "dark", "")


def dark_pass(p):
    for sn, su in PASS_RANGES:
        add(f"p{p}_{sn}{su[0]}_d", "pass_dark", f"blank_on=OFF;offset_on=OFF;sens_unit={su};sens_num={sn}", 12, "dark", "")
    add(f"p{p}_5u_d", "pass_dark", "sens_unit=uA/V;sens_num=5", 12, "dark", "5 uA/V again")
    add(f"p{p}_5u_b", "pass_blank", "blank_on=ON", 12, "", "")
    add(f"p{p}_5u_ub", "pass_dark", "blank_on=OFF", 12, "dark", "")
    add(f"p{p}_hold", "interim_hold", INTERIM, HOLD, "~59", "interim setting")


args = [a for a in sys.argv[1:] if not a.startswith("--")]
PASSES_ONLY = "--passes-only" in sys.argv
HOLD = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--hold=")), 480)
n_passes = int(args[1]) if len(args) > 1 else 110
grid_every = 24
add("S0", "start", FULL_OFF + ";sens_unit=uA/V;sens_num=5", 14, "dark at 5 uA/V", "full state write first (lesson F8)")
g = 1
if not PASSES_ONLY:
    grid(g)
for p in range(1, n_passes + 1):
    dark_pass(p)
    if p % grid_every == 0 and not PASSES_ONLY:
        g += 1
        grid(g)
with open(args[0], "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), "steps, nominal", round(sum(int(r["dwell_s"]) for r in rows) / 3600, 1), "h;", g, "grids")
