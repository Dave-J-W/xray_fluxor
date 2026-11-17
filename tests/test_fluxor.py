"""Tests for the fluxor package. Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 -m unittest discover -s tests -t .

Gates (docs/superpowers/specs/2026-11-13-ic500-chains-design.md):
  1 regression: SR570+V2F chain with the MonP chamber reproduces the published number (RESULT.md) and the live calc
  2 chain tests: manual numbers per range, flags
  3 chamber tests: independent conversion, recombination against a numerical solution
"""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fluxor import constants as k  # noqa: E402
from fluxor import params  # noqa: E402
from fluxor.chains import fx4, tetramm  # noqa: E402
from fluxor.chains.sr570_v2f import Sr570V2f  # noqa: E402
from fluxor.chambers import ic500_50  # noqa: E402
from fluxor.chambers.cmc_guarded import CmcGuarded  # noqa: E402
from fluxor.core import evaluate  # noqa: E402

import monp_transform as mt  # noqa: E402   (calc/, put on the path by fluxor.chambers.cmc_guarded)
import quality_slots as qs  # noqa: E402

SITE_P, SITE_T = 99.26, 24.9
HZ = 2.0e5


class Regression(unittest.TestCase):
    """Gate 1: the new framework reproduces MonP's published numbers before any new hardware is trusted."""

    def one_hz(self, e, lane="MonP"):
        reading = dict(counts=HZ, time_s=1.0, sens_num=8, sens_unit=1, dark_hz=0.0)    # 500 nA/V, 2e5 net hertz
        return evaluate(CmcGuarded(lane), Sr570V2f(), reading, e, SITE_P, SITE_T)

    def test_published_4p37e6_at_10_keV(self):
        r = self.one_hz(10.0)
        self.assertAlmostEqual(r.flux_formula / HZ / 4.37e6 - 1, 0, delta=0.01)  # RESULT.md headline, 3 digits

    def test_matches_live_calc_formula(self):
        for e in (5, 8, 10, 15, 20, 25, 30):
            v = mt.evaluate(A=HZ, B=1.0, C=8, D=1, E=e, F=SITE_T, G=SITE_P, H=0.0)
            self.assertAlmostEqual(self.one_hz(float(e)).flux_formula / v["P"] - 1, 0, delta=0.02, msg=f"{e} keV")

    def test_bounds_agree_with_live_bounds(self):
        for lane in ("MonP", "MonC"):
            for e in (10, 20, 30):
                v = mt.evaluate(A=HZ, B=1.0, C=8, D=1, E=e, F=SITE_T, G=SITE_P, H=0.0)
                b = qs.bounds(v["P"], e, rho=k.density_g_cm3(SITE_P, SITE_T), lane=lane)
                r = self.one_hz(float(e), lane)
                self.assertAlmostEqual(r.flux_best / b["L"] - 1, 0, delta=0.02, msg=f"{lane} {e} best")
                # same band, but this package has no 0.9 % cross-section-fit term: bounds within 1 % of live
                self.assertAlmostEqual(r.flux_high / b["E"] - 1, 0, delta=0.012, msg=f"{lane} {e} high")
                self.assertAlmostEqual(r.flux_low / b["D"] - 1, 0, delta=0.012, msg=f"{lane} {e} low")

    def test_total_sigma_is_the_live_budget_without_the_fit_term(self):
        r = self.one_hz(10.0)
        live = math.sqrt(sum(v * v for n, v in qs.SYMMETRIC_TERMS.items() if n != "cross-section fit"))
        # the Poisson term (type A) is not in the live budget: compare the systematic terms only
        sigma = math.sqrt(sum(t.rel ** 2 for t in r.budget if t.kind != "A"))
        self.assertAlmostEqual(sigma, live, places=6)


