"""Factorized simulated qubit register and opaque token handles (lane B).

Shared by every protocol in ``qmint.protocols`` (Wiesner, Kent et al. 2022 S-money,
Schiansky et al. 2023 payments). The register stores the joint state as a product of
independent *blocks*; each block is a dense density matrix over a few qubits. Fresh BB84
tokens are products of 1-qubit blocks, so ``n = 128`` never builds a ``2^n`` vector;
blocks merge only when a channel acts jointly on qubits from several blocks.

Conventions (C7):
  * BB84 states come exclusively from ``qmint.quantum.bb84.state_vector`` (C7 map
    ``qmint.core.contracts.BB84_STATE_OF``): ``(Z,0)=|0>, (Z,1)=|1>, (X,0)=|+>, (X,1)=|->``.
  * Inside a block the first listed qubit is the most significant tensor factor
    (big-endian, ``kron(q0, q1, ...)``). No Qiskit little-endian decoding anywhere.

Simulator caveat (master plan section 6, "separate truth levels"): a simulator necessarily
holds classical matrices. Deep-copying a handle is a simulator artefact, NOT cloning. The
information boundary is enforced at the API level: handles never reference an
``IssuerSecret``; only challengers hold secrets.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy.signal import convolve

from qmint.core.contracts import Basis, TokenRecord
from qmint.quantum.bb84 import state_vector

KRAUS_TOL = 1e-9


def bb84_projector(basis: Basis, bit: int) -> np.ndarray:
    v = state_vector(basis, bit)
    return np.outer(v, v.conj())


def projector_from_angle(theta: float) -> np.ndarray:
    """Rank-1 projector onto cos(theta)|0> + sin(theta)|1> (real great circle through Z and X).

    theta=0 -> |0>, theta=pi/4 -> |+>, theta=pi/8 -> Breidbart vector between |0> and |+>.
    """
    v = np.array([np.cos(theta), np.sin(theta)], dtype=complex)
    return np.outer(v, v.conj())


class RegisterError(RuntimeError):
    """Invalid register operation (consumed qubit, non-CPTP map, oversize block...)."""


class ConsumedTokenError(RegisterError):
    """The quantum state behind a handle was already measured / handed to a verifier."""


@dataclass
class _Block:
    qubits: list[int]
    rho: np.ndarray


def _rank1_basis_unitary(projector: np.ndarray) -> np.ndarray:
    """Unitary whose first column spans the (rank-1) projector's range."""
    w, v = np.linalg.eigh(projector)
    if not (np.isclose(w[-1], 1.0, atol=1e-9) and np.isclose(w[0], 0.0, atol=1e-9)):
        raise RegisterError("verification operator must be a rank-1 qubit projector")
    return np.column_stack([v[:, -1], v[:, 0]])


