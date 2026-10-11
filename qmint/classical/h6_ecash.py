"""H6 -- offline untraceable e-cash with EX-POST double-spender identification.

protocol_id: ``classical_h6_anonymous_ecash`` (game C1).

Construction: Chaum, Fiat, Naor, "Untraceable Electronic Cash", CRYPTO '88, LNCS 403,
pp. 319-327 (1990), doi:10.1007/0-387-34799-2_25 -- Section 1 "Untraceable Coins"
(withdrawal steps 1-6 with cut-and-choose over k blinded candidates
B_i = r_i^3 f(x_i, y_i) mod n, x_i = g(a_i, c_i), y_i = g(a_i XOR (u||(v+i)), d_i);
payment steps 1-5 with challenge bits z_i; double spending with complementary z_i
reveals both a_i and a_i XOR (u||(v+i)), hence the account number u).
Source read: Wayback copy of blog.koehntopp.de/uploads/chaum_fiat_naor_ecash.pdf
(sha256 07e6544a55c3bf754043133498b2db5356877c636d27fb2185399d1ccc915637), pp. 320-322.

DETECTION IS NOT PREVENTION: both offline merchants ACCEPT at presentation time; the
bank identifies the double spender only when both deposits arrive.

Deviations / limitations (documented, deliberate):
* f, g instantiated with SHA-256 (f as full-domain hash mod n). The paper requires g to
  be bijective in its 2nd argument for UNCONDITIONAL untraceability; SHA-256 does not
  satisfy that, so privacy here is heuristic, not unconditional.
* a_i, c_i, d_i are 32-byte strings rather than residues mod n.
* Toy RSA modulus (default 512 bits; two safe primes so that phi(n) has no small odd
  factors and cube roots are unique). NOT a secure key size; for systems-behaviour only.
* Section 2 (framing protection via Alice's signatures) and Section 3 (checks) are
  NOT implemented. Merchant collusion (identical challenges) defeats tracing, as the
  paper itself notes (p.322); fixed per-merchant query strings are not implemented.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field

from qmint.classical.common import Decision, Message, new_msg

PROTOCOL_ID = "classical_h6_anonymous_ecash"
SOURCE = ("Chaum-Fiat-Naor CRYPTO'88 LNCS 403 pp.319-327, Sec.1 'Untraceable Coins', "
          "doi:10.1007/0-387-34799-2_25")
_SMALL_PRIMES = [p for p in range(3, 2000) if all(p % q for q in range(2, int(p**0.5) + 1))]
BLOCK = 32  # bytes


def _is_probable_prime(n: int, rng: random.Random, rounds: int = 40) -> bool:
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(rounds):
        a = rng.randrange(2, n - 1)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _safe_prime(bits: int, rng: random.Random) -> int:
    """p = 2q+1 with q prime and p = 2 (mod 3), so gcd(3, p-1) = 1."""
    while True:
        q = rng.getrandbits(bits - 1) | (1 << (bits - 2)) | 1
        if any(q % sp == 0 and q != sp for sp in _SMALL_PRIMES):
            continue
        p = 2 * q + 1
        if p % 3 != 2 or any(p % sp == 0 for sp in _SMALL_PRIMES):
            continue
        if _is_probable_prime(q, rng) and _is_probable_prime(p, rng):
            return p


def g(a: bytes, b: bytes) -> bytes:
    return hashlib.sha256(b"cfn-g|" + a + b).digest()


def f(x: bytes, y: bytes, n: int) -> int:
    nbytes = (n.bit_length() + 7) // 8 + 16
    out, ctr = b"", 0
    while len(out) < nbytes:
        out += hashlib.sha256(b"cfn-f|" + ctr.to_bytes(4, "big") + x + y).digest()
        ctr += 1
    return int.from_bytes(out[:nbytes], "big") % n


def identity_block(u: int, counter: int) -> bytes:
    return (u.to_bytes(8, "big") + counter.to_bytes(8, "big")).rjust(BLOCK, b"\0")


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b, strict=True))


@dataclass
class CFNBank:
    """Bank: RSA e=3 signer, account counters v, deposit database for double-spend tracing."""

    node_id: str = "bank"
    site_id: str = "BANK"
    modulus_bits: int = 512
    k: int = 16
    seed: int = 0
    processing_ns: float = 50_000.0
    n: int = field(init=False)
    _d: int = field(init=False, repr=False)
    counters: dict[int, int] = field(default_factory=dict)
    deposits: dict[int, dict] = field(default_factory=dict)  # coin C -> {merchant, z, revealed}
    detections: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.k % 2:
            raise ValueError("k must be even")
        rng = random.Random(f"cfn-bank|{self.seed}")
        p = _safe_prime(self.modulus_bits // 2, rng)
        q = _safe_prime(self.modulus_bits // 2, rng)
        while q == p:
            q = _safe_prime(self.modulus_bits // 2, rng)
        self.n = p * q
        self._d = pow(3, -1, (p - 1) * (q - 1))
        self._rng = random.Random(f"cfn-bank-cc|{self.seed}")
        self._pending: dict[int, tuple[list[int], list[int]]] = {}

    def open_account(self, u: int) -> None:
        self.counters.setdefault(u, 0)

    # --- withdrawal (cut-and-choose) ---------------------------------------
    def withdraw_challenge(self, u: int, blinded: list[int]) -> list[int]:
        if len(blinded) != self.k:
            raise ValueError("expected k blinded candidates")
        reveal = sorted(self._rng.sample(range(self.k), self.k // 2))
        self._pending[u] = (blinded, reveal)
        return reveal

    def withdraw_sign(self, u: int, openings: dict[int, tuple[int, bytes, bytes, bytes]]) -> int | None:
        """Check the opened candidates; on success return prod_{i not in R} B_i^{1/3} and bump v by k."""
        blinded, reveal = self._pending.pop(u)
        v = self.counters[u]
        if set(openings) != set(reveal):
            return None
        for i in reveal:
            r, a, c, d = openings[i]
            x, y = g(a, c), g(_xor(a, identity_block(u, v + i)), d)
            if blinded[i] != (pow(r, 3, self.n) * f(x, y, self.n)) % self.n:
                return None  # Alice caught cheating in cut-and-choose
        prod = 1
        for i in range(self.k):
            if i not in reveal:
                prod = (prod * blinded[i]) % self.n
        self.counters[u] = v + self.k
        return pow(prod, self._d, self.n)

    # --- deposit and ex-post tracing ----------------------------------------
    def handle(self, msg: Message, now_ns: float) -> list[Message]:
        if msg.kind != "Deposit":
            raise ValueError(f"unexpected message {msg.kind}")
        p = msg.payload
        coin = int(p["coin"])
        if not verify_payment(self.n, coin, p["z"], p["responses"]):
            return [new_msg("DepositResult", self.node_id, msg.src, "h6", status="INVALID")]
        prev = self.deposits.get(coin)
        if prev is None:
            self.deposits[coin] = {"merchant": p["merchant_id"], "z": list(p["z"]), "responses": p["responses"]}
            return [new_msg("DepositResult", self.node_id, msg.src, "h6", status="CREDITED")]
        traced = trace_double_spender(prev["z"], prev["responses"], p["z"], p["responses"])
        det = {"coin": coin, "merchants": [prev["merchant"], p["merchant_id"]], "traced_account": traced,
               "detected_at_ns": now_ns + self.processing_ns}
        self.detections.append(det)
        return [new_msg("DepositResult", self.node_id, msg.src, "h6", status="DOUBLE_SPEND_DETECTED",
                        traced_account=traced)]


def payment_terms(n: int, z: list[int], responses: list[dict]) -> list[int]:
    terms = []
    for zi, resp in zip(z, responses, strict=True):
        if zi == 1:
            x = g(bytes.fromhex(resp["a"]), bytes.fromhex(resp["c"]))
            y = bytes.fromhex(resp["y"])
        else:
            x = bytes.fromhex(resp["x"])
            y = g(bytes.fromhex(resp["a_xor_id"]), bytes.fromhex(resp["d"]))
        terms.append(f(x, y, n))
    return terms


def verify_payment(n: int, coin: int, z: list[int], responses: list[dict]) -> bool:
    """C^3 == prod f(x_i, y_i) mod n, with terms in lexicographic (ascending) order."""
    if len(z) != len(responses):
        return False
    terms = payment_terms(n, z, responses)
    if terms != sorted(terms):
        return False
    prod = 1
    for t in terms:
        prod = (prod * t) % n
    return pow(coin, 3, n) == prod


def trace_double_spender(z1: list[int], r1: list[dict], z2: list[int], r2: list[dict]) -> int | None:
    """Recover u from an index where the two challenges differ (paper p.322). None if challenges identical."""
    for i, (a, b) in enumerate(zip(z1, z2, strict=True)):
        if a != b:
            a_i = bytes.fromhex((r1 if a == 1 else r2)[i]["a"])
            a_xor = bytes.fromhex((r1 if a == 0 else r2)[i]["a_xor_id"])
            ident = _xor(a_i, a_xor)
            return int.from_bytes(ident[-16:-8], "big")
    return None


@dataclass
class CFNWallet:
    """Alice: account u; holds coin C and the openings of its k/2 unrevealed candidates."""

    u: int
    seed: int = 0
    coins: list[dict] = field(default_factory=list)

    def withdraw(self, bank: CFNBank) -> dict | None:
        rng = random.Random(f"cfn-wallet|{self.u}|{self.seed}|{len(self.coins)}")
        n, k, v = bank.n, bank.k, bank.counters[self.u]
        cands = []
        for i in range(k):
            a, c, d = (rng.getrandbits(8 * BLOCK).to_bytes(BLOCK, "big") for _ in range(3))
            r = rng.randrange(2, n - 1)
            while math.gcd(r, n) != 1:
                r = rng.randrange(2, n - 1)
            x, y = g(a, c), g(_xor(a, identity_block(self.u, v + i)), d)
            cands.append({"r": r, "a": a, "c": c, "d": d, "x": x, "y": y, "i": i,
                          "B": (pow(r, 3, n) * f(x, y, n)) % n})
        reveal = bank.withdraw_challenge(self.u, [cd["B"] for cd in cands])
        sig = bank.withdraw_sign(self.u, {i: (cands[i]["r"], cands[i]["a"], cands[i]["c"], cands[i]["d"])
                                          for i in reveal})
        if sig is None:
            return None
        keep = [cd for cd in cands if cd["i"] not in reveal]
        r_prod = 1
        for cd in keep:
            r_prod = (r_prod * cd["r"]) % n
        coin_value = (sig * pow(r_prod, -1, n)) % n
        keep.sort(key=lambda cd: f(cd["x"], cd["y"], n))
        coin = {"C": coin_value, "terms": keep, "id_blocks": [identity_block(self.u, v + cd["i"]) for cd in keep]}
        self.coins.append(coin)
        return coin

    @staticmethod
    def respond(coin: dict, z: list[int]) -> list[dict]:
        out = []
        for zi, cd, ident in zip(z, coin["terms"], coin["id_blocks"], strict=True):
            if zi == 1:
                out.append({"a": cd["a"].hex(), "c": cd["c"].hex(), "y": cd["y"].hex()})
            else:
                out.append({"x": cd["x"].hex(), "a_xor_id": _xor(cd["a"], ident).hex(), "d": cd["d"].hex()})
        return out


@dataclass
class CFNMerchant:
    """Offline merchant: random challenge, local verification, later deposit. No bank contact at payment."""

    node_id: str
    site_id: str
    merchant_id: str
    n: int
    seed: int = 0
    processing_ns: float = 10_000.0
    to_deposit: list[dict] = field(default_factory=list)
    deposit_results: list[dict] = field(default_factory=list)
    _open: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._rng = random.Random(f"cfn-merchant|{self.merchant_id}|{self.seed}")

    def handle(self, msg: Message, now_ns: float) -> list[Message]:
        p = msg.payload
        if msg.kind == "PresentCoin":
            z = [self._rng.randrange(2) for _ in range(int(p["n_terms"]))]
            self._open[msg.src] = {"coin": int(p["coin"]), "z": z}
            return [new_msg("Challenge", self.node_id, msg.src, "h6", z=z)]
        if msg.kind == "Response":
            st = self._open.pop(msg.src)
            ok = verify_payment(self.n, st["coin"], st["z"], p["responses"])
            if ok:
                self.to_deposit.append({"coin": str(st["coin"]), "z": st["z"], "responses": p["responses"],
                                        "merchant_id": self.merchant_id})
            d = Decision.ACCEPT if ok else Decision.REJECT_BAD_SIGNATURE
            return [new_msg("Result", self.node_id, msg.src, "h6", decision=d.value,
                            decided_at_ns=now_ns + self.processing_ns)]
        if msg.kind == "DepositResult":  # bank's answer to a deposit: bookkeeping only
            self.deposit_results.append(dict(p))
            return []
        raise ValueError(f"unexpected message {msg.kind}")

    def deposit_messages(self, bank_node: str) -> list[Message]:
        out = [new_msg("Deposit", self.node_id, bank_node, "h6", **dep) for dep in self.to_deposit]
        self.to_deposit = []
        return out