class Chains(unittest.TestCase):
    def test_tetramm_noise_table(self):
        self.assertAlmostEqual(tetramm.noise_ppm(0, 10e-3), 0.7)
        self.assertAlmostEqual(tetramm.noise_ppm(0, 50e-6), 5.8)
        self.assertAlmostEqual(tetramm.noise_ppm(1, 10e-3), 1.8)
        self.assertAlmostEqual(tetramm.noise_ppm(0, 1.0), 0.7)             # clamped at the longest tabulated period
        self.assertTrue(0.7 < tetramm.noise_ppm(0, 7e-3) < 1.0)            # between 5 ms and 10 ms

    def test_tetramm_sums_signal_channels_and_subtracts_dark(self):
        ch = tetramm.TetraMM(("Current3", "Current4"), darks={"Current3": 0.2, "Current4": -0.1}, dark_age_h=2)
        r = ch.current({"channels": {"Current1": 0.4, "Current3": 2000.0, "Current4": 1300.0}})
        self.assertAlmostEqual(r.current_a, (2000.0 - 0.2 + 1300.0 + 0.1) * 1e-9, places=15)
        self.assertEqual(sorted(r.channels_a), ["Current3", "Current4"])       # Current1 is not summed
        self.assertIn("assumed:tetramm.gain_rel", r.flags)
        self.assertNotIn("dark_stale_or_age_unknown", r.flags)

    def test_tetramm_flags(self):
        ch = tetramm.TetraMM(("Current3",), rng=1)                             # +-120 nA range
        r = ch.current({"channels": {"Current3": 200.0}})
        self.assertIn("overrange_Current3", r.flags)
        self.assertIn("dark_not_given_Current3", r.flags)
        self.assertIn("dark_stale_or_age_unknown", r.flags)

    def test_fx4_resolution_matches_manual(self):
        lsb0 = fx4.Fx4(("c1",), 0).current({"channels": {"c1": 1e-9}}).detail["lsb_a"]
        self.assertAlmostEqual(lsb0 / 3e-12, 1.0, delta=0.1)                   # "around 3 pA per bit" on 100 nA
        lsb10m = 2 * 10e-3 / 65536
        self.assertAlmostEqual(lsb10m / 300e-9, 1.0, delta=0.1)                # "around 300 nA per bit" on 10 mA

    def test_fx4_flags(self):
        r = fx4.Fx4(("c1", "c2"), 5, sample_hz=10.0).current({"channels": {"c1": 1e-6, "c2": 2e-6}}, temp_c=40.0)
        self.assertAlmostEqual(r.current_a, 3e-6, places=15)
        for f in ("noise_from_resolution_only", "assumed:fx4.gain_rel", "temperature_outside_15_25C"):
            self.assertIn(f, r.flags)
        self.assertNotIn("range_full_scale_provisional", r.flags)              # range 5 = 100 uA is in the manual picture
        self.assertIn("range_full_scale_provisional", fx4.Fx4(("c1",), 7).current({"channels": {"c1": 0.0}}).flags)
        self.assertIn("overrange_c1", fx4.Fx4(("c1",), 0).current({"channels": {"c1": 150e-9}}).flags)


