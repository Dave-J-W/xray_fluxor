"""Regenerate every figure: import each fig_*.py module in this folder and call its main()."""
import importlib
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402,F401  (sets paths and style)


def main():
    ok = True
    for f in sorted(HERE.glob("fig_*.py")):
        try:
            mod = importlib.import_module(f.stem)
            mod.main(common.OUT)
            print("OK  ", f.name)
        except Exception:
            ok = False
            print("FAIL", f.name)
            traceback.print_exc()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
