"""Tests for the E-station lane definition and the calc evaluator (offline; no EPICS).

Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 -m unittest discover -s tests -t .
"""
import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "calc"))

import calc_eval as ce  # noqa: E402
import estation_lane as el  # noqa: E402
import monp_transform as mt  # noqa: E402
import quality_slots as qs  # noqa: E402

NOMINAL = dict(current3_nA=600.0, current4_nA=400.0, energy_keV=10.0, temp_F=72.0, pressure_kPa=98.99)
PLACEHOLDER_CFG = {k: "SOURCE:" + k.upper() for k in el.PV_KEYS}


def lane(**kw):
    return el.evaluate_lane({**NOMINAL, **kw})


class Evaluator(unittest.TestCase):
    def test_arithmetic_and_numbers(self):
        self.assertAlmostEqual(ce.evaluate("1E-9*2+.5", {}), 0.5 + 2e-9)
        self.assertEqual(ce.evaluate("2.17205E17", {}), 2.17205e17)
        self.assertEqual(ce.evaluate("A+B*C", dict(A=1, B=2, C=3)), 7)
        self.assertEqual(ce.evaluate("(A+B)*C", dict(A=1, B=2, C=3)), 9)
        self.assertEqual(ce.evaluate("2^3", {}), 8)
        self.assertEqual(ce.evaluate("2**3", {}), 8)
        self.assertEqual(ce.evaluate("10%3", {}), 1)

    def test_unary_minus_binds_tighter_than_power(self):
        self.assertEqual(ce.evaluate("-2^2", {}), 4.0)            # (-2)^2, not -(2^2)
        self.assertEqual(ce.evaluate("0-2^2", {}), -4.0)
        self.assertTrue(math.isnan(ce.evaluate("-(2)^1.5", {})))  # (-2)^1.5: NaN
        # the repo's known trap (calc/HANDOFF.md): EXP(-(x)^p) is NaN, 1/EXP(x^p) is the right form
        self.assertTrue(math.isnan(ce.evaluate("EXP(-(A)^1.22)", dict(A=3.0))))
        self.assertTrue(math.isfinite(ce.evaluate("1/EXP(A^1.22)", dict(A=3.0))))
        self.assertAlmostEqual(ce.evaluate("1/EXP(A^1.22)", dict(A=3.0)), math.exp(-3.0 ** 1.22))

    def test_comparisons_logic_ternary(self):
        self.assertEqual(ce.evaluate("A>1", dict(A=2)), 1.0)
        self.assertEqual(ce.evaluate("A>=2&&B<1", dict(A=2, B=0)), 1.0)
        self.assertEqual(ce.evaluate("A<0||A>5", dict(A=3)), 0.0)
        self.assertEqual(ce.evaluate("A>0?10:20", dict(A=1)), 10.0)
        self.assertEqual(ce.evaluate("A>0?10:B>0?20:30", dict(A=0, B=1)), 20.0)
        self.assertEqual(ce.evaluate("0.05*(A>13)", dict(A=14)), 0.05)

    def test_functions_and_c_double_semantics(self):
        self.assertAlmostEqual(ce.evaluate("EXP(LN(5))", {}), 5.0)
        self.assertEqual(ce.evaluate("MAX(A,B,0)", dict(A=-1, B=-2)), 0.0)
        self.assertEqual(ce.evaluate("MIN(.09,2*A)", dict(A=0.01)), 0.02)
        self.assertEqual(ce.evaluate("ABS(A)", dict(A=-3)), 3.0)
        self.assertEqual(ce.evaluate("FLOOR(A)", dict(A=-0.5)), -1.0)
        self.assertEqual(ce.evaluate("1/A", dict(A=0)), math.inf)
        self.assertTrue(math.isnan(ce.evaluate("A/B", dict(A=0, B=0))))
        self.assertEqual(ce.evaluate("LN(A)", dict(A=0)), -math.inf)
        self.assertEqual(ce.evaluate("EXP(A)", dict(A=1e4)), math.inf)

    def test_max_min_propagate_nan_and_zero_to_negative_power(self):
        nan = float("nan")
        self.assertTrue(math.isnan(ce.evaluate("MAX(A,0)", dict(A=nan))))
        self.assertTrue(math.isnan(ce.evaluate("MAX(0,A)", dict(A=nan))))
        self.assertTrue(math.isnan(ce.evaluate("MIN(A,.5)", dict(A=nan))))
        self.assertTrue(math.isnan(ce.evaluate("MIN(.5,A)", dict(A=nan))))
        self.assertEqual(ce.evaluate("0^-1", {}), math.inf)

    def test_syntax_errors(self):
        for bad in ("A+", "(A", "FOO(A)", "A $ B", "MAX()", "A B"):
            with self.assertRaises(ValueError, msg=bad):
                ce.evaluate(bad, dict(A=1, B=2))

    def test_transform_letter_order_and_state(self):
        # a letter used before it is computed holds its previous value; H+1 counts scans
        expr = {"CLCA": "B+1", "CLCB": "5", "CLCH": "H+1"}
        s1 = ce.eval_transform(expr, {}, {})
        self.assertEqual((s1["A"], s1["B"], s1["H"]), (1.0, 5.0, 1.0))          # A used the old B (0)
        s2 = ce.eval_transform(expr, {}, s1)
        self.assertEqual((s2["A"], s2["H"]), (6.0, 2.0))                        # now the previous B
        s3 = ce.eval_transform(expr, {"H": 0}, s2)                              # an input overrides the state
        self.assertEqual(s3["H"], 1.0)

    def test_reproduces_monp_flux_slot(self):
        for args in (dict(A=2.0e5, B=1.0, C=8, D=1, E=10.0, F=24.9, G=99.26, H=50.0),
                     dict(A=5.0e4, B=2.0, C=0, D=2, E=30.0, F=20.0, G=101.3, H=0.0),
                     dict(A=3.0e3, B=1.0, C=5, D=1, E=5.0, F=22.0, G=97.0, H=100.0)):
            ref = mt.evaluate(**args)
            got = ce.eval_transform(mt.SLOT["expr"], args)
            for x in "IJKLMNOP":
                self.assertAlmostEqual(got[x] / ref[x], 1.0, places=12, msg=f"{x} {args}")

    def test_reproduces_monp_bounds_slot(self):
        for p, e, rho in ((3.66e12, 10, qs.RHO0), (3.66e12, 20, 1.05e-3), (1e12, 30, 1.2e-3), (5e11, 14, qs.RHO0)):
            ref = qs.bounds(p, e, rho)
            got = ce.eval_transform(qs.BOUNDS["expr"], dict(A=p, B=e, I=rho, H=0))
            for x in "BCDEFGL":
                self.assertAlmostEqual(got[x], ref[x], delta=1e-12 * max(1.0, abs(ref[x])), msg=f"{x} E={e}")
        self.assertEqual(ce.eval_transform(qs.BOUNDS["expr"], dict(A=1, B=10, I=qs.RHO0), dict(H=41))["H"], 42.0)

    def test_reproduces_monp_flags_slot(self):
        expr = {f"CLC{k}": e for _, k, e, _ in qs.FLAG_BITS}
        expr["CLCL"] = qs.FLAGS_CODE
        cases = [(10, 1, 0, 100, 0, 10), (30, 1, 0, 100, 0, 10), (30, 1, 1, 8000, 0, 10), (30, 1, 0, 100, 60, 10),
                 (31, 1, 0, 100, 0, 10), (10, 0, 0, 100, 0, 10), (4, 0, 1, 9000, 60, 10), (12.5, 1, 0, 7200, 10, 10)]
        for E, ct, stale, age, nob, settle in cases:
            ref = qs.flags(E, ct, stale, age, nob, settle)
            got = ce.eval_transform(expr, dict(A=E, B=ct, C=stale, D=age, E=nob, P=settle))
            self.assertEqual(got["L"], ref["L"], msg=str((E, ct, stale, age, nob, settle)))
            for k in "FGHIJK":
                self.assertEqual(got[k], ref[k])