class Chambers(unittest.TestCase):
    def test_independent_conversion_ic500(self):
        """The chamber against calc/monp_transform.full_physics with its collection length set to 5 cm."""
        i_a = 4e-6
        ch = ic500_50.Ic500_50()
        saved = mt.L_CM
        mt.L_CM = ic500_50.L_EFF_CM
        try:
            for e in (6, 10, 15, 20):
                ref = mt.full_physics(rate_hz=i_a * 1e5 / 1e-0, sens_a_per_v=1.0, e_kev=e, t_c=SITE_T, p_kpa=SITE_P)
                # full_physics: current = rate * sens / 1e5, so rate = I * 1e5 / sens with sens = 1 A/V
                got = ch.flux(i_a, float(e), SITE_P, SITE_T).flux_formula
                self.assertAlmostEqual(got / ref - 1, 0, delta=0.005, msg=f"{e} keV")
        finally:
            mt.L_CM = saved

    def test_cross_sections_against_xraydb_table(self):
        import csv
        with open(k.ROOT / "data" / "queries" / "out" / "xraydb_N.csv", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(x for x in f if not x.startswith("#")))
        for r in rows:
            e = float(r["E_keV"])
            if e in (8.0, 10.0, 15.0, 20.0):
                self.assertAlmostEqual(k.muen_over_rho(e) / float(r["muen_eff_photo_plus_compton"]) - 1, 0, delta=0.05)

    def test_wall_loss_zero_below_threshold_and_band_ordered(self):
        ch = ic500_50.Ic500_50()
        self.assertEqual(ch.flux(1e-6, 10.0, SITE_P, SITE_T).wall_loss, 0.0)
        for e in (14.0, 20.0, 30.0):
            lo, c, hi = ch.wall_loss(e)
            self.assertTrue(lo <= c <= hi)

    @staticmethod
    def numerical_recombination_loss(i_a, d=1.0, volts=1700.0, h=0.01, w=0.05, ln=5.0):
        """Drift-only continuity equations for a sheet of height h in a gap d, solved by iteration."""
        alpha, kp, kn = ic500_50.ALPHA_CM3_S, ic500_50.MOBILITY_CM2_VS, ic500_50.MOBILITY_CM2_VS
        q = i_a / k.E_CHARGE / (h * w * ln)
        field = volts / d
        n = 4001
        dx = h / (n - 1)
        npos = [0.0] * n
        nneg = [0.0] * n
        for _ in range(60):
            # positive ions drift +x: dn+/dx = (q - a n+ n-)/(kp E); negative drift -x: -dn-/dx = (q - a n+ n-)/(kn E)
            new_p, new_n = [0.0] * n, [0.0] * n
            for j in range(1, n):
                new_p[j] = new_p[j - 1] + dx * (q - alpha * npos[j - 1] * nneg[j - 1]) / (kp * field)
            for j in range(n - 2, -1, -1):
                new_n[j] = new_n[j + 1] + dx * (q - alpha * npos[j + 1] * nneg[j + 1]) / (kn * field)
            npos, nneg = new_p, new_n
        # collected positive charge flux at the exit = kp E n+(h); undisturbed would be q h
        return 1 - npos[-1] * kp * field / (q * h)

    def test_recombination_formula_is_the_first_order_limit_of_the_numerical_solution(self):
        d, volts, h, w, ln = 1.0, 1700.0, 0.01, 0.05, 5.0
        low = ic500_50.recombination_loss(4e-8, d, volts, h, w, ln)
        self.assertAlmostEqual(low / self.numerical_recombination_loss(4e-8) - 1, 0, delta=0.01)   # first order is exact here
        mid = ic500_50.recombination_loss(4e-6, d, volts, h, w, ln)                                # 2.8 %: second order shows
        num = self.numerical_recombination_loss(4e-6)
        self.assertGreaterEqual(mid, num)                       # conservative: the bound never understates the loss
        self.assertAlmostEqual(mid / num - 1, 0, delta=0.10)

    def test_wall_loss_constant_matches_the_mc_fit_and_band_covers(self):
        sys.path.insert(0, str(ROOT / "analysis"))
        import wall_loss_fit_ic500 as fit_script
        self.assertEqual(fit_script.main(), 0)


