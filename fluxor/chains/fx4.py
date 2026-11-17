"""Pyramid FX4 (4-channel electrometer, signed current): reading = per-channel current in A after the unit's own offset and
scalar, settings in __init__.

Facts, with sources (FX4 User Manual v1):
- Eight input ranges, one for all channels (5.1.1). Read from the manual's own GUI picture (page 26, 2026-11-16):
  0 = 100 nA (1 kHz BW), 1 = 100 nA (10 kHz BW), 2 = 1 uA (5 kHz BW), 3 = 1 uA (50 kHz BW), 4 = 10 uA, 5 = 100 uA,
  6 = 1 mA, 7 = 10 mA (all 50 kHz BW). The picture shows a unit with the 10 mA option; the manual text says the standard
  top is 3 mA and 10 mA is by special order, and the user's quote lists no special range, so range 7 is taken as
  3 mA and stays PROVISIONAL (A12).
- Resolution 3 pA per bit on 100 nA, 300 nA per bit on 10 mA (6.2): LSB = 2 FS / 65536.
- Conversion 1e5 Hz; sample frequency by averaging, so N = 1e5 / sample_hz conversions per reading (5.1.2).
- Offset drift with air temperature: under 0.03 % of a 50 nA reading from 25 to 40 C on range 0 (6.4), mostly offset.
- Recommended recalibration every 1-2 years (8.1).
NOT in the manual text: a gain accuracy or a noise table. The noise floor is the quantisation noise of the averaged ADC
(LSB/sqrt(12 N)), a LOWER bound flagged noise_from_resolution_only (A13); gain uses a flagged placeholder (A10,
registry row fx4.gain_rel).
"""
import math

from fluxor import params
from fluxor.core import ChainResult, Term

RANGES = {0: ("100 nA, 1 kHz BW", 100e-9), 1: ("100 nA, 10 kHz BW", 100e-9), 2: ("1 uA, 5 kHz BW", 1e-6),
          3: ("1 uA, 50 kHz BW", 1e-6), 4: ("10 uA", 10e-6), 5: ("100 uA", 100e-6), 6: ("1 mA", 1e-3),
          7: ("3 mA standard (10 mA special order)", 3e-3)}
PROVISIONAL_RANGES = (7,)
CONVERSION_HZ = 1e5


class Fx4:
    name = "FX4"

    def __init__(self, signal_channels, rng, sample_hz=10.0, darks=None, dark_sigma_a=None,
                 gain_rel=None, dark_age_h=None, reg=None):
        """dark_sigma_a and gain_rel left as None come from the registry (fx4.dark_sigma_a, fx4.gain_rel), re-read in current()."""
        self.reg = reg or params.default()
        self._from_reg = []
        if dark_sigma_a is None:
            self._from_reg.append("fx4.dark_sigma_a")
            dark_sigma_a = self.reg.param("fx4.dark_sigma_a").value
        self.gain_given = gain_rel is not None
        if gain_rel is None:
            self._from_reg.append("fx4.gain_rel")
            gain_rel = self.reg.param("fx4.gain_rel").value
        self.signal_channels = tuple(signal_channels)
        self.rng = rng
        self.sample_hz = sample_hz
        self.darks = dict(darks or {})            # A, per channel, measured by the caller (beam off, HV on)
        self.dark_sigma_a = dark_sigma_a
        self.gain_rel = gain_rel
        self.dark_age_h = dark_age_h

    def current(self, reading, temp_c=None, **kw):
        self.reg.reset_use()
        for name in self._from_reg:
            self.reg.value(name)
        fs = RANGES[self.rng][1]
        lsb = 2 * fs / 65536
        flags, chan = [], {}
        if self.rng in PROVISIONAL_RANGES:
            flags.append("range_full_scale_provisional")
        for ch in self.signal_channels:
            raw = reading["channels"][ch]
            if abs(raw) >= 0.99 * fs:
                flags.append(f"overrange_{ch}")
            if ch not in self.darks:
                flags.append(f"dark_not_given_{ch}")
            chan[ch] = raw - self.darks.get(ch, 0.0)
        n_avg = max(CONVERSION_HZ / self.sample_hz, 1.0)
        noise_ch = lsb / math.sqrt(12 * n_avg)
        flags.append("noise_from_resolution_only")
        temp_abs = 0.0
        if temp_c is not None:
            if not 15 <= temp_c <= 25:
                flags.append("temperature_outside_15_25C")
            temp_abs = 0.0003 * 50e-9 * abs(temp_c - 25) / 15      # 0.03 % of 50 nA per 15 C, as an offset
        n = len(self.signal_channels)
        sigma = math.sqrt(n) * math.sqrt(noise_ch ** 2 + self.dark_sigma_a ** 2 + temp_abs ** 2)
        if self.dark_age_h is None or self.dark_age_h > 24:
            flags.append("dark_stale_or_age_unknown")
        gain = self.gain_rel
        return ChainResult(current_a=sum(chan.values()), abs_sigma_a=sigma,
                           terms=[Term("FX4 range gain", gain, "B", "given" if self.gain_given else "placeholder until the model's accuracy table is entered")],
                           flags=flags + self.reg.flags(), channels_a=chan,
                           detail={"full_scale_a": fs, "lsb_a": lsb, "n_avg": n_avg, "noise_per_channel_a": noise_ch})