class LaneDefinition(unittest.TestCase):
    def test_all_strings_within_39_characters(self):
        self.assertEqual(el.check_lengths(PLACEHOLDER_CFG), [])
        for role, expr in el.EXPR.items():
            for x, s in expr.items():
                self.assertLessEqual(len(s), 39, f"{role}.{x}: {s}")
        for r, desc, *_ in el.build(PLACEHOLDER_CFG):
            self.assertTrue(desc.endswith("(xray_fluxor)") and len(desc) <= 39, desc)

    def test_real_link_lengths_when_the_local_file_exists(self):
        if not el.PV_LOCAL.exists():
            self.skipTest("no local PV config")
        self.assertEqual(el.check_lengths(), [])

    def test_slots_and_install_order(self):
        b = el.build(PLACEHOLDER_CFG)
        self.assertEqual([x[0] for x in b], ["15IDC:util:userTran11", "15IDC:util:userCalcOut9",
                                             "15IDC:util:userTran9", "15IDC:util:userTran10"])
        self.assertEqual([x[4] for x in b], ["transform", "calcout", "transform", "transform"])
        for n in (3, 6, 7, 8):
            self.assertNotIn(f"userCalcOut{n}", " ".join(x[0] for x in b))
        for r, desc, fields, hv, kind in b:
            if kind == "transform":
                self.assertEqual(fields["SCAN"], "1 second")
        status = b[1][2]
        self.assertEqual((status["CALC"], status["HIGH"], status["HSV"], status["HIHI"], status["HHSV"]),
                         ("A", 0.5, "MINOR", 15.5, "MAJOR"))
        self.assertEqual(status["INPA"], "15IDC:util:userTran11.L NPP NMS")

    def test_tetramm_links_are_separate_and_inputs_read_only(self):
        flux = el.build(PLACEHOLDER_CFG)[2][2]
        self.assertNotIn("INPA", {k for k, v in flux.items() if v and k.startswith("INP")})
        self.assertEqual(flux["INPA"], "")
        links = el.input_links(PLACEHOLDER_CFG)
        self.assertEqual(set(links), {"INPA", "INPB"})
        for b in el.build(PLACEHOLDER_CFG):
            for k, v in b[2].items():
                if k.startswith("INP") and v:
                    self.assertTrue(v.endswith(("NPP NMS", "NPP MS")) or ":" in v and " " not in v, (k, v))
        self.assertEqual(flux["INPE"], "15IDC:util:userTran1.G NPP NMS")

    def test_missing_local_file_names_the_template(self):
        with self.assertRaises(FileNotFoundError) as cm:
            el.load_pvs(ROOT / "calc" / "no_such_file.local.json")
        self.assertIn("estation_pvs.template.json", str(cm.exception))

    def test_letter_order_rule(self):
        self.assertEqual(el.check_letter_order(), [])
        # and the checker does catch a violation
        saved = dict(el.EXPR["bounds"])
        try:
            el.EXPR["bounds"]["C"] = "B>17.7?M:0"                # M is computed later
            self.assertTrue(any(p[1] == "C" for p in el.check_letter_order()))
        finally:
            el.EXPR["bounds"].clear()
            el.EXPR["bounds"].update(saved)

    def test_constants_come_from_the_registry(self):
        c = el.LANE["constants"]
        self.assertEqual(c["l_eff_cm"], 5.0)
        self.assertIn("EXP(-5*K*I)", el.EXPR["flux"]["M"])
        self.assertEqual(el.EXPR["flux"]["P"], "G*2.17205E17/C/M*EXP(-5*L*I)")
        self.assertEqual(el.EXPR["bounds"]["C"], "B>17.7?1-1/EXP(((B-17.7)/25.9)^1.36):0")
        self.assertEqual((c["LOW_FACTOR"], c["HIGH_FACTOR"]), (0.954, 1.046))
        self.assertEqual(el.EXPR["flags"]["I"], "D<5E-8")
        self.assertEqual(el.EXPR["flux"]["O"], "A+B>=-5&&A<118800&&B<118800?0:1")
        self.assertEqual(el.EXPR["flags"]["J"], "A>=4.9&&A<=30.5?0:1")
        self.assertEqual(el.EXPR["flags"]["G"], "E>.05")

    def test_every_expression_is_finite_on_a_grid(self):
        for ua in (0.0, 0.0005, 0.5, 3, 4, 100, 120):
            for e in (5, 8, 12.5, 13, 20, 30, 30.5):
                r = lane(current3_nA=ua * 600, current4_nA=ua * 400, energy_keV=e)
                for role in ("flux", "bounds", "flags"):
                    for x, v in r[role].items():
                        self.assertTrue(math.isfinite(v), f"{role}.{x} at {ua} uA {e} keV")