class FactorizedRegister:
    """Product-of-blocks density-matrix register. Max block size bounds memory."""

    def __init__(self, max_block_qubits: int = 12) -> None:
        self.max_block_qubits = max_block_qubits
        self._blocks: dict[int, _Block] = {}
        self._where: dict[int, int] = {}
        self._next_qubit = 0
        self._next_block = 0

    # ------------------------------------------------------------------ building
    def _new_block(self, qubits: list[int], rho: np.ndarray) -> int:
        bid = self._next_block
        self._next_block += 1
        self._blocks[bid] = _Block(qubits, rho)
        for q in qubits:
            self._where[q] = bid
        return bid

    def _fresh_ids(self, k: int) -> list[int]:
        ids = list(range(self._next_qubit, self._next_qubit + k))
        self._next_qubit += k
        return ids

    def add_product_state(self, rhos: Sequence[np.ndarray]) -> list[int]:
        ids = self._fresh_ids(len(rhos))
        for q, rho in zip(ids, rhos, strict=True):
            r = np.asarray(rho, dtype=complex)
            if r.shape != (2, 2):
                raise RegisterError("product-state factors must be 2x2 density matrices")
            self._new_block([q], r.copy())
        return ids

    def live(self, q: int) -> bool:
        return q in self._where

    def _require(self, qubits: Sequence[int]) -> None:
        if len(set(qubits)) != len(qubits):
            raise RegisterError("duplicate qubit in operation")
        for q in qubits:
            if q not in self._where:
                raise ConsumedTokenError(f"qubit {q} no longer exists (measured or discarded)")

    def _merge(self, qubits: Sequence[int]) -> int:
        bids = list(dict.fromkeys(self._where[q] for q in qubits))
        if len(bids) == 1:
            return bids[0]
        total = sum(len(self._blocks[b].qubits) for b in bids)
        if total > self.max_block_qubits:
            raise RegisterError(
                f"joint operation would create a {total}-qubit block (> {self.max_block_qubits}); "
                "use a qubit-wise attack or a smaller n"
            )
        qs: list[int] = []
        rho = np.ones((1, 1), dtype=complex)
        for b in bids:
            blk = self._blocks.pop(b)
            qs.extend(blk.qubits)
            rho = np.kron(rho, blk.rho)
        return self._new_block(qs, rho)

    @staticmethod
    def _permute(rho: np.ndarray, perm: list[int]) -> np.ndarray:
        k = len(perm)
        t = rho.reshape((2,) * (2 * k))
        t = t.transpose(perm + [k + p for p in perm])
        return t.reshape(2**k, 2**k)

    def _front(self, bid: int, qubits: Sequence[int]) -> _Block:
        blk = self._blocks[bid]
        order = list(qubits) + [q for q in blk.qubits if q not in qubits]
        perm = [blk.qubits.index(q) for q in order]
        if perm != list(range(len(perm))):
            blk.rho = self._permute(blk.rho, perm)
            blk.qubits = order
        return blk

    # ----------------------------------------------------------------- dynamics
    def apply_channel(self, qubits_in: Sequence[int], kraus: Sequence[np.ndarray], n_out: int) -> list[int]:
        """Apply a CPTP map (Kraus list) from ``qubits_in`` (in order) to ``n_out`` fresh qubits."""
        self._require(qubits_in)
        a = len(qubits_in)
        ks = [np.asarray(k, dtype=complex) for k in kraus]
        if not ks:
            raise RegisterError("empty Kraus list")
        for k in ks:
            if k.shape != (2**n_out, 2**a):
                raise RegisterError(f"Kraus operator shape {k.shape} != {(2**n_out, 2**a)}")
        comp = sum(k.conj().T @ k for k in ks)
        if not np.allclose(comp, np.eye(2**a), atol=KRAUS_TOL):
            raise RegisterError("Kraus operators are not trace preserving (sum K^dag K != I)")
        bid = self._merge(qubits_in)
        blk = self._front(bid, qubits_in)
        rest = len(blk.qubits) - a
        if n_out + rest > self.max_block_qubits:
            raise RegisterError("channel output exceeds max block size")
        eye_r = np.eye(2**rest, dtype=complex)
        new = np.zeros((2 ** (n_out + rest),) * 2, dtype=complex)
        for k in ks:
            kk = np.kron(k, eye_r)
            new += kk @ blk.rho @ kk.conj().T
        out = self._fresh_ids(n_out)
        for q in qubits_in:
            del self._where[q]
        del self._blocks[bid]
        remaining = blk.qubits[a:]
        if n_out + rest == 0:
            return out
        self._new_block(out + remaining, new)
        return out

    def measure(self, q: int, projector0: np.ndarray, rng: np.random.Generator) -> int:
        """Two-outcome projective measurement {P, I-P}; returns 0 for P. Qubit is consumed."""
        self._require([q])
        bid = self._where[q]
        blk = self._front(bid, [q])
        rest = len(blk.qubits) - 1
        p0m = np.kron(np.asarray(projector0, dtype=complex), np.eye(2**rest))
        p0 = float(np.real(np.trace(p0m @ blk.rho)))
        p0 = min(max(p0, 0.0), 1.0)
        outcome = 0 if rng.random() < p0 else 1
        proj = p0m if outcome == 0 else np.eye(2 ** (rest + 1)) - p0m
        prob = p0 if outcome == 0 else 1.0 - p0
        post = proj @ blk.rho @ proj / prob
        del self._where[q]
        del self._blocks[bid]
        if rest:
            red = np.einsum("iaib->ab", post.reshape(2, 2**rest, 2, 2**rest))
            self._new_block(blk.qubits[1:], red)
        return outcome

    def discard(self, qubits: Sequence[int]) -> None:
        """Trace out qubits (e.g. losses)."""
        self._require(qubits)
        for q in qubits:
            bid = self._where[q]
            blk = self._front(bid, [q])
            rest = len(blk.qubits) - 1
            del self._where[q]
            del self._blocks[bid]
            if rest:
                red = np.einsum("iaib->ab", blk.rho.reshape(2, 2**rest, 2, 2**rest))
                self._new_block(blk.qubits[1:], red)

    # ----------------------------------------------------------------- analysis
    def reduced_state(self, qubits: Sequence[int]) -> np.ndarray:
        """Exact reduced density matrix of ``qubits`` (analysis oracle; merges nothing)."""
        self._require(qubits)
        rho = np.ones((1, 1), dtype=complex)
        order: list[int] = []
        for bid in dict.fromkeys(self._where[q] for q in qubits):
            blk = self._blocks[bid]
            keep = [q for q in blk.qubits if q in qubits]
            r = self._partial(blk, keep)
            rho = np.kron(rho, r)
            order.extend(keep)
        perm = [order.index(q) for q in qubits]
        return self._permute(rho, perm) if perm != list(range(len(perm))) else rho

    def _partial(self, blk: _Block, keep: list[int]) -> np.ndarray:
        k = len(blk.qubits)
        perm = [blk.qubits.index(q) for q in keep] + [i for i, q in enumerate(blk.qubits) if q not in keep]
        rho = self._permute(blk.rho, perm) if perm != list(range(k)) else blk.rho
        dk, dr = 2 ** len(keep), 2 ** (k - len(keep))
        return np.einsum("iaja->ij", rho.reshape(dk, dr, dk, dr))

    def count_distribution(self, groups: Sequence[Sequence[tuple[int, np.ndarray]]]) -> np.ndarray:
        """Exact joint distribution of per-group *error* counts.

        Each group is a list of ``(qubit, accept_projector)``; measuring a qubit with
        ``{P, I-P}`` gives an error on outcome ``I-P``. Returns an array ``D`` with
        ``D[c_0, c_1, ...] = Pr[group g has c_g errors]``. Measurements on different qubits
        commute, so this is the exact joint law of a destructive verification.
        """
        owner: dict[int, tuple[int, np.ndarray]] = {}
        for g, grp in enumerate(groups):
            for q, proj in grp:
                if q in owner:
                    raise RegisterError("qubit appears in two verification groups")
                owner[q] = (g, np.asarray(proj, dtype=complex))
        self._require(list(owner))
        ng = len(groups)
        dist = np.zeros((1,) * ng)
        dist[(0,) * ng] = 1.0
        for bid in dict.fromkeys(self._where[q] for q in owner):
            blk = self._blocks[bid]
            rel = [q for q in blk.qubits if q in owner]
            red = self._partial(blk, rel)
            u = np.ones((1, 1), dtype=complex)
            for q in rel:
                u = np.kron(u, _rank1_basis_unitary(owner[q][1]))
            probs = np.clip(np.real(np.diag(u.conj().T @ red @ u)), 0.0, 1.0)
            shape = [1] * ng
            for q in rel:
                shape[owner[q][0]] += 1
            local = np.zeros(shape)
            r = len(rel)
            for idx, p in enumerate(probs):
                if p == 0.0:
                    continue
                cnt = [0] * ng
                for j in range(r):
                    if (idx >> (r - 1 - j)) & 1:
                        cnt[owner[rel[j]][0]] += 1
                local[tuple(cnt)] += p
            dist = convolve(dist, local, method="direct")
        return dist


