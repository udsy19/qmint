"""Reference calculator for *published ideal-model theorems*, not a security proof.

W1: Wiesner simple 1->2 counterfeit, Molina/Vidick/Watrous (2012),
    P(success both verify) = (3/4)^n, absent verification oracle.
W1-classical-verification-variant: (3/4 + sqrt(2)/8)^n (distinct game).
S1: two-site ideal S-money, Kent et al. (2022), (1/2 + 1/(2sqrt(2)))^N.

DO NOT apply ideal formulas to noisy, lossy, thresholded, or adaptive-oracle
protocols. This is a smoke/reference fixture for future proof-engine agents.
"""
from __future__ import annotations
import argparse
import math

BASES = {
    "W1": (0.75, "Wiesner simple 1->2 counterfeiting; exact private verifier"),
    "W1_CLASSICAL_VARIANT": (0.75 + math.sqrt(2) / 8, "Distinct Wiesner classical-verification variant"),
    "S1": (0.5 + 1 / (2 * math.sqrt(2)), "Ideal two-site S-money bound"),
}


def log10_bound(model: str, n: int) -> float:
    if model not in BASES:
        raise ValueError(f"Unsupported published ideal model: {model}")
    if not isinstance(n, int) or n < 1:
        raise ValueError("n must be a positive integer")
    return n * math.log10(BASES[model][0])


def min_length_for_target(model: str, epsilon: float) -> int:
    if model not in BASES:
        raise ValueError(f"Unsupported published ideal model: {model}")
    if not math.isfinite(epsilon) or not (0 < epsilon < 1):
        raise ValueError("target epsilon must be strictly between 0 and 1")
    return math.ceil(math.log(epsilon) / math.log(BASES[model][0]))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", type=float, default=1e-9)
    p.add_argument("--lengths", type=int, nargs="*", default=[1, 8, 16, 32, 64, 128])
    args = p.parse_args()
    print("THEORETICAL IDEAL-MODEL REFERENCE ONLY — NOT AN EXPERIMENTAL SECURITY CERTIFICATE")
    for model, (_, desc) in BASES.items():
        print(f"\n{model}: {desc}")
        print("n\tlog10(P_bound)")
        for n in args.lengths:
            print(f"{n}\t{log10_bound(model, n):.9f}")
        print(f"min n for epsilon <= {args.target:.1e}: {min_length_for_target(model, args.target)}")


if __name__ == "__main__":
    main()
