"""Offline tests of the E-station lane installer (calc/install_lane.py --lane EStn): --dry-run, install, --compare, --remove.

No EPICS and no network: a fake `epics` module is injected into sys.modules BEFORE the installer is imported. Behind it is a
small in-memory IOC: four target records (userTran9/10/11, userCalcOut9) that start from the REAL free-slot defaults read from the
live IOC on 2026-11-16, whose slot strings are evaluated with calc/calc_eval.py, a table of external PVs (TetrAMM, mono, hutch
temperature, the MonP pressure), and a log of every put. The tests assert on the exact put sequence, on the refusal of an occupied
slot, on the "TetrAMM down" warning path, on the END STATE of every failure path, and that nothing outside the four target
records is ever written.

Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 -m unittest discover -s tests -t .
"""
import contextlib
import importlib
import io
import json
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "calc"))

import calc_eval as ce  # noqa: E402
import estation_lane as el  # noqa: E402

LETTERS = "ABCDEFGHIJKLMNOP"
PLACEHOLDER_CFG = {"current3": "SRC:TETRAMM:CHANNEL3:MEAN_CURRENT_NA",       # 36 characters: written bare
                   "current4": "SRC:TETRAMM:CHANNEL4:MEAN_CURRENT_NA",
                   "energy": "SRC:MONO:ENERGY_KEV",
                   "hutch_temp_f": "SRC:HUTCH:AIR_TEMPERATURE_DEGF_MEAN"}     # long enough to be written bare too
HEARTBEAT = "15IDC:util:HEARTBEAT"
OTHER = {"pressure": "15IDC:util:userTran1.G", "age": "15IDC:util:userTran3.H"}
NUMERIC_TRANSFORM = set(LETTERS)
NUMERIC_CALCOUT = set("ABCDEFGHIJKL") | {"VAL", "HIGH", "HIHI", "HYST"}
TEST_CURRENTS = (2400.0, 1600.0)


def canon(s):
    """How the IOC reads a link back: a bare PV gets the default modifiers, cut at the 39-character limit."""
    return (s + " NPP NMS")[:39] if s and len(s.split()) == 1 else s


def default_record(r):
    """A FREE slot exactly as read from the live IOC (2026-11-16). Transforms: CMTA-P are the lower-case letters a-p, PREC 3,
    COPT Conditional. Calcouts: DESC is the bare record name, PREC 5."""
    if "userCalcOut" in r:
        f = {"DESC": r[len("15IDC:util:"):], "SCAN": "Passive", "SEVR": "NO_ALARM", "EGU": "", "PREC": "5", "CALC": "0", "VAL": 0.0,
             "HIGH": 0.0, "HIHI": 0.0, "HYST": 0.0, "HSV": "NO_ALARM", "HHSV": "NO_ALARM", "OOPT": "Every Time",
             "DOPT": "Use CALC", "OCAL": "0", "OUT": ""}
        f.update({f"INP{x}": "" for x in "ABCDEFGHIJKL"})
        f.update({x: 0.0 for x in "ABCDEFGHIJKL"})
        return f
    n = r.rsplit("userTran", 1)[1]
    f = {"DESC": f"user Transform {n}", "SCAN": "Passive", "SEVR": "NO_ALARM", "EGU": "", "PREC": "3", "COPT": "Conditional"}
    f.update({f"INP{x}": "" for x in LETTERS})
    f.update({f"CLC{x}": "" for x in LETTERS})
    f.update({f"OUT{x}": "" for x in LETTERS})
    f.update({f"CMT{x}": x.lower() for x in LETTERS})
    f.update({x: 0.0 for x in LETTERS})
    return f


class FakeIOC:
    """Dict-backed stand-in for the four target records plus the PVs they read. Records are evaluated lazily, on the first
    get after a put, to a fixed point (the real IOC would have scanned a few times by then). Hooks for the tests:
    fail_when(pv, value) -> None | 'fail' (caput returns 0) | 'raise'; corrupt {pv: stored string}; ioc_hidden (PVs this PC
    can read but the IOC cannot); wrong_clc {(record, field): expression the IOC really evaluates}."""

    def __init__(self, cfg=PLACEHOLDER_CFG, tetramm_up=True):
        self.cfg = cfg
        self.targets = [el.rec(r) for r in ("flags", "status", "flux", "bounds")]
        self.order = [el.rec(r) for r in ("flux", "bounds", "flags", "status")]
        self.rec, self.enable, self.puts, self.dirty = {}, {}, [], True
        self.before_put = self.fail_when = None
        self.wrong_clc, self.corrupt, self.ioc_hidden = {}, {}, set()
        for r in self.targets:
            self.rec[r] = default_record(r)
            self.enable[r] = 1.0                 # a free slot reads Enable 1
        self.ext = {HEARTBEAT: 1.0, cfg["energy"]: 10.0, cfg["hutch_temp_f"]: 72.0, OTHER["pressure"]: 98.99, OTHER["age"]: 100.0}
        if tetramm_up:
            self.ext.update({cfg["current3"]: 600.0, cfg["current4"]: 400.0})

    # --- the epics API -------------------------------------------------------------------------------------------
    def _where(self, pv):
        for r in self.rec:
            if pv == r + "Enable":
                return r, "Enable"
            if pv.startswith(r + "."):
                return r, pv[len(r) + 1:]
        return None, None

    def _numeric(self, r, field):
        return field in (NUMERIC_CALCOUT if "userCalcOut" in r else NUMERIC_TRANSFORM)

    def caget(self, pv, as_string=False, timeout=None):
        r, field = self._where(pv)
        if r is None:
            return self.ext.get(pv)
        if self.dirty:
            self.settle()
        if field == "Enable":
            return self.enable[r]
        v = self.rec[r].get(field)
        if v is None:
            return None
        if field == "SEVR":
            return v if as_string else ["NO_ALARM", "MINOR", "MAJOR", "INVALID"].index(v)
        if as_string:
            return canon(v) if field.startswith("INP") else (f"{v:g}" if isinstance(v, float) else str(v))
        return v

    def caput(self, pv, value, wait=False, timeout=None):
        if self.before_put:
            self.before_put(pv, value)
        self.puts.append((pv, value))
        mode = self.fail_when(pv, value) if self.fail_when else None
        if mode == "raise":
            raise OSError(f"injected failure on {pv}")
        if mode == "fail":
            return 0
        r, field = self._where(pv)
        if r is None:
            self.ext[pv] = value                     # a write outside the four records: logged, and the tests forbid it
            return 1
        if field == "Enable":
            self.enable[r] = float(value)
        else:
            value = self.corrupt.get(pv, value) if value != "" else value
            self.rec[r][field] = float(value) if self._numeric(r, field) else str(value)
        self.dirty = True
        return 1

    # --- the records ---------------------------------------------------------------------------------------------
    def _read(self, src):
        if src in self.ioc_hidden:
            return None
        r, field = self._where(src)
        if r is not None and field != "Enable":
            return self.rec[r].get(field)
        return self.ext.get(src)

    def settle(self):
        for _ in range(8):
            changed = False
            for r in self.order:
                changed |= self._scan(r)
            if not changed:
                break
        self.dirty = False

    def _scan(self, r):
        if self.enable[r] != 1.0:
            return False
        f = self.rec[r]
        calc = "userCalcOut" in r
        inputs, invalid = {}, False
        for x in ("ABCDEFGHIJKL" if calc else LETTERS):
            link = f[f"INP{x}"].strip()
            if link:
                v = self._read(link.split()[0])
                if v is None:
                    invalid = True
                else:
                    inputs[x] = float(v)
        before = dict(f)
        if calc:
            f.update(inputs)
            f["VAL"] = ce.evaluate(self.wrong_clc.get((r, "CALC"), f["CALC"]), {x: f[x] for x in "ABCDEFGHIJKL"})
            sev = ("MAJOR" if f["HHSV"] == "MAJOR" and f["VAL"] > f["HIHI"] else
                   "MINOR" if f["HSV"] == "MINOR" and f["VAL"] > f["HIGH"] else "NO_ALARM")
        else:
            clc = {f"CLC{x}": f[f"CLC{x}"] for x in LETTERS if f[f"CLC{x}"].strip()}
            clc.update({k: v for (rr, k), v in self.wrong_clc.items() if rr == r and k.startswith("CLC")})
            new = ce.eval_transform(clc, inputs, {x: f[x] for x in LETTERS})
            f.update(new)
            sev = "NO_ALARM"
        f["SEVR"] = "INVALID" if invalid else sev
        same = all(f[k] == before[k] or (isinstance(f[k], float) and math.isnan(f[k]) and math.isnan(before[k])) for k in f)
        return not same