class FlagBits(unittest.TestCase):
    def bits(self, **kw):
        fl = lane(**kw)["flags"]
        return {b: fl[k] for b, k, _ in el.FLAG_BITS}, fl["L"]

    def test_clean_case_is_code_zero(self):
        bits, code = self.bits()
        self.assertEqual(code, 0.0)
        self.assertEqual(lane()["severity"], "NO_ALARM")

    def test_bit1_energy_above_12_5(self):
        self.assertEqual(self.bits(energy_keV=12.5)[0][1], 0.0)
        self.assertEqual(self.bits(energy_keV=12.51)[0][1], 1.0)

    def test_bit2_recombination_above_threshold(self):
        k = el.G["k_per_a"][1]                                  # central loss per ampere
        i_na = el.RECOMB_FLAG_FRACTION / k * 1e9                # current (nA) at exactly the threshold
        self.assertEqual(self.bits(current3_nA=0.99 * i_na, current4_nA=0.0)[0][2], 0.0)
        self.assertEqual(self.bits(current3_nA=1.01 * i_na, current4_nA=0.0)[0][2], 1.0)
        # ordinary E-station currents (up to about 4 uA) do not set it
        self.assertEqual(self.bits(current3_nA=2400.0, current4_nA=1600.0)[0][2], 0.0)

    def test_bit4_pressure_age(self):
        self.assertEqual(self.bits(p_age_s=7200)[0][4], 0.0)
        self.assertEqual(self.bits(p_age_s=7201)[0][4], 1.0)

    def test_bit8_low_current(self):
        t = el.LOW_CURRENT_NA
        for i in (0.0, 4.2, 5.0, 10.0, t - 1):
            self.assertEqual(self.bits(current3_nA=i, current4_nA=0.0)[0][8], 1.0, i)
        for i in (t + 1, 100.0):
            self.assertEqual(self.bits(current3_nA=i, current4_nA=0.0)[0][8], 0.0, i)
        # the dark is subtracted first
        self.assertEqual(self.bits(current3_nA=t + 10, current4_nA=0.0, dark_nA=20.0)[0][8], 1.0)

    def test_low_current_region_is_finite_and_flagged(self):
        for i in (5.0, 10.0, 49.0):
            r = lane(current3_nA=i, current4_nA=0.0)
            self.assertEqual(r["flags"]["I"], 1.0)
            for x in "KLM":
                self.assertTrue(math.isfinite(r["bounds"][x]), (i, x))

    def test_just_above_low_current_agrees_with_fluxor(self):
        for i_na in (el.LOW_CURRENT_NA + 1, 100.0):
            for e in (8.0, 10.0, 20.0):
                ref = el.fluxor_reference(i_na / 1e3, e, 98.99, 22.2, split=1.0)
                r = el.evaluate_lane(dict(current3_nA=i_na, current4_nA=0.0, energy_keV=e, temp_F=22.2 * 1.8 + 32, pressure_kPa=98.99))
                self.assertAlmostEqual(r["bounds"]["K"] / ref.flux_low, 1.0, delta=0.02, msg=("low", i_na, e))
                self.assertAlmostEqual(r["bounds"]["M"] / ref.flux_high, 1.0, delta=0.02, msg=("high", i_na, e))
                self.assertAlmostEqual(r["bounds"]["L"] / ref.flux_best, 1.0, delta=0.02, msg=("best", i_na, e))

    def test_bit16_energy_range_major(self):
        self.assertEqual(self.bits(energy_keV=4.9)[0][16], 0.0)
        self.assertEqual(self.bits(energy_keV=4.89)[0][16], 1.0)
        self.assertEqual(self.bits(energy_keV=30.5)[0][16], 0.0)
        self.assertEqual(self.bits(energy_keV=30.6)[0][16], 1.0)
        self.assertEqual(lane(energy_keV=31.0)["severity"], "MAJOR")

    def test_bit32_raw_current_negative_or_full_scale_major(self):
        fs = el.FULL_SCALE_FRACTION * 120000.0
        m = el.RAW_NEG_MARGIN_NA
        self.assertEqual(self.bits(current3_nA=fs - 1, current4_nA=0.0)[0][32], 0.0)
        self.assertEqual(self.bits(current3_nA=fs, current4_nA=0.0)[0][32], 1.0)
        self.assertEqual(self.bits(current3_nA=0.0, current4_nA=fs + 1)[0][32], 1.0)
        # noise below zero does not flicker MAJOR; a raw sum below -margin does
        self.assertEqual(self.bits(current3_nA=-0.1, current4_nA=0.0)[0][32], 0.0)
        self.assertEqual(self.bits(current3_nA=-(m - 0.1), current4_nA=0.0)[0][32], 0.0)
        self.assertEqual(self.bits(current3_nA=-(m + 0.1), current4_nA=0.0)[0][32], 1.0)
        self.assertEqual(self.bits(current3_nA=-(m + 2.0), current4_nA=3.0)[0][32], 0.0)      # the SUM is tested
        self.assertEqual(lane(current3_nA=-50.0, current4_nA=0.0)["severity"], "MAJOR")

    def test_nan_inputs_are_major(self):
        nan = float("nan")
        for kw in (dict(energy_keV=nan), dict(current3_nA=nan), dict(current4_nA=nan)):
            r = lane(**kw)
            self.assertEqual(r["severity"], "MAJOR", kw)

    def test_code_is_the_sum_and_severity_follows(self):
        bits, code = self.bits(energy_keV=13.0, p_age_s=9000)
        self.assertEqual(code, 5.0)
        self.assertEqual(lane(energy_keV=13.0, p_age_s=9000)["severity"], "MINOR")
        self.assertEqual(self.bits(energy_keV=40.0, current3_nA=-(el.RAW_NEG_MARGIN_NA + 1), current4_nA=0.0)[1], 1 + 8 + 16 + 32)   # E>12.5, low current, range, raw