class BeamSize(unittest.TestCase):
    def result(self, reg=None, current=4e-6):
        ch = ic500_50.Ic500_50(reg=reg)
        return ch.flux(current, 10.0, SITE_P, SITE_T)

    def test_loss_scales_with_aspect_and_not_with_a_uniform_beam_scale(self):
        base = params.default()
        a = self.result(base).detail["recomb_central"]
        b = self.result(base.replaced("beam.width_mm", 2.0)).detail["recomb_central"]
        self.assertAlmostEqual(a / b, 1.0, places=9)                         # same aspect, double the size: loss unchanged
        c = self.result(base.replaced("beam.aspect_central", 0.05)).detail["recomb_central"]
        self.assertAlmostEqual(c / a, 0.5, places=9)                         # half the aspect: half the loss

    def test_range_orders_low_central_high(self):
        d = self.result().detail
        self.assertLess(d["recomb_low"], d["recomb_central"])
        self.assertLess(d["recomb_central"], d["recomb_high"])

    def test_best_carries_the_central_correction_and_bounds_the_range(self):
        chain = tetramm.TetraMM(("c3", "c4"), darks={"c3": 0.0, "c4": 0.0}, dark_age_h=1)
        r = evaluate(ic500_50.Ic500_50(), chain, {"channels": {"c3": 2400.0, "c4": 1600.0}}, 10.0, SITE_P, SITE_T)
        d = r.detail["chamber"]
        self.assertAlmostEqual(r.flux_best, r.flux_formula / (1 - d["recomb_central"]), delta=1e-9 * r.flux_best)
        self.assertLess(r.flux_low, r.flux_best)
        self.assertGreater(r.flux_high, r.flux_best)

    def test_turning_the_correction_off_is_one_registry_row(self):
        off = params.default().replaced("recomb.apply_to_best", False, tag="CHOICE", source="user veto")
        chain = tetramm.TetraMM(("c3", "c4"), darks={"c3": 0.0, "c4": 0.0}, dark_age_h=1)
        r = evaluate(ic500_50.Ic500_50(reg=off), chain, {"channels": {"c3": 2400.0, "c4": 1600.0}}, 10.0, SITE_P, SITE_T)
        self.assertAlmostEqual(r.flux_best, r.flux_formula, delta=1e-9 * r.flux_best)

    def test_a_beam_taller_than_the_gap_is_capped_and_flagged(self):
        reg = params.default().replaced("beam.width_mm", 40.0).replaced("beam.aspect_central", 1.0)
        r = self.result(reg)
        self.assertEqual(r.detail["beam_h_cm"], 1.0)
        self.assertIn("beam_taller_than_30_percent_of_gap_formula_weak", r.flags)

    def test_energy_limits_are_the_live_calcs(self):
        r = ic500_50.Ic500_50().flux(4e-6, 30.001, SITE_P, SITE_T)
        self.assertNotIn("energy_outside_cross_section_range", r.flags)
        self.assertIn("energy_outside_cross_section_range", ic500_50.Ic500_50().flux(4e-6, 30.6, SITE_P, SITE_T).flags)


class Evaluate(unittest.TestCase):
    def setUp(self):
        self.chamber = ic500_50.Ic500_50()
        self.chain = tetramm.TetraMM(("Current3", "Current4"), darks={"Current3": 0.0, "Current4": 0.0}, dark_age_h=1)

    def run_eval(self, a3, a4, e=10.0):
        return evaluate(self.chamber, self.chain, {"channels": {"Current3": a3, "Current4": a4}}, e, SITE_P, SITE_T)

    def test_per_channel_flux_sums_to_best_and_is_flagged(self):
        r = self.run_eval(2400.0, 1600.0)
        self.assertAlmostEqual(sum(r.per_channel.values()) / r.flux_best, 1.0, places=9)
        self.assertIn("per_channel_flux_depends_on_beam_position", r.flags)
        self.assertAlmostEqual(r.per_channel["Current3"] / r.flux_best, 0.6, places=9)

    def test_bounds_bracket_best(self):
        r = self.run_eval(2400.0, 1600.0)
        self.assertTrue(r.flux_low < r.flux_best < r.flux_high)
        self.assertGreater(r.sigma_rel, 0.03)

    def test_dark_gives_a_number_with_a_warning(self):
        r = self.run_eval(0.1, 0.05)
        self.assertIn("current_within_3_sigma_of_zero", r.flags)
        self.assertEqual(r.flux_low, 0.0)
        self.assertGreater(r.flux_high, r.flux_best)

    def test_placeholders_are_visible(self):
        r = self.run_eval(2400.0, 1600.0)
        for f in ("assumed:tetramm.gain_rel", "assumed:beam.aspect_central"):
            self.assertIn(f, r.flags)

    def test_energy_outside_table_is_flagged(self):
        r = self.run_eval(2400.0, 1600.0, e=40.0)
        self.assertIn("energy_outside_cross_section_range", r.flags)