class FakeEpics(types.ModuleType):
    """The module that stands in for pyepics: delegates to whichever FakeIOC the current test installed."""
    ioc = None

    def caget(self, *a, **k):
        return self.ioc.caget(*a, **k)

    def caput(self, *a, **k):
        return self.ioc.caput(*a, **k)


class StaticIOC:
    """Read-only dict: every field of a generated lane as it would read on a correctly installed IOC (for MonP/MonC)."""

    def __init__(self, entries):
        self.v = {}
        for r, desc, fields, hand, kind in entries:
            for k, x in fields.items():
                self.v[f"{r}.{k}"] = x
        self.puts = []

    def caget(self, pv, as_string=False, timeout=None):
        x = self.v.get(pv)
        if x is None:
            return None
        return str(x) if as_string else x

    def caput(self, pv, value, **k):
        self.puts.append((pv, value))
        return 1


FAKE = FakeEpics("epics")
inst = None            # calc/install_lane.py, imported against the fake
slot = None            # calc/slotlib.py, likewise
_saved = {}


def setUpModule():
    global inst, slot
    for name in ("epics", "slotlib", "install_lane"):
        _saved[name] = sys.modules.pop(name, None)
    sys.modules["epics"] = FAKE
    slot = importlib.import_module("slotlib")
    inst = importlib.import_module("install_lane")


def tearDownModule():
    for name, mod in _saved.items():
        sys.modules.pop(name, None)
        if mod is not None:
            sys.modules[name] = mod


class Base(unittest.TestCase):
    tetramm_up = True

    def setUp(self):
        self.ioc = FakeIOC(tetramm_up=self.tetramm_up)
        FAKE.ioc = self.ioc
        for p in (mock.patch("time.sleep"), mock.patch.object(el, "load_pvs", lambda path=None: dict(PLACEHOLDER_CFG))):
            p.start()
            self.addCleanup(p.stop)
        self.cfg = dict(PLACEHOLDER_CFG)
        self.entries = el.build(self.cfg)                       # flags, status, flux, bounds
        self.links = el.input_links(self.cfg)
        self.flags, self.status, self.flux, self.bounds = (e[0] for e in self.entries)

    def run_cli(self, *argv):
        out = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                inst.main(list(argv))
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
                if not isinstance(e.code, (int, type(None))):
                    out.write(str(e.code) + "\n")
        return code, out.getvalue()

    def expected_puts(self, rerun=False, dark=True):
        """The put sequence of an install, written out from the definition (not from the installer). rerun: the lane is
        already commissioned (flux ours, links in place)."""
        exp = []
        if rerun:
            exp += [(f"{r}Enable", 0) for r in (self.flux, self.flags, self.status, self.bounds)]
        for r, desc, fields, hand, kind in self.entries:
            fields = dict(fields)
            hv = dict(hand) if dark else {}
            if r == self.flux:
                if rerun:
                    fields.pop("INPA")
                    fields.pop("INPB")
                else:
                    fields["INPA"] = ""            # commissioning: the TetrAMM links are empty
                    fields["INPB"] = ""
                    hv = {"A": 2400.0, "B": 1600.0, **hv}
            exp.append((f"{r}Enable", 0))
            exp += [(f"{r}.{k}", v) for k, v in fields.items()]
            exp += [(f"{r}.{k}", v) for k, v in hv.items()]
            exp.append((f"{r}Enable", 1))
        if not rerun:
            exp += [(f"{self.flux}.A", 0.0), (f"{self.flux}.B", 0.0)]
            exp += [(f"{self.flux}.INPA", self.links["INPA"]), (f"{self.flux}.INPB", self.links["INPB"])]
        return exp

    def assert_only_targets(self, puts=None):
        for pv, _ in (self.ioc.puts if puts is None else puts):
            r, field = self.ioc._where(pv)
            self.assertIn(r, self.ioc.targets, f"write outside the four target records: {pv}")

    def install_clean(self):
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 0, out)
        return out

    def touched(self):
        return [r for r in self.ioc.targets if any(self.ioc._where(pv)[0] == r for pv, _ in self.ioc.puts)]

    def assert_failed_safe(self, code, out):
        """The END STATE of a failed install: exit 1, LANE FAILED with the recovery line, every slot this run touched is
        disabled, an untouched slot is exactly as it was, and no test current is left on the flux slot."""
        touched = self.touched()
        self.assertEqual(code, 1, out)
        self.assertIn("LANE FAILED", out)
        self.assertIn("fix the cause and re-run, or run --lane EStn --remove", out)
        self.assertTrue(touched)
        for r in self.ioc.targets:
            if r in touched:
                self.assertEqual(self.ioc.enable[r], 0.0, f"{r} still enabled after a failure")
            else:
                self.assertEqual(self.ioc.enable[r], 1.0)
                self.assertEqual(self.ioc.rec[r], default_record(r), f"{r} was not touched but changed")
        a, b = self.ioc.rec[self.flux]["A"], self.ioc.rec[self.flux]["B"]
        self.assertNotIn(a, (TEST_CURRENTS[0],), "test current A left on the flux slot")
        self.assertNotIn(b, (TEST_CURRENTS[1],), "test current B left on the flux slot")
        self.assert_only_targets()
        return touched