class ZeroAndNegativeCurrent(unittest.TestCase):
    def test_result_finite_nonnegative_and_ordered(self):
        for e in (8, 10, 20, 30):
            for i3, i4 in ((0.0, 0.0), (-3.0, 0.0), (-50.0, -20.0), (0.5, 0.2), (2.0, 1.0), (4.2, 0.0), (1500.0, 1500.0)):
                b = lane(current3_nA=i3, current4_nA=i4, energy_keV=e)["bounds"]
                for x in "KLM":
                    self.assertTrue(math.isfinite(b[x]) and b[x] >= 0, (e, i3, i4, x, b[x]))
                self.assertLessEqual(b["K"], b["L"] + 1e-9 * abs(b["L"]))
                self.assertLessEqual(b["L"], b["M"] + 1e-9 * abs(b["M"]))
                self.assertTrue(math.isfinite(b["N"]) and math.isfinite(b["O"]))

    def test_zero_current_gives_zero_flux_and_flags_noise(self):
        r = lane(current3_nA=0.0, current4_nA=0.0)
        self.assertEqual(r["flux"]["P"], 0.0)
        self.assertEqual(r["bounds"]["L"], 0.0)
        self.assertEqual(r["flags"]["I"], 1.0)

    def test_energy_zero_still_flags_major(self):
        r = lane(energy_keV=0.0)           # a disconnected mono: values may be garbage, the flag must still say so
        self.assertEqual(r["severity"], "MAJOR")


