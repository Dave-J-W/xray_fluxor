"""SR570 -> N101VTF V2F (1e5 Hz/V, 0-10 V) -> scaler counts: the chain MonP and MonC use. Reference chain for the regression.

Reading: counts, time_s, sens_num (enum index 0..), sens_unit (0 pA, 1 nA, 2 uA, 3 mA per V), dark_hz.
Same arithmetic as the live calc (calc/monp_transform.py letters I and J).
"""
import math

from fluxor import params
from fluxor.core import ChainResult, Term

V2F_HZ_PER_V = 1e5


def sensitivity_a_per_v(num_idx, unit_idx):
    return (1 + (int(num_idx) % 3) ** 2) * 10 ** (math.floor(num_idx / 3) + 3 * unit_idx - 12)


class Sr570V2f:
    name = "SR570+V2F"

    def __init__(self, reg=None):
        self.reg = reg or params.default()

    def current(self, reading, **kw):
        self.reg.reset_use()
        t = reading["time_s"]
        rate = reading["counts"] / t if t > 0 else 0.0
        net = max(rate - reading.get("dark_hz", 0.0), 0.0)
        sens = sensitivity_a_per_v(reading["sens_num"], reading["sens_unit"])
        per_hz = sens / V2F_HZ_PER_V
        sigma_hz = math.sqrt(max(reading["counts"], 0)) / t if t > 0 else 0.0
        return ChainResult(current_a=net * per_hz, abs_sigma_a=sigma_hz * per_hz,
                           terms=[Term("electronics (SR570 gain x V2F)", self.reg.value("sr570.electronics_rel"), "B", "ELECTRONICS_CONCLUSIONS.md")],
                           flags=self.reg.flags(),
                           detail={"sens_a_per_v": sens, "net_rate_hz": net})