class DryRun(Base):
    def test_lists_every_write_in_order_and_writes_nothing(self):
        code, out = self.run_cli("--lane", "EStn", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ioc.puts, [], "a dry run must not write")
        listed = [l.strip() for l in out.splitlines() if l.strip().startswith("would put")]
        want = [f"would put {pv} = {v!r}" for pv, v in self.expected_puts()]
        self.assertEqual(listed, want)
        verifies = [l for l in out.splitlines() if "would verify" in l]
        self.assertEqual([l.split()[-1] for l in verifies], self.ioc.targets)
        self.assertLess(out.index(f"would put {self.flux}.A = 0.0"), out.index(f"would put {self.flux}.INPA = {self.links['INPA']!r}"))

    def test_dry_run_matches_the_real_install(self):
        _, out = self.run_cli("--lane", "EStn", "--dry-run")
        listed = [l.strip()[len("would put "):] for l in out.splitlines() if l.strip().startswith("would put")]
        self.install_clean()
        self.assertEqual(listed, [f"{pv} = {v!r}" for pv, v in self.ioc.puts])

    def test_rerun_dry_run_matches_the_real_rerun(self):
        self.install_clean()
        self.ioc.puts.clear()
        _, out = self.run_cli("--lane", "EStn", "--dry-run")
        self.assertIn("re-run of a commissioned lane", out)
        listed = [l.strip()[len("would put "):] for l in out.splitlines() if l.strip().startswith("would put")]
        self.assertEqual(self.ioc.puts, [])
        self.install_clean()
        self.assertEqual(listed, [f"{pv} = {v!r}" for pv, v in self.ioc.puts])

    def test_free_and_ours_are_accepted_and_reported(self):
        _, out = self.run_cli("--lane", "EStn", "--dry-run")
        self.assertEqual(out.count(": free, DESC="), 4)
        self.install_clean()
        self.ioc.puts.clear()
        code, out = self.run_cli("--lane", "EStn", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count(": ours, DESC="), 4)
        self.assertEqual(self.ioc.puts, [])

    def test_refuses_a_slot_used_by_someone_else(self):
        for victim in (self.flux, self.bounds, self.flags, self.status):
            with self.subTest(victim=victim):
                self.setUp()
                self.ioc.rec[victim]["DESC"] = "someone else's calc"
                self.ioc.rec[victim]["INPA" if "Tran" in victim else "INPB"] = "OTHER:PV.VAL NPP NMS"
                code, out = self.run_cli("--lane", "EStn", "--dry-run")
                self.assertEqual(code, 1)
                self.assertIn("in use by someone else", out)
                self.assertIn(victim, out)
                self.assertEqual(self.ioc.puts, [])

    def test_occupancy_rule_free_only_if_default_desc_and_nothing_set(self):
        """I2: ours = DESC ends (xray_fluxor); free = the exact default DESC and no INP/CLC/OUT set; everything else foreign."""
        cases = {
            "foreign DESC with only a CMT set": lambda r, f: f.update(DESC="my calc", CMTA="mine"),
            "foreign DESC, nothing else": lambda r, f: f.update(DESC="my calc"),
            "empty DESC": lambda r, f: f.update(DESC=""),
            "default DESC with an INP set": lambda r, f: f.update(INPA="X:Y.VAL NPP NMS"),
            "default DESC with a CLC set": lambda r, f: f.update(CLCA="1+1") if "Tran" in r else f.update(CALC="A+1"),
            "default DESC with an OUT set": lambda r, f: f.update(OUTA="X:Y PP") if "Tran" in r else f.update(OUT="X:Y PP"),
        }
        for name, mutate in cases.items():
            for victim in self.ioc.targets:
                with self.subTest(case=name, victim=victim):
                    self.setUp()
                    mutate(victim, self.ioc.rec[victim])
                    for argv in (("--dry-run",), (), ("--remove",), ("--remove", "--dry-run")):
                        code, out = self.run_cli("--lane", "EStn", *argv)
                        self.assertEqual(code, 1, (argv, out))
                        self.assertIn("in use by someone else", out)
                        self.assertEqual(self.ioc.puts, [], argv)

    def test_the_real_default_comments_do_not_count_as_set(self):
        self.assertEqual(self.ioc.rec[self.flux]["CMTA"], "a")        # CMTA-P are 'a'..'p' on a free slot
        code, out = self.run_cli("--lane", "EStn", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count(": free, DESC="), 4)

    def test_unreachable_ioc_exits_1(self):
        del self.ioc.ext[HEARTBEAT]
        code, out = self.run_cli("--lane", "EStn", "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("HEARTBEAT", out)


class Install(Base):
    def test_put_sequence_and_commissioning_order(self):
        seen = {}

        def hook(pv, value):
            # the moment A is zeroed, the flux slot has been commissioned on the test currents: it must match the mirror
            if pv == f"{self.flux}.A" and value == 0.0:
                if self.ioc.dirty:
                    self.ioc.settle()
                seen["flux"] = dict(self.ioc.rec[self.flux])
                seen["enable"] = self.ioc.enable[self.flux]
                seen["links"] = (self.ioc.rec[self.flux]["INPA"], self.ioc.rec[self.flux]["INPB"])
        self.ioc.before_put = hook
        out = self.install_clean()
        self.assertEqual(self.ioc.puts, self.expected_puts())
        self.assert_only_targets()
        self.assertEqual(seen["enable"], 1.0)
        self.assertEqual(seen["links"], ("", ""), "the TetrAMM links must be empty while the formula is verified")
        self.assertEqual((seen["flux"]["A"], seen["flux"]["B"]), TEST_CURRENTS)
        ref = el.evaluate_lane(dict(current3_nA=2400.0, current4_nA=1600.0, energy_keV=10.0, temp_F=72.0, pressure_kPa=98.99))["flux"]
        for x in "GHIJKLMOP":
            self.assertAlmostEqual(seen["flux"][x] / ref[x] if ref[x] else seen["flux"][x], 1.0 if ref[x] else 0.0, places=9, msg=x)
        # the tail of the sequence, literally: zero A and B, then the two bare 36-character links
        self.assertEqual(self.ioc.puts[-4:], [(f"{self.flux}.A", 0.0), (f"{self.flux}.B", 0.0),
                                              (f"{self.flux}.INPA", PLACEHOLDER_CFG["current3"]),
                                              (f"{self.flux}.INPB", PLACEHOLDER_CFG["current4"])])
        self.assertTrue(all(len(v) == 36 for _, v in self.ioc.puts[-2:]))
        self.assertTrue(all(" " not in v for _, v in self.ioc.puts[-2:]), "the two long links are written bare")
        self.assertIn("LANE OK", out)
        self.assertNotIn("WARNING", out)
        self.assertIn("reads back", out)                      # each link is read back and the string reported
        self.assertIn(repr(canon(PLACEHOLDER_CFG["current3"])), out)

    def test_final_state_follows_the_live_inputs(self):
        self.install_clean()
        f = self.ioc.rec
        self.assertEqual((f[self.flux]["A"], f[self.flux]["B"]), (600.0, 400.0))
        ref = el.evaluate_lane(dict(current3_nA=600.0, current4_nA=400.0, energy_keV=10.0, temp_F=72.0, pressure_kPa=98.99))
        self.assertAlmostEqual(f[self.flux]["P"] / ref["flux"]["P"], 1.0, places=9)
        self.assertAlmostEqual(f[self.bounds]["L"] / ref["bounds"]["L"], 1.0, places=9)
        self.assertEqual(f[self.flags]["L"], ref["flags"]["L"])
        self.assertEqual(f[self.status]["VAL"], ref["status"])
        self.assertEqual(f[self.flux]["SEVR"], "NO_ALARM")
        for r in self.ioc.targets:
            self.assertEqual(self.ioc.enable[r], 1.0)
        self.assertEqual(f[self.bounds]["P"], 1.0)             # plates constant

    def test_tetramm_down_is_a_warning_not_a_failure(self):
        self.tetramm_up = False
        self.setUp()
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 0, out)
        self.assertIn("WARNING", out)
        self.assertIn("LANE OK (with 1 WARNING)", out)
        self.assertNotIn("verified on live currents (", out)           # I5: never claim it
        self.assertEqual(self.ioc.puts, self.expected_puts())          # the same writes, links included
        f = self.ioc.rec[self.flux]
        self.assertEqual(f["INPA"], PLACEHOLDER_CFG["current3"])
        self.assertEqual(f["SEVR"], "INVALID")
        self.assertEqual(self.ioc.enable[self.flux], 1.0)
        self.assertEqual((f["A"], f["B"]), (0.0, 0.0), "no test current may be left to look like a flux")
        self.assertEqual(f["P"], 0.0)

    def test_final_check_both_answer_and_agree(self):                  # I5 (a)
        out = self.install_clean()
        self.assertIn("verified on live currents (", out)
        self.assertNotIn("WARNING", out)

    def test_final_check_this_pc_sees_the_tetramm_but_the_ioc_does_not(self):   # I5 (b)
        self.ioc.ioc_hidden = {PLACEHOLDER_CFG["current3"], PLACEHOLDER_CFG["current4"]}
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 0, out)                                 # a warning, the lane is still installed
        self.assertIn("WARNING: the utilioc does not see the TetrAMM (links INVALID or stale)", out)
        self.assertNotIn("verified on live currents (", out)
        self.assertIn("LANE OK (with 1 WARNING)", out)
        self.assertEqual((self.ioc.rec[self.flux]["A"], self.ioc.rec[self.flux]["B"]), (0.0, 0.0))

    def _sev_invalid(self):
        real = self.ioc.caget
        self.ioc.caget = lambda pv, as_string=False, timeout=None: (
            ("INVALID" if as_string else 3) if pv == f"{self.flux}.SEVR" else real(pv, as_string, timeout))

    def test_final_check_beam_off_proves_nothing(self):                # R2-1: PC reads 0.3 / 0.2 nA, the slot reads 0
        self.ioc.ext[PLACEHOLDER_CFG["current3"]] = 0.3
        self.ioc.ext[PLACEHOLDER_CFG["current4"]] = 0.2
        self.ioc.ioc_hidden = {PLACEHOLDER_CFG["current3"], PLACEHOLDER_CFG["current4"]}
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 0, out)
        self.assertIn("WARNING: beam off or currents below 5 nA: the live link check proves nothing", out)
        self.assertNotIn("verified on live currents (", out)
        self.assertNotIn("check the energy, temperature and pressure links", out)

    def test_final_check_beam_off_even_when_the_utilioc_sees_it(self):
        self.ioc.ext[PLACEHOLDER_CFG["current3"]] = 0.3
        self.ioc.ext[PLACEHOLDER_CFG["current4"]] = 0.2
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 0, out)
        self.assertIn("beam off or currents below 5 nA", out)
        self.assertNotIn("verified on live currents (", out)

    def test_final_check_blind_utilioc_with_beam_on(self):             # PC reads 600/400, slot reads 0
        self.ioc.ioc_hidden = {PLACEHOLDER_CFG["current3"], PLACEHOLDER_CFG["current4"]}
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 0, out)
        self.assertIn("the utilioc does not see the TetrAMM", out)
        self.assertNotIn("verified on live currents (", out)
        self.assertNotIn("beam off", out)

    def test_final_check_agrees_but_the_slot_is_invalid(self):         # PC 600/400, slot agrees, SEVR INVALID
        self._sev_invalid()
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 0, out)
        self.assertIn("flux slot SEVR is INVALID: a link is not answering. Suspects: the TetrAMM inputs", out)
        self.assertNotIn("verified on live currents (", out)
        self.assertNotIn("although the TetrAMM links answer", out)

    def test_final_check_neither_answers(self):                        # I5 (c)
        self.tetramm_up = False
        self.setUp()
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 0, out)
        self.assertIn("not connected from this PC", out)
        self.assertNotIn("verified on live currents (", out)

    def test_final_check_one_scan_of_drift_is_allowed(self):
        calls = {"n": 0}
        real = self.ioc.caget

        def drifting(pv, as_string=False, timeout=None):
            v = real(pv, as_string, timeout)
            if pv == PLACEHOLDER_CFG["current3"] and not as_string:
                calls["n"] += 1
                if calls["n"] == 1:
                    return v * 1.5           # the first direct read is from a different scan
            return v
        self.ioc.caget = drifting
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 0, out)
        self.assertIn("verified on live currents (", out)

    def test_foreign_slot_refuses_and_nothing_is_written(self):
        self.ioc.rec[self.bounds]["DESC"] = "FX4 calc"
        self.ioc.rec[self.bounds]["CLCA"] = "A+1"
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 1)
        self.assertEqual(self.ioc.puts, [], "refusal must happen before any slot is touched")
        self.assertNotIn("LANE OK", out)

    def test_reinstall_keeps_a_hand_dark_but_reset_values_restores_it(self):
        self.install_clean()
        self.ioc.rec[self.flux]["F"] = 0.7
        self.ioc.puts.clear()
        self.install_clean()
        self.assertEqual(self.ioc.rec[self.flux]["F"], 0.7)
        self.assertNotIn(f"{self.flux}.F", [pv for pv, _ in self.ioc.puts])
        self.ioc.puts.clear()
        code, out = self.run_cli("--lane", "EStn", "--reset-values")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ioc.rec[self.flux]["F"], 0.0)
        self.assert_only_targets()

    def test_rerun_with_the_links_in_place_publishes_no_test_current(self):     # I1
        self.install_clean()
        self.ioc.puts.clear()
        out = self.install_clean()
        puts = self.ioc.puts
        self.assertEqual(puts, self.expected_puts(rerun=True, dark=False))
        flux_enable_on = [i for i, (pv, v) in enumerate(puts) if pv == f"{self.flux}Enable" and v == 1]
        a = [v for pv, v in puts if pv in (f"{self.flux}.A", f"{self.flux}.B")]
        self.assertEqual(a, [], "a re-run must not put test currents (or anything) into A and B")
        self.assertNotIn((f"{self.flux}.INPA", ""), puts)
        # every slot is disabled before the first field write of the flux slot (and of any other)
        self.assertEqual(puts[:4], [(f"{r}Enable", 0) for r in (self.flux, self.flags, self.status, self.bounds)])
        first_flux_field = min(i for i, (pv, v) in enumerate(puts) if pv.startswith(self.flux + "."))
        for r in (self.flux, self.flags, self.status, self.bounds):
            self.assertLess(puts.index((f"{r}Enable", 0)), first_flux_field, r)
        self.assertEqual(len(flux_enable_on), 1)
        self.assertIn("verified on live currents (", out)
        self.assertEqual((self.ioc.rec[self.flux]["A"], self.ioc.rec[self.flux]["B"]), (600.0, 400.0))
        self.assertEqual(self.ioc.rec[self.flux]["INPA"], PLACEHOLDER_CFG["current3"])

    def test_rerun_with_links_missing_is_a_fresh_commissioning(self):
        self.install_clean()
        self.ioc.rec[self.flux]["INPB"] = ""
        self.ioc.puts.clear()
        self.install_clean()
        self.assertIn((f"{self.flux}.A", 2400.0), self.ioc.puts)
        self.assertEqual(self.ioc.puts[-2:], [(f"{self.flux}.INPA", self.links["INPA"]), (f"{self.flux}.INPB", self.links["INPB"])])


