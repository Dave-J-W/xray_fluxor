#!/usr/bin/env python3
"""Generate the flux dashboard, op/bob/flux_dashboard.bob (read-only, indicators only).

Three lane cards (E-station IC-500-50, MonP, MonC) on top; a details panel below for the chamber
selected by a card's button (a local PV, loc://flux_sel; nothing is written to the IOC). Lane PV
maps are the tables below (xray_fluxor docs/phoebus_estation_dashboard_brief.md); the parameter and
budget tabs read docs/dashboard_model.json (tools/export_dashboard_model.py). Moved here from 15IDC HA
(ioc/utilioc/tools/gen_dashboard.py, commit 7109653) on 2026-11-17; 15IDC HA vendors the .bob it writes.

    python3 gen_dashboard.py <out.bob>            write
    python3 gen_dashboard.py <out.bob> --check    exit 1 if the file differs
Standard library only. Phoebus 4.7.4 widget versions (phoebus skill).
"""
import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bob_widgets as g                      # widget helpers, colours, fonts (copied from 15IDC HA gen_screens.py)
from bob_widgets import label, rect, textupdate, led, state_label, color, font, geom

P = "$(P)"
W, H, M = 1180, 940, 6
OPT = {"sel": 0, "tab": 0, "ptab": 0}
SEL = "loc://flux_sel(0)"
g.C.update({
    "alarm": (None, 255, 60, 60), "warnc": (None, 255, 215, 0), "muted": (None, 190, 190, 190),
    "info": (None, 150, 185, 235), "nodata": (None, 255, 0, 255), "assumed": (None, 255, 225, 170),
    "prov": (None, 255, 200, 200), "white": (None, 255, 255, 255), "ctrl": (None, 225, 232, 240),
})
g.FONTS["huge"] = ("Default Bold", "BOLD", 34)


def f(rec, fld=None):
    return f"{P}{rec}" + (f".{fld}" if fld else "")


# ---- the lanes: PV map (brief) ----------------------------------------------------------------
# input/corr row: (label, record, field, unit, format (None, 2 = exponential), precision)
def estation():
    return dict(
        name="E-station IC-500-50", sel=0,
        beam="side-bounce mono, TetrAMM channels 3 + 4, N2",
        flux="userTran9", bounds="userTran10", flagrec="userTran11", status="userCalcOut9",
        result=("userTran10", "L"), low=("userTran10", "K"), high=("userTran10", "M"),
        up=("userTran10", "N"), down=("userTran10", "O"),
        flags=[("F", 1, "info", "energy above 12.5 keV: wall-loss band in use"),
               ("G", 2, "warn", "central recombination above 5 %"),
               ("H", 4, "warn", "pressure not updated for 2 h"),
               ("I", 8, "low", "net current below 50 nA: low current, bounds understate"),
               ("J", 16, "alarm", "energy outside 4.9 to 30.5 keV, or NaN"),
               ("K", 32, "alarm", "raw current fault: sum below -5 nA, a channel at or above 99 % of 120 uA, or NaN")],
        code=("userTran11", "L"),
        chip_low="LOW CURRENT", chip_warn_bits=("G", "H"), chip_low_bit="I", chip_alarm_bits=("J", "K"),
        inputs=[("Channel 3 current", "userTran9", "A", "nA", None, 3), ("Channel 4 current", "userTran9", "B", "nA", None, 3),
                ("Net current", "userTran9", "G", "A", 2, 3), ("Dark subtracted (hand-set)", "userTran9", "F", "nA", None, 3),
                ("Energy (side-bounce mono)", "userTran9", "C", "keV", None, 4),
                ("Hutch air temperature", "userTran9", "D", "deg F", None, 1), ("Hutch air temperature", "userTran9", "H", "deg C", None, 1),
                ("N2 pressure", "userTran9", "E", "kPa", None, 2), ("N2 density", "userTran9", "I", "g/cm3", 2, 4)],
        corr=[("Formula flux (uncorrected)", "userTran9", "P", "ph/s", 2, 3), ("Wall-loss fraction", "userTran10", "C", "fraction", None, 4),
              ("Recombination loss, central", "userTran10", "E", "fraction", None, 4),
              ("Recombination loss, low aspect", "userTran10", "F", "fraction", None, 4),
              ("Recombination loss, high aspect", "userTran10", "G", "fraction", None, 4),
              ("Plates constant (1 = horizontal)", "userTran10", "P", "", None, 0),
              ("RESULT (best, corrected)", "userTran10", "L", "ph/s", 2, 3), ("Low bound", "userTran10", "K", "ph/s", 2, 3),
              ("High bound", "userTran10", "M", "ph/s", 2, 3), ("Up", "userTran10", "N", "%", None, 1), ("Down", "userTran10", "O", "%", None, 1)],
        gap="KNOWN GAP (not monitored): a frozen TetrAMM (readings constant, no alarm) is not detected by the lane. "
            "While the TetrAMM is frozen these numbers are not a measurement. Freeze detector: proposed in TODO.md, not built.",
    )


