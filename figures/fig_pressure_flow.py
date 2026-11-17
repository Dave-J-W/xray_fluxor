"""How the live pressure is used (calc/PRESSURE.md section 2), as a flow diagram.

Read from the code, not typed:
  tools/asos_pressure.py  STATION, LOT_ELEV_M, HUTCH_ELEV_M, MAX_AGE_S, PV_PRESSURE, PV_AGE,
                          INHG_TO_HPA, the docstrings of obs_iem / obs_awc / station_kpa
  calc/lanes.py           records, links, expressions and comments of MonP and MonC
  calc/quality_slots.py   FLAG_BITS (bit value, meaning, severity)
Not in code (stated here as constants, cited): the cron schedule and the pressure sanity band.
Run:  <bluesky venv>\\Scripts\\python.exe -I -X utf8 figures/fig_pressure_flow.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
from common import plt, save, ROOT  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
import asos_pressure as ap  # noqa: E402
from fig_signal_chain import box, arrow, _pv, _height  # noqa: E402
from lanes import build, rec, PRESSURE_LANE  # noqa: E402
from quality_slots import FLAG_BITS, severity  # noqa: E402

# Upstream (tools/asos_pressure.py): the installed cron schedule (documentation constant) and the guard
CRON_SCHEDULE = ap.CRON_SCHEDULE
PRESSURE_GUARD_KPA = (ap.P_MIN_KPA, ap.P_MAX_KPA)   # upstream: tools/asos_pressure.py


def main(outdir=common.OUT):
    lane, other = PRESSURE_LANE, "MonC"
    P = {r: f for r, _, f, _, _ in build(lane)}
    C = {r: f for r, _, f, _, _ in build(other)}
    fl, bd, fg, st = (rec(lane, k) for k in ("flux", "bounds", "flags", "status"))
    cfl, cbd, cfg = (rec(other, k) for k in ("flux", "bounds", "flags"))
    F, B, G, CF, CB, CG = P[fl], P[bd], P[fg], C[cfl], C[cbd], C[cfg]
    # the updater's PVs must be the lane's own fields, or this figure would lie
    assert ap.PV_PRESSURE == f"{fl}.G", (ap.PV_PRESSURE, fl)
    assert ap.PV_AGE == f"{bd}.H", (ap.PV_AGE, bd)
    age_bit = next(b for b in FLAG_BITS if "D" in b[2])           # the flag that reads the age link
    assert age_bit[2] == f"D>{ap.MAX_AGE_S}", age_bit
    assert _pv(G["INPD"]) == ap.PV_AGE
    drop = ap.station_kpa(29.92, ap.HUTCH_ELEV_M) / ap.station_kpa(29.92, ap.LOT_ELEV_M) - 1
    sev = severity(age_bit[0])
    first = lambda f: f.__doc__.strip().splitlines()[0]            # noqa: E731

    BW, GAP = 38.0, 9.0
    xs = [3 + i * (BW + GAP) for i in range(5)]
    items = {
        "asos": ("1  Airport ASOS station",
                 [("eq", f"station {ap.STATION}, field elevation {ap.LOT_ELEV_M:g} m"),
                  ("txt", "reports an altimeter setting (inHg), about hourly"),
                  ("note", "cadence from PRESSURE.md section 2; not in code")], "#eef3fb"),
        "fetch": ("2  Fetch: IEM, else NOAA",
                  [("note", first(ap.obs_iem)), ("note", first(ap.obs_awc)),
                   ("txt", "stdlib HTTP only; if both fail, nothing is written")], "#eef3fb"),
        "upd": ("3  Updater on the host",
                [("eq", f"cron: {CRON_SCHEDULE}"), ("note", "= every 15 min, from PRESSURE.md section 2"),
                 ("txt", f"altimeter -> pressure at {ap.HUTCH_ELEV_M:g} m, i.e. {-drop*100:.2f} % below the "
                         f"{ap.LOT_ELEV_M:g} m station value"),
                 ("eq", f"guards: {PRESSURE_GUARD_KPA[0]:g} < P < {PRESSURE_GUARD_KPA[1]:g} kPa and obs age <= "
                        f"{ap.MAX_AGE_S} s"),
                 ("note", "else writes nothing: G keeps its last value")], "#e6f4ea"),
        "put": ("4  CA put, read back",
                [("pv", f"G (kPa)   -> {ap.PV_PRESSURE}"), ("pv", f"0 (s)     -> {ap.PV_AGE}"),
                 ("note", "G = N2 pressure input of the MonP flux slot; the zero resets the age counter")],
         "#fdf3e1"),
        "age": ("5  Age counter H",
                [("eq", f"H = {B['CLCH']}"), ("pv", ap.PV_AGE), ("note", "seconds since the last good update; +1 per 1 s scan"),
                 ("pv", f"{other} reads it: {_pv(CB['INPH'])[:0]}{CB['INPH']}".replace(" NPP NMS", ""))],
         "#fdf3e1"),
        "K": ("6  Density K",
              [("eq", f"K = {F['CLCK']}"), ("pv", f"K held in {fl}.K"),
               ("note", "g/cm3 N2; G = pressure kPa, F = hutch temperature C"),
               ("pv", f"F <- {_pv(F['INPF'])}")], "#eef3fb"),
        "O": ("7  Absorbed fraction O, exit transmission",
              [("eq", f"O = {F['CLCO']}"), ("note", "M = mu_en/rho; absorbed in the plates"),
               ("eq", "exit transmission = " + F["CLCP"].split("EXP")[-1].join(["EXP", ""])),
               ("note", "N = mu/rho; both depend on K")], "#eef3fb"),
        "P": ("8  Flux P at the exit",
              [("eq", f"P = {F['CLCP']}"), ("pv", f"P held in {fl}.P"),
               ("note", "denser gas: more absorbed, so fewer photons per count")], "#eef3fb"),
        "monc": (f"9  {other} reads G by link",
                 [("pv", f"{_pv(CF['INPG'])} -> {cfl}.G"), ("note", f"link flags: {' '.join(CF['INPG'].split()[1:])} (read, no processing)"),
                  ("txt", "same K, O, P expressions follow in the MonC flux slot")], "#eef3fb"),
        "flag": (f"10  Status bit {age_bit[0]}: pressure age",
                 [("eq", f"{age_bit[1]}: {age_bit[2]}"), ("pv", f"{fg}.INPD <- {_pv(G['INPD'])}"),
                  ("pv", f"{other}: {cfg}.INPD <- {_pv(CG['INPD'])}"),
                  ("txt", f"{age_bit[3]} -> {sev}")], "#fbe3d4"),
        "eeff": ("11  Density-scaled energy B in the bounds slot",
                 [("eq", f"B = {B['CLCB']}"), ("pv", f"I <- {_pv(B['INPI'])}   (I = density K)"),
                  ("note", "E_eff: the wall-loss fit follows the live density"),
                  ("pv", f"B held in {bd}.B;  {other}: {cbd}.B")], "#fdf3e1"),
        "bnd": ("12  Wall loss C, bounds, RESULT",
                [("eq", f"C = {B['CLCC']}"), ("pv", f"RESULT {bd}.L, low {bd}.D, high {bd}.E"),
                 ("note", "C is evaluated at E_eff, so pressure moves the bounds too")], "#fdf3e1"),
        "stat": ("13  Status code -> alarm",
                 [("pv", f"{fg}.L -> {st}.VAL"), ("txt", f"bit {age_bit[0]} alone = {sev} on the flux record"),
                  ("note", "the number is still published; only the alarm changes")], "#fbe3d4"),
    }
    h = {k: _height(v[1], 52) for k, v in items.items()}
    rowh = [max(h[k] for k in r) for r in (("asos", "fetch", "upd", "put", "age"),
                                           ("K", "O", "P", "monc", "flag"),
                                           ("eeff", "bnd", "stat"))]
    RG = 17.0
    yC = 16.0
    yB = yC + rowh[2] + RG
    yA = yB + rowh[1] + RG
    top = yA + rowh[0] + 14
    Wt = xs[-1] + BW + 3
    fig = plt.figure(figsize=(Wt / 10, top / 10 + 0.3))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, Wt)
    ax.set_ylim(0, top)
    ax.axis("off")
    ax.text(2, top - 3, "How the live pressure is used: weather station -> updater -> flux, bounds and status",
            fontsize=13, fontweight="bold", va="center")
    ax.text(2, top - 8, "Green: runs on the host. Blue: formula in a transform record. Yellow: PV or bounds slot. "
            "Red-orange: status. Monospace = read from code; italic = note. Formula flow only, no live values.",
            fontsize=8, va="center", color="0.3")

    place = {"asos": (0, yA), "fetch": (1, yA), "upd": (2, yA), "put": (3, yA), "age": (4, yA),
             "K": (0, yB), "O": (1, yB), "P": (2, yB), "monc": (3, yB), "flag": (4, yB),
             "eeff": (0, yC), "bnd": (1, yC), "stat": (4, yC)}
    g = {}
    for k, (c, y) in place.items():
        row = 0 if y == yA else (1 if y == yB else 2)
        hh = rowh[row]
        box(ax, xs[c], y, BW, hh, items[k][0], items[k][1], items[k][2], width=52)
        g[k] = (xs[c], y, BW, hh)

    def mid(k, side, f=0.5):
        x, y, w, hh = g[k]
        return {"r": (x + w, y + hh * f), "l": (x, y + hh * f), "t": (x + w * f, y + hh),
                "b": (x + w * f, y)}[side]

    for a, b in (("asos", "fetch"), ("fetch", "upd"), ("upd", "put")):
        arrow(ax, mid(a, "r", 0.7), mid(b, "l", 0.7))
    # updater -> age counter, arching over the PV box
    arrow(ax, mid("upd", "t", 0.8), mid("age", "t", 0.4), rad=-0.18, label=f"writes 0 to {ap.PV_AGE.split(':')[-1]}",
          lpos=(0, 3.2))
    # G box -> elbow to K, and straight down to MonC
    x0, ymid = mid("put", "b", 0.3)[0], yA - RG / 2
    ax.plot([x0, x0, mid("K", "t")[0]], [yA, ymid, ymid], color="0.15", lw=1.4, zorder=4)
    arrow(ax, (mid("K", "t")[0], ymid), mid("K", "t"))
    ax.text(x0 - 4, ymid + 1.2, "G, kPa", fontsize=7, ha="right", va="bottom")
    arrow(ax, mid("put", "b", 0.8), mid("monc", "t", 0.8), label="G, kPa (link)", lpos=(7, 0))
    arrow(ax, mid("K", "r", 0.6), mid("O", "l", 0.6), label="K", lpos=(0, 2.2))
    arrow(ax, mid("O", "r", 0.6), mid("P", "l", 0.6), label="O", lpos=(0, 2.2))
    arrow(ax, mid("K", "b", 0.5), mid("eeff", "t", 0.5), label="K, g/cm3", lpos=(7, 0))
    arrow(ax, mid("P", "b", 0.3), mid("bnd", "t", 0.8), label="P, ph/s", lpos=(7, 0))
    arrow(ax, mid("eeff", "r", 0.5), mid("bnd", "l", 0.5), label="B, keV", lpos=(0, 2.2))
    arrow(ax, mid("age", "b", 0.5), mid("flag", "t", 0.5), label="H, s", lpos=(5, 0))
    arrow(ax, mid("flag", "b", 0.5), mid("stat", "t", 0.5), label="bit", lpos=(5, 0))
    arrow(ax, mid("stat", "l", 0.5), mid("bnd", "r", 0.5), ls="--", color="#b00020",
          label="severity rides the MS links", lpos=(0, 2.4))
    # MonC lane note
    ax.text(2, 9.5,
            f"Sources: the {lane} lane owns G and H; {other} reads both by internal link, so one updater serves both "
            f"monitors ({ap.PV_PRESSURE}, {ap.PV_AGE}). No host names or addresses are shown.",
            fontsize=7.6, va="center", color="0.25")
    ax.text(2, 5.5,
            f"Constants stated here because no code holds them: CRON_SCHEDULE = '{CRON_SCHEDULE}' (PRESSURE.md section 2); "
            f"pressure guard {PRESSURE_GUARD_KPA} kPa (asos_pressure.P_MIN_KPA/P_MAX_KPA).",
            fontsize=7.6, va="center", color="0.25")
    return save(fig, "pressure_flow", ["tools/asos_pressure.py", "calc/lanes.py", "calc/quality_slots.py",
                                       "calc/PRESSURE.md section 2"], outdir)


if __name__ == "__main__":
    print(main())
