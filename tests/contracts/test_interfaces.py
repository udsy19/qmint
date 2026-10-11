"""Structural interface conformance (qmint.core.interfaces), incl. the B-B1 Protocol additions."""

import numpy as np
import pytest

from qmint.attacks.games import W1Challenger
from qmint.core.interfaces import Challenger, ChannelTokenHandle, PairChallenger, TokenHandle
from qmint.protocols.wiesner import WiesnerChallenger, WiesnerMode


@pytest.mark.parametrize("mode", [WiesnerMode.EXACT, WiesnerMode.SHOTS])
def test_lane_b_wiesner_satisfies_extended_protocols(mode):
    ch = WiesnerChallenger(mode=mode, seed=1)
    note = ch.mint(3, 5)
    assert isinstance(ch, Challenger) and isinstance(ch, PairChallenger)
    assert isinstance(note, TokenHandle) and isinstance(note, ChannelTokenHandle)
    # the Protocol methods behave as documented: split consumes and yields candidates
    ident = [np.kron(np.eye(2), np.array([[1], [0]], dtype=complex))]
    c1, c2 = note.split(ident)
    assert note.consumed and isinstance(c1, ChannelTokenHandle)
    assert ch.verify_pair(c1, c2)[0] is True  # copy 0 keeps the original qubits


def test_backward_compatible_token_handle():
    """Implementers of the original TokenHandle/Challenger stay conformant (sub-Protocols only)."""
    ch = W1Challenger()
    note = ch.mint(2, 3)
    assert isinstance(note, TokenHandle) and isinstance(ch, Challenger)
    assert not isinstance(note, ChannelTokenHandle)  # lane C's own register has no split()
    assert not isinstance(ch, PairChallenger)

    class Minimal:
        record = None

        def n_qubits(self) -> int:
            return 0

    assert isinstance(Minimal(), TokenHandle) and not isinstance(Minimal(), ChannelTokenHandle)


def test_handle_never_exposes_secret_attributes():
    ch = WiesnerChallenger(seed=2)
    note = ch.mint(4, 9)
    public = {a for a in dir(note) if not a.startswith("_")}
    assert not public & {"bases", "bits", "secret", "issuer_secret"}