def cstation(name, n, beamnote, plates_note, detached):
    fl, bg, bd, fr, st = {1: ("userTran1", "userTran2", "userTran3", "userTran7", "userCalcOut1"),
                          4: ("userTran4", "userTran5", "userTran6", "userTran8", "userCalcOut4")}[n]
    return dict(
        name=name, sel=0, beam=beamnote,
        flux=fl, bounds=bd, flagrec=fr, status=st, detached=detached,
        result=(bd, "L"), low=(bd, "D"), high=(bd, "E"), up=(bd, "F"), down=(bd, "G"),
        flags=[("F", 1, "info", "energy above 12.5 keV: wall-loss band in use"),
               ("G", 2, "warn", "background stale (other gain, or none)"),
               ("H", 4, "warn", "pressure not updated for 2 h"),
               ("I", 8, "low", "no beam: bounds not meaningful"),
               ("J", 16, "alarm", "energy outside 4.9 to 30.5 keV"),
               ("K", 32, "alarm", "scaler not counting")],
        code=(fr, "L"),
        chip_low="NO BEAM", chip_warn_bits=("G", "H"), chip_low_bit="I", chip_alarm_bits=("J", "K"),
        inputs=[("Scaler counts", fl, "A", "counts", None, 0), ("Count time", fl, "B", "s", None, 2),
                ("SR570 gain: number (index)", fl, "C", "index", None, 0), ("SR570 gain: unit (index)", fl, "D", "index", None, 0),
                ("SR570 sensitivity", "formula", f"{fl}.I", "µA/V", None, 3), ("Energy (DCM)", fl, "E", "keV", None, 4),
                ("Hutch temperature", fl, "F", "deg C", None, 1),
                ("N2 pressure", fl, "G", "kPa", None, 2),
                ("N2 density", fl, "K", "g/cm3", 2, 4),
                ("Pressure age (shared updater)", "userTran3", "H", "s", None, 0),
                ("Background used", fl, "H", "Hz", None, 2), ("Net rate", fl, "J", "Hz", None, 2),
                ("Background estimate", bg, "L", "Hz", None, 2), ("Background stale (1 = yes)", bg, "N", "", None, 0)],
        corr=[("Formula flux (uncorrected)", fl, "P", "ph/s", 2, 3), ("Wall-loss fraction", bd, "C", "fraction", None, 4),
              ("Recombination", None, None, "not applicable", None, 0),
              (plates_note, bd, "M", "", None, 0),
              ("RESULT (best, corrected)", bd, "L", "ph/s", 2, 3), ("Low bound", bd, "D", "ph/s", 2, 3),
              ("High bound", bd, "E", "ph/s", 2, 3), ("Up", bd, "F", "%", None, 1), ("Down", bd, "G", "%", None, 1)],
        gap="")


LANES = [estation(),
         cstation("MonP", 1, "DCM beam, CMC chamber (SR570 + V2F + scaler), N2", "Plates constant (0 = vertical)", False),
         cstation("MonC", 4, "DCM beam, CMC chamber (SR570 + V2F + scaler), N2",
                  "Plates constant (1 = horizontal)", True)]
for _i, _L in enumerate(LANES):
    _L["sel"] = _i


# ---- widgets ----------------------------------------------------------------------------------
def vis_rule(k):
    return (f'<rules><rule name="show" prop_id="visible" out_exp="false"><exp bool_exp="pv0 == {k}">'
            f"<value>true</value></exp><pv_name>{SEL}</pv_name></rule></rules>")


