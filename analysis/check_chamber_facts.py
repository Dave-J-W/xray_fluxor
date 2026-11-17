"""Check CHAMBER_FACTS.md against the code and tables that define each value (METHOD_REVIEW C1).

Every register row whose last cell holds a `python expression` is evaluated here, and the result must equal the
row's Value cell to the digits printed there. A row whose check cell is "register" has no other source: the register
itself is where that fact lives; only the IDs in REGISTER_ONLY may say so. Exit 1 on any mismatch, malformed row,
duplicate ID, unknown tag, or a "register" row that is not on REGISTER_ONLY.

Names available to the expressions:
  cg   analysis/cmc_chamber_geometry (cg.v(name), cg.slot_fit())     d    cg.derived()
  qs   calc/quality_slots                                             mt   calc/monp_transform
  fam  analysis/wall_loss_families.families()
  cal  data/calibration/monc_sr570_ranges.csv: {sensitivity: {column: float or ''}}
  hdr(regex)  first group of regex in that CSV's header, as a float
  leff analysis/out/collection_length_cmc.csv, nominal l_eff in mm
  lcase(case, column)  any cell of that CSV, e.g. lcase("beam_z_+1", "flux_deficit_pct")

Run: <bluesky venv>\\Scripts\\python.exe -X utf8 analysis/check_chamber_facts.py
"""
import csv
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "CHAMBER_FACTS.md"
CAL_CSV = ROOT / "data" / "calibration" / "monc_sr570_ranges.csv"
LEFF_CSV = ROOT / "analysis" / "out" / "collection_length_cmc.csv"
TAGS = {"MEASURED", "INTERPRETED", "ASSUMED", "GUESS-USER", "UNKNOWN", "DERIVED", "MODEL", "LIVE", "OBSERVED",
        "DECISION"}
# The only rows no file defines, so the register is their home (MonC state, V2F floors, the N1 acceptance, the MonP
# dark). Any other row with check "register" fails: it must point at its source (METHOD_REVIEW S1).
REGISTER_ONLY = {"F7.1", "F7.2", "F7.3", "F7.4", "F8.1", "F8.2", "F10.4", "F13.1"}

sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "calc"))
import cmc_chamber_geometry as cg  # noqa: E402
import monp_transform as mt  # noqa: E402
import quality_slots as qs  # noqa: E402
import wall_loss_families as wf  # noqa: E402


def _cal():
    lines = CAL_CSV.read_text(encoding="utf-8").splitlines()
    header = "\n".join(x for x in lines if x.startswith("#"))
    rows = csv.DictReader([x for x in lines if not x.startswith("#")])
    out = {}
    for r in rows:
        out[r["sensitivity"]] = {k: (float(v) if re.fullmatch(r"-?[\d.]+", v or "") else v) for k, v in r.items()}
    return out, header


def _leff(case="nominal", column="l_eff_mm"):
    for r in csv.DictReader(x for x in LEFF_CSV.read_text(encoding="utf-8").splitlines() if not x.startswith("#")):
        if r["case"] == case:
            return float(r[column])
    raise KeyError(case)


CAL, CAL_HEADER = _cal()


def hdr(pattern):
    m = re.search(pattern, CAL_HEADER)
    if not m:
        raise KeyError(pattern)
    return float(m.group(1))


NS = {"cg": cg, "d": cg.derived(), "qs": qs, "mt": mt, "fam": wf.families(), "cal": CAL, "hdr": hdr,
      "leff": _leff(), "lcase": _leff, "math": math}


def tokens(cell):
    """The Value cell as a list of numbers or strings: '17.9, 19.7, 1.17', '95.16 × 101.4 × 44.5', 'vertical'."""
    cell = cell.replace("−", "-").replace("**", "").strip()
    return [t.strip() for t in re.split(r",|×", cell) if t.strip()]


def as_number(t):
    try:
        return float(t)
    except ValueError:
        return None


def tolerance(t):
    """Half a unit in the last printed digit. A number written in a form this doesn't parse gets no tolerance at all
    (strict), never a loose default: '+0.62' once fell through to 0.5 and passed anything."""
    m = re.fullmatch(r"[+-]?(\d*)\.?(\d*)(?:[eE]([+-]?\d+))?", t)
    if not m:
        return 1e-12
    dec = len(m.group(2))
    exp = int(m.group(3)) if m.group(3) else 0
    return 0.5 * 10 ** (exp - dec) + 1e-12


def same(want, got):
    if not isinstance(got, (list, tuple)):
        got = [got]
    got = list(got)
    if len(want) != len(got):
        return False
    for w, g in zip(want, got):
        n = as_number(w)
        if n is None or isinstance(g, str):
            if str(g) != w:
                return False
        elif abs(float(g) - n) > tolerance(w):
            return False
    return True


def rows():
    """Register table rows: | ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |.
    Every line that starts like a fact row is returned, whatever its cell count, so a malformed row is reported
    instead of silently dropped (METHOD_REVIEW S1)."""
    for line in REGISTER.read_text(encoding="utf-8").splitlines():
        if re.match(r"\s*\|\s*F\d+\.\d+\s*\|", line):
            yield [c.strip() for c in line.strip().strip("|").split("|")]


def main():
    ok, seen, n_code, n_reg = True, set(), 0, 0
    for c in rows():
        if len(c) != 9:
            print(f"  MALFORMED {c[0]}: {len(c)} cells, want 9 (a '|' inside a cell, or a cell missing)")
            ok = False
            continue
        fid, fact, value, tag, check = c[0], c[1], c[2], c[5], c[8]
        if check == "register" and fid not in REGISTER_ONLY:
            print(f"  NOT ALLOWED {fid}: check is 'register', but {fid} is not on REGISTER_ONLY; give it its source "
                  f"expression, or add it to the list if no file defines it")
            ok = False
        if fid in REGISTER_ONLY and check != "register":
            print(f"  REGISTER_ONLY {fid} now has a check; take it off the list")
            ok = False
        if fid in seen:
            print(f"  DUPLICATE {fid}")
            ok = False
        seen.add(fid)
        if tag.split()[0].strip("*") not in TAGS:
            print(f"  UNKNOWN TAG {fid}: {tag}")
            ok = False
        if check == "register":
            n_reg += 1
            continue
        m = re.fullmatch(r"`(.+)`", check)
        if not m:
            print(f"  NO CHECK {fid}: {check!r} (a `python expression` or 'register')")
            ok = False
            continue
        try:
            got = eval(m.group(1), NS)  # noqa: S307 - our own tracked file
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {fid}: {m.group(1)} -> {e!r}")
            ok = False
            continue
        n_code += 1
        if not same(tokens(value), got):
            print(f"  DIFFERS {fid} {fact}: register {value!r}, source {got!r}  ({m.group(1)})")
            ok = False
    for fid in sorted(REGISTER_ONLY - seen):
        print(f"  MISSING {fid}: on REGISTER_ONLY but not in the register")
        ok = False
    print(f"CHAMBER_FACTS.md: {len(seen)} facts, {n_code} checked against code or tables, {n_reg} defined in the "
          f"register itself")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
