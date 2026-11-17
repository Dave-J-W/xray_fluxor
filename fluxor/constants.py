"""Physical constants and N2 cross sections shared by every chamber. Provenance: physics_note.md, data/queries/."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data" / "queries"))

W_EV = 34.8                  # physics_note section 2.1
E_CHARGE = 1.602176634e-19   # exact
R_GAS = 8.314462618
M_N2 = 28.0134               # g/mol
RHO0_G_CM3 = 1.1221e-3       # reference density of the wall-loss MC (99.26 kPa, 24.9 C)
RANGE_EXP = 0.568            # CSDA range ~ T^1.76 / rho
NIST_N = ROOT / "data" / "queries" / "nist_hubbell_seltzer" / "z07_nitrogen.html"

_table = None


def density_g_cm3(p_kpa, t_c):
    """Ideal-gas N2 density."""
    return p_kpa * 1e3 * M_N2 / (R_GAS * (t_c + 273.15)) / 1e6


def _nist():
    global _table
    if _table is None:
        from query_cross_sections import parse_nist
        _table = parse_nist(NIST_N)
    return _table


def mu_over_rho(e_kev):
    """NIST Hubbell-Seltzer N mu/rho, cm2/g (column 1, as calc/monp_transform.full_physics), log-log interpolation."""
    from query_cross_sections import loglog_interp
    return loglog_interp(e_kev / 1e3, _nist(), 1)


def muen_over_rho(e_kev):
    """NIST mu_en/rho of N, cm2/g (column 2), log-log interpolation."""
    from query_cross_sections import loglog_interp
    return loglog_interp(e_kev / 1e3, _nist(), 2)


def e_eff(e_kev, rho_g_cm3):
    """Density-scaled energy at which the wall-loss fit is evaluated."""
    return e_kev * (RHO0_G_CM3 / rho_g_cm3) ** RANGE_EXP