def select_button(x, y, w, h, k, text):
    return (f'<widget type="action_button" version="3.0.0"><name>{g.D.name("select")}</name>'
            f'<actions><action type="write_pv"><pv_name>{SEL}</pv_name><value>{k}</value>'
            f"<description>{escape(text)}</description></action></actions><text>{escape(text)}</text>"
            f"{geom(x, y, w, h)}{font('default')}{color('background_color', 'button')}"
            f"<tooltip>show this chamber's details below (a local selection, nothing is written to the IOC)</tooltip>"
            f"</widget>")


def chip(x, y, w, h, L):
    """State chip (spec): ALARM > NO DATA > NO BEAM/LOW CURRENT > WARNING > none; bit 1 is never used.
    No contact with the IOC leaves the file's NO CONTACT; contact is judged by the heartbeat (pv1)."""
    fr, res = L["flagrec"], L["result"]
    a, b = L["chip_alarm_bits"]
    wa, wb = L["chip_warn_bits"]
    lo = L["chip_low_bit"]
    pvs = [f(*res), f"{P}HEARTBEAT", f(fr, a), f(fr, b), f(fr, lo), f(fr, wa), f(fr, wb)]
    ok = 'pvStr1 != "" && pvSev1 < 3'
    alarm = "(pv2 > 0.5 || pv3 > 0.5)"
    nodata = "pvSev0 == 3"
    low = "pv4 > 0.5"
    warn = "(pv5 > 0.5 || pv6 > 0.5)"
    br = [(f"{ok} && {alarm}", "ALARM", "alarm"),
          (f"{ok} && !{alarm} && {nodata}", "NO DATA", "nodata"),
          (f"{ok} && !{alarm} && !{nodata} && {low}", L["chip_low"], "muted"),
          (f"{ok} && !{alarm} && !{nodata} && !{low} && {warn}", "WARNING", "warnc"),
          (f"{ok} && !{alarm} && !{nodata} && !{low} && !{warn}", "", "ctrl")]
    return state_label(x, y, w, h, pvs, br, "NO CONTACT", f="bold", fallback_bg="grey",
                       tooltip="ALARM: flag 16 or 32. NO DATA: RESULT INVALID (an input link is dead). "
                               "NO BEAM / LOW CURRENT: flag 8. WARNING: flag 2 or 4. Flag 1 is informational (Flags tab).")


def card(L, x, y, w, h):
    out = [rect(x, y, w, h, bg="ctrl", lw=2), label(x + 10, y + 6, w - 170, 26, L["name"], f="h2")]
    out.append(chip(x + w - 150, y + 8, 138, 26, L))
    out.append(label(x + 10, y + 34, w - 20, 20, L["beam"], f="tiny", fg="note", wrap=False))
    vw = w - 130

    def line(yy, text, key, fmt, prec):
        return [label(x + 10, yy + 2, 70, 18, text, f="small", fg="note", wrap=False),
                textupdate(x + 84, yy, vw - 74, 22, f(*L[key]), f="small", fmt=fmt, prec=prec, tooltip=f(*L[key]))]
    out += line(y + 58, "high", "high", 2, 3)
    out += line(y + 82, "up, %", "up", None, 1)
    out.append(label(x + 10, y + 108, 60, 16, "RESULT", f="tiny", fg="note", wrap=False))
    big = textupdate(x + 10, y + 122, vw, 62, f(*L["result"]), f="huge", fmt=2, prec=3, tooltip=f(*L["result"]) + " (ph/s)")
    # a named font ignores its size in Phoebus: the big RESULT uses an unnamed font
    big = re.sub(r"<font><font .*?></font></font>", '<font><font family="Liberation Sans" style="BOLD" size="44.0"></font></font>', big, count=1)
    out.append(big)
    out.append(label(x + vw + 14, y + 150, 100, 24, "photons/s", f="default", wrap=False))
    out += line(y + 188, "down, %", "down", None, 1)
    out += line(y + 212, "low", "low", 2, 3)
    out.append(select_button(x + w - 118, y + 210, 108, 28, L["sel"], "Details"))
    if L["gap"]:
        out.append(label(x + 10, y + 242, w - 20, 30, "inputs not checked for freeze: not a trusted measurement while the TetrAMM is frozen (Flags tab)",
                         f="tiny", fg="text", bg="warnc", wrap=True))
    return out


