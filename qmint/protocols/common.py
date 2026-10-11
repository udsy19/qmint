"""Shared protocol-layer helpers (lane B)."""

from __future__ import annotations

from typing import Any

from qmint.core.contracts import SecretBoundaryError


class SecretHolder:
    """Mixin for challengers / bank agents that hold ``IssuerSecret`` objects.

    The frozen C1 ``IssuerSecret`` refuses pickling and ``model_dump`` but pydantic's own
    ``__deepcopy__``/``__copy__`` still duplicate it. Secret-holding objects therefore
    refuse copying and pickling themselves (defence in depth; see the lane-B handoff
    migration proposal for ``IssuerSecret.__deepcopy__``).
    """

    def __deepcopy__(self, memo: Any) -> Any:
        raise SecretBoundaryError(f"{type(self).__name__} holds issuer secrets and cannot be copied")

    def __copy__(self) -> Any:
        raise SecretBoundaryError(f"{type(self).__name__} holds issuer secrets and cannot be copied")

    def __reduce_ex__(self, protocol: Any) -> Any:
        raise SecretBoundaryError(f"{type(self).__name__} holds issuer secrets and cannot be pickled")