class Spectrum(unittest.TestCase):
    def test_pure_fundamental_equals_the_default(self):
        ch = ic500_50.Ic500_50()
        a = ch.flux(4e-6, 10.0, SITE_P, SITE_T)
        b = ch.flux(4e-6, 10.0, SITE_P, SITE_T, spectrum=[(1.0, 1.0)])
        self.assertAlmostEqual(a.flux_formula / b.flux_formula, 1.0, places=12)

    def test_default_pure_fundamental_raises_no_flag(self):
        # the user's decision (2026-11-14): monochromators monochromate; the row is a CHOICE, not an assumption to flag
        flags = ic500_50.Ic500_50().flux(4e-6, 10.0, SITE_P, SITE_T).flags
        self.assertFalse([f for f in flags if "spectrum" in f])

    def test_two_components_against_the_hand_formula(self):
        ch = ic500_50.Ic500_50()
        e, third = 10.0, 3.0
        f1, f3 = 0.95, 0.05
        rho = k.density_g_cm3(SITE_P, SITE_T)
        a = lambda en: 1 - math.exp(-k.muen_over_rho(en) * rho * ic500_50.L_EFF_CM)
        denom = f1 * e * a(e) + f3 * third * e * a(third * e)
        phi_in = 4e-6 * k.W_EV / (k.E_CHARGE * 1e3 * denom)
        exit_frac = f1 * math.exp(-k.mu_over_rho(e) * rho * 5.0) + f3 * math.exp(-k.mu_over_rho(third * e) * rho * 5.0)
        got = ch.flux(4e-6, e, SITE_P, SITE_T, spectrum=[(1.0, f1), (third, f3)])
        self.assertAlmostEqual(got.flux_formula / (phi_in * exit_frac) - 1, 0, delta=1e-9)
        self.assertAlmostEqual(sum(got.detail["signal_share"]), 1.0, places=12)

    def test_fractions_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            ic500_50.Ic500_50().flux(4e-6, 10.0, SITE_P, SITE_T, spectrum=[(1.0, 0.5), (3.0, 0.2)])

    def test_negative_fractions_are_refused(self):                                  # M4
        with self.assertRaises(ValueError):
            ic500_50.Ic500_50().flux(4e-6, 10.0, SITE_P, SITE_T, spectrum=[(1.0, 1.2), (3.0, -0.2)])


def _ic500_eval(i_a, e=10.0, reg=None, spectrum=None, p=SITE_P, t=SITE_T):
    """TetrAMM channel c, zero dark, current i_a amperes (the registry's unit is nA)."""
    chain = tetramm.TetraMM(("c",), darks={"c": 0.0}, dark_age_h=1)
    return evaluate(ic500_50.Ic500_50(reg=reg), chain, {"channels": {"c": i_a / 1e-9}}, e, p, t, spectrum=spectrum)


def _correction_off():
    return params.default().replaced("recomb.apply_to_best", False, tag="CHOICE", source="test: correction off")