def rows(items, x0, y0, colw=560):
    """Two columns of label | value | unit; returns widgets."""
    out = []
    half = (len(items) + 1) // 2
    for i, (text, rec, fld, unit, fmt, prec) in enumerate(items):
        x = x0 + (i // half) * colw
        y = y0 + (i % half) * 30
        out.append(label(x, y, 250, 24, text, f="default", wrap=False))
        if rec is None:
            out.append(label(x + 256, y, 200, 24, unit, f="small", fg="note", wrap=False))
            continue
        pv = f"=`{P}{fld}`*1e6" if rec == "formula" else f(rec, fld)       # formula PV: read-only, scales A/V to uA/V
        out.append(textupdate(x + 256, y, 170, 24, pv, fmt=fmt, prec=prec, tooltip=(f"{P}{fld} x 1e6" if rec == "formula" else f(rec, fld))))
        out.append(label(x + 432, y, 110, 24, unit, f="small", fg="note", wrap=False))
    return out


def flags_tab(L):
    out = [label(10, 8, 1130, 40, "Each lamp is one status bit of the lane. Bit 1 is informational only: it is not a warning "
                 "(the stated bounds already carry it). The legend text comes from the lane, not from the bit number.", f="small", wrap=True)]
    y = 54
    for key, bit, cls, text in L["flags"]:
        colr = {"info": "info", "warn": "warnc", "low": "muted", "alarm": "alarm"}[cls]
        out.append(led(14, y, 24, f(L["flagrec"], key), on=colr, off="off", tooltip=f(L["flagrec"], key)))
        out.append(label(48, y, 60, 24, f"bit {bit}", f="bold", wrap=False))
        out.append(label(110, y, 140, 24, {"info": "informational", "warn": "warning", "low": "state (number stays)", "alarm": "ALARM"}[cls],
                         f="small", fg="note", wrap=False))
        out.append(label(260, y, 880, 24, text, f="default", wrap=False))
        y += 34
    y += 8
    out.append(label(14, y, 160, 24, "Status code (sum)", f="bold", wrap=False))
    out.append(textupdate(180, y, 90, 24, f(*L["code"]), prec=0, tooltip=f(*L["code"])))
    out.append(label(290, y, 200, 24, "Status record severity", f="bold", wrap=False))
    out.append(textupdate(490, y, 120, 24, f(L["status"], "SEVR"),
                          tooltip=f(L["status"], "SEVR") + ": MINOR whenever bit 1 is set (always at 30 keV); the record is unchanged"))
    out.append(label(630, y, 520, 24, "(MINOR whenever bit 1 is set: that is why the dashboard does not use the severity)", f="small", fg="note", wrap=False))
    if L["gap"]:
        out.append(label(14, y + 50, 1130, 56, L["gap"], f="default", bg="warnc", wrap=True))
    return out


MODEL = json.loads((Path(__file__).resolve().parents[2] / "docs" / "dashboard_model.json").read_text(encoding="utf-8"))
KEYS = ["estation", "monp", "monc"]
SEG = ["ctrl", "info", "warnc", "muted", "alarm", "assumed", "prov"]       # stacked-bar segment colours (g.C keys)
g.C.update({"s0": (None, 90, 130, 190), "s1": (None, 230, 140, 40), "s2": (None, 90, 170, 110), "s3": (None, 170, 90, 170),
            "s4": (None, 200, 80, 80), "s5": (None, 120, 120, 120), "s6": (None, 60, 170, 190)})


def footer(y):
    return label(14, y, 1130, 20, f"Model export: xray_fluxor commit {MODEL['xray_fluxor_commit']}, {MODEL['date']}. "
                 "Static text generated at build time; the live .CLC strings (Model parameters, last page) are what runs on the IOC.",
                 f="tiny", fg="note", wrap=False)


def fv(v):
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, list):
        return ", ".join(fv(x) for x in v)
    if isinstance(v, dict):
        return ", ".join(f"{k} {fv(x)}" for k, x in v.items())
    return str(v)


