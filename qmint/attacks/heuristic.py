"""Heuristic (non-optimal unless stated) attacks with exact analytics and Monte Carlo.

Every attack is a per-qubit channel given by Kraus operators K: C^2 -> C^2 (x) C^2 with
output ordering (out1, out2), so it can be adapted to any challenger exposing per-qubit
channel application. Monte Carlo draws a FRESH secret note per trial (never repeated shots
of one secret instance). MC rates are lower bounds on the worst-case adversary only.

Attack ids follow master plan Sec. 3.2:
  A01 basis-guess measure/resend (naive resend, and Bayes-optimal resend)
  A02 Breidbart (pi/8) measurement + resend (naive and Bayes-optimal)
  A03 universal Buzek-Hillery cloner; economical phase-covariant cloner for the x-z circle
  A04 MVW Sec. 3.2 optimal channel (achieves the W1 optimum 3/4 per qubit)
  A06 split-and-report-loss against the toy W2 threshold/loss verifier
  A08 adaptive accept/reject oracle probing (toy leaky verifier, OUT_OF_MODEL for W1)
  CTRL secret-basis leak (OUT_OF_MODEL negative control)
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from qmint.attacks.coherent_sdp import mvw_optimal_kraus
from qmint.attacks.games import (
    LeakyOracleChallenger,
    NoteRegister,
    ThresholdLossChallenger,
    W1Challenger,
    fresh_note,
)
from qmint.attacks.linalg import BB84_LABELS, apply_kraus, ket, proj

# --------------------------------------------------------------------------- #
# Kraus constructions (per qubit, C^2 -> C^2 (x) C^2)
# --------------------------------------------------------------------------- #


def measure_prepare_kraus(meas: Sequence[np.ndarray], prepared: Sequence[np.ndarray], weight: float = 1.0) -> list[np.ndarray]:
    """K_m = sqrt(weight) |phi_m><e_m|; ``meas`` kets e_m (2-dim), ``prepared`` kets phi_m (4-dim)."""
    return [np.sqrt(weight) * np.outer(p, e.conj()) for e, p in zip(meas, prepared, strict=True)]


def _z() -> list[np.ndarray]:
    return [ket("0"), ket("1")]


def _x() -> list[np.ndarray]:
    return [ket("+"), ket("-")]


def breidbart_basis() -> list[np.ndarray]:
    c, s = math.cos(math.pi / 8), math.sin(math.pi / 8)
    return [np.array([c, s], dtype=complex), np.array([-s, c], dtype=complex)]


def bayes_resend(meas: Sequence[np.ndarray], weight: float = 1.0) -> list[np.ndarray]:
    """For each outcome, resend the top eigenvector of sum_s p(s|m) rho_s (x) rho_s (exact optimum
    of the resend step for a FIXED measurement; the measurement itself is not optimised)."""
    prepared = []
    for e in meas:
        m = weight * proj(e)
        a = sum(0.25 * np.real(np.trace(m @ proj(ket(s)))) * np.kron(proj(ket(s)), proj(ket(s))) for s in BB84_LABELS)
        _, vecs = np.linalg.eigh(a)
        prepared.append(vecs[:, -1])
    return measure_prepare_kraus(meas, prepared, weight)


def a01_kraus(bayes: bool = False) -> list[np.ndarray]:
    """Guess Z or X with prob 1/2, measure, resend two copies."""
    if bayes:
        return bayes_resend(_z(), 0.5) + bayes_resend(_x(), 0.5)
    z = measure_prepare_kraus(_z(), [np.kron(v, v) for v in _z()], 0.5)
    x = measure_prepare_kraus(_x(), [np.kron(v, v) for v in _x()], 0.5)
    return z + x


def a02_kraus(bayes: bool = False) -> list[np.ndarray]:
    b = breidbart_basis()
    return bayes_resend(b) if bayes else measure_prepare_kraus(b, [np.kron(v, v) for v in b])


def buzek_hillery_kraus() -> list[np.ndarray]:
    """Universal symmetric 1->2 qubit cloner as two Kraus ops (MVW 2012 Sec. 3.3, p.8)."""
    a0 = np.array([[2, 0], [0, 1], [0, 1], [0, 0]], dtype=complex) / np.sqrt(6)
    a1 = np.array([[0, 0], [1, 0], [1, 0], [0, 2]], dtype=complex) / np.sqrt(6)
    return [a0, a1]


def phase_covariant_xz_kraus() -> list[np.ndarray]:
    """Economical (ancilla-free) symmetric phase-covariant cloner, |0>->|00>,
    |1>->(|01>+|10>)/sqrt2 (Bruss, Cinchetti, D'Ariano, Macchiavello, PRA 62, 012302 (2000);
    optimal for the x-y equator), conjugated by V = Rx(pi/2) so that it covers the x-z great
    circle that contains the four BB84 states. Not claimed optimal for W1's joint figure of merit."""
    s = 1 / np.sqrt(2)
    iso = np.array([[1, 0], [0, s], [0, s], [0, 0]], dtype=complex)
    v = np.array([[s, -1j * s], [-1j * s, s]], dtype=complex)  # Rx(pi/2)
    return [np.kron(v.conj().T, v.conj().T) @ iso @ v]


