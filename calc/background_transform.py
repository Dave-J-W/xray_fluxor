"""Running estimate of MonP's no-beam background (dark rate) for utilioc: design, mirror, test.

The slot is a transform, 15IDC:util:userTran2, scanned every 1 s. It reads MonP's counts, count
time and SR570 gain from the MonP flux slot (15IDC:util:userTran1.A-D), so it adds **no new
outside links**.

Rule:
  - "No beam" means the raw MonP rate has stayed below a threshold F (default 400 Hz; the user's
    dark/light split) for more than G seconds (default 10 s). This covers both a closed shutter
    and a beam dump.
  - While that holds, every sample updates the estimate L. It is a plain running mean for the
    first I samples (default 60), then an exponential average with time constant I samples.
  - At all other times L holds its last value.
  - Each estimate is tagged with the SR570 gain it was taken at (M). The dark in Hz depends on
    the gain (the offset current is fixed in amps, and is re-tweaked by hand at gain changes).
    N = 1 flags "the estimate was taken at a different gain than now". The next dark period
    after a gain change restarts the mean.
  - The shutter PV is not used (user, 2026-11-12: its state is unreliable); the rate decides.

Letters (evaluated A->P; a letter used before it is computed holds its previous value: state):
  inputs   A counts (userTran1.A)    B count time s (userTran1.B)
           C sens_num idx (userTran1.C)   D sens_unit idx (userTran1.D)
  hand     F threshold Hz [400]   G settle s [10]   I averaging samples [60]
  computed E raw rate Hz          H seconds below threshold (run length)
           J gain code now        K samples in the current estimate
           L BACKGROUND ESTIMATE, Hz   M gain code of the estimate
           N stale flag (1: the estimate is at another gain, or none yet)
           O seconds since the estimate was last updated
           P background as an input current, A (valid while N = 0)
"""
import math
import random
import sys

SLOT = {
    "DESC": "MonP background Hz (xray_fluxor)",
    "SCAN": "1 second",
    "PREC": "3",
    "EGU": "Hz",
    "links": {
        "INPA": "15IDC:util:userTran1.A NPP NMS",
        "INPB": "15IDC:util:userTran1.B NPP NMS",
        "INPC": "15IDC:util:userTran1.C NPP NMS",
        "INPD": "15IDC:util:userTran1.D NPP NMS",
    },
    "values": {"F": 400.0, "G": 10.0, "I": 60.0},
    "expr": {
        "CLCE": "B>0?A/B:-1",
        "CLCH": "E>=0&&E<F?H+1:0",
        "CLCJ": "C+10*D",
        "CLCK": "H>G?(J#M?1:MIN(K+1,I)):K",
        "CLCL": "H>G?(K<2?E:L+(E-L)/K):L",
        "CLCM": "H>G?J:M",
        "CLCN": "M#J",
        "CLCO": "H>G?0:O+1",
        "CLCP": "(1+(C%3)^2)*10^(FLOOR(C/3)+3*D-17)*L",
    },
}
COMMENTS = {
    "A": "MonP counts (userTran1.A)", "B": "count time s (userTran1.B)",
    "C": "SR570 sens_num idx", "D": "SR570 sens_unit idx",
    "E": "raw MonP rate Hz", "F": "no-beam threshold Hz",
    "G": "settle time s", "H": "s below threshold",
    "I": "averaging samples", "J": "gain code now",
    "K": "samples in estimate", "L": "BACKGROUND estimate Hz",
    "M": "gain code of estimate", "N": "1=stale (other gain/none)",
    "O": "s since estimate updated", "P": "background current A",
}


def step(s, A, B, C, D):
    """One transform processing, mirroring SLOT['expr'] in order. `s` holds every letter."""
    s.update(A=A, B=B, C=C, D=D)
    s["E"] = A / B if B > 0 else -1
    s["H"] = s["H"] + 1 if (s["E"] >= 0 and s["E"] < s["F"]) else 0
    s["J"] = C + 10 * D
    if s["H"] > s["G"]:
        s["K"] = 1 if s["J"] != s["M"] else min(s["K"] + 1, s["I"])
        s["L"] = s["E"] if s["K"] < 2 else s["L"] + (s["E"] - s["L"]) / s["K"]
        s["M"] = s["J"]
    s["N"] = 1.0 if s["M"] != s["J"] else 0.0
    s["O"] = 0 if s["H"] > s["G"] else s["O"] + 1
    s["P"] = (1 + (int(C) % 3) ** 2) * 10 ** (math.floor(C / 3) + 3 * D - 17) * s["L"]
    return s


def new_state():
    s = {x: 0.0 for x in "ABCDEFGHIJKLMNOP"}
    s.update(SLOT["values"])
    return s


def test():
    """Simulated day: beam, shutter closed (dark 60 Hz), beam, gain change, dark at the new gain (25 Hz)."""
    random.seed(1)
    s = new_state()
    ok = True
    log = []

    def run(n, rate, c=8, d=1, noise=3.0):
        for _ in range(n):
            a = max(0.0, random.gauss(rate, noise if rate < 1000 else rate * 1e-3))
            step(s, a, 1.0, c, d)
        log.append((n, rate, c, d, round(s["L"], 2), s["K"], s["N"], s["O"], s["H"]))

    run(30, 75000)                      # beam: no estimate yet
    ok &= s["N"] == 1 and s["L"] == 0
    run(5, 60)                          # shutter just closed: still settling
    ok &= s["K"] == 0
    run(100, 60)                        # dark: estimate converges to 60
    ok &= abs(s["L"] - 60) < 1.5 and s["N"] == 0 and s["K"] == 60
    l_dark = s["L"]
    run(40, 75000)                      # beam back: L held, age counts up
    ok &= s["L"] == l_dark and s["O"] == 40
    run(20, 37000, c=0, d=2)            # gain changed to 1 uA/V: estimate now stale
    ok &= s["N"] == 1 and s["L"] == l_dark
    run(60, 25, c=0, d=2)               # dark at the new gain: mean restarts and converges to 25
    ok &= abs(s["L"] - 25) < 1.5 and s["N"] == 0
    for row in log:
        print("  ran %4d s at %7.0f Hz gain(c=%d,d=%d) -> L=%7.2f Hz K=%d stale=%d age=%d s H=%d" % row)
    print("current at 1 uA/V for L:", f"{s['P']:.3e} A")
    lens = {k: len(v) for k, v in {**SLOT['expr'], **SLOT['links']}.items()}
    ok &= all(v <= 39 for v in lens.values()) and len(SLOT["DESC"]) <= 39
    print("lengths:", lens)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(test())