def budget_tab(L):
    m = MODEL["lanes"][KEYS[L["sel"]]]
    tot2 = sum(t["rel"] ** 2 for t in m["terms"])
    out = [label(14, 6, 1130, 36, "Symmetric terms (relative, 1 sigma) add in quadrature; the bar shows each term's share of the variance. "
                 "The wall-loss and recombination terms are energy dependent and live: they widen the stated up/down beyond this total.",
                 f="small", wrap=True)]
    x = 14
    for i, t in enumerate(m["terms"]):
        w = max(2, round(1110 * t["rel"] ** 2 / tot2))
        out.append(rect(x, 46, w, 22, bg=f"s{i % 7}", line="line", lw=1, corner=0))
        x += w
    y = 78
    for h, hx, hw in (("term", 40, 220), ("1 sigma, %", 270, 90), ("share", 365, 70), ("tag", 440, 110), ("source", 560, 580)):
        out.append(label(hx, y, hw, 18, h, f="bold", wrap=False))
    y += 22
    for i, t in enumerate(m["terms"]):
        flagged = t["tag"] in ("ASSUMED", "PROVISIONAL")
        bgk = "assumed" if t["tag"] == "ASSUMED" else ("prov" if t["tag"] == "PROVISIONAL" else "read")
        out.append(rect(14, y, 1130, 34, bg=bgk, lw=1, corner=0))
        out.append(rect(18, y + 8, 16, 16, bg=f"s{i % 7}", lw=1, corner=0))
        out.append(label(40, y + 2, 226, 30, t["name"], f="default", wrap=True))
        out.append(label(270, y + 2, 90, 30, f"{100 * t['rel']:.2f}", f="default", wrap=False))
        out.append(label(365, y + 2, 70, 30, f"{100 * t['rel'] ** 2 / tot2:.0f} %", f="default", wrap=False))
        out.append(label(440, y + 2, 116, 30, t["tag"], f="small" if flagged else "default", wrap=True))
        out.append(label(560, y + 1, 580, 32, t["source"], f="tiny", wrap=True))
        y += 36
    out.append(label(40, y + 4, 220, 24, "Total (quadrature)", f="bold", wrap=False))
    out.append(label(270, y + 4, 90, 24, f"{100 * m['quad_total']:.2f}", f="bold", wrap=False))
    out.append(label(365, y + 4, 760, 24, f"-> slot factors: low x {m['low_factor']}, high x {m['high_factor']} (applied in the bounds expression)",
                     f="default", wrap=False))
    y += 36
    out.append(label(14, y, 520, 22, "Live (this chamber)", f="bold", wrap=False))
    b = L["bounds"]
    items = [("Wall-loss fraction (asymmetric band; carried by the bounds)", b, "C", 4)]
    if KEYS[L["sel"]] == "estation":
        items += [("Recombination loss, central", b, "E", 4), ("Recombination loss, low aspect", b, "F", 4), ("Recombination loss, high aspect", b, "G", 4)]
    items += [("Stated up, % of RESULT", L["up"][0], L["up"][1], 1), ("Stated down, % of RESULT", L["down"][0], L["down"][1], 1)]
    y += 26
    for text, rec, fld, prec in items:
        out.append(label(14, y, 500, 24, text, f="default", wrap=False))
        out.append(textupdate(520, y, 120, 24, f(rec, fld), prec=prec, tooltip=f(rec, fld)))
        y += 28
    out.append(label(660, y - 28 * len(items) + 0, 480, 60, f"Quadrature total {100 * m['quad_total']:.2f} % symmetric; the live up and down add the "
                     "energy-dependent corrections and exceed it.", f="small", wrap=True))
    out.append(label(660, y - 28 * len(items) + 66, 480, 80, "Not in the live budget: " + "; ".join(m["not_in_budget"]) + ".", f="small", wrap=True))
    out.append(footer(y + 6))
    return out


def params_pages(L):
    m = MODEL["lanes"][KEYS[L["sel"]]]
    per = 8
    order = ("ASSUMED", "PROVISIONAL", "CHOICE", "DERIVED", "MEASURED", "GIVEN")      # the open ones first
    rows_ = sorted(m["params"], key=lambda r: (order.index(r["tag"]), r["name"]))
    pages = []
    for pi in range(0, len(rows_), per):
        out = []
        y = 4
        for h, hx, hw in (("parameter", 10, 200), ("value", 215, 170), ("unit", 390, 90), ("tag", 485, 100), ("source (full text in the tooltip)  /  closes with", 590, 560)):
            out.append(label(hx, y, hw, 18, h, f="bold", wrap=False))
        y += 20
        for r in rows_[pi:pi + per]:
            bgk = "assumed" if r["tag"] == "ASSUMED" else ("prov" if r["tag"] == "PROVISIONAL" else "read")
            val = fv(r["value"]) + (f"  (sigma {fv(r['sigma'])})" if r.get("sigma") is not None else "")
            src = r["source"] + (f"  | CLOSES WITH: {r['closes_with']}" if r.get("closes_with") else "")
            shown = src if len(src) <= 260 else src[:257] + "..."
            full = r["name"] + ": " + src + (f" ({r['date']})" if r.get("date") else "")
            out.append(rect(6, y, 1138, 52, bg=bgk, lw=1, corner=0))
            out.append(label(10, y + 2, 200, 48, r["name"], f="small", wrap=True))
            out.append(label(215, y + 2, 170, 48, val, f="small", wrap=True))
            out.append(label(390, y + 2, 92, 48, r["unit"], f="tiny", wrap=True))
            out.append(label(485, y + 2, 100, 48, r["tag"], f="bold" if bgk != "read" else "small", wrap=True))
            out.append(label(590, y + 1, 552, 50, shown, f="tiny", wrap=True).replace("</widget>", f"<tooltip>{escape(full)}</tooltip></widget>"))
            y += 54
        out.append(footer(y + 2))
        pages.append((f"{pi // per + 1}", out))
    return pages


