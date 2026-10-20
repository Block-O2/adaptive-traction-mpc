"""Stage-5 architecture-recovery audit support.

This package is not connected to the controller while the campaign is blocked.
"""

from .provenance import (
    QuantityProvenance,
    SourceClass,
    assert_deployable_session_provenance,
)

__all__ = [
    "QuantityProvenance",
    "SourceClass",
    "assert_deployable_session_provenance",
]