class FailurePaths(Base):
    """C1: whatever fails, every slot this run touched ends disabled and the flux slot holds no test current."""

    def once(self, match, mode="fail"):
        state = {"n": 0}

        def f(pv, value):
            if match(pv, value) and state["n"] == 0:
                state["n"] += 1
                return mode
        self.ioc.fail_when = f

    def test_verifier_failure_on_each_slot(self):
        cases = [("flags", "CLCL", "F+2*G"), ("status", "CALC", "A+1"), ("flux", "CLCP", "G*2E17/C/M*EXP(-5*L*I)"),
                 ("bounds", "CLCL", "A")]
        for role, field, expr in cases:
            with self.subTest(role=role):
                self.setUp()
                r = {"flags": self.flags, "status": self.status, "flux": self.flux, "bounds": self.bounds}[role]
                self.ioc.wrong_clc[(r, field)] = expr
                code, out = self.run_cli("--lane", "EStn")
                self.assertIn("MISMATCH", out)
                touched = self.assert_failed_safe(code, out)
                self.assertEqual(touched[-1], r)
                self.assertNotIn(self.links["INPA"], [v for _, v in self.ioc.puts], "links must not be written")

    def test_caput_failure_at_each_stage(self):
        flux = lambda: self.flux
        stages = {
            "first slot, a field": lambda pv, v: pv == f"{self.flags}.CLCL",
            "flux field": lambda pv, v: pv == f"{self.flux}.CLCP",
            "flux hand A (test current)": lambda pv, v: pv == f"{self.flux}.A" and v == 2400.0,
            "flux Enable on": lambda pv, v: pv == f"{self.flux}Enable" and v == 1,
            "bounds Enable on": lambda pv, v: pv == f"{self.bounds}Enable" and v == 1,
            "zeroing A": lambda pv, v: pv == f"{self.flux}.A" and v == 0.0,
            "zeroing B": lambda pv, v: pv == f"{self.flux}.B" and v == 0.0,
            "writing INPA": lambda pv, v: pv == f"{self.flux}.INPA" and v != "",
            "writing INPB": lambda pv, v: pv == f"{self.flux}.INPB" and v != "",
        }
        for name, match in stages.items():
            for mode in ("fail", "raise"):
                with self.subTest(stage=name, mode=mode):
                    self.setUp()
                    self.once(match, mode)
                    code, out = self.run_cli("--lane", "EStn")
                    self.assert_failed_safe(code, out)
                    self.assertNotIn("LANE OK", out)

    def test_link_readback_mismatch(self):
        self.ioc.corrupt[f"{self.flux}.INPB"] = "OTHER:PV NPP NMS"
        code, out = self.run_cli("--lane", "EStn")
        self.assertIn("MISMATCH", out)
        self.assert_failed_safe(code, out)

    def test_an_exception_in_the_final_check_is_caught(self):
        with mock.patch.object(inst, "read_values", side_effect=OSError("boom")):
            code, out = self.run_cli("--lane", "EStn")
        self.assertIn("ERROR: OSError: boom", out)
        self.assert_failed_safe(code, out)

    def test_a_final_check_mismatch_disables_the_lane(self):
        orig = inst.v_estn_flux

        def bad(v):
            return ["P"] if v["A"] == 600.0 else orig(v)          # fails only on the live currents
        with mock.patch.object(inst, "v_estn_flux", bad):
            # the installer's verifier table is built inside estn_install: patch the name it looks up
            code, out = self.run_cli("--lane", "EStn")
        self.assertIn("MISMATCH in ['P'] with the live TetrAMM currents", out)
        self.assert_failed_safe(code, out)

    def test_cleanup_zeroes_a_and_b_while_enabled_then_disables_in_order(self):     # R2-2
        seen = []
        state = {"on": False}

        def snap(pv, value):
            if not state["on"] or not pv.endswith("Enable") or value != 0:
                return
            if self.ioc.dirty:
                self.ioc.settle()
            f, b = self.ioc.rec[self.flux], self.ioc.rec[self.bounds]
            seen.append((pv[len("15IDC:util:"):-len("Enable")], dict(A=f["A"], B=f["B"], P=f["P"], flux_on=self.ioc.enable[self.flux],
                                                                      L=b["L"], bounds_on=self.ioc.enable[self.bounds])))
        self.ioc.before_put = snap

        def fail(pv, value):
            if pv == f"{self.flux}.B" and value == 0.0 and not state["on"]:   # all four enabled, A zeroed, B still 1600
                state["on"] = True
                return "fail"
        self.ioc.fail_when = fail
        code, out = self.run_cli("--lane", "EStn")
        self.assert_failed_safe(code, out)
        self.assertGreater(self.ioc.puts.index((f"{self.flux}.B", 0.0)), 0)
        order = [n for n, _ in seen]
        self.assertEqual(order, ["userTran9", "userTran10", "userTran11", "userCalcOut9"])
        flux_snap, bounds_snap = seen[0][1], seen[1][1]
        # when the flux is disabled its A, B and the formula P are already 0 (recomputed while it was enabled)
        self.assertEqual((flux_snap["A"], flux_snap["B"], flux_snap["P"], flux_snap["flux_on"]), (0.0, 0.0, 0.0, 1.0))
        # when bounds is disabled, the flux is off and bounds has recomputed from the zero flux
        self.assertEqual((bounds_snap["flux_on"], bounds_snap["L"], bounds_snap["bounds_on"]), (0.0, 0.0, 1.0))
        tail = self.ioc.puts[self.ioc.puts.index((f"{self.flux}.B", 0.0)) + 1:]     # after the failing put: the cleanup
        self.assertEqual(tail[:2], [(f"{self.flux}.A", 0.0), (f"{self.flux}.B", 0.0)])

    def test_an_incomplete_cleanup_says_so(self):
        self.ioc.wrong_clc[(self.bounds, "CLCL")] = "A"
        started = lambda: any(self.ioc._where(p)[0] == self.bounds for p, _ in self.ioc.puts)
        self.ioc.fail_when = lambda pv, v: "fail" if pv == f"{self.flux}Enable" and v == 0 and started() else None
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 1)
        self.assertIn("cleanup is INCOMPLETE", out)
        self.assertIn(f"{self.flux}Enable", out.split("cleanup is INCOMPLETE")[1])
        self.assertNotIn("LANE FAILED: the slots this run touched are disabled", out)

    def test_a_failing_disable_does_not_stop_the_other_disables(self):
        self.ioc.wrong_clc[(self.bounds, "CLCL")] = "A"
        started = lambda: any(self.ioc._where(p)[0] == self.bounds for p, _ in self.ioc.puts)
        self.ioc.fail_when = lambda pv, v: "fail" if pv == f"{self.flux}Enable" and v == 0 and started() else None
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 1)
        self.assertIn("cleanup is INCOMPLETE", out)
        for r in (self.flags, self.status, self.bounds):
            self.assertEqual(self.ioc.enable[r], 0.0, r)

    def test_a_failed_rerun_leaves_everything_disabled(self):
        self.install_clean()
        self.ioc.wrong_clc[(self.flags, "CLCL")] = "F+2*G+1"
        self.ioc.puts.clear()
        code, out = self.run_cli("--lane", "EStn")
        self.assertEqual(code, 1)
        for r in self.ioc.targets:
            self.assertEqual(self.ioc.enable[r], 0.0, r)
        self.assert_only_targets()


