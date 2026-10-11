"""QMint on Qollab -- Wiesner quantum-money counterfeiting experiment in ONE circuit.

This effort is supported by Qollab & IonQ.

What it does
------------
Mints one random n-qubit Wiesner (BB84) banknote and packs three experiments into a single circuit:

  A. honest verification  -- the bank measures the untouched note in its secret bases;
  B. phase-covariant cloner attack (Bruss et al. 2000)  -- 1 note -> 2 notes, bank verifies BOTH copies;
  C. MVW-optimal cloner attack (Molina, Vidick & Watrous 2012, Sec. 3.2) -- same game.

The counterfeiter wins game W1 only if BOTH copies pass. The published theorem (MVW 2012, Thm 1) says no
quantum strategy wins with probability above (3/4)^n. The run prints, side by side and labelled:
  * measured shot frequencies from the selected backend, with 95% Wilson intervals,
  * exact model values computed here in NumPy (density matrices),
  * the published theorem bound.

Results from the full QMint platform (github.com/udsy19/qmint) quoted for context (NOT recomputed here):
  * optimal 1->2 attack SDP, n=1: 0.75; exact rational certificate 3/4 <= OPT <= 0.750000000003638,
    independently re-verified (n=2: 9/16).  Evidence: CERTIFIED_NUMERIC (QMint lanes C + D).
  * basis-guess measure-and-resend counterfeiter wins (5/8)^n, not (3/4)^n.

Honesty notes: a simulator copying a statevector is not "cloning"; this is a circuit-level demonstration of
the counterfeiting GAME, not a deployable quantum banknote. Shots re-prepare the same secret note; per-qubit
both-pass probabilities of both cloners are identical for all four BB84 states (checked in `exact_values`),
so the n-qubit value is the product over qubits.

Qubits: n (honest) + 3n (Bruss) + 3n (MVW) = 7n. Keep 7n <= simulator width (n <= 3 on a 24-qubit simulator,
n <= 4 on IonQ's 29-qubit noisy simulators).
"""

import math

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import UnitaryGate

# ---------------------------------------------------------------- cloner maps (8x2 isometries)
# Row index = 4*copy1 + 2*copy2 + ancilla; column = input bit.


def bruss_isometry():
    a, b, c = 0.5 + math.sqrt(1 / 8), math.sqrt(1 / 8), 0.5 - math.sqrt(1 / 8)
    v = np.zeros((8, 2))
    v[0b000, 0], v[0b011, 0], v[0b101, 0], v[0b110, 0] = a, b, b, c
    v[0b111, 1], v[0b100, 1], v[0b010, 1], v[0b001, 1] = a, b, b, c
    return v


def mvw_isometry():
    # MVW 2012 Sec. 3.2 Kraus operators A0, A1 (rows = copy1 copy2), over sqrt(12); ancilla = Kraus index.
    a0 = np.array([[3, 0], [0, 1], [0, 1], [1, 0]]) / math.sqrt(12)
    a1 = np.array([[0, 1], [1, 0], [1, 0], [0, 3]]) / math.sqrt(12)
    e = np.eye(2)
    return np.kron(a0, e[:, [0]]) + np.kron(a1, e[:, [1]])


def unitary_completion(v):
    """8x8 unitary whose columns 0 and 4 (input |0>,|1> with blank copy & ancilla) equal the isometry."""
    m = np.concatenate([v, np.eye(8)], axis=1)
    q, _ = np.linalg.qr(m)
    basis = q[:, :8]
    for k in range(2):  # fix signs so the first two columns are exactly v
        if np.dot(basis[:, k], v[:, k]) < 0:
            basis[:, k] = -basis[:, k]
    u = np.zeros((8, 8), dtype=complex)
    order = [0, 4, 1, 2, 3, 5, 6, 7]
    for j, col in zip(order, range(8), strict=True):
        u[:, j] = basis[:, col]
    return u


# ---------------------------------------------------------------- exact model values (NumPy)
KET = {("Z", 0): np.array([1, 0]), ("Z", 1): np.array([0, 1]),
       ("X", 0): np.array([1, 1]) / math.sqrt(2), ("X", 1): np.array([1, -1]) / math.sqrt(2)}


def both_pass_exact(v, basis, bit):
    psi = KET[(basis, bit)]
    out = (v @ psi).reshape(2, 2, 2)  # copy1, copy2, ancilla
    proj = KET[(basis, bit)]
    amp = np.einsum("a,b,abe->e", proj.conj(), proj.conj(), out)
    return float(np.sum(np.abs(amp) ** 2))


def exact_values():
    rows = {}
    for name, v in (("bruss", bruss_isometry()), ("mvw", mvw_isometry())):
        per_state = [both_pass_exact(v, b, x) for b in "ZX" for x in (0, 1)]
        rows[name] = per_state
    return rows


# ---------------------------------------------------------------- circuit
def prepare(qc, q, basis, bit):
    if bit:
        qc.x(q)
    if basis == "X":
        qc.h(q)


def measure_in(qc, q, c, basis):
    if basis == "X":
        qc.h(q)
    qc.measure(q, c)


