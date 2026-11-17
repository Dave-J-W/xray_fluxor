"""Slot map of both monitor lanes (MonP, MonC) and the status-bit table.

Everything on the figure is generated from
  calc/lanes.py          LANES, build(), rec(), PRESSURE_LANE (records, DESC, links, comments, EGU)
  calc/quality_slots.py  FLAG_BITS, STATUS (alarm limits), severity()
Layout coordinates and colours are the only typed content, plus the row titles and the
output field per role (which lanes.py documents in its docstring, not as data).
Arrows are the internal links: every INPx of a record that points at another lane record.
Run:  <bluesky venv>\\Scripts\\python.exe -I -X utf8 figures/fig_lanes_status.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from common import plt, save  # noqa: E402
from fig_signal_chain import box, _pv  # noqa: E402
from lanes import LANES, build, rec, PRESSURE_LANE, P as UTIL  # noqa: E402
from quality_slots import FLAG_BITS, STATUS, severity  # noqa: E402

# row order and what each row is called. key = lanes.py role; outs = fields that are the slot's outputs.
from lanes import ROLE_OUTPUTS  # noqa: E402
ROWS = [(role, title, outs) for role, (title, outs) in ROLE_OUTPUTS.items()]
FILL = {"flux": "#eef3fb", "bkg": "#e6f4ea", "bounds": "#fbe3d4", "flags": "#fdf3e1", "status": "#fbe3d4",
        "dark": "#e6f4ea"}
SEV_COLOR = {"MINOR": "#e08a00", "MAJOR": "#c00020", "NO_ALARM": "#2e7d32"}
LANE_COLOR = {"MonP": "#0b3d91", "MonC": "#6a1b9a"}


def main(outdir=common.OUT):
    # ---- gather records, roles, links --------------------------------------------------------
    info = {}                         # record -> dict(lane, role, desc, fields)
    for lane in LANES:
        for r, desc, fields, _, _ in build(lane):
            role = next(k for k, _ in ((k, 0) for k in LANES[lane]["slots"]) if rec(lane, k) == r)
            info[r] = dict(lane=lane, role=role, desc=desc, fields=fields)
    edges = {}                        # (src, dst) -> [(srcfield, dstinp)]
    for dst, d in info.items():
        for k, v in d["fields"].items():
            if k.startswith("INP") and v:
                src, _, fld = _pv(v).partition(".")
                if src in info and src != dst:
                    edges.setdefault((src, dst), []).append((fld, k[3:]))

    # ---- geometry ----------------------------------------------------------------------------
    CW, CH, RS = 50.0, 14.0, 24.0                 # cell width, height, row pitch
    xL = 44.0
    xC = xL + CW + 44.0
    xT = xC + CW + 50.0
    colx = {"MonP": xL, "MonC": xC}
    nrow = len(ROWS)
    ytop = 10.0 + nrow * RS
    ycell = {role: ytop - (i + 1) * RS + (RS - CH) / 2 for i, (role, _, _) in enumerate(ROWS)}
    Wt = xT + 92.0
    Ht = ytop + 16
    fig = plt.figure(figsize=(Wt / 10, Ht / 10 + 0.3))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, Wt)
    ax.set_ylim(0, Ht)
    ax.axis("off")
    ax.text(2, Ht - 3, "Monitor lanes: slot map, internal links and status bits",
            fontsize=13, fontweight="bold", va="center")
    ax.text(2, Ht - 7.6,
            f"One identical set of {nrow} slots per ion chamber, all in {UTIL}. Arrows = internal links "
            "(label: source field > target input letter). Monospace = read from calc/lanes.py. No live values.",
            fontsize=8, va="center", color="0.3")

    # ---- cells -------------------------------------------------------------------------------
    box_xy = {}
    for lane, x in colx.items():
        L = LANES[lane]
        ax.text(x + CW / 2, ytop + 2.2, lane, fontsize=12, fontweight="bold", ha="center", color=LANE_COLOR[lane])
        ax.text(x + CW / 2, ytop - 1.0, f"scaler {L['scaler']}, SR570 {L['sr570']}"
                + ("; owns pressure" if L["pressure_owner"] else "; reads pressure from " + PRESSURE_LANE),
                fontsize=7.5, ha="center", color="0.3")
    for lane, x in colx.items():
        for role, title, outs in ROWS:
            r = rec(lane, role)
            d = info[r]
            f = d["fields"]
            items = [("pv", r), ("txt", d["desc"])]
            for o in outs:
                cmt = f.get(f"CMT{o}", "")
                unit = f.get("EGU", "")
                what = cmt or (f.get("DESC", "") if o == "VAL" else "")
                items.append(("eq", f"output {r.split(':')[-1]}.{o}" + (f"  [{unit}]" if unit else "")
                              + (f"  {what}" if what else "")))
            box(ax, x, ycell[role], CW, CH, f"{title}", items, FILL[role], width=68, ec=LANE_COLOR[lane])
            box_xy[r] = (x, ycell[role])
        # row titles use a smaller font than the generic box title
    # ---- arrows: orthogonal routing, one vertical channel per link -----------------------------
    elist = []
    for (s, t), lst in edges.items():
        elist.append(dict(s=s, t=t, lab=",".join(f"{a}>{b}" for a, b in lst), ls=info[s]["lane"], lt=info[t]["lane"]))

    def ykey(r):
        return box_xy[r][1]

    def side_of(e, end):                      # which edge of the cell this end of the link uses
        if e["ls"] == e["lt"]:
            return "L" if e["ls"] == "MonP" else "R"
        return "R" if end == "s" else "L"      # cross-lane: leaves MonP's right edge, enters MonC's left edge

    slots = {}                                 # (record, side) -> ends, to spread the anchors
    for e in elist:
        for end, rr in (("s", e["s"]), ("t", e["t"])):
            other = e["t"] if end == "s" else e["s"]
            slots.setdefault((rr, side_of(e, end)), []).append((-ykey(other), id(e), end))
    anchor_y = {}
    for (rr, side), lst in slots.items():
        lst.sort()
        pitch = min(2.0, (CH - 3.0) / max(len(lst), 1))
        for i, (_, eid, end) in enumerate(lst):
            anchor_y[(eid, end)] = ykey(rr) + CH / 2 + ((len(lst) - 1) / 2 - i) * pitch

    chan = {"MonP": 0, "MonC": 0}
    for e in sorted(elist, key=lambda e: abs(ykey(e["s"]) - ykey(e["t"]))):
        ls, lt = e["ls"], e["lt"]
        ys, yt = anchor_y[(id(e), "s")], anchor_y[(id(e), "t")]
        if ls == lt:
            k = chan[ls]
            chan[ls] += 1
            col = LANE_COLOR[ls]
            if ls == "MonP":
                xe, xc = colx[ls], colx[ls] - 4.0 - 3.0 * k
            else:
                xe, xc = colx[ls] + CW, colx[ls] + CW + 4.0 + 3.0 * k
            ax.plot([xe, xc, xc], [ys, ys, yt], color=col, lw=1.1, zorder=5)
            ax.annotate("", xy=(xe, yt), xytext=(xc, yt), zorder=6,
                        arrowprops=dict(arrowstyle="-|>", color=col, lw=1.1, shrinkA=0, shrinkB=0))
            ax.text(xc, (ys + yt) / 2, e["lab"], fontsize=6.6, rotation=90, ha="center", va="center", color=col,
                    zorder=7, bbox=dict(fc="white", ec="none", pad=0.3))
        else:
            col = "#b00020"
            p0, p1 = (colx[ls] + CW, ys), (colx[lt], yt)
            ax.annotate("", xy=p1, xytext=p0, zorder=6,
                        arrowprops=dict(arrowstyle="-|>", color=col, lw=1.3, shrinkA=0, shrinkB=0))
            f = 0.3 if abs(yt - ys) > 1 else 0.5
            ax.text(p0[0] + f * (p1[0] - p0[0]), p0[1] + f * (p1[1] - p0[1]), e["lab"], fontsize=6.5, ha="center",
                    va="center", color=col, zorder=7, bbox=dict(fc="white", ec="none", pad=0.4))
    ax.text((xL + CW + xC) / 2, ytop + 2.2, "pressure links\n(MonC reads MonP)", fontsize=7, ha="center",
            color="#b00020")

    # ---- status-bit table --------------------------------------------------------------------
    ty = ytop - 1.0
    ax.text(xT, ty + 3.2, "Status bits (flags slot .L = sum of the set bits)", fontsize=10, fontweight="bold",
            va="center")
    cols = [xT, xT + 12, xT + 21, xT + 61]
    for x, h in zip(cols, ("bit", "letter", "condition", "meaning  /  severity")):
        ax.text(x, ty - 2.5, h, fontsize=8, fontweight="bold", va="center")
    ax.plot([xT - 1, xT + 91], [ty - 4.8, ty - 4.8], color="0.3", lw=1)
    y = ty - 8.0
    for val, letter, expr, cmt in FLAG_BITS:
        sev = severity(val)
        ax.add_patch(plt.Rectangle((xT - 1, y - 3.1), 92, 6.2, fc=SEV_COLOR[sev], alpha=0.12, ec="none"))
        ax.text(cols[0], y, f"{val}", fontsize=8.5, va="center", family="monospace", fontweight="bold")
        ax.text(cols[1] + 3, y, letter, fontsize=8.5, va="center", family="monospace")
        ax.text(cols[2], y, expr, fontsize=8, va="center", family="monospace", color="#0b3d91")
        meaning = cmt.split(":", 1)[1].strip().replace(" (MAJOR)", "")
        ax.text(cols[3], y + 1.3, meaning, fontsize=7.6, va="center")
        ax.text(cols[3], y - 1.7, sev, fontsize=7.6, va="center", fontweight="bold", color=SEV_COLOR[sev])
        y -= 7.2
    sf = STATUS["fields"]
    ax.plot([xT - 1, xT + 91], [y + 3.0, y + 3.0], color="0.3", lw=1)
    y -= 2.2
    ax.text(xT, y, f"code = sum of the set bits ({FLAG_BITS[0][0]}..{sum(b[0] for b in FLAG_BITS)}); "
            f"{severity(0)} if 0.", fontsize=7.8, va="center")
    y -= 4.4
    ax.text(xT, y, f"{rec('MonP', 'status').split(':')[-1]} alarm limits: code > {sf['HIGH']} {sf['HSV']},"
            f" code > {sf['HIHI']} {sf['HHSV']}.", fontsize=7.8, va="center")
    y -= 4.4
    ax.text(xT, y, "Nothing blocks, zeroes or freezes the flux: the status only sets alarm severity\n"
            "(rides the MS links through the dark feed onto the flux record).", fontsize=7.8, va="top",
            color="0.25")
    return save(fig, "lanes_status", ["calc/lanes.py", "calc/quality_slots.py"], outdir)


if __name__ == "__main__":
    print(main())