class Compare(Base):
    def test_zero_differences_after_install_and_nothing_written(self):
        self.install_clean()
        self.ioc.puts.clear()
        code, out = self.run_cli("--lane", "EStn", "--compare")
        self.assertEqual(code, 0, out)
        self.assertIn("EStn: 0 field(s) differ", out)
        self.assertEqual(self.ioc.puts, [])

    def test_a_changed_expression_is_one_difference(self):
        self.install_clean()
        self.ioc.rec[self.flags]["CLCL"] = "F+2*G"
        code, out = self.run_cli("--lane", "EStn", "--compare")
        self.assertEqual(code, 1)
        self.assertIn(f"DIFF {self.flags}.CLCL", out)
        self.assertIn("1 field(s) differ", out)

    def test_a_missing_tetramm_link_is_a_difference(self):
        self.install_clean()
        self.ioc.rec[self.flux]["INPB"] = ""
        code, out = self.run_cli("--lane", "EStn", "--compare")
        self.assertEqual(code, 1)
        self.assertIn(f"DIFF {self.flux}.INPB", out)

    def test_dark_is_compared_only_when_the_slot_is_not_ours(self):
        self.install_clean()
        self.ioc.rec[self.flux]["F"] = 1.5                       # a hand-entered dark on our slot: not a difference
        code, out = self.run_cli("--lane", "EStn", "--compare")
        self.assertEqual(code, 0, out)
        self.assertNotIn(f"{self.flux}.F", out)
        self.ioc.rec[self.flux]["DESC"] = "user Transform 9"      # not ours any more: F is now compared
        code, out = self.run_cli("--lane", "EStn", "--compare")
        self.assertEqual(code, 1)
        self.assertIn(f"DIFF {self.flux}.F", out)

    def test_a_clean_ioc_differs_everywhere(self):
        code, out = self.run_cli("--lane", "EStn", "--compare")
        self.assertEqual(code, 1)
        self.assertEqual(self.ioc.puts, [])

    def test_unreachable_utilioc_is_not_n_differences(self):     # M3
        del self.ioc.ext[HEARTBEAT]
        code, out = self.run_cli("--lane", "EStn", "--compare")
        self.assertEqual(code, 2)
        self.assertIn("utilioc not reachable", out)
        self.assertNotIn("field(s) differ", out)
        self.assertEqual(self.ioc.puts, [])


