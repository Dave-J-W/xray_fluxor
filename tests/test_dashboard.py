"""The flux dashboard (op/) is current: its .bob matches the generator and the model export adds up."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestDashboard(unittest.TestCase):
    def test_static_check_passes(self):
        r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "op" / "tests" / "check_dashboard.py"), "--static"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