def build_circuit(bases, bits):
    n = len(bases)
    qc = QuantumCircuit(7 * n, 5 * n, name="qmint_w1")
    # A. honest note on qubits 0..n-1 -> clbits 0..n-1
    for i in range(n):
        prepare(qc, i, bases[i], bits[i])
    # B/C. cloner blocks: block offset o, copy1 = o+i, copy2 = o+n+i, ancilla = o+2n+i
    blocks = ((n, UnitaryGate(unitary_completion(bruss_isometry()), label="bruss")),
              (4 * n, UnitaryGate(unitary_completion(mvw_isometry()), label="mvw")))
    for o, gate in blocks:
        for i in range(n):
            prepare(qc, o + i, bases[i], bits[i])
            # Qiskit: matrix index bit k <-> qargs[k]; row 4*c1 + 2*c2 + anc => qargs (anc, c2, c1)
            qc.append(gate, [o + 2 * n + i, o + n + i, o + i])
    qc.barrier()
    for i in range(n):
        measure_in(qc, i, i, bases[i])
    for blk, (o, _) in enumerate(blocks):
        for i in range(n):
            measure_in(qc, o + i, n + 2 * n * blk + i, bases[i])          # copy 1
            measure_in(qc, o + n + i, n + 2 * n * blk + n + i, bases[i])  # copy 2
    return qc


def wilson(k, m, z=1.959963984540054):
    if m == 0:
        return (0.0, 1.0)
    p = k / m
    d = 1 + z * z / m
    c = (p + z * z / (2 * m)) / d
    h = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main(n_qubits: int = 3, shots: int = 2000, seed: int = 7) -> None:
    n = int(n_qubits)
    if not 1 <= n <= 4:
        print("n_qubits must be between 1 and 4 (circuit width is 7n qubits).")
        return
    rng = np.random.default_rng(int(seed))
    bases = ["Z" if b == 0 else "X" for b in rng.integers(0, 2, n)]
    bits = [int(x) for x in rng.integers(0, 2, n)]

    print("QMint -- Wiesner counterfeiting game W1 (one circuit)")
    print("This effort is supported by Qollab & IonQ.")
    print(f"note: n={n} qubits, seed={seed}; secret bases/bits stay with the bank (printed only after the run)")
    qc = build_circuit(bases, bits)
    print(f"circuit: {qc.num_qubits} qubits, {qc.num_clbits} clbits")

    try:
        be = backend  # noqa: F821  -- supplied by Qollab's runtime
    except NameError:
        from qiskit.providers.basic_provider import BasicSimulator
        be = BasicSimulator()
    print(f"backend: {getattr(be, 'name', be)}")
    tqc = transpile(qc, be, seed_transpiler=int(seed))
    job = be.run(tqc, shots=int(shots))
    try:  # remote backends (IonQ noisy simulators): poll like Qollab's template
        import time

        from qiskit.providers.jobstatus import JobStatus
        while True:
            status = job.status()
            if status == JobStatus.DONE:
                break
            if status in (JobStatus.ERROR, JobStatus.CANCELLED):
                raise RuntimeError(f"job ended with status {status}")
            print(f"job status: {status}")
            time.sleep(5)
    except ImportError:
        pass
    counts = job.result().get_counts()

    honest = bruss = mvw = 0
    total = 0
    for key, c in counts.items():
        bitsstr = key.replace(" ", "")[::-1]  # clbit j at index j (Qiskit keys are little-endian)
        def ok(start):
            return all(int(bitsstr[start + i]) == bits[i] for i in range(n))  # noqa: B023 (called immediately)
        total += c
        honest += c if ok(0) else 0
        bruss += c if (ok(n) and ok(2 * n)) else 0
        mvw += c if (ok(3 * n) and ok(4 * n)) else 0

    ex = exact_values()
    exact_bruss = float(np.prod([ex["bruss"][0] for _ in range(n)]))
    exact_mvw = float(np.prod([ex["mvw"][0] for _ in range(n)]))
    bound = 0.75 ** n

    def line(label, k, exact, kind):
        lo, hi = wilson(k, total)
        print(f"  {label:<34} measured {k / total:.4f}  95% CI [{lo:.4f}, {hi:.4f}]   "
              f"exact model {exact:.4f}   ({kind})")

    print("\nresults (shots re-prepare the same secret note):")
    line("A. honest note accepted", honest, 1.0, "ideal = 1; noise lowers it")
    line("B. phase-covariant cloner: both pass", bruss, exact_bruss, "heuristic attack")
    line("C. MVW optimal cloner: both pass", mvw, exact_mvw, "attains the theorem bound")
    print(f"  {'theorem bound (3/4)^n  [MVW 2012, Thm 1]':<34} {bound:.4f}   (PUBLISHED_THEOREM, all attacks, game W1)")
    print("\nper-state exact both-pass (|0>,|1>,|+>,|->):")
    print("  bruss:", [round(x, 6) for x in ex["bruss"]], " (3+2*sqrt2)/8 =", round((3 + 2 * math.sqrt(2)) / 8, 6))
    print("  mvw:  ", [round(x, 6) for x in ex["mvw"]], " 3/4 =", 0.75)
    above = (mvw / total) > bound and wilson(mvw, total)[0] > bound
    print("\nverdict:", "measured MVW rate significantly ABOVE the bound -- investigate!" if above else
          "no attack exceeds the published bound beyond statistical error (as the theorem requires).")
    print(f"secret (revealed after the experiment, TEST_ONLY): bases={''.join(bases)} bits={bits}")
    print("Evidence labels: measured = SIMULATOR (or IonQ noisy simulator) counts; exact = NumPy model; "
          "bound = PUBLISHED_THEOREM. Not a physical banknote. Full platform: github.com/udsy19/qmint (MIT).")