class AgainstFluxor(unittest.TestCase):
    def test_mirror_matches_fluxor_core_evaluate(self):
        w = el.compare_with_fluxor()
        self.assertLess(w["formula_5_20"], 0.01)
        self.assertLess(w["formula_30"], 0.02)
        for k in ("best", "low", "high"):
            self.assertLess(w[k], 0.02, k)

    def test_self_test_passes(self):
        self.assertEqual(el.main(), 0)


class Privacy(unittest.TestCase):
    """The real E-station source PV names live only in the gitignored local file."""
    # built from pieces so this file does not contain them itself
    BANNED = ["15ID" + "1", "15ID" + "Gen", "BL15ID" + "-Metasys", "sbm" + "E"]
    FILES = ["calc/calc_eval.py", "calc/estation_lane.py", "calc/estation_pvs.template.json", "tests/test_estation_lane.py",
             "calc/HANDOFF.md", "calc/OPERATOR.md"]

    def test_new_and_edited_tracked_files_carry_none_of_the_names(self):
        words = list(self.BANNED)
        if el.PV_LOCAL.exists():
            words += [v for k, v in el.load_pvs().items() if not k.startswith("_")]
        for f in self.FILES:
            text = (ROOT / f).read_text(encoding="utf-8")
            for w in words:
                self.assertNotIn(w, text, f"{f} contains {w[:4]}...")

    def test_local_config_is_ignored_and_the_template_is_tracked_content(self):
        try:
            r = subprocess.run(["git", "check-ignore", "-q", "calc/estation_pvs.local.json"], cwd=ROOT)
        except FileNotFoundError:
            self.skipTest("git not available")
        self.assertEqual(r.returncode, 0, "calc/estation_pvs.local.json must be gitignored")
        self.assertTrue((ROOT / "calc" / "estation_pvs.template.json").exists())


if __name__ == "__main__":
    unittest.main()
