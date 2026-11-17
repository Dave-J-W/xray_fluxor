"""IonChamber: current, energy, gas conditions -> ChamberResult (photons/s at the reference plane, wall-loss band, terms).

Shared physics for a parallel-plate N2 chamber with a collection length l (cm): the signal current I carries
I*W/(e*E) ion pairs per absorbed photon; the absorbed fraction is f = 1 - exp(-mu_en rho l); the flux at the exit of the
collection region is the incident flux times exp(-mu rho l). Wall loss (photoelectrons into the plates above ~17 keV)
raises the best estimate by 1/(1 - Lw); its band is the live calc's formula (calc/quality_slots.BAND).
"""
import math

from fluxor import constants as k
from fluxor import params
from fluxor.core import ChamberResult, Term


class IonChamber:
    name = "ionchamber"
    l_cm = 6.0
    wall_fit = (None, None, None)      # (E0 keV, s keV, p): Lw = 1 - exp(-((E_eff-E0)/s)^p) above E0
    band = {"a": 0.9, "b": 0.07, "cap": 0.09, "k": 2, "floor": 0.05, "e_widen": 13}
    symmetric_terms = {}               # name -> (rel, kind, note)
    energy_range_kev = (4.9, 30.5)     # the live calc's status-bit-16 limits (quality_slots FLAG_BITS); outside it a flag is raised

    def __init__(self, reg=None):
        self.reg = reg or params.default()

    def _read_parameters(self):
        """Hook: a chamber that takes its numbers from the registry sets them here (called at the start of every flux())."""

    def wall_loss(self, e_eff):
        e0, s, p = self.wall_fit
        if e0 is None or e_eff <= e0:
            c = 0.0
        else:
            c = 1 - math.exp(-((e_eff - e0) / s) ** p)
        b = self.band
        lo = max(b["a"] * c - b["b"], 0.0)
        hi = c + min(b["cap"], b["k"] * c + b["floor"] * (e_eff > b["e_widen"]))
        return lo, c, hi

    def extra_flags_and_high(self, current_a, e_kev, p_kpa, t_c):
        """Hook for chamber-specific one-sided bounds (recombination). Returns (flags, (r_low, r_central, r_high), detail): recombination loss fractions at the low, central and high beam aspect ratio."""
        return [], (0.0, 0.0, 0.0), {}

    def flux(self, current_a, e_kev, p_kpa=None, t_c=None, spectrum=None):
        """p_kpa, t_c: the gas conditions; left as None they are read from the registry rows gas.p_kpa / gas.t_c (flagged
        stand-ins) and a "gas stand-in P,T" term is added from those rows' sigma.
        spectrum: list of (multiple_of_e, photon_fraction) summing to 1; default the registry row spectrum.fractions.
        The returned flux is the total photons/s across components; the signal share of component i is
        f_i E_i a_i / sum_j f_j E_j a_j, and the wall loss is the share-weighted sum."""
        self.reg.reset_use()
        self._read_parameters()
        if spectrum is None:
            spectrum = [tuple(x) for x in self.reg.value("spectrum.fractions")]
        if any(f < 0 for _, f in spectrum):
            raise ValueError("spectrum photon fractions must not be negative")
        if abs(sum(f for _, f in spectrum) - 1.0) > 1e-9:
            raise ValueError("spectrum photon fractions must sum to 1")
        stand_in = []                                   # relative contributions of the gas stand-ins (absolute sigma / value)
        if p_kpa is None:
            p_kpa = self.reg.value("gas.p_kpa")
            stand_in.append(self.reg.param("gas.p_kpa").sigma / p_kpa)
        if t_c is None:
            t_c = self.reg.value("gas.t_c")
            stand_in.append(self.reg.param("gas.t_c").sigma / (t_c + 273.15))
        rho = k.density_g_cm3(p_kpa, t_c)
        weights, exits, comps = [], [], []
        for mult, frac in spectrum:
            en = e_kev * mult
            a = 1 - math.exp(-k.muen_over_rho(en) * rho * self.l_cm)
            weights.append(frac * en * a)
            exits.append(frac * math.exp(-k.mu_over_rho(en) * rho * self.l_cm))
            comps.append(en)
        total_w = sum(weights)
        phi_in = current_a * k.W_EV / (k.E_CHARGE * 1e3 * total_w)
        phi_exit = phi_in * sum(exits)
        shares = [w / total_w for w in weights]
        lo = c = hi = 0.0
        for share, en in zip(shares, comps):
            l_lo, l_c, l_hi = self.wall_loss(k.e_eff(en, rho))
            lo, c, hi = lo + share * l_lo, c + share * l_c, hi + share * l_hi
        absorbed = 1 - math.exp(-k.muen_over_rho(e_kev) * rho * self.l_cm)      # the fundamental's
        flags = []
        lo_e, hi_e = self.energy_range_kev
        if any(not lo_e <= en <= hi_e for en in comps):
            flags.append("energy_outside_cross_section_range")
        f2, (r_lo, r_c, r_hi), d2 = self.extra_flags_and_high(current_a, e_kev, p_kpa, t_c)
        terms = [Term(n, v[0], v[1], v[2]) for n, v in self.symmetric_terms.items()]
        if stand_in:
            terms.append(Term("gas stand-in P,T", math.sqrt(sum(x * x for x in stand_in)), "B",
                              "registry rows gas.p_kpa / gas.t_c used because the caller gave no P or T; sigma from the rows"))
        return ChamberResult(phi_exit, c, lo, hi, terms, flags + f2 + self.reg.flags(),
                             min(r_c, 0.5), min(r_lo, 0.5), min(r_hi, 0.5),
                             {"rho_g_cm3": rho, "absorbed_fraction": absorbed, "phi_in": phi_in,
                              "signal_share": shares, **d2})