class RegisterHandle:
    """Opaque capability to qubits in a simulated register (implements ``TokenHandle``).

    Exposes only what a physical holder could do: count qubits, apply a CPTP map,
    measure. It carries the public ``TokenRecord`` and never an ``IssuerSecret``.
    """

    def __init__(self, register: FactorizedRegister | None, qubits: list[int], record: TokenRecord) -> None:
        self._register = register
        self._qubits = list(qubits)
        self.record = record
        self.consumed = False

    def __repr__(self) -> str:
        return f"RegisterHandle(token_id={self.record.token_id!r}, n={len(self._qubits)}, consumed={self.consumed})"

    def n_qubits(self) -> int:
        return self.record.n_prepared if self._register is None else len(self._qubits)

    def _live(self) -> FactorizedRegister:
        if self.consumed:
            raise ConsumedTokenError("token state already consumed")
        if self._register is None:
            raise RegisterError("symbolic token has no quantum register; operation unsupported")
        return self._register

    def measure(self, position: int, projector0: np.ndarray, rng: np.random.Generator) -> int:
        """Measure one qubit with ``{P, I-P}`` (destroys that qubit)."""
        reg = self._live()
        out = reg.measure(self._qubits[position], projector0, rng)
        self._qubits[position] = -1
        return out

    def split(
        self, kraus: Sequence[np.ndarray], *, joint: bool = False, copies: int = 2
    ) -> tuple[RegisterHandle, ...]:
        """Apply a CPTP map and split the output into ``copies`` candidate handles.

        * ``joint=False``: the same 2 -> 2^copies Kraus map acts on every qubit independently;
          output qubit ``j`` of each map goes to candidate ``j``. Scales to n = 128.
        * ``joint=True``: one 2^n -> 2^(copies*n) map on all n qubits; output qubits
          ``[j*n, (j+1)*n)`` form candidate ``j``. Only for small n.

        The input handle is consumed. Candidate records are copies of the public record
        (copying classical serials is always possible).
        """
        reg, _ = self._peek()
        n = len(self._qubits)
        outs: list[list[int]] = [[] for _ in range(copies)]
        if joint:
            new = reg.apply_channel(self._qubits, kraus, copies * n)
            for j in range(copies):
                outs[j] = new[j * n : (j + 1) * n]
        else:
            for q in self._qubits:
                new = reg.apply_channel([q], kraus, copies)
                for j in range(copies):
                    outs[j].append(new[j])
        self.consumed = True
        return tuple(
            RegisterHandle(
                reg, outs[j], self.record.model_copy(update={"ownership_context": f"candidate_{j}"})
            )
            for j in range(copies)
        )

    def _peek(self) -> tuple[FactorizedRegister, list[int]]:
        """Challenger/analysis-side access to the qubits without consuming them."""
        reg = self._live()
        if any(q < 0 for q in self._qubits):
            raise ConsumedTokenError("some qubits of this token were already measured")
        return reg, list(self._qubits)

    def _take(self) -> tuple[FactorizedRegister, list[int]]:
        """Challenger-side: hand the qubits to a verifier (consumes the handle)."""
        reg, qs = self._peek()
        self.consumed = True
        return reg, qs
