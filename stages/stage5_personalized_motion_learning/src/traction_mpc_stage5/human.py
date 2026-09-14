"""Stage-5 placement-only extension of the frozen Human V2 mechanics."""

from __future__ import annotations

from dataclasses import dataclass

from traction_mpc_stage3.human import HumanV2Parameters

from .config import STAGE5_CONFIG


@dataclass(frozen=True)
class Stage5HumanParameters(HumanV2Parameters):
    """Human V2 with a parameterized cuff location; dynamics stay unchanged."""

    cuff_fraction_of_shank: float = 0.72

    def __post_init__(self) -> None:
        if not 0.0 < self.cuff_fraction_of_shank < 1.0:
            raise ValueError("cuff_fraction_of_shank must lie strictly inside the shank")

    @property
    def sleeve_center_m(self) -> float:
        return self.cuff_fraction_of_shank * self.shank_length_m


STAGE5_HUMAN = Stage5HumanParameters(
    cuff_fraction_of_shank=float(
        STAGE5_CONFIG["geometry"]["cuff_center_fraction_of_shank_from_knee"]
    )
)
