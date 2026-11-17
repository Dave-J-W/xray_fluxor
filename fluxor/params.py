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


def _check_flagged(name, tag, closes_with):
    """The tag and closes_with rules, shared by load() and replaced()."""
    if tag not in TAGS:
        raise ValueError(f"{name}: tag {tag!r} is not one of {TAGS}")
    if tag in FLAGGED_TAGS and not closes_with:
        raise ValueError(f"{name}: a {tag} row must say how it closes (closes_with)")


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
            _check_flagged(name, row["tag"], row.get("closes_with"))
            out[name] = Param(name=name, **{k: v for k, v in row.items()})
        return cls(out)

    def param(self, name):
        return self._p[name]

    def names(self):
        return sorted(self._p)

    def value(self, name):
        v = self._p[name].value      # lookup first: a bad name raises here and is never recorded as used
        self.used.add(name)
        return v

    def reset_use(self):
        self.used.clear()

    def flags(self):
        return sorted(f"assumed:{n}" for n in self.used if self._p[n].tag in FLAGGED_TAGS)

    def replaced(self, name, value, tag="MEASURED", source="", date="", sigma=None, closes_with=None):
        old = self._p[name]
        new = replace(old, value=value, tag=tag, source=source or old.source, date=date or old.date,
                      sigma=old.sigma if sigma is None else sigma,
                      closes_with=old.closes_with if closes_with is None else closes_with)
        _check_flagged(name, new.tag, new.closes_with)
        out = dict(self._p)
        out[name] = new
        return Registry(out)


_default = None


def default():
    global _default
    if _default is None:
        _default = Registry.load()
    return _default