def installed_page(L):
    m = MODEL["lanes"][KEYS[L["sel"]]]
    out = [label(10, 2, 1130, 34, "As installed on the IOC (live, read-only): the expression strings (.CLC fields) of each slot, with its DESC. "
                 "These are the numbers that run; the tables on the other pages are the model they were generated from (checked by xray_fluxor op/tests/check_dashboard.py --live).",
                 f="tiny", wrap=True)]
    col, y0 = 0, 40
    y = y0
    for rec, exprs in sorted(m["expected_clc"].items(), key=lambda kv: int(re.sub(r"\D", "", kv[0]))):
        if y > y0 + 330 and col == 0:
            col, y = 1, y0
        x = 10 + 575 * col
        out.append(label(x, y, 110, 20, rec, f="bold", wrap=False))
        out.append(textupdate(x + 112, y, 450, 20, f(rec, "DESC"), f="tiny"))
        y += 22
        for k in exprs:
            out.append(label(x + 6, y, 62, 18, k, f="tiny", fg="note", wrap=False))
            out.append(textupdate(x + 70, y, 492, 18, f(rec, k), f="tiny", tooltip=f(rec, k)))
            y += 19
        y += 6
    return [("As installed (live)", out)]


RANGES = [("10 minutes", "10 minutes"), ("1 hour", "1 hour"), ("24 hours", "24 hours")]
TRACE_COLORS = [(47, 111, 191), (224, 138, 30), (60, 160, 90)]


def stripchart(x, y, w, h, title, start, axis_title, traces, log=False):
    """Phoebus strip chart: it plots what the display receives while it is open (no archive, no retrieval)."""
    tr = "".join(
        f"<trace><name>{escape(n)}</name><y_pv>{pv}</y_pv><axis>0</axis><trace_type>2</trace_type>"
        f'<color><color red="{c[0]}" green="{c[1]}" blue="{c[2]}"></color></color><line_width>2</line_width>'
        f"<point_type>0</point_type><point_size>10</point_size><visible>true</visible></trace>"
        for (n, pv), c in zip(traces, TRACE_COLORS))
    return (f'<widget type="stripchart" version="2.1.0"><name>{g.D.name("trend")}</name>{geom(x, y, w, h)}'
            f"<title>{escape(title)}</title><show_toolbar>false</show_toolbar><show_legend>true</show_legend>"
            f"<start>{start}</start><end>now</end><y_axes><y_axis><title>{escape(axis_title)}</title><autoscale>true</autoscale>"
            f"<log_scale>{'true' if log else 'false'}</log_scale><minimum>0.0</minimum><maximum>1.0</maximum><show_grid>true</show_grid>"
            f"<visible>true</visible></y_axis></y_axes><traces>{tr}</traces></widget>")


TREND_NOTE = "Live history only: plots what this display has received since it was opened; nothing is read from the archiver."


