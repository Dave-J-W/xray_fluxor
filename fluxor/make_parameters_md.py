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
