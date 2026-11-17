"""CAEN TetrAMM (4-channel, 24-bit, signed current): reading = per-channel mean values in the IOC's unit, settings in __init__.

Facts, with sources:
- Two ranges (manual 1.3): RNG 0 full scale +-120 uA, RNG 1 +-120 nA; LSB 15 (nA, pA) of the 24-bit ADC.
- Equivalent input noise vs sampling period (manual 5.1, model WTETRAMM05PX), ppm of full scale; the table's longest
  period is 10 ms (100 Hz). Used as the per-reading noise floor, no further 1/sqrt(N) credit (conservative, A9).
- User offset calibration I = gain*I_raw + offset on the unit (manual 1.7.1); the IOC also applies per-channel offsets.
  Either way the reading arrives net of whatever is applied, so this chain subtracts only the dark the CALLER measured.
NOT in the manuals' text: a gain accuracy figure for the user's order code. A placeholder is used and flagged
(the registry flag assumed:tetramm.gain_rel) until the order code and its table are entered (A10). Unit of the IOC values at the E-station:
nA (CurrentScale 1e9, Experimenter 2026-11-13); pass unit_a=1e-9.
"""
import math

from fluxor import params
from fluxor.core import ChainResult, Term

FULL_SCALE_A = {0: 120e-6, 1: 120e-9}
# ppm of full scale vs sampling period (s), from the manual's tables (typical values)
NOISE_PPM = {0: [(50e-6, 5.8), (100e-6, 2.8), (200e-6, 2.2), (500e-6, 1.7), (1e-3, 1.3), (2e-3, 1.1), (5e-3, 1.0), (10e-3, 0.7)],
             1: [(50e-6, 24.2), (100e-6, 19.6), (200e-6, 16.7), (500e-6, 12.9), (1e-3, 8.3), (2e-3, 5.8), (5e-3, 4.2), (10e-3, 1.8)]}


def noise_ppm(rng, sample_period_s):
    tab = NOISE_PPM[rng]
    p = min(max(sample_period_s, tab[0][0]), tab[-1][0])
    for (p0, n0), (p1, n1) in zip(tab, tab[1:]):
        if p0 <= p <= p1:
            f = (math.log(p) - math.log(p0)) / (math.log(p1) - math.log(p0))
            return math.exp(math.log(n0) + f * (math.log(n1) - math.log(n0)))
    return tab[-1][1]


class TetraMM:
    name = "TetrAMM"

    def __init__(self, signal_channels, rng=None, sample_period_s=10e-3, unit_a=None, darks=None,
                 dark_sigma_a=None, gain_rel=None, dark_age_h=None, reg=None):
        """An argument left as None is taken from the registry (tetramm.range, .unit_a, .dark_sigma_nA, .gain_rel); the rows used
        are re-read in current(), so their ASSUMED/PROVISIONAL flags travel with every result."""
        self.reg = reg or params.default()
        self._from_reg = []                       # registry rows standing in for arguments the caller did not give

        def pick(arg, name, scale=1.0):
            if arg is not None:
                return arg
            self._from_reg.append(name)
            return self.reg.param(name).value * scale
        self.signal_channels = tuple(signal_channels)
        self.rng = pick(rng, "tetramm.range")
        self.sample_period_s = sample_period_s
        self.unit_a = pick(unit_a, "tetramm.unit_a")
        self.darks = dict(darks or {})
        self.dark_sigma_a = pick(dark_sigma_a, "tetramm.dark_sigma_nA", 1e-9)
        self.gain_rel = pick(gain_rel, "tetramm.gain_rel")
        self.gain_given = gain_rel is not None
        self.dark_age_h = dark_age_h

    def current(self, reading, **kw):
        self.reg.reset_use()
        for name in self._from_reg:
            self.reg.value(name)
        fs = FULL_SCALE_A[self.rng]
        flags, chan = [], {}
        for ch in self.signal_channels:
            raw = reading["channels"][ch] * self.unit_a
            if abs(raw) >= 0.99 * fs:
                flags.append(f"overrange_{ch}")
            if ch not in self.darks:
                flags.append(f"dark_not_given_{ch}")
            chan[ch] = raw - self.darks.get(ch, 0.0) * self.unit_a
        n = len(self.signal_channels)
        noise_ch = noise_ppm(self.rng, self.sample_period_s) * 1e-6 * fs
        sigma = math.sqrt(n) * math.hypot(noise_ch, self.dark_sigma_a)
        if self.dark_age_h is None or self.dark_age_h > 24:
            flags.append("dark_stale_or_age_unknown")
        gain = self.gain_rel
        total = sum(chan.values())
        return ChainResult(current_a=total, abs_sigma_a=sigma,
                           terms=[Term("TetrAMM range gain", gain, "B", "given" if self.gain_given else "placeholder until the order code is entered")],
                           flags=flags + self.reg.flags(), channels_a=chan,
                           detail={"full_scale_a": fs, "noise_per_channel_a": noise_ch, "dark_sigma_a": self.dark_sigma_a})
