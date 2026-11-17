# fluxor parameter framework: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the offline `fluxor/` package into a framework where every number that is not measured lives in one registry row with a tag, a source and a "closes with" note, so a better number is a one-row edit that removes its own warning, and so the package can carry the unknowns we still have (beam aspect ratio, harmonic content, gas conditions, instrument accuracies) without hiding them.

**Architecture:** A TOML parameter registry (`fluxor/parameters.toml`) loaded by `fluxor/params.py`. Chambers and chains read their numbers from it; every ASSUMED or PROVISIONAL value that a calculation actually uses raises an `assumed:<name>` flag automatically. The chamber accepts a photon spectrum (default: pure fundamental, the user's call) so harmonic content can be added later if it ever matters. Recombination is carried as a central value and a range over the beam's height/width ratio, and the central value corrects the best estimate. The parameter table in `fluxor/PARAMETERS.md` is generated from the registry, so it can never go stale.

**Tech Stack:** Python 3.12 (bluesky venv, `tomllib` from the standard library, no new dependencies), `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-13-ic500-chains-design.md` (build status table and open items), with the user's 2026-11-14 direction: "make a plan to implement with assumptions chosen wisely and recorded. we need a framework that works that we can add better numbers to later."

## Global Constraints

- Offline only: no PV reads or writes, no utilioc slots, no edits under `calc/` (spec scope guard). `calc/` is imported read-only.
- Run Python as `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8`; `-I` ignores the working directory, so every entry point inserts the repo root on `sys.path`.
- A flagged number beats none (user rule, 2026-11-12): nothing returns None or raises on doubt; doubt is a flag and a bound.
- No PV names, host names, IPs or account names in tracked files (CLAUDE.md). The E-station PV names stay in the local note and local memory.
- A change is not done until the OPERATOR.md and HANDOFF.md it affects are updated in the same commit (CLAUDE.md).
- `PROGRESS.md` is append-only: add one entry, never edit an old one. `PLAN.md` changes are new rows quoting the user.
- Commit as you go (user standing rule); never push without asking.
- Tags, exactly these strings: `GIVEN` (the user stated it), `MEASURED`, `DERIVED`, `CHOICE` (a design decision the user may overturn), `PROVISIONAL` (read from a manual or pattern, unconfirmed), `ASSUMED` (placeholder). `PROVISIONAL` and `ASSUMED` raise flags.
- Name change: the archived beam-on time ranges were called "windows" and the user did not know what that meant. They are now **beam-on periods** everywhere except the append-only log and the Experimenter's own script name; HANDOFF.md glossary records the old name.

## Assumptions chosen for this plan (each becomes a registry row in Task 2)

| Name | Chosen value | Why this value |
|---|---|---|
| `beam.width_mm` | 1.0 | the white-beam slits, upstream of the chamber, read 1.00 mm horizontal in every beam-on period; they sit outside the hot zone, so this is an upper bound |
| `beam.aspect_central` | 0.1 | height/width. Recombination scales with it. The only measured beam on this site (MonC) is 0.03 mm tall by about 1 mm wide, ratio 0.03; 0.1 is deliberately less flat, so the central value is not optimistic |
| `beam.aspect_low`, `beam.aspect_high` | 0.03, 1.0 | MonC's measured ratio; and the symmetric 1 × 1 mm slits taken at face value |
| `recomb.apply_to_best` | true | an uncorrected recombination always understates the flux, so the best estimate carries the central correction (this reverses the earlier choice A19 of correcting only the high bound) |
| `spectrum.fractions` | pure fundamental, [[1.0, 1.0]] | user, 2026-11-14: "monochromators are fairly good at monochromating". Tag CHOICE, so it raises no flag; the spectrum input stays so a harmonic fraction can be added later |
| `gas.p_kpa`, `gas.t_c` | 98.99, 22.2 | user accepted stand-ins on 2026-11-14: the site-mean pressure and the E-hutch air temperature |

## File Structure

| File | Responsibility |
|---|---|
| `fluxor/parameters.toml` (create) | every non-code number: value, sigma, unit, tag, source, date, `closes_with`, `legacy_id` |
| `fluxor/params.py` (create) | `Param`, `Registry` (load, value, flags, replaced), `default()` |
| `fluxor/make_parameters_md.py` (create) | writes `fluxor/PARAMETERS.md` from the registry |
| `fluxor/PARAMETERS.md` (generated) | the one list of assumptions, replacing the hand-written `ASSUMPTIONS.md` |
| `fluxor/chambers/base.py` (modify) | reads the registry, accepts a spectrum, adds `assumed:` flags |
| `fluxor/chambers/ic500_50.py` (modify) | numbers from the registry; recombination as central and range; `Conditions` default |
| `fluxor/chains/tetramm.py`, `fx4.py` (modify) | placeholders from the registry |
| `fluxor/core.py` (modify) | `evaluate()` takes the spectrum and registry-default gas conditions; the best estimate carries recombination |
| `analysis/estation_step6.py` (modify), `data/estation/beam_on_periods_2026-11.csv` (rename from `clean_windows_2026-11.csv`) | the rerun reads the registry |
| `tests/test_params.py` (create), `tests/test_fluxor.py` (modify) | registry tests; existing tests adapted |
| `fluxor/OPERATOR.md`, `fluxor/HANDOFF.md`, spec, `PLAN.md`, `PROGRESS.md` (modify) | docs, including "how to replace an assumed number" |

---

### Task 1: Parameter registry

**Files:**
- Create: `fluxor/params.py`, `fluxor/parameters.toml` (two seed rows here, the full set in Task 2)
- Test: `tests/test_params.py`

**Interfaces:**
- Produces: `params.Param` (frozen dataclass: `name, value, sigma, unit, tag, source, date, closes_with, legacy_id, note`), `params.Registry.load(path=DEFAULT_PATH) -> Registry`, `Registry.value(name)` (records the use), `Registry.param(name) -> Param`, `Registry.names() -> list[str]`, `Registry.flags() -> list[str]` (one `assumed:<name>` per used ASSUMED or PROVISIONAL param, sorted), `Registry.reset_use()`, `Registry.replaced(name, value, tag="MEASURED", source="", date="", sigma=None) -> Registry` (copy with one row changed), `params.default() -> Registry` (cached), `params.TAGS`, `params.FLAGGED_TAGS`.

- [ ] **Step 1: Write the failing test**

```python
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

    def test_assumed_rows_say_how_they_close(self):
        bad = Path("bad_registry2.toml")
        bad.write_text('["x"]\nvalue = 1\nunit = "mm"\ntag = "ASSUMED"\nsource = "s"\ndate = "d"\n', encoding="utf-8")
        self.addCleanup(bad.unlink)
        with self.assertRaises(ValueError):
            params.Registry.load(bad)                            # ASSUMED without closes_with


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 -m unittest tests.test_params -v`
Expected: FAIL with `ImportError: cannot import name 'params' from 'fluxor'`

- [ ] **Step 3: Write the implementation**

```python
# fluxor/params.py
"""Parameter registry: every number that is not code, with its tag, source and how to improve it.

Rows live in fluxor/parameters.toml. A calculation reads a number with Registry.value(name); the registry remembers which
rows were used, and flags() returns one `assumed:<name>` flag for each used row whose tag is ASSUMED or PROVISIONAL.
To improve a number, edit its row (new value, tag MEASURED, source, date): its flag disappears by itself.
"""
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent / "parameters.toml"
TAGS = ("GIVEN", "MEASURED", "DERIVED", "CHOICE", "PROVISIONAL", "ASSUMED")
FLAGGED_TAGS = ("PROVISIONAL", "ASSUMED")
REQUIRED = ("value", "unit", "tag", "source", "date")


@dataclass(frozen=True)
class Param:
    name: str
    value: object
    unit: str
    tag: str
    source: str
    date: str
    sigma: object = None          # 1-sigma on the value, same unit (or relative if the row's note says so)
    closes_with: str = ""         # what would close an ASSUMED or PROVISIONAL row
    legacy_id: str = ""           # id in the old hand-written ASSUMPTIONS.md (A1..A30)
    note: str = ""


class Registry:
    def __init__(self, params):
        self._p = dict(params)
        self.used = set()

    @classmethod
    def load(cls, path=DEFAULT_PATH):
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        out = {}
        for name, row in raw.items():
            missing = [k for k in REQUIRED if k not in row]
            if missing:
                raise ValueError(f"{name}: missing {missing}")
            if row["tag"] not in TAGS:
                raise ValueError(f"{name}: tag {row['tag']!r} is not one of {TAGS}")
            if row["tag"] in FLAGGED_TAGS and not row.get("closes_with"):
                raise ValueError(f"{name}: a {row['tag']} row must say how it closes (closes_with)")
            out[name] = Param(name=name, **{k: v for k, v in row.items()})
        return cls(out)

    def param(self, name):
        return self._p[name]

    def names(self):
        return sorted(self._p)

    def value(self, name):
        self.used.add(name)
        return self._p[name].value

    def reset_use(self):
        self.used.clear()

    def flags(self):
        return sorted(f"assumed:{n}" for n in self.used if self._p[n].tag in FLAGGED_TAGS)

    def replaced(self, name, value, tag="MEASURED", source="", date="", sigma=None):
        old = self._p[name]
        new = replace(old, value=value, tag=tag, source=source or old.source, date=date or old.date,
                      sigma=old.sigma if sigma is None else sigma)
        out = dict(self._p)
        out[name] = new
        return Registry(out)


_default = None


def default():
    global _default
    if _default is None:
        _default = Registry.load()
    return _default
```

```toml
# fluxor/parameters.toml  (seed; the full set is added in Task 2)
["gas.p_kpa"]
value = 98.99
unit = "kPa"
tag = "ASSUMED"
source = "stand-in: the C-station site-mean pressure; no E-station gas pressure sensor exists (user accepted, 2026-11-14)"
date = "2026-11-14"
closes_with = "a pressure reading on the chamber gas line"
legacy_id = "A7"

["gas.t_c"]
value = 22.2
unit = "C"
tag = "ASSUMED"
source = "stand-in: E-hutch air temperature seen in the beam-on periods (a degF PV); no chamber temperature sensor exists (TODO.md)"
date = "2026-11-14"
closes_with = "a temperature sensor on the chamber body"
legacy_id = "A7"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 -m unittest tests.test_params -v`
Expected: `Ran 5 tests ... OK`

- [ ] **Step 5: Commit**

```bash
git add fluxor/params.py fluxor/parameters.toml tests/test_params.py
git commit -m "fluxor: parameter registry (tagged rows, automatic assumed: flags)"
```

---

### Task 2: Move every number into the registry and make the chambers and chains read it

**Files:**
- Modify: `fluxor/parameters.toml` (full set), `fluxor/chambers/base.py`, `fluxor/chambers/ic500_50.py`, `fluxor/chambers/cmc_guarded.py`, `fluxor/chains/tetramm.py`, `fluxor/chains/fx4.py`, `fluxor/chains/sr570_v2f.py`, `fluxor/core.py`
- Test: `tests/test_fluxor.py` (existing tests must pass unchanged except where listed), `tests/test_params.py`

**Interfaces:**
- Consumes: `params.default()`, `Registry.value`, `Registry.flags`, `Registry.reset_use` from Task 1.
- Produces: `IonChamber.__init__(self, reg=None)` storing `self.reg`; `IonChamber.flux(...)` returns `ChamberResult` whose `flags` now also contain `self.reg.flags()` (registry reset at the start of every call); `Ic500_50(reg=None)`; `TetraMM(..., reg=None)`, `Fx4(..., reg=None)` reading `tetramm.gain_rel`, `tetramm.dark_sigma_nA`, `tetramm.unit_a`, `fx4.gain_rel`, `fx4.dark_sigma_a`; registry names listed below.

Registry names to add (each with `value, unit, tag, source, date`, plus `closes_with` for ASSUMED and PROVISIONAL, `legacy_id` where an A-id exists). Values are exactly the ones now hard-coded:

| Name | Value | Tag | legacy |
|---|---|---|---|
| `ic500.gap_mm` | 10.0 | GIVEN | |
| `ic500.volts` | 1700.0 | GIVEN | |
| `ic500.l_eff_cm` | 5.0, sigma 0.03 (relative) | ASSUMED | A3 |
| `ic500.plate_orientation` | "horizontal" | ASSUMED | A2 |
| `ic500.wall_fit` | [17.7, 25.9, 1.36] | DERIVED | A5 |
| `terms.mu_en_tables_rel` | 0.03 | CHOICE | A15 |
| `terms.w_rel` | 0.006 | CHOICE | A15 |
| `terms.density_rel` | 0.002 | CHOICE | A15 |
| `recomb.alpha_cm3_s` | 1.6e-6 | CHOICE | A8 |
| `recomb.mobility_cm2_vs` | 1.8 | CHOICE | A8 |
| `beam.width_mm` | 1.0 | ASSUMED | A28 |
| `beam.aspect_central` | 0.1 | ASSUMED | A29 |
| `beam.aspect_low` | 0.03 | ASSUMED | A29 |
| `beam.aspect_high` | 1.0 | ASSUMED | A29 |
| `recomb.apply_to_best` | true | CHOICE | A19 |
| `tetramm.gain_rel` | 0.01 | ASSUMED | A10 |
| `tetramm.dark_sigma_nA` | 1.0 | ASSUMED | A11 |
| `tetramm.unit_a` | 1e-9 | ASSUMED | A14 |
| `tetramm.range` | 0 | PROVISIONAL | A24 |
| `fx4.gain_rel` | 0.01 | ASSUMED | A10 |
| `fx4.dark_sigma_a` | 1e-9 | ASSUMED | A11 |
| `sr570.electronics_rel` | 0.007 | DERIVED | |

(`gas.p_kpa` and `gas.t_c` already exist from Task 1; `spectrum.fractions` is added in Task 4.)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_params.py`)

```python
class DefaultRegistryTests(unittest.TestCase):
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
        for f in ("assumed:ic500.l_eff_cm", "assumed:beam.aspect_central"):
            self.assertIn(f, r.flags)

    def test_improving_a_number_removes_its_flag_and_changes_the_result(self):
        from fluxor.chambers.ic500_50 import Ic500_50
        base = Ic500_50().flux(4e-6, 10.0, 98.99, 22.2)
        better = params.default().replaced("ic500.l_eff_cm", 5.2, tag="MEASURED", source="vendor drawing", date="2026-12-01")
        r = Ic500_50(reg=better).flux(4e-6, 10.0, 98.99, 22.2)
        self.assertNotIn("assumed:ic500.l_eff_cm", r.flags)
        self.assertNotEqual(r.flux_formula, base.flux_formula)
```

- [ ] **Step 2: Run to verify they fail**

Run: `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 -m unittest tests.test_params -v`
Expected: FAIL (`KeyError` on the missing registry names or `TypeError: __init__() got an unexpected keyword argument 'reg'`)

- [ ] **Step 3: Implement**

1. Add all rows above to `fluxor/parameters.toml`, copying each `source` text from the row's comment in the current code (`ic500_50.py`, `tetramm.py`, `fx4.py`) and each `closes_with` from the matching "How to close" cell of `fluxor/ASSUMPTIONS.md`.
2. `IonChamber.__init__(self, reg=None)`: `self.reg = reg or params.default()`. In `flux()`, start with `self.reg.reset_use()`; read `W`-independent constants as before; at the end `flags += self.reg.flags()`.
3. `Ic500_50.__init__(self, reg=None)`: `super().__init__(reg)`. Replace each class constant with a `self.reg.value(...)` read at `flux()` time: `l_cm = ic500.l_eff_cm`, `gap_cm = ic500.gap_mm / 10`, `volts`, `wall_fit = tuple(ic500.wall_fit)`, the three symmetric terms from `terms.*`, plus `("collection length (l_eff)", sigma of ic500.l_eff_cm)` taken from `self.reg.param("ic500.l_eff_cm").sigma`. Recombination reads `recomb.alpha_cm3_s`, `recomb.mobility_cm2_vs`, `beam.width_mm`, `beam.aspect_central`. Remove the constructor arguments `beam_h_mm`, `beam_w_mm`, `source`, `volts` and the `beam_given` logic; keep the flag `beam_taller_than_30_percent_of_gap_formula_weak` and the `recombination_over_1_percent` / `recombination_formula_not_valid` flags.
4. `TetraMM.__init__(..., reg=None)` and `Fx4.__init__(..., reg=None)`: the defaults for `gain_rel`, `dark_sigma_a`, `unit_a`, `rng` come from the registry when the argument is None; the placeholder flag becomes the registry's `assumed:tetramm.gain_rel` (drop the hand-written `gain_accuracy_placeholder`, `dark_*` placeholder flags stay because they depend on the call). Chains report `reg.flags()` in `ChainResult.flags` after reading.
5. `Sr570V2f` reads `sr570.electronics_rel`.
6. `cmc_guarded.CmcGuarded` keeps importing from `calc/`; it only gets `reg=None` pass-through.
7. Adapt `tests/test_fluxor.py`: the `BeamSize` class is replaced by the registry-override version in Task 5; for now delete `test_flags_say_where_the_beam_size_came_from` and `test_loss_scales_as_height_over_width_and_not_with_a_uniform_scale`, and change the assertions on `gain_accuracy_placeholder` and `beam_size_assumed_for_recombination` to `assumed:tetramm.gain_rel`, `assumed:fx4.gain_rel`, and `assumed:beam.aspect_central`.

- [ ] **Step 4: Run the whole suite**

Run: `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 -m unittest discover -s tests -t .`
Expected: all tests OK (regression, chain, chamber, evaluate, registry). The regression numbers must not move: 4.37e6 ph/s per Hz at 10 keV within 1 %.

- [ ] **Step 5: Commit**

```bash
git add fluxor tests
git commit -m "fluxor: all non-code numbers move into parameters.toml; chambers and chains read the registry"
```

---

### Task 3: Generated PARAMETERS.md replaces the hand-written assumptions list

**Files:**
- Create: `fluxor/make_parameters_md.py`, `fluxor/PARAMETERS.md` (generated)
- Modify: `fluxor/ASSUMPTIONS.md` (header only: superseded note), `fluxor/HANDOFF.md`
- Test: `tests/test_params.py`

**Interfaces:**
- Consumes: `params.default()`, `Registry.names()`, `Registry.param(name)`.
- Produces: `make_parameters_md.render(reg) -> str` (deterministic, sorted by tag then name), `make_parameters_md.main()` writing `fluxor/PARAMETERS.md`.

- [ ] **Step 1: Write the failing test**

```python
class ParametersMdTests(unittest.TestCase):
    def test_generated_file_is_current(self):
        from fluxor import make_parameters_md
        text = (ROOT / "fluxor" / "PARAMETERS.md").read_text(encoding="utf-8")
        self.assertEqual(text, make_parameters_md.render(params.default()))

    def test_render_lists_flagged_rows_first_with_how_to_close(self):
        from fluxor import make_parameters_md
        out = make_parameters_md.render(params.default())
        self.assertLess(out.index("ASSUMED"), out.index("GIVEN"))
        self.assertIn("closes with", out.lower())
```

- [ ] **Step 2: Run to verify it fails** (`ModuleNotFoundError: fluxor.make_parameters_md`)

Run: `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 -m unittest tests.test_params.ParametersMdTests -v`

- [ ] **Step 3: Implement**

```python
# fluxor/make_parameters_md.py
r"""Write fluxor/PARAMETERS.md from fluxor/parameters.toml.

Run: <bluesky venv>\Scripts\python.exe -I -X utf8 fluxor/make_parameters_md.py
The file is generated: edit parameters.toml, then rerun this. A test fails if the file is out of date.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fluxor import params  # noqa: E402

ORDER = ("ASSUMED", "PROVISIONAL", "CHOICE", "DERIVED", "MEASURED", "GIVEN")
HEAD = """# fluxor parameters (generated from parameters.toml: do not edit)

Every number the package uses that is not code. ASSUMED and PROVISIONAL rows raise an `assumed:<name>` flag in every result
that uses them. To improve one, edit its row in `parameters.toml` (new value, tag MEASURED, source, date), then run
`python -I -X utf8 fluxor/make_parameters_md.py`. `legacy` is the id in the old hand-written ASSUMPTIONS.md.

"""


def render(reg):
    out = [HEAD]
    for tag in ORDER:
        rows = [reg.param(n) for n in reg.names() if reg.param(n).tag == tag]
        if not rows:
            continue
        out.append(f"## {tag}\n\n| name | value | sigma | unit | source (date) | closes with | legacy |\n|---|---|---|---|---|---|---|\n")
        for p in rows:
            out.append(f"| `{p.name}` | {p.value} | {'' if p.sigma is None else p.sigma} | {p.unit} | {p.source} ({p.date}) | "
                       f"{p.closes_with} | {p.legacy_id} |\n")
        out.append("\n")
    return "".join(out)


def main():
    path = Path(__file__).resolve().parent / "PARAMETERS.md"
    path.write_text(render(params.default()), encoding="utf-8", newline="")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
```

Then run the generator once, replace the first line of `fluxor/ASSUMPTIONS.md` with `> Superseded 2026-11-14 by PARAMETERS.md (generated from parameters.toml). Kept for the A-ids and their reasoning; do not add rows here.` plus the old title, and add a HANDOFF.md line under "Files" for `parameters.toml`, `params.py`, `make_parameters_md.py`.

- [ ] **Step 4: Run to verify they pass**

Run: `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 fluxor/make_parameters_md.py` then `... -m unittest discover -s tests -t .`
Expected: `wrote ...PARAMETERS.md`; all tests OK.

- [ ] **Step 5: Commit**

```bash
git add fluxor tests
git commit -m "fluxor: PARAMETERS.md generated from the registry; ASSUMPTIONS.md marked superseded"
```

---

### Task 4: Photon spectrum support (harmonics can be added later)

**Files:**
- Modify: `fluxor/parameters.toml` (add `spectrum.fractions`), `fluxor/chambers/base.py`, `fluxor/core.py`
- Test: `tests/test_fluxor.py`

**Interfaces:**
- Consumes: `IonChamber.flux` from Task 2.
- Produces: `IonChamber.flux(current_a, e_kev, p_kpa, t_c, spectrum=None)` where `spectrum` is a list of `(multiple_of_e, photon_fraction)` pairs summing to 1, default from the registry row `spectrum.fractions` (value `[[1.0, 1.0]]`, tag CHOICE, legacy A27, source the user's 2026-11-14 statement); `evaluate(..., spectrum=None)` passes it through. The returned flux is the TOTAL photons/s across components. The signal share of component i is `s_i = f_i E_i a_i / Σ f_j E_j a_j`; the wall loss is `Σ s_i Lw_i` (band edges weighted the same way); `detail["signal_share"]` lists the `s_i`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify they fail** (`TypeError: flux() got an unexpected keyword argument 'spectrum'`)

Run: `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 -m unittest tests.test_fluxor.Spectrum -v`

- [ ] **Step 3: Implement** in `IonChamber.flux`:

```python
    def flux(self, current_a, e_kev, p_kpa, t_c, spectrum=None):
        self.reg.reset_use()
        if spectrum is None:
            spectrum = [tuple(x) for x in self.reg.value("spectrum.fractions")]
        if abs(sum(f for _, f in spectrum) - 1.0) > 1e-9:
            raise ValueError("spectrum photon fractions must sum to 1")
        rho = k.density_g_cm3(p_kpa, t_c)
        weights, exits, comps = [], [], []
        for mult, frac in spectrum:
            en = e_kev * mult
            a = 1 - math.exp(-k.muen_over_rho(en) * rho * self.l_cm)
            weights.append(frac * en * a)
            exits.append(frac * math.exp(-k.mu_over_rho(en) * rho * self.l_cm))
            comps.append(en)
        total_w = sum(weights)
        phi_in = current_a * k.W_EV / (k.E_CHARGE * 1e3 * total_w)
        phi_exit = phi_in * sum(exits)
        shares = [w / total_w for w in weights]
        lo = c = hi = 0.0
        for share, en in zip(shares, comps):
            l_lo, l_c, l_hi = self.wall_loss(k.e_eff(en, rho))
            lo, c, hi = lo + share * l_lo, c + share * l_c, hi + share * l_hi
        # energy-range flag, symmetric terms, extra_flags_and_high: as before, then
        # flags += self.reg.flags(); detail["signal_share"] = shares
```

Keep the existing energy-range check on every component energy, the symmetric terms, `extra_flags_and_high`, and `absorbed_fraction` (fundamental's). `evaluate()` gains `spectrum=None` and forwards it (including to the `unit` calculation in the noisy branch).

- [ ] **Step 4: Run the whole suite** (all OK, the earlier regression numbers unchanged)

- [ ] **Step 5: Commit**

```bash
git add fluxor tests
git commit -m "fluxor: photon spectrum input (harmonics can be added); default pure fundamental, flagged"
```

---

### Task 5: Recombination as a central value and a range over the beam aspect ratio

**Files:**
- Modify: `fluxor/chambers/ic500_50.py`, `fluxor/core.py`
- Test: `tests/test_fluxor.py` (new `BeamSize` class replacing the deleted one)

**Interfaces:**
- Consumes: registry rows `beam.width_mm`, `beam.aspect_central`, `beam.aspect_low`, `beam.aspect_high`, `recomb.apply_to_best` (Task 2) and `recombination_loss(current_a, gap_cm, volts, beam_h_cm, beam_w_cm, length_cm, ...)` (existing).
- Produces: `ChamberResult.recomb_best`, `recomb_low`, `recomb_high` (loss fractions at the central, low and high aspect ratios); `Result.flux_best = flux_formula / ((1 - wall_loss) * (1 - recomb_best))` when `recomb.apply_to_best` is true; `flux_low` uses `recomb_low`, `flux_high` uses `recomb_high`; `detail["chamber"]` carries all three; formula validity flag when any of them exceeds 0.1.

- [ ] **Step 1: Write the failing tests**

```python
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
        from fluxor.core import evaluate
        chain = tetramm.TetraMM(("c3", "c4"), darks={"c3": 0.0, "c4": 0.0}, dark_age_h=1)
        r = evaluate(ic500_50.Ic500_50(), chain, {"channels": {"c3": 2400.0, "c4": 1600.0}}, 10.0, SITE_P, SITE_T)
        d = r.detail["chamber"]
        self.assertAlmostEqual(r.flux_best, r.flux_formula / (1 - d["recomb_central"]), delta=1e-9 * r.flux_best)
        self.assertLess(r.flux_low, r.flux_best)
        self.assertGreater(r.flux_high, r.flux_best)

    def test_turning_the_correction_off_is_one_registry_row(self):
        off = params.default().replaced("recomb.apply_to_best", False, tag="CHOICE", source="user veto")
        from fluxor.core import evaluate
        chain = tetramm.TetraMM(("c3", "c4"), darks={"c3": 0.0, "c4": 0.0}, dark_age_h=1)
        r = evaluate(ic500_50.Ic500_50(reg=off), chain, {"channels": {"c3": 2400.0, "c4": 1600.0}}, 10.0, SITE_P, SITE_T)
        self.assertAlmostEqual(r.flux_best, r.flux_formula, delta=1e-9 * r.flux_best)

    def test_a_beam_taller_than_the_gap_is_capped_and_flagged(self):
        reg = params.default().replaced("beam.width_mm", 40.0).replaced("beam.aspect_central", 1.0)
        r = self.result(reg)
        self.assertEqual(r.detail["beam_h_cm"], 1.0)
        self.assertIn("beam_taller_than_30_percent_of_gap_formula_weak", r.flags)
```

(Add `from fluxor import params` at the top of `tests/test_fluxor.py`.)

- [ ] **Step 2: Run to verify they fail** (`KeyError: 'recomb_central'`)

- [ ] **Step 3: Implement.** In `Ic500_50.extra_flags_and_high`, compute `w = beam.width_mm / 10`; for each of `aspect_low`, `aspect_central`, `aspect_high`: `h = min(aspect * w, gap_cm)`, `r = recombination_loss(current_a, gap_cm, volts, h, w, l_cm, alpha, k, k)`. Return flags (`beam_taller_than_30_percent_of_gap_formula_weak` if the central `h` exceeds 0.3 × gap, `recombination_over_1_percent` / `recombination_formula_not_valid` from the HIGH value) and `detail = {"recomb_low": r_lo, "recomb_central": r_c, "recomb_high": r_hi, "beam_h_cm": h_central, "beam_w_cm": w}`. Replace `high_extra` in `ChamberResult` by the three loss fields (`recomb_best`, `recomb_low`, `recomb_high`, each capped at 0.5). In `evaluate()`:

```python
    apply = chamber.reg.value("recomb.apply_to_best")
    best = p / ((1 - ch.wall_loss) * (1 - (ch.recomb_best if apply else 0.0)))
    low = p * max(1 - sigma, 0.0) / ((1 - ch.wall_lo) * (1 - ch.recomb_low))
    high = p * (1 + sigma) / ((1 - ch.wall_hi) * (1 - ch.recomb_high))
```

The noisy-current branch uses the same `(1 - recomb_high)`. The `CmcGuarded` chamber returns zeros for the three fields.

- [ ] **Step 4: Run the whole suite** (all OK; the MonP regression numbers are unchanged because `CmcGuarded` has no recombination)

- [ ] **Step 5: Commit**

```bash
git add fluxor tests
git commit -m "fluxor: recombination as central value and aspect-ratio range; best estimate carries the central correction"
```

---

### Task 6: Rename "windows", move the step-6 rerun onto the registry, and record the new results

**Files:**
- Rename: `data/estation/clean_windows_2026-11.csv` → `data/estation/beam_on_periods_2026-11.csv`
- Modify: `analysis/estation_step6.py`, `fluxor/OPERATOR.md`, `fluxor/HANDOFF.md`, `docs/superpowers/specs/2026-11-13-ic500-chains-design.md`
- Output: `analysis/out/estation_step6.csv`, `analysis/out/estation_step6.txt`

**Interfaces:**
- Consumes: `Ic500_50(reg=...)`, `evaluate(..., spectrum=None)`, the registry rows, the CSV columns `start_utc, minutes, energy_kev, net_ch3_nA, net_ch4_nA, slit_h_mm, slit_v_mm, dark3_before, dark3_after, dark4_before, dark4_after` (unchanged).
- Produces: `analysis/out/estation_step6.csv` columns `start_utc, energy_kev, current_nA, flux_best, flux_low, flux_high, sigma_rel, wall_loss, recomb_low, recomb_central, recomb_high, flags`.

- [ ] **Step 1: Write the failing test** (`tests/test_fluxor.py`)

```python
class Step6Rerun(unittest.TestCase):
    def test_script_runs_on_the_registry_and_orders_the_bounds(self):
        import csv
        sys.path.insert(0, str(ROOT / "analysis"))
        import estation_step6
        estation_step6.main()
        rows = list(csv.DictReader(open(ROOT / "analysis/out/estation_step6.csv", encoding="utf-8")))
        self.assertEqual(len(rows), 7)
        for r in rows:
            self.assertLess(float(r["flux_low"]), float(r["flux_best"]))
            self.assertLess(float(r["flux_best"]), float(r["flux_high"]))
            self.assertLess(float(r["recomb_low"]), float(r["recomb_high"]))
            self.assertIn("assumed:gas.p_kpa", r["flags"])
```

- [ ] **Step 2: Run to verify it fails** (`KeyError: 'recomb_low'` or file not found)

- [ ] **Step 3: Implement.** `git mv` the CSV; in `estation_step6.py` drop `Ic500_50(beam_h_mm=..., ...)`, read the gas conditions from `params.default().value("gas.p_kpa")` and `gas.t_c` (so improving them is a registry edit), construct `Ic500_50()`, write the new CSV columns, and replace the aspect-ratio sensitivity table by the registry's three aspect values. Every "window" in `estation_step6.py`, `OPERATOR.md`, `HANDOFF.md` and the spec becomes "beam-on period"; add to the HANDOFF.md glossary: `beam-on period (was "window", renamed 2026-11-14): a stretch of the archive in which the E-station chamber saw beam, with constant energy and slits and a dark measurement on both sides; the Experimenter's script keeps the old name estation_windows.py`.

- [ ] **Step 4: Run the script and the whole suite**

Run: `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 analysis/estation_step6.py` then `... -m unittest discover -s tests -t .`
Expected: a 7-row table with the best estimate now including the central recombination correction (about +1 % at aspect 0.1), bounds spanning aspect 0.03 to 1.0; all tests OK. Record the new numbers in the spec's step 6 row.

- [ ] **Step 5: Commit**

```bash
git add analysis data docs fluxor tests
git commit -m "fluxor: step 6 rerun on the registry; windows renamed beam-on periods"
```

---

### Task 7: Operator and handoff documentation, progress and plan rows

**Files:**
- Modify: `fluxor/OPERATOR.md`, `fluxor/HANDOFF.md`, `PLAN.md` (new rows), `PROGRESS.md` (new entry), `docs/superpowers/specs/2026-11-13-ic500-chains-design.md` (status)

- [ ] **Step 1: OPERATOR.md** gets a new section "How to replace an assumed number" with this exact worked example:

```text
1. Find the row in fluxor/PARAMETERS.md (the flag says which: assumed:gas.p_kpa).
2. Edit that row in fluxor/parameters.toml: new value, tag = "MEASURED", source = "what you measured it with", date.
3. Run: python -I -X utf8 fluxor/make_parameters_md.py   then   python -I -X utf8 -m unittest discover -s tests -t .
4. The flag assumed:gas.p_kpa no longer appears in results, and the flux changes accordingly.
```

and the flag table gains the `assumed:<name>` row ("the result used a number nobody measured: look it up in PARAMETERS.md") and drops the retired `gain_accuracy_placeholder` and `beam_size_assumed_for_recombination`.

- [ ] **Step 2: HANDOFF.md** gets the registry design (files, flag mechanism, the `replaced()` override for what-if runs, the spectrum input, the recombination range and the decision `recomb.apply_to_best`, dated 2026-11-14 with the user's direction quoted), and the trap: "a row's `value` in the TOML is the only copy; do not re-introduce a constant in code".

- [ ] **Step 3: PLAN.md** gets a row: `| 2026-11-14 | Parameter framework for fluxor: assumptions move into a tagged registry, spectrum input, recombination range; best estimate carries the central recombination correction. User: "make a plan to implement with assumptions chosen wisely and recorded. we need a framework that works that we can add better numbers to later." Plan: docs/superpowers/plans/2026-11-14-fluxor-parameter-framework.md. | user |`

- [ ] **Step 4: PROGRESS.md** gets one appended entry in the CLAUDE.md format with the evidence lines from Tasks 1 to 6 (test counts, the regression number, the step-6 table headline).

- [ ] **Step 5: Verify and commit**

Run: `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 -m unittest discover -s tests -t .` and `git grep -n "sbmE\|WB_SL2\|ID15A\|15ID1" -- fluxor docs data/estation analysis/estation_step6.py PLAN.md` (the second must print nothing new).

```bash
git add -A fluxor docs PLAN.md PROGRESS.md
git commit -m "fluxor: parameter framework docs, plan row, progress entry"
```

---

## Self-review

- **Spec coverage:** registry and flags (Task 1 and 2); every assumption recorded with how it closes (Task 2 rows, Task 3 generated list); harmonic content (Task 4); beam-size unknown handled as a range (Task 5); gas stand-ins as registry rows the user can replace (Task 1); "windows" renamed (Task 6); docs and the upgrade drill (Task 7). The Kapton and air path remain out of scope, as in the spec.
- **Placeholder scan:** no TBD or "similar to" steps. Task 2's registry rows are listed with exact values; their `source` and `closes_with` texts are copied from existing code comments and `ASSUMPTIONS.md` cells, named as the source in the step.
- **Type consistency:** `Registry.value/flags/reset_use/replaced`, `IonChamber.__init__(reg)`, `flux(..., spectrum=None)`, `ChamberResult.recomb_best/low/high`, and `detail["recomb_low"/"recomb_central"/"recomb_high"]` are used with the same names in Tasks 2 to 6. - **Open items the plan does not close** (they need the user, not code): the beam's real aspect ratio, chamber gas pressure and temperature, vendor drawing for `l_eff`, instrument order codes, and one trusted flux number.
