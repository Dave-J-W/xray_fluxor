"""MonP and MonC as built (guarded, l_eff 6.19 cm): wraps the live calc's constants so the package can be regression-tested
against the published numbers (RESULT.md). Constants come from calc/quality_slots.py and calc/monp_transform.py (read only).

Difference from the live calc, on purpose: this package interpolates NIST directly instead of the calc's cubic fit, so
the live "cross-section fit" term (0.9 %, a property of the 39-character expression) is not carried here; the live
"electronics" term belongs to the chain (chains/sr570_v2f.py).
"""
import sys

from fluxor import constants as k
from fluxor.chambers.base import IonChamber

sys.path.insert(0, str(k.ROOT / "calc"))
import monp_transform as mt  # noqa: E402
import quality_slots as qs  # noqa: E402

CHAMBER_ONLY_TERMS = {n: v for n, v in qs.SYMMETRIC_TERMS.items() if n not in ("electronics", "cross-section fit")}


class CmcGuarded(IonChamber):
    def __init__(self, lane="MonP", reg=None):
        super().__init__(reg)
        self.name = lane
        self.l_cm = mt.L_CM
        self.wall_fit = qs.WALL_FITS[lane]
        self.band = dict(qs.BAND)
        self.symmetric_terms = {n: (v, "B", "calc/quality_slots.SYMMETRIC_TERMS") for n, v in CHAMBER_ONLY_TERMS.items()}
