"""Small, explicit linear-algebra helpers for lane C (attacks).

Conventions (C7, documented once here and used everywhere in ``qmint.attacks``):

* Single-qubit computational basis: index 0 = |0>, index 1 = |1>.
* BB84 labels follow ``qmint.core.contracts.BB84_STATE_OF``:
  (Z,0)=|0>, (Z,1)=|1>, (X,0)=|+>, (X,1)=|->; kets come from ``qmint.quantum.bb84``.
* Multi-system kets use ``np.kron(a, b)``: the FIRST factor is the most significant
  (big-endian) index. No Qiskit little-endian decoding is used anywhere in this package.
* Choi operator of a map Phi: L(C^din) -> L(C^dout) is
      J(Phi) = sum_{i,j} |i><j| (x) Phi(|i><j|)          ordering (input, output)
  so that Phi(rho) = Tr_in[(rho^T (x) I) J] and <A, Phi(rho)> = Tr[J (rho^T (x) A)].
  For the 1->2 counterfeiting game the output is (out1, out2), giving the documented
  ordering (input, out1, out2). This is MVW 2012's J(Phi) (Sec. 2.2, which orders
  (output, input)) with the tensor factors swapped.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

from qmint.core.contracts import BB84State
from qmint.quantum.bb84 import STATE_VECTORS

#: The four BB84 labels in a fixed order; Wiesner samples them uniformly.
BB84_LABELS: tuple[str, ...] = tuple(s.value for s in BB84State)


def ket(label: str) -> np.ndarray:
    """BB84 ket by C7 label ('0', '1', '+', '-'); canonical table in ``qmint.quantum.bb84``."""
    return STATE_VECTORS[BB84State(label)].copy()


def proj(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=complex).reshape(-1)
    return np.outer(v, v.conj())


def kron_all(mats: Iterable[np.ndarray]) -> np.ndarray:
    out = np.array([[1.0 + 0j]])
    for m in mats:
        out = np.kron(out, m)
    return out


def partial_trace(m: np.ndarray, dims: Sequence[int], keep: Sequence[int]) -> np.ndarray:
    """Partial trace of ``m`` on subsystems with sizes ``dims``, keeping indices ``keep`` (in order)."""
    dims = list(dims)
    k = len(dims)
    t = np.asarray(m).reshape(dims + dims)
    trace_out = [i for i in range(k) if i not in keep]
    # trace highest index first so axis numbers stay valid
    for i in sorted(trace_out, reverse=True):
        cur = t.ndim // 2
        t = np.trace(t, axis1=i, axis2=i + cur)
    dk = int(np.prod([dims[i] for i in keep])) if keep else 1
    return t.reshape(dk, dk)


def choi_from_kraus(kraus: Sequence[np.ndarray]) -> np.ndarray:
    """J = sum_ij |i><j| (x) Phi(|i><j|), ordering (input, output)."""
    din = kraus[0].shape[1]
    dout = kraus[0].shape[0]
    j = np.zeros((din * dout, din * dout), dtype=complex)
    for a in range(din):
        for b in range(din):
            eab = np.zeros((din, din), dtype=complex)
            eab[a, b] = 1.0
            j += np.kron(eab, apply_kraus(kraus, eab))
    return j


def apply_kraus(kraus: Sequence[np.ndarray], rho: np.ndarray) -> np.ndarray:
    return sum(k @ rho @ k.conj().T for k in kraus)


def tp_residual(kraus: Sequence[np.ndarray]) -> float:
    """Frobenius norm of sum_k K^dag K - I (0 for a trace-preserving map)."""
    din = kraus[0].shape[1]
    return float(np.linalg.norm(sum(k.conj().T @ k for k in kraus) - np.eye(din)))


def choi_tp_residual(j: np.ndarray, din: int, dout: int) -> float:
    """Frobenius norm of Tr_out J - I_din."""
    return float(np.linalg.norm(partial_trace(j, [din, dout], keep=[0]) - np.eye(din)))


def min_eig(h: np.ndarray) -> float:
    return float(np.linalg.eigvalsh((h + h.conj().T) / 2).min())
