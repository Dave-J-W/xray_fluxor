"""AVS IC-500-50 at the E-station: 50 mm electrode, 10 mm gap, flowing N2, factory 25 um Kapton windows, split collector.

Given (user 2026-11-13): gap 10 mm, flowing nitrogen, factory Kapton, not gridded, HV 1.7 kV. Everything else is an
ASSUMPTION listed in fluxor/ASSUMPTIONS.md (ids A-n in the comments below). Reference plane: the exit of the collection
region, before the exit Kapton (as MonP); the Kapton and air path are out of scope.
"""
from fluxor import params
from fluxor.chambers.base import IonChamber

# Every number below lives in fluxor/parameters.toml (tag, source, how to close). These module-level names are the registry's
# default rows, read once at import for the scripts and tests that import them; the chamber itself reads the registry at
# flux() time, so a replaced row takes effect.
WALL_FIT = tuple(params.default().param("ic500.wall_fit").value)
L_EFF_CM = params.default().param("ic500.l_eff_cm").value
ALPHA_CM3_S = params.default().param("recomb.alpha_cm3_s").value
MOBILITY_CM2_VS = params.default().param("recomb.mobility_cm2_vs").value


def recombination_loss(current_a, gap_cm, volts, beam_h_cm, beam_w_cm, length_cm,
                       alpha=ALPHA_CM3_S, k_pos=MOBILITY_CM2_VS, k_neg=MOBILITY_CM2_VS):
    """First-order volume-recombination loss fraction of a thin beam (height h along the field, width w, length l).

    Ions of both signs stream through the ionised sheet of height h; the product n+ n- integrates to
    alpha q^2 h^3 / (6 k+ k- E^2) per unit area against q h produced, so the loss is alpha q h^2 / (6 k+ k- E^2) with
    q = (I/e) / (h w l) and E = V/d. Valid for a loss << 1; larger values mean the formula no longer applies.
    """
    e_charge = 1.602176634e-19
    field = volts / gap_cm
    q = abs(current_a) / e_charge / (beam_h_cm * beam_w_cm * length_cm)
    return alpha * q * beam_h_cm ** 2 / (6 * k_pos * k_neg * field ** 2)


class Ic500_50(IonChamber):
    """The beam size comes from the registry: beam.width_mm along the plate and height = width x beam.aspect_central across
    the field. The loss scales as h/w, so the ratio is what matters; both rows are ASSUMED and flagged while they are."""
    name = "IC-500-50"

    def __init__(self, reg=None):
        super().__init__(reg)
        self._read_parameters()

    def _read_parameters(self):
        r = self.reg
        self.l_cm = r.value("ic500.l_eff_cm")
        self.gap_cm = r.value("ic500.gap_mm") / 10
        self.volts = r.value("ic500.volts")
        self.wall_fit = tuple(r.value("ic500.wall_fit"))
        self.symmetric_terms = {
            "mu_en/rho tables": (r.value("terms.mu_en_tables_rel"), "B", "spread of NIST vs Chantler/Elam (physics_note 3.7)"),
            "W": (r.value("terms.w_rel"), "B", "spread of five sources, as a 1-sigma"),
            "density (P, T from the caller)": (r.value("terms.density_rel"), "B", "as MonP; the real P, T source for flowing N2 is open (A7)"),
            "energy readback": (r.value("terms.energy_readback_rel"), "B", "assumed 0.1 % mono energy error x d ln(flux)/d ln E (UNCERTAINTY.md)"),
            "collection length (l_eff)": (r.param("ic500.l_eff_cm").sigma, "B", "relative; l_eff = the 50 mm electrode length (user), 3 % allowance for fringe field and guard rings"),
        }
        self.beam_w_cm = r.value("beam.width_mm") / 10
        self.beam_h_cm = self.beam_w_cm * r.value("beam.aspect_central")
        self.alpha = r.value("recomb.alpha_cm3_s")
        self.mobility = r.value("recomb.mobility_cm2_vs")

    def wall_loss(self, e_eff):
        lo, c, hi = super().wall_loss(e_eff)
        if c > 0:
            self.reg.value("ic500.plate_orientation")      # the wall-loss fit assumes it; flag only when the correction is nonzero
        return lo, c, hi

    def extra_flags_and_high(self, current_a, e_kev, p_kpa, t_c):
        """Recombination at the low, central and high beam aspect ratio (registry rows beam.aspect_*), same width.
        The ionised sheet cannot be taller than the gap, so h is capped at the gap; the beam-taller flag uses the uncapped height."""
        w = self.beam_w_cm
        losses, h_c = [], None
        for row in ("beam.aspect_low", "beam.aspect_central", "beam.aspect_high"):
            h = min(w * self.reg.value(row), self.gap_cm)
            losses.append(recombination_loss(current_a, self.gap_cm, self.volts, h, w, self.l_cm,
                                             alpha=self.alpha, k_pos=self.mobility, k_neg=self.mobility))
            if row == "beam.aspect_central":
                h_c = h
        r_lo, r_c, r_hi = losses
        flags = []
        if not (self.reg.value("beam.aspect_low") <= self.reg.value("beam.aspect_central") <= self.reg.value("beam.aspect_high")):
            flags.append("beam_aspect_rows_not_ordered")
        if w * self.reg.value("beam.aspect_central") > 0.3 * self.gap_cm:
            flags.append("beam_taller_than_30_percent_of_gap_formula_weak")
        if r_hi > 0.01:
            flags.append("recombination_over_1_percent")
        if r_hi > 0.1:
            flags.append("recombination_formula_not_valid")
        return flags, (r_lo, r_c, r_hi), {"recomb_low": r_lo, "recomb_central": r_c, "recomb_high": r_hi,
                                          "beam_h_cm": h_c, "beam_w_cm": w}
