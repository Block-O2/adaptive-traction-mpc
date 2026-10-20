"""Fail-loud source classification for recovered session quantities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class SourceClass(str, Enum):
    MEASURED = "MEASURED"
    CALIBRATED = "CALIBRATED"
    ONLINE_ESTIMATED = "ONLINE_ESTIMATED"
    STRUCTURAL_PRIOR = "STRUCTURAL_PRIOR"
    FIXED_NOMINAL = "FIXED_NOMINAL"
    SIMULATION_TRUTH = "SIMULATION_TRUTH"
    HIDDEN_ORACLE = "HIDDEN_ORACLE"


ALLOWED_DEPLOYABLE_SOURCES = frozenset(
    {
        SourceClass.MEASURED,
        SourceClass.CALIBRATED,
        SourceClass.ONLINE_ESTIMATED,
        SourceClass.STRUCTURAL_PRIOR,
    }
)


@dataclass(frozen=True)
class QuantityProvenance:
    quantity: str
    source: SourceClass
    session_specific: bool
    version: str
    evidence: str

    def __post_init__(self) -> None:
        if not self.quantity or not self.version or not self.evidence:
            raise ValueError("quantity, version, and evidence are required")


def assert_deployable_session_provenance(
    records: Iterable[QuantityProvenance],
) -> None:
    """Reject forbidden sources for any session-specific deployable quantity."""

    forbidden = [
        record
        for record in records
        if record.session_specific and record.source not in ALLOWED_DEPLOYABLE_SOURCES
    ]
    if forbidden:
        details = ", ".join(
            f"{record.quantity}={record.source.value}" for record in forbidden
        )
        raise ValueError(f"forbidden deployable session provenance: {details}")