def keep_original_kraus(lane: int) -> list[np.ndarray]:
    """Original qubit to ``lane`` (0 or 1), |0> blank to the other lane."""
    blank = np.array([[1], [0]], dtype=complex)
    return [np.kron(np.eye(2), blank) if lane == 0 else np.kron(blank, np.eye(2))]


#: Named per-qubit 1->2 attacks for game W1.
W1_PRODUCT_ATTACKS: dict[str, tuple[Callable[[], list[np.ndarray]], str]] = {
    "A01_basis_guess_resend": (a01_kraus, "random Z/X measurement, resend |m>|m>"),
    "A01b_basis_guess_bayes_resend": (lambda: a01_kraus(True), "random Z/X measurement, Bayes-optimal 2-qubit resend"),
    "A02_breidbart_resend": (a02_kraus, "Breidbart pi/8 basis measurement, resend |b_m>|b_m>"),
    "A02b_breidbart_bayes_resend": (lambda: a02_kraus(True), "Breidbart measurement, Bayes-optimal resend"),
    "A03_universal_buzek_hillery": (buzek_hillery_kraus, "universal symmetric 1->2 cloner (Buzek-Hillery)"),
    "A03b_phase_covariant_xz": (phase_covariant_xz_kraus, "economical phase-covariant cloner on x-z circle"),
    "A04_mvw_optimal_channel": (mvw_optimal_kraus, "MVW 2012 Sec. 3.2 explicit optimal channel"),
}

# --------------------------------------------------------------------------- #
# Exact analytics
# --------------------------------------------------------------------------- #


def joint_outcome_probs(kraus: Sequence[np.ndarray]) -> dict[str, float]:
    """Per-position joint verification-outcome distribution averaged over the uniform BB84
    secret: keys 'pp','pf','fp','ff' (copy1 pass/fail, copy2 pass/fail)."""
    out = {"pp": 0.0, "pf": 0.0, "fp": 0.0, "ff": 0.0}
    for s in BB84_LABELS:
        r = proj(ket(s))
        sig = apply_kraus(kraus, r)
        q = np.eye(2) - r
        for key, (a, b) in {"pp": (r, r), "pf": (r, q), "fp": (q, r), "ff": (q, q)}.items():
            out[key] += 0.25 * float(np.real(np.trace(np.kron(a, b) @ sig)))
    return out


def w1_product_exact(kraus: Sequence[np.ndarray], n: int) -> float:
    """Exact W1 both-pass probability of an i.i.d. per-qubit attack: p_pp^n."""
    return joint_outcome_probs(kraus)["pp"] ** n


def a06_exact(n: int, n_exclusive: int, max_loss_fraction: float, max_error_fraction: float) -> float:
    """Exact success of split-and-report-loss with MVW cloning on the shared positions."""
    ch = ThresholdLossChallenger(max_loss_fraction, max_error_fraction)
    max_lost, max_err = ch.allowed(n, n_exclusive)
    if n_exclusive > max_lost or 2 * n_exclusive > n:
        return 0.0
    m = n - 2 * n_exclusive
    jp = joint_outcome_probs(mvw_optimal_kraus())
    total = 0.0
    for c_pp in range(m + 1):
        for c_pf in range(m - c_pp + 1):
            for c_fp in range(m - c_pp - c_pf + 1):
                c_ff = m - c_pp - c_pf - c_fp
                err_a, err_b = c_fp + c_ff, c_pf + c_ff
                if err_a <= max_err and err_b <= max_err:
                    coef = math.factorial(m) / (
                        math.factorial(c_pp) * math.factorial(c_pf) * math.factorial(c_fp) * math.factorial(c_ff)
                    )
                    total += coef * jp["pp"] ** c_pp * jp["pf"] ** c_pf * jp["fp"] ** c_fp * jp["ff"] ** c_ff
    return total


def honest_acceptance_w2(n: int, eta_loss: float, q_error: float, max_loss_fraction: float, max_error_fraction: float) -> float:
    """Exact honest acceptance of the toy W2 verifier: i.i.d. loss eta, i.i.d. error q on detected."""
    ch = ThresholdLossChallenger(max_loss_fraction, max_error_fraction)
    total = 0.0
    for lost in range(n + 1):
        max_lost, max_err = ch.allowed(n, lost)
        if lost > max_lost:
            continue
        pl = math.comb(n, lost) * eta_loss**lost * (1 - eta_loss) ** (n - lost)
        k = n - lost
        pe = sum(math.comb(k, e) * q_error**e * (1 - q_error) ** (k - e) for e in range(min(max_err, k) + 1))
        total += pl * pe
    return total


def a08_exact(n: int, r: int) -> float:
    """Exact success of the A08 probing strategy: (1 - 2^-r)^n (error only when an X-basis
    qubit gives r identical Z-probe outcomes)."""
    return (1 - 2.0**-r) ** n


