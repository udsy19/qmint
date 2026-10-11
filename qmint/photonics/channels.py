"""Versioned detector-channel -> (basis, bit) mapping for the Schiansky et al. 2023 dataset.

Sources (both read directly, see datasets/manifests/zenodo_7979319.yaml):
  * Zenodo 7979319 / 7997998 record description + archive README:
    TTP channels 2:H 3:V 4:+ 5:-; Client channels 2:"H / +" 4:"V / -".
  * Paper (Nat. Commun. 14, 3849 (2023), "Experimental demonstration"): the TTP keeps one
    photon of |Psi^-> = (|HV> - |VH>)/sqrt2 and measures it via a passive 50/50 beamsplitter
    in H/V or D/A; the Client measures in H/V (commitment to M0, archive folder ``linear``)
    or D/A (M1, folder ``diagonal``) set by a half-wave plate.

C7 bit convention: (Z,0)=H=|0>, (Z,1)=V=|1>, (X,0)=+=D, (X,1)=-=A.
Because |Psi^-> is anticorrelated in every basis, the bit *imprinted* on the Client photon is
``1 - ttp_bit``; an error in a basis-matched coincidence is therefore ``client_bit == ttp_bit``.
This sign is verified on the real data (matched-basis error fraction << 1/2), and
:func:`detect_channel_swap` fails loudly if a dataset contradicts it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from qmint.core.contracts import Basis


class ChannelMappingError(ValueError):
    """Data are inconsistent with the declared channel mapping (e.g. swapped detectors)."""


@dataclass(frozen=True)
class ChannelMapping:
    version: str
    ttp: dict[int, tuple[Basis, int]]
    client_bit: dict[int, int]
    client_basis_by_folder: dict[str, Basis]
    anticorrelated: bool
    sources: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ttp_channels(self) -> frozenset[int]:
        return frozenset(self.ttp)

    @property
    def client_channels(self) -> frozenset[int]:
        return frozenset(self.client_bit)

    def ttp_arrays(self, ch: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Vectorised (is_Z, bit) for TTP channels; unknown channels raise."""
        lut_basis = np.full(256, -1, np.int8)
        lut_bit = np.full(256, -1, np.int8)
        for c, (b, bit) in self.ttp.items():
            lut_basis[c] = 0 if b == Basis.Z else 1
            lut_bit[c] = bit
        bz, bit = lut_basis[ch], lut_bit[ch]
        if np.any(bz < 0):
            raise ChannelMappingError(f"unmapped TTP channels {sorted(set(np.asarray(ch)[bz < 0].tolist()))}")
        return bz == 0, bit

    def client_bits(self, ch: np.ndarray) -> np.ndarray:
        lut = np.full(256, -1, np.int8)
        for c, bit in self.client_bit.items():
            lut[c] = bit
        bit = lut[ch]
        if np.any(bit < 0):
            raise ChannelMappingError(f"unmapped client channels {sorted(set(np.asarray(ch)[bit < 0].tolist()))}")
        return bit


SCHIANSKY_2023_V1 = ChannelMapping(
    version="schiansky2023-zenodo7979319-v1",
    ttp={2: (Basis.Z, 0), 3: (Basis.Z, 1), 4: (Basis.X, 0), 5: (Basis.X, 1)},
    client_bit={2: 0, 4: 1},
    client_basis_by_folder={"linear": Basis.Z, "diagonal": Basis.X},
    anticorrelated=True,
    sources=(
        "https://zenodo.org/api/records/7979319 metadata.description",
        "Archive.zip:README",
        "https://www.nature.com/articles/s41467-023-39519-w#Sec (Experimental demonstration; |Psi^->)",
    ),
)


def detect_channel_swap(n_errors: int, n_sifted: int, *, max_error_fraction: float = 0.25) -> None:
    """Raise if a matched-basis error fraction is implausible for the declared mapping.

    Swapping the two Client detectors (or a TTP H/V or +/- pair) maps error fraction e to 1-e,
    so a value above ``max_error_fraction`` (default 0.25, far above the paper's reported
    <= 3.3%) indicates a swap or a wrong correlation sign rather than physics.
    """
    if n_sifted == 0:
        raise ChannelMappingError("no basis-matched coincidences: cannot validate mapping")
    e = n_errors / n_sifted
    if e > max_error_fraction:
        raise ChannelMappingError(
            f"matched-basis error fraction {e:.4f} > {max_error_fraction}: channels swapped or wrong "
            "correlation sign for the declared mapping"
        )
