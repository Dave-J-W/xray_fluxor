"""evaluate(): one chain + one chamber -> photons/s at the chamber's reference plane, with bounds, budget and flags.

Rules (CLAUDE.md, user 2026-11-12): an imperfect number with a warning and a stated uncertainty is better than no number.
Nothing here withholds a value; doubt travels as flags and as bounds.
"""
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Term:
    name: str
    rel: float        # 1-sigma relative size, on the flux
    kind: str         # "A" statistical, "B" systematic
    note: str = ""


@dataclass
class ChainResult:
    current_a: float                 # signed, net of the dark
    abs_sigma_a: float               # absolute 1-sigma on the current (noise, residual offset), A
    terms: list = field(default_factory=list)      # relative Terms (gain etc.)
    flags: list = field(default_factory=list)
    channels_a: dict = field(default_factory=dict)  # per-channel net current, A (empty for single-channel chains)
    detail: dict = field(default_factory=dict)


@dataclass
class ChamberResult:
    flux_formula: float      # photons/s at the reference plane from the standard formula (no wall loss)
    wall_loss: float         # best estimate of the signal fraction lost to the plates
    wall_lo: float
    wall_hi: float
    terms: list = field(default_factory=list)      # symmetric relative Terms
    flags: list = field(default_factory=list)
    recomb_best: float = 0.0   # recombination loss fraction at the central beam aspect ratio (capped at 0.5)
    recomb_low: float = 0.0    # ... at the low aspect ratio (smallest loss)
    recomb_high: float = 0.0   # ... at the high aspect ratio (largest loss)
    detail: dict = field(default_factory=dict)


@dataclass
class Result:
    flux_best: float
    flux_low: float
    flux_high: float
    flux_formula: float
    current_a: float
    sigma_rel: float
    budget: list
    flags: list
    per_channel: dict
    detail: dict


def evaluate(chamber, chain, reading, energy_kev, p_kpa=None, t_c=None, spectrum=None, **chain_kw):
    c = chain.current(reading, **chain_kw)
    ch = chamber.flux(c.current_a, energy_kev, p_kpa, t_c, spectrum=spectrum)
    budget = list(c.terms) + list(ch.terms)
    i = abs(c.current_a)
    flags = list(c.flags) + list(ch.flags)
    noisy = i <= 3 * c.abs_sigma_a
    if not noisy:
        budget.append(Term("current noise/offset", c.abs_sigma_a / i, "A", "absolute sigma / current"))
        if c.current_a < 0:
            flags.append("negative_current")
    else:
        flags.append("current_within_3_sigma_of_zero")
    sigma = math.sqrt(sum(t.rel ** 2 for t in budget))
    p = ch.flux_formula
    apply = chamber.reg.value("recomb.apply_to_best")
    flags += [f for f in chamber.reg.flags() if f not in flags]       # the read above may itself be a flagged row
    # Bounds are built on |I| so that low <= best <= high; a negative current is mirrored afterwards.
    # With the correction off the best estimate carries no recombination, so the low bound carries none either;
    # the high bound always keeps the largest-aspect loss.
    r_best = ch.recomb_best if apply else 0.0
    r_low = ch.recomb_low if apply else 0.0
    pa = abs(p)
    best = p / ((1 - ch.wall_loss) * (1 - r_best))
    low = pa * max(1 - sigma, 0.0) / ((1 - ch.wall_lo) * (1 - r_low))
    high = pa * (1 + sigma) / ((1 - ch.wall_hi) * (1 - ch.recomb_high))
    if p < 0:
        low, high = -high, -low
    if noisy:
        # the relative noise term is meaningless near zero: bound the flux by the absolute noise instead
        unit = chamber.flux(1e-9, energy_kev, p_kpa, t_c, spectrum=spectrum).flux_formula / 1e-9      # photons/s per A (formula)
        high = unit * (max(c.current_a, 0.0) + c.abs_sigma_a) * (1 + sigma) / ((1 - ch.wall_hi) * (1 - ch.recomb_high))
        if c.current_a <= c.abs_sigma_a:
            low = 0.0
        best = max(best, 0.0)
    per = {}
    if c.channels_a and c.current_a != 0:
        for name, ia in c.channels_a.items():
            per[name] = best * ia / c.current_a
        flags.append("per_channel_flux_depends_on_beam_position")
    detail = {"chain": c.detail, "chamber": ch.detail}
    return Result(best, low, high, p, c.current_a, sigma, budget, flags, per, detail)