class MonLanesUnchanged(unittest.TestCase):
    """M6: the MonP/MonC compare output is exactly as before (golden strings), against an IOC holding the generated lane."""

    def setUp(self):
        FAKE.ioc = None

    def run_cli(self, *argv):
        out = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                inst.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()

    def test_compare_of_the_generated_lane_is_zero_and_the_output_is_golden(self):
        for lane in ("MonP", "MonC"):
            with self.subTest(lane=lane):
                FAKE.ioc = StaticIOC(inst.build(lane))
                code, out = self.run_cli("--lane", lane, "--compare")
                self.assertEqual((code, out), (0, f"{lane}: 0 field(s) differ from the generated lane\n"))
                self.assertEqual(FAKE.ioc.puts, [])

    def test_a_single_changed_field_prints_the_old_diff_line(self):
        for lane in ("MonP", "MonC"):
            with self.subTest(lane=lane):
                entries = inst.build(lane)
                ioc = FAKE.ioc = StaticIOC(entries)
                r, _, fields, _, _ = entries[3]                           # the flux slot
                ioc.v[f"{r}.CLCP"] = "changed"
                ioc.v[f"{r}.PREC"] = "9"
                code, out = self.run_cli("--lane", lane, "--compare")
                self.assertEqual(code, 1)
                self.assertEqual(out, f"  DIFF {r}.PREC: live '9'  generated {fields['PREC']!r}\n"
                                      f"  DIFF {r}.CLCP: live 'changed'  generated {fields['CLCP']!r}\n"
                                      f"{lane}: 2 field(s) differ from the generated lane\n")

    def test_remove_is_for_estn_only_and_mon_lanes_have_no_new_writes(self):
        FAKE.ioc = StaticIOC(inst.build("MonP"))
        code, _ = self.run_cli("--lane", "MonP", "--remove")
        self.assertEqual(code, 2)
        self.assertEqual(FAKE.ioc.puts, [])