class BoundsBracketBest(unittest.TestCase):
    """I1, I2, T2/T5(a): low <= best <= high over currents, energies, spectra and the correction switch."""

    def test_grid(self):
        sigma_a = tetramm.TetraMM(("c",), darks={"c": 0.0}, dark_age_h=1).current({"channels": {"c": 0.0}}).abs_sigma_a
        currents = [-100e-6, -4e-6, -3 * sigma_a, 0.0, 3 * sigma_a, 4e-6, 100e-6]
        spectra = [None, [(1.0, 0.95), (3.0, 0.05)]]
        for reg in (None, _correction_off()):
            for i_a in currents:
                for sp in spectra:
                    for e in (8.0, 20.0, 30.0):
                        r = _ic500_eval(i_a, e, reg, sp)
                        msg = f"apply_off={reg is not None} I={i_a:g} spectrum={sp} E={e}"
                        self.assertLessEqual(r.flux_low, r.flux_best, msg)
                        self.assertLessEqual(r.flux_best, r.flux_high, msg)

    def test_correction_off_brackets_at_large_current(self):                       # I1
        for i_a in (60e-6, 100e-6):
            r = _ic500_eval(i_a, 10.0, _correction_off())
            self.assertLessEqual(r.flux_low, r.flux_best, f"{i_a}")
            self.assertLessEqual(r.flux_best, r.flux_high, f"{i_a}")

    def test_negative_current_is_flagged_and_bracketed(self):                      # I2
        r = _ic500_eval(-4e-6)
        self.assertIn("negative_current", r.flags)
        self.assertLess(r.flux_best, 0)
        self.assertLessEqual(r.flux_low, r.flux_best)
        self.assertLessEqual(r.flux_best, r.flux_high)
        pos = _ic500_eval(4e-6)
        self.assertNotIn("negative_current", pos.flags)
        self.assertAlmostEqual(r.flux_low, -pos.flux_high, delta=1e-9 * abs(pos.flux_high))     # mirrored: same magnitudes
        self.assertAlmostEqual(r.flux_high, -pos.flux_low, delta=1e-9 * abs(pos.flux_low))

    def test_noise_level_negative_current_is_not_flagged_negative(self):
        sigma_a = tetramm.TetraMM(("c",), darks={"c": 0.0}, dark_age_h=1).current({"channels": {"c": 0.0}}).abs_sigma_a
        r = _ic500_eval(-sigma_a)
        self.assertNotIn("negative_current", r.flags)
        self.assertIn("current_within_3_sigma_of_zero", r.flags)


class RecombinationBounds(unittest.TestCase):
    """T2/T5(b),(c): which recombination term each bound carries, the 0.5 cap and the recombination flags."""

    def parts(self, reg):
        r = _ic500_eval(4e-6, 10.0, reg)
        ch = ic500_50.Ic500_50(reg=reg).flux(4e-6, 10.0, SITE_P, SITE_T)
        return r, ch

    def test_apply_on_low_uses_recomb_low_high_uses_recomb_high(self):
        r, ch = self.parts(None)
        p = r.flux_formula
        self.assertAlmostEqual(r.flux_low, p * (1 - r.sigma_rel) / ((1 - ch.wall_lo) * (1 - ch.recomb_low)), delta=1e-9 * p)
        self.assertAlmostEqual(r.flux_high, p * (1 + r.sigma_rel) / ((1 - ch.wall_hi) * (1 - ch.recomb_high)), delta=1e-9 * p)

    def test_apply_off_high_carries_recomb_high_and_low_does_not(self):
        r, ch = self.parts(_correction_off())
        p = r.flux_formula
        self.assertAlmostEqual(r.flux_best, p / (1 - ch.wall_loss), delta=1e-9 * p)
        self.assertAlmostEqual(r.flux_low, p * (1 - r.sigma_rel) / (1 - ch.wall_lo), delta=1e-9 * p)
        self.assertAlmostEqual(r.flux_high, p * (1 + r.sigma_rel) / ((1 - ch.wall_hi) * (1 - ch.recomb_high)), delta=1e-9 * p)

    def test_recombination_is_capped_at_half_in_the_result_but_not_in_the_detail(self):
        ch = ic500_50.Ic500_50().flux(1e-3, 10.0, SITE_P, SITE_T)               # 1 mA: every aspect ratio is past 0.5
        self.assertEqual(ch.recomb_high, 0.5)
        self.assertEqual(ch.recomb_low, 0.5)
        self.assertEqual(ch.recomb_best, 0.5)
        self.assertGreater(ch.detail["recomb_high"], 0.5)
        self.assertGreater(ch.detail["recomb_central"], 0.5)

    def test_recombination_flags(self):
        ch = ic500_50.Ic500_50()
        quiet = ch.flux(0.1e-6, 10.0, SITE_P, SITE_T).flags
        mid = ch.flux(1e-6, 10.0, SITE_P, SITE_T).flags
        big = ch.flux(100e-6, 10.0, SITE_P, SITE_T).flags
        for f in ("recombination_over_1_percent", "recombination_formula_not_valid"):
            self.assertNotIn(f, quiet)
        self.assertIn("recombination_over_1_percent", mid)
        self.assertNotIn("recombination_formula_not_valid", mid)
        self.assertIn("recombination_over_1_percent", big)
        self.assertIn("recombination_formula_not_valid", big)
        self.assertNotIn("beam_taller_than_30_percent_of_gap_formula_weak", big)    # the default central beam is 0.1 mm tall
        tall = params.default().replaced("beam.width_mm", 40.0).replaced("beam.aspect_central", 1.0)
        self.assertIn("beam_taller_than_30_percent_of_gap_formula_weak", ic500_50.Ic500_50(reg=tall).flux(1e-6, 10.0, SITE_P, SITE_T).flags)

    def test_unordered_aspect_rows_are_flagged(self):                                # M1
        self.assertNotIn("beam_aspect_rows_not_ordered", ic500_50.Ic500_50().flux(1e-6, 10.0, SITE_P, SITE_T).flags)
        bad = params.default().replaced("beam.aspect_low", 0.5)
        self.assertIn("beam_aspect_rows_not_ordered", ic500_50.Ic500_50(reg=bad).flux(1e-6, 10.0, SITE_P, SITE_T).flags)

    def test_a_retagged_apply_row_still_flags(self):                                 # M2
        reg = params.default().replaced("recomb.apply_to_best", True, tag="ASSUMED", source="test", closes_with="a decision")
        self.assertIn("assumed:recomb.apply_to_best", _ic500_eval(4e-6, 10.0, reg).flags)
        self.assertNotIn("assumed:recomb.apply_to_best", _ic500_eval(4e-6, 10.0).flags)


