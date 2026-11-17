# tests/test_params.py
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fluxor import params  # noqa: E402

SEED = """
["demo.a"]
value = 2.0
sigma = 0.1
unit = "cm"
tag = "ASSUMED"
source = "a guess"
date = "2026-11-14"
closes_with = "a measurement"

["demo.b"]
value = 5
unit = "mm"
tag = "GIVEN"
source = "the user"
date = "2026-11-14"
"""


class RegistryTests(unittest.TestCase):
    def setUp(self):
        p = Path(self.id().replace(".", "_") + ".toml")
        p.write_text(SEED, encoding="utf-8")
        self.addCleanup(p.unlink)
        self.reg = params.Registry.load(p)

    def test_value_and_param(self):
        self.assertEqual(self.reg.value("demo.a"), 2.0)
        self.assertEqual(self.reg.param("demo.a").sigma, 0.1)
        self.assertEqual(self.reg.param("demo.b").tag, "GIVEN")

    def test_only_used_flagged_tags_raise_flags(self):
        self.assertEqual(self.reg.flags(), [])
        self.reg.value("demo.b")
        self.assertEqual(self.reg.flags(), [])                   # GIVEN: no flag
        self.reg.value("demo.a")
        self.assertEqual(self.reg.flags(), ["assumed:demo.a"])   # ASSUMED: flag
        self.reg.reset_use()
        self.assertEqual(self.reg.flags(), [])

    def test_replacing_a_number_removes_its_flag(self):
        better = self.reg.replaced("demo.a", 2.3, tag="MEASURED", source="caliper", date="2026-12-01")
        self.assertEqual(better.value("demo.a"), 2.3)
        self.assertEqual(better.flags(), [])
        self.assertEqual(self.reg.value("demo.a"), 2.0)           # the original is untouched

    def test_missing_fields_and_bad_tags_are_refused(self):
        bad = Path("bad_registry.toml")
        bad.write_text('["x"]\nvalue = 1\nunit = "mm"\ntag = "HOPE"\nsource = "s"\ndate = "d"\n', encoding="utf-8")
        self.addCleanup(bad.unlink)
        with self.assertRaises(ValueError):
            params.Registry.load(bad)
        bad.write_text('["x"]\nvalue = 1\ntag = "GIVEN"\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            params.Registry.load(bad)

    def test_bad_lookup_does_not_poison_flags(self):
        with self.assertRaises(KeyError):
            self.reg.value("nope")
        self.assertEqual(self.reg.flags(), [])                   # must not raise
        self.reg.value("demo.a")
        self.assertEqual(self.reg.flags(), ["assumed:demo.a"])

    def test_assumed_rows_say_how_they_close(self):
        bad = Path("bad_registry2.toml")
        bad.write_text('["x"]\nvalue = 1\nunit = "mm"\ntag = "ASSUMED"\nsource = "s"\ndate = "d"\n', encoding="utf-8")
        self.addCleanup(bad.unlink)
        with self.assertRaises(ValueError):
            params.Registry.load(bad)                            # ASSUMED without closes_with


class ReplacedValidationTests(unittest.TestCase):                    # T1
    def setUp(self):
        p = Path(self.id().replace(".", "_") + ".toml")
        p.write_text(SEED, encoding="utf-8")
        self.addCleanup(p.unlink)
        self.reg = params.Registry.load(p)

    def test_a_typoed_tag_is_refused(self):
        with self.assertRaises(ValueError):
            self.reg.replaced("demo.a", 2.3, tag="MEASURD")

    def test_an_assumed_row_without_closes_with_is_refused(self):
        with self.assertRaises(ValueError):
            self.reg.replaced("demo.b", 6, tag="ASSUMED")             # demo.b has no closes_with to carry over
        ok = self.reg.replaced("demo.b", 6, tag="ASSUMED", closes_with="a caliper")
        self.assertEqual(ok.flags(), [])
        ok.value("demo.b")
        self.assertEqual(ok.flags(), ["assumed:demo.b"])

    def test_sigma_is_carried_through_and_can_be_replaced(self):
        self.assertEqual(self.reg.replaced("demo.a", 2.3).param("demo.a").sigma, 0.1)
        self.assertEqual(self.reg.replaced("demo.a", 2.3, sigma=0.02).param("demo.a").sigma, 0.02)


class DefaultRegistryTests(unittest.TestCase):
    def test_every_assumed_or_provisional_row_has_a_code_reader(self):
        """An ASSUMED/PROVISIONAL row nobody reads never raises its flag, so its assumption is invisible."""
        reg = params.default()
        sources = [p for d in ("fluxor", "analysis") for p in (ROOT / d).rglob("*.py")]
        text = "\n".join(p.read_text(encoding="utf-8") for p in sources)
        for name in reg.names():
            if reg.param(name).tag in params.FLAGGED_TAGS:
                self.assertTrue(f'"{name}"' in text or f"'{name}'" in text, f"{name} is never read by code")

    def test_every_row_is_complete_and_flagged_rows_say_how_they_close(self):
        reg = params.default()           # load() already refuses incomplete rows; this guards the default file
        self.assertGreater(len(reg.names()), 20)
        for name in reg.names():
            p = reg.param(name)
            self.assertIn(p.tag, params.TAGS, name)
            if p.tag in params.FLAGGED_TAGS:
                self.assertTrue(p.closes_with, name)

    def test_ic500_flags_come_from_the_registry(self):
        from fluxor.chambers.ic500_50 import Ic500_50
        r = Ic500_50().flux(4e-6, 10.0, 98.99, 22.2)
        for f in ("assumed:beam.aspect_central", "assumed:beam.width_mm"):
            self.assertIn(f, r.flags)
        # the collection length is a GIVEN row since 2026-11-16 (user: 50 mm, vendor figure): no assumed flag
        self.assertNotIn("assumed:ic500.l_eff_cm", r.flags)

    def test_improving_a_number_removes_its_flag_and_changes_the_result(self):
        from fluxor.chambers.ic500_50 import Ic500_50
        base = Ic500_50().flux(4e-6, 10.0, 98.99, 22.2)
        better = params.default().replaced("beam.aspect_central", 0.05, tag="MEASURED", source="screen image", date="2026-12-01")
        r = Ic500_50(reg=better).flux(4e-6, 10.0, 98.99, 22.2)
        self.assertIn("assumed:beam.aspect_central", base.flags)
        self.assertNotIn("assumed:beam.aspect_central", r.flags)
        self.assertNotEqual(r.detail["recomb_central"], base.detail["recomb_central"])

    def test_collection_length_follows_its_registry_row(self):
        from fluxor.chambers.ic500_50 import Ic500_50
        base = Ic500_50().flux(4e-6, 10.0, 98.99, 22.2)
        longer = params.default().replaced("ic500.l_eff_cm", 5.2, tag="MEASURED", source="fringe-field run", date="2026-12-01")
        self.assertNotEqual(Ic500_50(reg=longer).flux(4e-6, 10.0, 98.99, 22.2).flux_formula, base.flux_formula)


class ParametersMdTests(unittest.TestCase):
    def test_generated_file_is_current(self):
        from fluxor import make_parameters_md
        text = (ROOT / "fluxor" / "PARAMETERS.md").read_text(encoding="utf-8")
        self.assertEqual(text, make_parameters_md.render(params.default()))

    def test_render_lists_flagged_rows_first_with_how_to_close(self):
        from fluxor import make_parameters_md
        reg = params.default()
        out = make_parameters_md.render(reg)
        self.assertLess(out.index("\n## ASSUMED\n"), out.index("\n## PROVISIONAL\n"))
        self.assertLess(out.index("\n## PROVISIONAL\n"), out.index("\n## GIVEN\n"))
        if "\n## CHOICE\n" in out:
            self.assertLess(out.index("\n## ASSUMED\n"), out.index("\n## CHOICE\n"))
        assumed = [n for n in reg.names() if reg.param(n).tag == "ASSUMED"]
        self.assertTrue(assumed)
        self.assertIn(reg.param(assumed[0]).closes_with, out)


if __name__ == "__main__":
    unittest.main()