class Remove(Base):
    def assert_free(self, r):
        self.assertEqual(self.ioc.rec[r], default_record(r), r)          # every field equals the real default
        self.assertEqual(self.ioc.enable[r], 1.0, r)                      # and a free slot reads Enable 1

    def test_dry_run_lists_and_writes_nothing(self):
        self.install_clean()
        self.ioc.puts.clear()
        code, out = self.run_cli("--lane", "EStn", "--remove", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ioc.puts, [])
        for r in self.ioc.targets:
            self.assertIn(f"would put {r}Enable = 0", out)
            self.assertIn(f"would put {r}Enable = 1", out)
        self.assertIn(f"would put {self.flux}.CMTA = 'a'", out)
        self.assertIn(f"would put {self.flux}.PREC = '3'", out)
        self.assertIn(f"would put {self.status}.PREC = '5'", out)
        self.assertIn("nothing written", out)

    def test_remove_restores_the_real_defaults_of_all_four_slots(self):   # I3
        self.install_clean()
        self.ioc.puts.clear()
        code, out = self.run_cli("--lane", "EStn", "--remove")
        self.assertEqual(code, 0, out)
        self.assertIn("REMOVED 4 slot(s)", out)
        self.assert_only_targets()
        for r in self.ioc.targets:
            self.assert_free(r)
        pvs = [pv for pv, _ in self.ioc.puts]
        self.assertEqual(pvs[:4], [f"{r}Enable" for r in (self.bounds, self.flux, self.status, self.flags)])
        code, _ = self.run_cli("--lane", "EStn", "--compare")
        self.assertEqual(code, 1)

    def test_remove_after_a_hand_dark_still_gives_the_default(self):
        self.install_clean()
        self.ioc.rec[self.flux]["F"] = 3.2
        self.run_cli("--lane", "EStn", "--remove")
        self.assert_free(self.flux)

    def test_a_refused_computed_letter_is_ignored_and_reported(self):
        self.install_clean()
        self.ioc.fail_when = lambda pv, v: "fail" if pv == f"{self.bounds}.K" else None
        self.ioc.puts.clear()
        code, out = self.run_cli("--lane", "EStn", "--remove")
        self.assertEqual(code, 0, out)
        self.assertIn(f"{self.bounds}.K: put refused or not read back", out)
        self.assertEqual(self.ioc.enable[self.bounds], 1.0)

    def test_a_refused_required_field_fails_the_remove(self):
        self.install_clean()
        self.ioc.fail_when = lambda pv, v: "fail" if pv == f"{self.flux}.CLCP" else None
        code, out = self.run_cli("--lane", "EStn", "--remove")
        self.assertEqual(code, 1, out)
        self.assertIn("partly restored", out)
        self.assertNotIn("the slots stay disabled", out)

    def test_remove_then_install_again(self):
        self.install_clean()
        self.run_cli("--lane", "EStn", "--remove")
        self.ioc.puts.clear()
        self.install_clean()
        self.assertEqual(self.ioc.puts, self.expected_puts())

    def test_refuses_when_any_slot_is_someone_elses_and_writes_nothing(self):
        self.install_clean()
        self.ioc.rec[self.bounds]["DESC"] = "taken over"
        self.ioc.rec[self.bounds]["INPA"] = "X:Y NPP NMS"
        self.ioc.puts.clear()
        for argv in (("--remove",), ("--remove", "--dry-run")):
            code, out = self.run_cli("--lane", "EStn", *argv)
            self.assertEqual(code, 1)
            self.assertIn("in use by someone else", out)
            self.assertEqual(self.ioc.puts, [])

    def test_an_already_free_slot_is_not_touched(self):
        code, out = self.run_cli("--lane", "EStn", "--remove")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ioc.puts, [])
        self.assertEqual(out.count("already free"), 4)

    def test_only_our_slots_are_written_when_some_are_free(self):
        self.install_clean()
        for r in (self.flags, self.status):
            for pv, v, _ in inst.estn_free_writes(r):
                self.ioc.caput(pv, v)
        self.ioc.puts.clear()
        code, out = self.run_cli("--lane", "EStn", "--remove")
        self.assertEqual(code, 0, out)
        written = {self.ioc._where(pv)[0] for pv, _ in self.ioc.puts}
        self.assertEqual(written, {self.flux, self.bounds})

    def test_remove_is_for_estn_only(self):
        for argv in (("--lane", "MonP", "--remove"), ("--lane", "EStn", "--remove", "--compare")):
            code, _ = self.run_cli(*argv)
            self.assertEqual(code, 2)
        self.assertEqual(self.ioc.puts, [])