class ChainDefaults(unittest.TestCase):
    """T2/T5(d) and I3: an explicit argument suppresses its assumed: flag; a defaulted one raises it."""

    def flags(self, chain):
        return chain.current({"channels": {"c": 1.0}}).flags

    def test_tetramm_explicit_arguments_suppress_their_flags(self):
        dflt = self.flags(tetramm.TetraMM(("c",)))
        for f in ("assumed:tetramm.gain_rel", "assumed:tetramm.dark_sigma_nA", "assumed:tetramm.unit_a", "assumed:tetramm.range"):
            self.assertIn(f, dflt)
        got = self.flags(tetramm.TetraMM(("c",), rng=0, unit_a=1e-9, dark_sigma_a=1e-9, gain_rel=0.02))
        self.assertFalse([f for f in got if f.startswith("assumed:")])
        self.assertNotIn("assumed:tetramm.gain_rel", self.flags(tetramm.TetraMM(("c",), gain_rel=0.02)))

    def test_default_range_is_flagged_but_an_explicit_range_is_not(self):          # I3
        self.assertIn("assumed:tetramm.range", self.flags(tetramm.TetraMM(("c",))))
        self.assertNotIn("assumed:tetramm.range", self.flags(tetramm.TetraMM(("c",), rng=0)))

    def test_fx4_explicit_arguments_suppress_their_flags(self):
        c = {"channels": {"c": 1e-9}}
        dflt = fx4.Fx4(("c",), 0).current(c).flags
        for f in ("assumed:fx4.gain_rel", "assumed:fx4.dark_sigma_a"):
            self.assertIn(f, dflt)
        got = fx4.Fx4(("c",), 0, dark_sigma_a=1e-9, gain_rel=0.02).current(c).flags
        self.assertFalse([f for f in got if f.startswith("assumed:")])


class AssumedRowsAreRead(unittest.TestCase):
    def test_plate_orientation_flag_only_when_the_wall_loss_is_nonzero(self):         # I4
        ch = ic500_50.Ic500_50()
        self.assertIn("assumed:ic500.plate_orientation", ch.flux(4e-6, 25.0, SITE_P, SITE_T).flags)
        self.assertNotIn("assumed:ic500.plate_orientation", ch.flux(4e-6, 10.0, SITE_P, SITE_T).flags)