# --------------------------------------------------------------------------- #
# Monte Carlo runners (fresh secret note per trial)
# --------------------------------------------------------------------------- #


def _seeds(seed: int, trials: int) -> list[int]:
    return [int(x) for x in np.random.default_rng(seed).integers(0, 2**62, trials)]


def mc_w1_product_attack(
    kraus: Sequence[np.ndarray],
    n: int,
    trials: int,
    seed: int,
    challenger_factory: Callable[[], W1Challenger] = W1Challenger,
) -> int:
    """Number of trials in which BOTH candidates pass the W1 verifier."""
    wins = 0
    for s in _seeds(seed, trials):
        ch = challenger_factory()
        note = ch.mint(n, s)
        note.apply_channel(kraus)
        a = ch.verify(note.candidate(0))
        b = ch.verify(note.candidate(1))
        wins += a and b
    return wins


def a06_plan(n: int, max_loss_fraction: float) -> int:
    """Number of exclusive positions per candidate: as many as the loss budget allows."""
    return min(math.floor(max_loss_fraction * n + 1e-12), n // 2)


def mc_a06_split_loss(n: int, max_loss_fraction: float, max_error_fraction: float, trials: int, seed: int) -> int:
    k = a06_plan(n, max_loss_fraction)
    only_a = list(range(k))
    only_b = list(range(k, 2 * k))
    wins = 0
    for s in _seeds(seed, trials):
        ch = ThresholdLossChallenger(max_loss_fraction, max_error_fraction)
        note = ch.mint(n, s)
        chans = []
        for i in range(n):
            if i in only_a:
                chans.append(keep_original_kraus(0))
            elif i in only_b:
                chans.append(keep_original_kraus(1))
            else:
                chans.append(mvw_optimal_kraus())
        note.apply_position_channels(chans)
        # loss flags are fixed now, before any verification outcome exists
        a = ch.verify(note.candidate(0, loss_flags=only_b))
        b = ch.verify(note.candidate(1, loss_flags=only_a))
        wins += a and b
    return wins


@dataclass(frozen=True)
class OracleAttackStats:
    wins: int
    mean_queries: float


def a08_oracle_probe_once(ch: LeakyOracleChallenger, note: NoteRegister, r: int) -> list[str]:
    """Learn each position's BB84 label using only accept/reject bits of the leaky oracle."""
    learned = []
    for i in range(note.n_qubits()):
        held = note.detach(i)
        z_results = []
        for _ in range(r):
            note.attach(i, proj(ket("0")))
            z_results.append(ch.query_oracle(note))
        if all(z_results):
            label = "0"
        elif not any(z_results):
            label = "1"
        else:
            note.attach(i, proj(ket("+")))
            label = "+" if ch.query_oracle(note) else "-"
        note.attach(i, held)
        learned.append(label)
    return learned


def mc_a08_oracle(n: int, r: int, trials: int, seed: int) -> OracleAttackStats:
    wins = 0
    queries = 0
    for s in _seeds(seed, trials):
        ch = LeakyOracleChallenger()
        note = ch.mint(n, s)
        labels = a08_oracle_probe_once(ch, note, r)
        queries += ch.oracle_queries
        forged = [fresh_note([proj(ket(lab)) for lab in labels], note.record) for _ in range(2)]
        wins += ch.verify(forged[0]) and ch.verify(forged[1])
    return OracleAttackStats(wins, queries / trials)


def mc_secret_leak_control(n: int, trials: int, seed: int) -> int:
    """OUT_OF_MODEL: the attacker is (illegitimately) handed the issuer secret."""
    wins = 0
    for s in _seeds(seed, trials):
        ch = W1Challenger()
        note = ch.mint(n, s)
        sec = ch.leak_secret_out_of_model(note.record.token_id)
        labels = [{("Z", 0): "0", ("Z", 1): "1", ("X", 0): "+", ("X", 1): "-"}[(b, x)] for b, x in zip(sec["bases"], sec["bits"], strict=True)]  # type: ignore[call-overload]
        forged = [fresh_note([proj(ket(lab)) for lab in labels], note.record) for _ in range(2)]
        wins += ch.verify(forged[0]) and ch.verify(forged[1])
    return wins


def honest_acceptance_mc(n: int, trials: int, seed: int, challenger_factory: Callable[[], W1Challenger] = W1Challenger) -> int:
    wins = 0
    for s in _seeds(seed, trials):
        ch = challenger_factory()
        wins += ch.verify(ch.mint(n, s))
    return wins


def bit_order_swap_honest_acceptance(n: int = 2) -> float:
    """Exact honest acceptance if the verifier reads qubit positions in REVERSED order
    (an endianness bug): E_s prod_i |<s_i|s_{n-1-i}>|^2. 1.0 iff no bug."""
    total = 0.0
    for labels in itertools.product(BB84_LABELS, repeat=n):
        p = 1.0
        for i in range(n):
            p *= abs(np.vdot(ket(labels[i]), ket(labels[n - 1 - i]))) ** 2
        total += p / 4**n
    return total
