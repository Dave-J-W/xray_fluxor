#!/usr/bin/env python3
"""Phoebus 4.7.4 widget helpers for op/tools/gen_dashboard.py: colours, fonts, label, rect, textupdate, led, state_label.

Copied unchanged from 15IDC HA ioc/utilioc/tools/gen_screens.py (commit 7109653, 2026-11-17), where utilioc's
own screens are generated, so that this repository builds the flux dashboard on its own. If the helpers there change,
copy them again and rerun op/tests/check_dashboard.py --static. Standard library only.
"""
from xml.sax.saxutils import escape


# ---- colours and fonts (Phoebus named colours, with their RGB) -------------------------------
C = {
    "bg": (None, 200, 212, 224), "read": ("Read_Background", 240, 240, 240),
    "text": ("Text", 0, 0, 0), "button": ("Button_Background", 210, 210, 210),
    "ok": ("OK", 0, 255, 0), "off": ("Off", 60, 100, 60), "major": ("MAJOR", 255, 0, 0),
    "invalid": ("INVALID", 255, 0, 255), "header": ("Header_Background", 77, 77, 77),
    "header_fg": ("Header_ForeGround", 255, 255, 255), "grey": (None, 150, 150, 150),
    "box": (None, 255, 255, 240), "ext": (None, 230, 230, 230), "line": (None, 60, 60, 60),
    "fb": (None, 235, 245, 255), "note": (None, 90, 90, 90), "warn": (None, 255, 220, 150),
}
FONTS = {"default": ("Default", "REGULAR", 14), "small": ("Default", "REGULAR", 12),
         "bold": ("Default Bold", "BOLD", 14), "h1": ("Header 1", "BOLD", 22),
         "h2": ("Header 2", "BOLD", 18), "tiny": ("Default", "REGULAR", 11)}


def color(tag, key):
    name, r, g, b = C[key]
    n = f' name="{name}"' if name else ""
    return f'<{tag}><color{n} red="{r}" green="{g}" blue="{b}"></color></{tag}>'


def font(key):
    name, style, size = FONTS[key]
    return (f'<font><font name="{name}" family="Liberation Sans" style="{style}" size="{size}.0">'
            f'</font></font>')


class Display:
    def __init__(self):
        self.n = 0

    def name(self, base):
        self.n += 1
        return f"{base}_{self.n}"


D = Display()


def geom(x, y, w, h):
    return f"<x>{x}</x><y>{y}</y><width>{w}</width><height>{h}</height>"


def label(x, y, w, h, text, f="default", fg="text", bg=None, align=0, valign=1, wrap=True, rules=""):
    back = color("background_color", bg) + "<transparent>false</transparent>" if bg else "<transparent>true</transparent>"
    return (f'<widget type="label" version="2.0.0"><name>{D.name("label")}</name>'
            f"<text>{escape(text)}</text>{geom(x, y, w, h)}{font(f)}{color('foreground_color', fg)}{back}"
            f"<horizontal_alignment>{align}</horizontal_alignment><vertical_alignment>{valign}</vertical_alignment>"
            f"<wrap_words>{'true' if wrap else 'false'}</wrap_words>{rules}</widget>")


def rect(x, y, w, h, bg="box", line="line", lw=1, corner=8):
    return (f'<widget type="rectangle" version="2.0.0"><name>{D.name("box")}</name>{geom(x, y, w, h)}'
            f"<line_width>{lw}</line_width>{color('line_color', line)}{color('background_color', bg)}"
            f"<corner_width>{corner}</corner_width><corner_height>{corner}</corner_height></widget>")


def textupdate(x, y, w, h, pv, f="default", fmt=None, prec=None, align=0, tooltip=None):
    extra = (f"<format>{fmt}</format>" if fmt is not None else "") + (f"<precision>{prec}</precision>" if prec is not None else "")
    return (f'<widget type="textupdate" version="2.0.0"><name>{D.name("value")}</name><pv_name>{pv}</pv_name>'
            f"{geom(x, y, w, h)}{font(f)}{color('background_color', 'read')}<transparent>false</transparent>"
            f"<horizontal_alignment>{align}</horizontal_alignment>{extra}"
            + (f"<tooltip>{escape(tooltip)}</tooltip>" if tooltip else "")
            + f"<border_alarm_sensitive>true</border_alarm_sensitive></widget>")


def led(x, y, size, pv, on="ok", off="off", tooltip=""):
    return (f'<widget type="led" version="2.0.0"><name>{D.name("led")}</name><pv_name>{pv}</pv_name>'
            f"{geom(x, y, size, size)}{color('off_color', off)}{color('on_color', on)}"
            f"<tooltip>{escape(tooltip)}</tooltip><border_alarm_sensitive>true</border_alarm_sensitive></widget>")


def state_label(x, y, w, h, pvs, branches, fallback, f="bold", fallback_bg="grey", tooltip=""):
    """Label whose text and colour follow rules. The file holds the fallback (no contact) state:
    a rule that matches no branch, or whose PVs never connected, leaves it (phoebus skill)."""
    pv_xml = "".join(f"<pv_name>{p}</pv_name>" for p in pvs)
    text_exps = "".join(f'<exp bool_exp="{escape(e, {chr(34): "&quot;"})}"><value>{escape(t)}</value></exp>'
                        for e, t, _ in branches)
    bg_exps = "".join(f'<exp bool_exp="{escape(e, {chr(34): "&quot;"})}">{color("value", c)}</exp>'
                      for e, _, c in branches)
    rules = (f'<rules><rule name="text" prop_id="text" out_exp="false">{text_exps}{pv_xml}</rule>'
             f'<rule name="colour" prop_id="background_color" out_exp="false">{bg_exps}{pv_xml}</rule></rules>')
    return label(x, y, w, h, fallback, f=f, bg=fallback_bg, align=1, rules=rules).replace(
        "</widget>", f"<tooltip>{escape(tooltip)}</tooltip></widget>")