def trends_tab(L):
    key = KEYS[L["sel"]]
    if key == "estation":
        rate = ("Net current", "A", f"{P}userTran9.G")
        energy = f"{P}userTran9.E" if False else f"{P}userTran9.C"
    else:
        rate = ("Net rate", "Hz", f"{P}{L['flux']}.J")
        energy = f"{P}{L['flux']}.E"
    pages = []
    for label_, start in RANGES:
        ws = [label(10, 2, 1130, 18, TREND_NOTE, f="tiny", fg="note", wrap=False),
              stripchart(6, 22, 1130, 168, f"{L['name']}: RESULT with its low and high, last {label_}", start, "photons/s",
                         [("RESULT", f(*L["result"])), ("low", f(*L["low"])), ("high", f(*L["high"]))]),
              stripchart(6, 194, 1130, 168, f"{rate[0]}, last {label_}", start, rate[1], [(rate[0], rate[2])]),
              stripchart(6, 366, 1130, 168, f"Energy, last {label_}", start, "keV", [("energy", energy)])]
        pages.append((f"{label_}", ws))
    cmp_pages = []
    for label_, start in RANGES:
        ws = [label(10, 2, 1130, 18, TREND_NOTE, f="tiny", fg="note", wrap=False),
              stripchart(6, 22, 1130, 510, f"RESULT of the three lanes, last {label_} (log scale)", start, "photons/s",
                         [(LANES[i]["name"], f(*LANES[i]["result"])) for i in range(3)], log=True)]
        cmp_pages.append((f"{label_}", ws))
    top = [(f"This chamber, {n}", ws) for n, ws in pages] + [(f"All three, {n}", ws) for n, ws in cmp_pages]
    return [nested_tabs(f"trends_{L['sel']}", 0, 0, W - 2 * M - 14, 560, top)]


def nested_tabs(name, x, y, w, h, pages):
    t = "".join(f"<tab><name>{escape(n)}</name><children>{''.join(ws)}</children></tab>" for n, ws in pages)
    return (f'<widget type="tabs" version="2.0.0"><name>{name}</name>{geom(x, y, w, h)}<tabs>{t}</tabs>{font("small")}'
            f"<tab_height>24</tab_height><active_tab>{OPT['ptab']}</active_tab></widget>")


def params_tab(L):
    pages = [(f"Parameters {n}", ws) for n, ws in params_pages(L)] + installed_page(L)
    return [nested_tabs(f"params_{L['sel']}", 0, 0, W - 2 * M - 14, 560, pages)]


def details(L):
    pages = [("Inputs", rows(L["inputs"], 14, 12)), ("Corrections", rows(L["corr"], 14, 12)),
             ("Flags", flags_tab(L)), ("Uncertainty budget", budget_tab(L)), ("Model parameters", params_tab(L)), ("Trends", trends_tab(L))]
    t = "".join(f"<tab><name>{escape(n)}</name><children>{''.join(ws)}</children></tab>" for n, ws in pages)
    return (f'<widget type="tabs" version="2.0.0"><name>details_{L["sel"]}</name><visible>false</visible>{geom(M, 340, W - 2 * M, H - 340 - M)}'
            f"<tabs>{t}</tabs>{font('bold')}<tab_height>30</tab_height><active_tab>{OPT['tab']}</active_tab>{vis_rule(L['sel'])}</widget>")


def header():
    return [label(M, M, W - 2 * M, 44, "", bg="header"),
            label(12, 6, 760, 38, "Photon flux: three ion-chamber lanes (read-only)", f="h1", fg="header_fg"),
            state_label(W - 300, 8, 288, 34, [f"{P}HEARTBEAT"], [('pvStr0 != "" && pvSev0 < 3', "utilioc running", "ok")],
                        "No contact with utilioc", tooltip=f"{P}HEARTBEAT")]


def build():
    g.D.n = 0
    body = header()
    cw = (W - 2 * M - 20) // 3
    for i, L in enumerate(LANES):
        body += card(L, M + i * (cw + 10), 54, cw, 278)
    body += [details(L) for L in LANES]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           "<!-- Generated by xray_fluxor op/tools/gen_dashboard.py. Do not edit. Macro P (15IDC:util:) comes from the opener or the settings. -->\n"
           f'<display version="2.0.0"><name>flux dashboard</name><width>{W}</width><height>{H}</height>'
           f"{color('background_color', 'bg')}{''.join(body)}</display>\n")
    return xml.replace("<widget ", "\n<widget ").replace("</display>", "\n</display>")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    for i, a in enumerate(argv):
        if a in ("--sel", "--tab", "--ptab"):
            OPT[a[2:]] = int(argv[i + 1])
    global SEL
    SEL = f"loc://flux_sel({OPT['sel']})"
    out, text = Path(argv[1]), build()
    if "--check" in argv:
        same = out.exists() and out.read_text(encoding="utf-8") == text
        print(f"{out}: {'up to date' if same else 'DIFFERS'}")
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(text.encode("utf-8"))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
