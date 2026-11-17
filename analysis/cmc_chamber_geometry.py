"""CMC-custom ion chamber geometry: the single source of chamber dimensions for models and figures.

Provenance: the user's hands-on measurements of the MonC chamber, 2026-11-13. MonP is the same design
(user), but MonP is mounted with its plates VERTICAL and MonC with its plates HORIZONTAL. Values that were
only seen on MonC (beam position, plate bias, crust) must be re-checked on MonP before MonP uses them.

Tags (every value carries one):
  MEASURED     the user's reading on MonC (approximate where the user said "about"/"appears")
  INTERPRETED  my reading of the user's words; listed so it can be corrected
  ASSUMED      not given; a placeholder needed to draw or model
  GUESS-USER   the user's own stated guess
  UNKNOWN      not known; nothing here should depend on it without saying so
  DERIVED      computed below from the values above
  OBSERVED     a reading of a state or an instrument display, not a measurement of the chamber itself

Coordinates (mm), in the chamber's own frame, independent of mounting:
  x  along the beam, downstream positive; x = 0 at the middle of the inner length (end wall to end wall)
  y  across the plate width; y = 0 at the plates' width centre; +y = inboard (toward the beam's 2 mm offset)
  z  across the gap, from the lower plate toward the upper plate; z = 0 at the window aperture centre
     (MonC: z is up. MonP: the same chamber turned 90 degrees, so z is horizontal.)

Electrically (meter, 2026-11-13): the upper plate is the collector (BNC centre pin), the lower plate is HV, and the
Al blocks beside the collector are grounded to the shell, so they are GUARD electrodes.
Updated 2026-11-13 with the exterior shell dimensions and the meter checks.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class P:
    value: object
    unit: str
    tag: str
    note: str


PARAMS = {
    # mounting and polarization
    "monc_plates": P("horizontal", "", "MEASURED", "MonC is operated with the plates horizontal"),
    "monp_plates": P("vertical", "", "MEASURED", "MonP: same design, plates vertical"),
    "polarization": P("horizontal", "", "MEASURED", "beam E-vector horizontal (user, earlier)"),
    # windows and beam
    "window_aperture_h": P(12.8, "mm", "MEASURED",
                           "window aperture height (input and exit), along z; calipers (was 12.7 by eye)"),
    # the apertures are machined slots in the end walls (user, 2026-11-13; "machining is not very precise")
    "slot_width_measured": P(63.67, "mm", "MEASURED", "slot length along y, including the round ends"),
    "slot_flat_measured": P(53.0, "mm", "MEASURED", "flat (non-arched) part of the slot, about"),
    "slot_ends": P("semicircle", "", "MEASURED", "round ends are semicircles of radius 12.8/2 mm (user, confirmed)"),
    "slot_apex_to_outboard_exterior": P(31.74, "mm", "MEASURED",
                                        "outboard arch apex to the shell exterior on the electronics-mount side"),
    "slot_apex_to_inboard_exterior": P(6.22, "mm", "MEASURED", "inboard arch apex to the shell exterior"),
    "plates_centred_on_slot": P(True, "", "ASSUMED", "plate width centre taken on the slot centre; not given"),
    "beam_below_aperture_top": P(5.5, "mm", "MEASURED", "beam scar on the Kapton, from the top of the aperture"),
    "beam_inboard_of_plate_centre": P(2.0, "mm", "MEASURED", "beam offset across the 60 mm plate width, inboard"),
    # beam size and MonP's beam position (METHOD_REVIEW C8: these feed analysis/wall_loss_families.py)
    "beam_fwhm_vertical": P(0.03, "mm", "MEASURED",
                            "vertical beam size 0.02-0.04 mm FWHM (user); mid value taken. Across MonC's gap"),
    "beam_fwhm_horizontal": P(1.0, "mm", "MEASURED", "horizontal beam size ~1 mm FWHM (user). Across MonP's gap"),
    "monp_beam_offset": P(0.0, "mm", "ASSUMED",
                          "MonP's beam taken centred in its gap; not measured on MonP (the MonC scar does not apply)"),
    # high voltage
    "hv": P(2.7, "kV", "OBSERVED", "HV supply readout (user); not verified at the chamber"),
    # plates
    # plate faces from the aperture ledges (user, 2026-11-13, new measurement): each plate's gap-facing face lies inside
    # the aperture opening by this much (inset = inward from the ledge, toward the beam; confirmed by the user for the
    # upper plate, 2026-11-13: its 1 mm thickness straddles the top ledge)
    "upper_plate_inset_from_aperture_top": P(0.6, "mm", "MEASURED",
                                             "upper plate face 0.6 mm inside the upper aperture ledge; the plate's 1 mm "
                                             "thickness straddles the ledge (user confirmed 2026-11-13)"),
    "lower_plate_inset_from_aperture_bottom": P(1.0, "mm", "MEASURED", "lower plate inset from the lower aperture ledge"),
    "plate_gap_reading": P(10.0, "mm", "MEASURED", "earlier 'about 1 cm' by eye; superseded by the inset readings"),
    "plate_bias_reading": P(0.7, "mm", "MEASURED", "earlier ~0.7 mm upward bias by eye (user not confident); superseded"),
    "plate_thickness": P(1.0, "mm", "MEASURED", "revised estimate 1 mm (was 1/16 inch), both plates"),
    "plate_width": P(60.0, "mm", "MEASURED", "about 6 cm transverse to the beam, both plates"),
    "plate_material": P("aluminium", "", "MEASURED", "plates appear to be aluminium"),
    "lower_plate_length": P(75.5, "mm", "MEASURED", "along the beam"),
    "lower_plate_end_clearance": P(6.5, "mm", "MEASURED",
                                   "plate end to end wall; taken as the same at both ends (INTERPRETED)"),
    "upper_plate_length": P(60.5, "mm", "MEASURED", "along the beam"),
    "upper_plate_end_clearance": P(14.3, "mm", "MEASURED",
                                   "plate end to end wall; taken as the same at both ends (INTERPRETED)"),
    "end_wall_thickness": P(3.0, "mm", "MEASURED", "about 3 mm steel"),
    # the aluminium blocks beside the upper plate
    "block_gap": P(1.0, "mm", "MEASURED",
                   "~1 mm gaps; taken as one gap plate-to-block and one block-to-wall at each end (INTERPRETED)"),
    "block_plane": P("upper plate", "", "MEASURED", "conductive (aluminium) blocks in the same plane as the upper plate"),
    "block_extra_inboard": P(3.0, "mm", "ASSUMED",
                             "guards are wider than the plate by 'a few millimetres' on the inboard side; 3 mm taken"),
    "block_extra_outboard": P(0.4, "mm", "MEASURED", "guards wider than the plate by ~0.4 mm on the outboard side"),
    "block_thickness": P(12.7, "mm", "MEASURED",
                         "much thicker than the plates: mounted directly on the shell, no gap, ~12.7 mm in z"),
    "block_recess": P(0.51, "mm", "MEASURED",
                      "guard blocks set back 0.51 mm from the plate plane, away from the gap, so they give a larger "
                      "clear aperture, not a smaller one. Taken from the collector's gap-facing face (INTERPRETED)"),
    "block_connection": P("ground", "", "MEASURED", "blocks electrically connected to the body (meter): guard electrodes"),
    # connections (meter checks, 2026-11-13)
    "signal_plate": P("upper", "", "MEASURED", "BNC centre pin connected to the upper plate: the collector"),
    "hv_plate": P("lower", "", "MEASURED", "HV centre pin connected to the lower plate"),
    "grounds": P("shell", "", "MEASURED", "HV ground and BNC ground both connected to the frame/shell"),
    # exterior shell
    "exterior_length": P(95.16, "mm", "MEASURED", "end to end, along x; +-0.2 mm (corrected from 95.0)"),
    "exterior_width": P(101.4, "mm", "MEASURED",
                        "along y; +-0.25 mm (corrected from 101.5); the most precise width reading, held fixed"),
    "exterior_height": P(44.5, "mm", "MEASURED", "along z; +-0.25 mm (corrected from 44.0)"),
    "shell_wall_thickness": P(3.0, "mm", "ASSUMED", "top, bottom and side walls taken equal to the ~3 mm end walls; not given"),
    "plates_centred_in_width": P(False, "", "MEASURED",
                                 "the window and plates sit off-centre across the width, leaving room inside for the "
                                 "electrical connections; the offset is not given"),
    "plate_offset_in_width": P("derived", "mm", "DERIVED",
                               "from the reconciled slot position (slot_fit) and plates_centred_on_slot"),
    # beam-exposure marks
    "lower_plate_crust_width": P(8.0, "mm", "MEASURED", "white crust, thicker and wider, on the lower plate"),
    "upper_plate_crust_width": P(6.0, "mm", "MEASURED", "white crust, much thinner, on the upper plate"),
    "crust_centre_y": P("beam", "", "ASSUMED", "crusts drawn centred on the beam's y; their extent along x not given"),
    # not given
    "window_aperture_w": P("slot_fit", "mm", "DERIVED", "the reconciled slot length, slot_fit()['W']"),
    "window_bc": P("ground", "", "ASSUMED", "the Kapton window aperture is modelled as grounded, like the steel around it"),
}


# Gap at the beam track: MEASURED (user, 2026-11-13): 11.45 mm lower plate to upper guard face, minus ~0.6 mm back to
# the upper plate = 10.85 mm, varying by ~0.5 mm inboard to outboard (the plates are not truly parallel). The upper
# plate is placed from its ledge inset; the lower plate then follows from the gap. The lower ledge inset reading is a
# check (implied vs read below). User: diminishing returns, do not refine further.
PARAMS["plate_gap"] = P(10.85, "mm", "MEASURED",
                        "inner face to inner face at the beam track, +-0.2 mm there; +-0.5 mm if the beam moves across the width (plates not parallel); was 11.2 from the insets")
_H = PARAMS["window_aperture_h"].value
_up = _H / 2 - PARAMS["upper_plate_inset_from_aperture_top"].value
_lo = _up - PARAMS["plate_gap"].value
PARAMS["plate_mid_gap_above_aperture_centre"] = P((_up + _lo) / 2, "mm", "DERIVED",
                                                  "from the upper ledge inset and the measured gap")
PARAMS["lower_inset_implied"] = P(_lo + _H / 2, "mm", "DERIVED",
                                  "lower ledge inset implied by the gap; the reading was 1.0 mm (plates not parallel)")


def v(name):
    return PARAMS[name].value


def slot_fit():
    """Reconcile the slot readings, holding the exterior width fixed (user: the most precise measurement; split the
    difference for the rest). Unknowns: the two apex-to-exterior distances a (outboard) and b (inboard). Then the slot
    length W = exterior_width - a - b and the flat F = W - height (semicircular ends of radius height/2, MEASURED). Equal-weight
    least squares over the four readings a, b, W, F. Returns the fitted values and the residuals (fit - reading)."""
    import numpy as np
    E, H = v("exterior_width"), v("window_aperture_h")
    a0, b0 = v("slot_apex_to_outboard_exterior"), v("slot_apex_to_inboard_exterior")
    W0, F0 = v("slot_width_measured"), v("slot_flat_measured")
    # residual vector r = M @ [a, b] - y
    M = np.array([[1, 0], [0, 1], [-1, -1], [-1, -1]], float)
    y = np.array([a0, b0, W0 - E, F0 + H - E])
    (a, b), *_ = np.linalg.lstsq(M, y, rcond=None)
    W = E - a - b
    F = W - H
    a, b, W, F = (float(x) for x in (a, b, W, F))
    return {"a_outboard": a, "b_inboard": b, "W": W, "F": F,
            "res_a": a - a0, "res_b": b - b0, "res_W": W - W0, "res_F": F - F0,
            "W_from_apexes_raw": E - a0 - b0, "W_from_flat_raw": F0 + H}


def derived():
    """Derived quantities (DERIVED), from PARAMS only."""
    g, t = v("plate_gap"), v("plate_thickness")
    zmid = v("plate_mid_gap_above_aperture_centre")
    beam_z = v("window_aperture_h") / 2 - v("beam_below_aperture_top")
    inner_len_lower = v("lower_plate_length") + 2 * v("lower_plate_end_clearance")
    inner_len_upper = v("upper_plate_length") + 2 * v("upper_plate_end_clearance")
    # walls at +-inner_length/2, from the exterior length (+-0.2 mm) and the ~3 mm end walls; the two plates'
    # own clearance readings (88.5, 89.1 mm) are kept as checks
    inner_len = v("exterior_length") - 2 * v("end_wall_thickness")
    block_len = inner_len / 2 - v("upper_plate_length") / 2 - 2 * v("block_gap")
    w = v("shell_wall_thickness")
    upper_inner = zmid + g / 2
    guard_z0 = upper_inner + v("block_recess")                 # guard gap-facing face, set back from the collector plane
    shell_top_inner = guard_z0 + v("block_thickness")          # the blocks sit directly on the top shell
    shell_top_outer = shell_top_inner + w
    shell_bot_outer = shell_top_outer - v("exterior_height")
    inner_w = v("exterior_width") - 2 * w
    sf = slot_fit()
    # y frame: y = 0 at the plate width centre, +y inboard. Slot centre from the inboard exterior face:
    slot_c_from_inboard = sf["b_inboard"] + sf["W"] / 2
    plate_c_from_inboard = slot_c_from_inboard            # plates_centred_on_slot (ASSUMED)
    shell_centre_y = plate_c_from_inboard - v("exterior_width") / 2   # shell width centre in the plate frame (negative = outboard)
    pw = v("plate_width")
    return {
        "inner_length_from_lower_plate": inner_len_lower,
        "inner_length_from_upper_plate": inner_len_upper,
        "inner_length": inner_len,
        "upper_end_clearance_implied": (inner_len - v("upper_plate_length")) / 2,
        "lower_end_clearance_implied": (inner_len - v("lower_plate_length")) / 2,
        "block_length": block_len,
        "shell_top_inner_z": shell_top_inner, "shell_top_outer_z": shell_top_outer,
        "shell_bottom_inner_z": shell_bot_outer + w, "shell_bottom_outer_z": shell_bot_outer,
        "inner_height": v("exterior_height") - 2 * w,
        "upper_outer_face_to_shell": shell_top_inner - (upper_inner + t),
        "lower_outer_face_to_shell": (zmid - g / 2 - t) - (shell_bot_outer + w),
        "inner_width": inner_w,
        "side_clearance_total": inner_w - pw,
        "shell_centre_y": shell_centre_y,
        "shell_inboard_exterior_y": shell_centre_y + v("exterior_width") / 2,
        "shell_outboard_exterior_y": shell_centre_y - v("exterior_width") / 2,
        "side_clearance_inboard": (plate_c_from_inboard - pw / 2) - w,
        "side_clearance_outboard": inner_w - pw - ((plate_c_from_inboard - pw / 2) - w),
        "slot_y": (shell_centre_y + v("exterior_width") / 2 - sf["b_inboard"] - sf["W"],
                   shell_centre_y + v("exterior_width") / 2 - sf["b_inboard"]),
        "slot_flat_y": (shell_centre_y + v("exterior_width") / 2 - sf["b_inboard"] - sf["W"] + v("window_aperture_h") / 2,
                        shell_centre_y + v("exterior_width") / 2 - sf["b_inboard"] - v("window_aperture_h") / 2),
        "block_width": pw + v("block_extra_inboard") + v("block_extra_outboard"),
        "block_y": (-pw / 2 - v("block_extra_outboard"), pw / 2 + v("block_extra_inboard")),
        "guard_z0": guard_z0,
        "collector_length": v("upper_plate_length"),
        "collector_l_eff_guard_rule": v("upper_plate_length") + v("block_gap"),   # textbook: + half of each guard gap
        "beam_z": beam_z,                                   # beam height above the aperture centre
        "beam_above_mid_gap": beam_z - zmid,
        "upper_inner_z": zmid + g / 2, "upper_outer_z": zmid + g / 2 + t,
        "lower_inner_z": zmid - g / 2, "lower_outer_z": zmid - g / 2 - t,
        "beam_to_upper_inner_face": zmid + g / 2 - beam_z,
        "beam_to_lower_inner_face": beam_z - (zmid - g / 2),
        "beam_y": v("beam_inboard_of_plate_centre"),
        "upper_plate_x": (-v("upper_plate_length") / 2, v("upper_plate_length") / 2),
        "lower_plate_x": (-v("lower_plate_length") / 2, v("lower_plate_length") / 2),
    }


def blocks_x():
    """x extents of the two blocks beside the upper plate (INTERPRETED layout: wall | gap | block | gap | plate)."""
    d = derived()
    half_inner = d["inner_length"] / 2
    up = v("upper_plate_length") / 2
    gap = v("block_gap")
    # downstream block, between the plate end + gap and the wall - gap; mirrored upstream
    lo, hi = up + gap, half_inner - gap
    return [(-hi, -lo), (lo, hi)]


def main():
    print(f"{'parameter':38s} {'value':>14s} {'unit':4s} {'tag':12s} note")
    for k, p in PARAMS.items():
        val = "—" if p.value is None else (f"{p.value:.3f}" if isinstance(p.value, float) else str(p.value))
        print(f"{k:38s} {val:>14s} {p.unit:4s} {p.tag:12s} {p.note}")
    print("\nderived:")
    for k, x in derived().items():
        print(f"  {k:34s} {x if isinstance(x, tuple) else round(x, 3)}")
    d = derived()
    mismatch = abs(d["inner_length_from_lower_plate"] - d["inner_length_from_upper_plate"])
    print(f"\ncheck: inner length from the two plates agrees to {mismatch:.1f} mm "
          f"({d['inner_length_from_lower_plate']:.1f} vs {d['inner_length_from_upper_plate']:.1f}); "
          f"from the exterior length {d['inner_length']:.1f} mm")
    print(f"check: blocks {blocks_x()} mm; block length {d['block_length']:.1f} mm")
    sf = slot_fit()
    print("slot reconciliation (exterior width held at %.2f mm):" % v("exterior_width"))
    print(f"  raw: slot length {v('slot_width_measured'):.2f} measured, {sf['W_from_apexes_raw']:.2f} from the apex distances, "
          f"{sf['W_from_flat_raw']:.2f} from flat + height")
    print(f"  fit: outboard apex {sf['a_outboard']:.2f} ({sf['res_a']:+.2f}), inboard apex {sf['b_inboard']:.2f} ({sf['res_b']:+.2f}), "
          f"slot {sf['W']:.2f} ({sf['res_W']:+.2f}), flat {sf['F']:.2f} ({sf['res_F']:+.2f}) mm")


if __name__ == "__main__":
    main()