class WriteGuard(Base):
    def test_only_the_four_records_may_be_written(self):                  # M2
        for pv in (f"{self.flux}.INPA", f"{self.status}Enable", f"{self.bounds}.CLCL"):
            inst._guard_write(pv)
        for pv in ("15IDC:util:userCalcOut3.PROC", "15IDC:util:userTran1.G", "15IDC:util:userTran10Enable.VAL",
                   "SRC:TETRAMM:CHANNEL3:MEAN_CURRENT_NA", "15IDC:util:userTran12.A", "15IDC:userTran10.A"):
            with self.assertRaises(RuntimeError, msg=pv):
                inst._guard_write(pv)
        self.assertEqual(self.ioc.puts, [])


class Verifiers(Base):
    def setUp(self):
        super().setUp()
        self.install_clean()
        self.v = {r: slot.read_values(r) for r in (self.flux, self.bounds, self.flags)}
        self.v[self.status] = slot.read_values(self.status, list("ABCDEFGHIJKL") + ["VAL"])
        p = mock.patch("builtins.print")                           # the verifiers narrate; keep the test output clean
        p.start()
        self.addCleanup(p.stop)

    def test_good_values_pass(self):
        self.assertEqual(inst.v_estn_flux(self.v[self.flux]), [])
        self.assertEqual(inst.v_estn_bounds(self.v[self.bounds]), [])
        self.assertEqual(inst.v_estn_flags(self.v[self.flags]), [])
        self.assertEqual(inst.v_estn_status(self.v[self.status]), [])

    def test_flux_catches_a_wrong_letter_and_ignores_rounding(self):
        v = dict(self.v[self.flux])
        v["P"] *= 1.01
        v["K"] *= 1.0005
        self.assertEqual(inst.v_estn_flux(v), ["P"])

    def test_flux_zero_guard(self):
        v = dict(self.v[self.flux], A=0.0, B=0.0, G=0.0, P=0.0, O=0.0)
        self.assertEqual(inst.v_estn_flux(v), [])

    def test_bounds_catches_each_kind_of_error(self):
        v = dict(self.v[self.bounds])
        v["L"] *= 1.01
        self.assertEqual(inst.v_estn_bounds(v), ["L"])
        v = dict(self.v[self.bounds], P=0.0)
        self.assertEqual(inst.v_estn_bounds(v), ["P"])             # the plate-orientation constant
        v = dict(self.v[self.bounds])
        v["B"] = 11.0                                              # E_eff must be the density-scaled energy
        self.assertEqual(inst.v_estn_bounds(v), ["B"])

    def test_flags_catches_a_wrong_bit_and_code(self):
        v = dict(self.v[self.flags], L=self.v[self.flags]["L"] + 1)
        self.assertEqual(inst.v_estn_flags(v), ["L"])
        v = dict(self.v[self.flags], K=1.0 - self.v[self.flags]["K"])
        self.assertEqual(inst.v_estn_flags(v), ["K"])

    def test_status_checks_value_and_severity(self):
        v = dict(self.v[self.status], VAL=3.0, A=0.0)
        self.assertEqual(inst.v_estn_status(v), ["VAL/SEVR"])
        for code, sev in ((0.0, "NO_ALARM"), (8.0, "MINOR"), (16.0, "MAJOR")):
            self.ioc.rec[self.status]["SEVR"] = sev
            self.assertEqual(inst.v_estn_status(dict(self.v[self.status], A=code, VAL=code)), [], code)


class StringMatch(unittest.TestCase):
    def test_bare_link_matches_its_default_form_only_on_link_fields(self):    # M1
        sm = lambda back, value, field="INPA": slot.strings_match(back, value, field)
        pv = "SRC:TETRAMM:CHANNEL3:MEAN_CURRENT_NA"
        self.assertTrue(sm(pv, pv))
        self.assertTrue(sm(pv + " NPP NMS", pv))
        self.assertTrue(sm((pv + " NPP NMS")[:39], pv))
        self.assertTrue(sm(pv + " NPP NMS", pv, "OUTA"))
        self.assertFalse(sm(pv + " PP", pv))
        self.assertFalse(sm("OTHER:PV NPP NMS", pv))
        self.assertFalse(sm(pv + " NPP NMS", pv + " NPP MS"))
        self.assertTrue(sm("Passive", "Passive", "SCAN"))
        self.assertFalse(sm("Passive NPP", "Passive", "SCAN"))             # not a link field: exact only
        self.assertFalse(sm(pv + " NPP NMS", pv, "DESC"))
        self.assertFalse(sm(pv + " NPP NMS", pv, None))


class PvConfig(unittest.TestCase):
    """I4: the local PV config must hold bare PV names."""

    def load(self, **over):
        cfg = {"current3": "SRC:A:CH3", "current4": "SRC:A:CH4", "energy": "SRC:E", "hutch_temp_f": "SRC:T"}
        cfg.update(over)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pvs.json"
            p.write_text(json.dumps(cfg), encoding="utf-8")
            return el.load_pvs(p)

    def test_valid_names_are_accepted(self):
        self.assertEqual(self.load()["energy"], "SRC:E")
        self.load(energy="IOC-1:mono_E.RBV", hutch_temp_f="a.b:c-d_1")

    def test_each_rejection_names_the_key_not_the_value(self):
        bad = {"a trailing modifier": "SRC:E PP", "leading space": " SRC:E", "tab": "SRC:E\tCPP", "a semicolon": "SRC:E;X",
               "a quote": 'SRC:"E"', "a brace": "SRC:{E}", "an own record": "15IDC:util:userCalcOut3.PROC",
               "our own transform": "15IDC:util:userTran9.P", "empty": ""}
        for name, value in bad.items():
            for key in ("current3", "current4", "energy", "hutch_temp_f"):
                with self.subTest(case=name, key=key):
                    with self.assertRaises(ValueError) as cm:
                        self.load(**{key: value})
                    msg = str(cm.exception)
                    self.assertIn(key, msg)
                    if value.strip():
                        self.assertNotIn(value, msg)

    def test_non_string_values_are_rejected_naming_the_key(self):
        for value in (None, 5, 1.5, ["SRC:A"], {"a": 1}, True):
            for key in ("current3", "energy"):
                with self.subTest(value=value, key=key):
                    with self.assertRaises(ValueError) as cm:
                        self.load(**{key: value})
                    self.assertIn(key, str(cm.exception))
                    self.assertNotIn("SRC:A", str(cm.exception))

    def test_build_and_input_links_validate_too(self):
        cfg = dict(PLACEHOLDER_CFG, current3="SRC:X PP")
        with self.assertRaises(ValueError):
            el.build(cfg)
        with self.assertRaises(ValueError):
            el.input_links(cfg)


if __name__ == "__main__":
    unittest.main()
