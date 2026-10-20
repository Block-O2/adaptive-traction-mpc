"""C2 reference-only prefix plus an already selected waypoint suffix.

The prefix is sampled from the active certified schedule itself.  MPC's
candidate set, cost, and selected suffix are not changed by this adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class RollingSuffixCompositeSchedule:
    prefix: Any
    prefix_start_s: float
    suffix: Any
    request_id: int

    def __post_init__(self) -> None:
        if not np.isfinite(self.prefix_start_s) or not (0 <= self.prefix_start_s < self.prefix.duration_s):
            raise ValueError("rolling prefix start must precede its endpoint")
        old = self.prefix.sample(self.prefix.duration_s)
        new = self.suffix.sample(0.0)
        if any(np.max(np.abs(a-b)) > 1e-10 for a, b in (
                (old.q_rad, new.q_rad),
                (old.dq_rad_s, new.dq_rad_s),
                (old.ddq_rad_s2, new.ddq_rad_s2))):
            raise ValueError("rolling suffix is not C2 at the original prefix endpoint")

    @property
    def splice_elapsed_s(self) -> float:
        return float(self.prefix.duration_s-self.prefix_start_s)

    @property
    def duration_s(self) -> float:
        return self.splice_elapsed_s+self.suffix.duration_s

    @property
    def candidate(self) -> Any:
        return self.suffix.candidate

    @property
    def version(self) -> str:
        return "rolling_suffix_splice_v1/"+self.suffix.version

    def sample(self, elapsed_s: float) -> Any:
        if not np.isfinite(elapsed_s) or elapsed_s < 0:
            raise ValueError("elapsed_s must be finite and nonnegative")
        elapsed_s = min(float(elapsed_s), self.duration_s)
        if elapsed_s <= self.splice_elapsed_s:
            return self.prefix.sample(self.prefix_start_s+elapsed_s)
        return self.suffix.sample(elapsed_s-self.splice_elapsed_s)

    def record(self) -> dict[str, Any]:
        return dict(version=self.version, request_id=self.request_id,
                    prefix_source_label=self.prefix.candidate.label,
                    prefix_start_progress_s=self.prefix_start_s,
                    splice_elapsed_s=self.splice_elapsed_s,
                    total_duration_s=self.duration_s,
                    suffix_label=self.suffix.candidate.label,
                    suffix_version=self.suffix.version)