class GasStandIn(unittest.TestCase):                                                  # I5
    def test_none_reads_the_flagged_rows_and_equals_the_explicit_values(self):
        ch = ic500_50.Ic500_50()
        a = ch.flux(4e-6, 10.0)
        for f in ("assumed:gas.p_kpa", "assumed:gas.t_c"):
            self.assertIn(f, a.flags)
        reg = params.default()
        b = ch.flux(4e-6, 10.0, reg.param("gas.p_kpa").value, reg.param("gas.t_c").value)
        self.assertEqual(a.flux_formula, b.flux_formula)
        term = [t for t in a.terms if t.name == "gas stand-in P,T"]
        self.assertEqual(len(term), 1)
        p, t = reg.param("gas.p_kpa"), reg.param("gas.t_c")
        self.assertAlmostEqual(term[0].rel, math.hypot(p.sigma / p.value, t.sigma / (t.value + 273.15)), places=12)

    def test_replacing_a_gas_row_removes_its_flag_and_changes_the_flux(self):
        base = ic500_50.Ic500_50().flux(4e-6, 10.0)
        better = params.default().replaced("gas.p_kpa", 95.0, tag="MEASURED", source="gauge", date="2026-12-01")
        r = ic500_50.Ic500_50(reg=better).flux(4e-6, 10.0)
        self.assertNotIn("assumed:gas.p_kpa", r.flags)
        self.assertIn("assumed:gas.t_c", r.flags)
        self.assertNotEqual(r.flux_formula, base.flux_formula)

    def test_explicit_p_and_t_add_no_gas_flag_and_no_term(self):
        r = ic500_50.Ic500_50().flux(4e-6, 10.0, SITE_P, SITE_T)
        self.assertFalse([f for f in r.flags if f.startswith("assumed:gas.")])
        self.assertFalse([t for t in r.terms if "stand-in" in t.name])
        r2 = ic500_50.Ic500_50().flux(4e-6, 10.0, 98.0, None)                         # one given, one stand-in
        self.assertNotIn("assumed:gas.p_kpa", r2.flags)
        self.assertIn("assumed:gas.t_c", r2.flags)

    def test_evaluate_with_none_flags_the_stand_ins(self):
        chain = tetramm.TetraMM(("c",), darks={"c": 0.0}, dark_age_h=1)
        r = evaluate(ic500_50.Ic500_50(), chain, {"channels": {"c": 4000.0}}, 10.0)
        self.assertIn("assumed:gas.p_kpa", r.flags)
        self.assertIn("gas stand-in P,T", [t.name for t in r.budget])


class ExampleScript(unittest.TestCase):                                               # I6
    def test_main_runs_and_prints_flux_and_flags(self):
        import contextlib
        import io
        from fluxor import example
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            example.main()
        out = buf.getvalue()
        self.assertIn("flux", out)
        self.assertIn("flags", out)
        self.assertIn("recombination", out)


class Step6Rerun(unittest.TestCase):
    def test_script_runs_on_the_registry_and_orders_the_bounds(self):
        import csv
        import tempfile
        analysis = str(ROOT / "analysis")
        sys.path.insert(0, analysis)
        self.addCleanup(sys.path.remove, analysis)
        import estation_step6
        out = tempfile.TemporaryDirectory()
        self.addCleanup(out.cleanup)
        estation_step6.main(out_dir=out.name)                      # never writes the committed analysis/out files
        rows = list(csv.DictReader(open(Path(out.name) / "estation_step6.csv", encoding="utf-8")))
        self.assertEqual(len(rows), 7)
        for r in rows:
            self.assertLess(float(r["flux_low"]), float(r["flux_best"]))
            self.assertLess(float(r["flux_best"]), float(r["flux_high"]))
            self.assertLess(float(r["recomb_low"]), float(r["recomb_high"]))
            self.assertIn("assumed:gas.p_kpa", r["flags"])
            self.assertIn("assumed:gas.t_c", r["flags"])
            self.assertIn("assumed:tetramm.range", r["flags"])        # I3: the provisional range is not passed as a literal


if __name__ == "__main__":
    unittest.main()
