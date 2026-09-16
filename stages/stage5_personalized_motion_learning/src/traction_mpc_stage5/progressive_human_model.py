"""Versioned repetition-boundary authority for progressive Human models.

This module contains authority semantics only.  It does not run Goal-MPC,
change pacing, or manufacture Human-ID evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
import hashlib
import re
from typing import Any

import numpy as np

from .human_identification_reduced import ReducedShadowHumanIdentificationService
from .human_model_update import (
    BoundedHumanModelTransition,
    build_bounded_human_model_transition,
)


POPULATION_PRIOR_THETA = (1.0, 1.0, 1.0)
PROGRESSIVE_FIXED_GAMMA = 0.5
_SESSION_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class PostUpdateSupport(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


def _theta(values: Any, label: str = "theta") -> tuple[float, float, float]:
    array = np.asarray(values, dtype=float)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{label} must be a finite three-scale vector")
    if np.any(array < 0.5) or np.any(array > 1.5):
        raise ValueError(f"{label} lies outside frozen [0.5,1.5] bounds")
    return tuple(float(value) for value in array)


def human_model_id(
    session_id: str, update_index: int, theta: Any
) -> str:
    """Generate a deterministic identity that cryptographically binds theta."""

    session = str(session_id)
    index = int(update_index)
    values = _theta(theta)
    if not session or _SESSION_ID.fullmatch(session) is None:
        raise ValueError("session id must be a non-empty filesystem-safe token")
    if index < 0:
        raise ValueError("Human-model update index cannot be negative")
    encoded = np.asarray(values, dtype="<f8").tobytes()
    digest = hashlib.sha256(encoded).hexdigest()[:12]
    return f"stage5-human:{session}:u{index:03d}:{digest}"


@dataclass(frozen=True)
class ActiveHumanModel:
    """One immutable control-authorized Human model and its lineage."""

    session_id: str
    update_index: int
    model_id: str
    theta: tuple[float, float, float]
    predecessor_model_id: str | None
    provenance: str
    activation_repetition: int
    activation_time_s: float
    rollback_predecessor_id: str | None
    candidate_evidence_id: str | None
    bounded_transition_delta: tuple[float, float, float]
    qualification_repetition: int | None
    qualification_time_s: float | None
    post_update_support: PostUpdateSupport
    post_update_evidence_id: str | None = None
    post_update_evidence_time_s: float | None = None

    def __post_init__(self) -> None:
        values = _theta(self.theta)
        object.__setattr__(self, "theta", values)
        expected = human_model_id(self.session_id, self.update_index, values)
        if self.model_id != expected:
            raise ValueError("Human-model id and theta/version index disagree")
        if self.activation_repetition < 1 or not np.isfinite(
            self.activation_time_s
        ):
            raise ValueError("activation repetition/time must be valid")
        delta = np.asarray(self.bounded_transition_delta, dtype=float)
        if delta.shape != (3,) or not np.all(np.isfinite(delta)):
            raise ValueError("bounded transition delta must be finite length three")
        if not self.provenance:
            raise ValueError("active Human model requires provenance")
        if self.update_index > 0:
            if not self.predecessor_model_id or not self.rollback_predecessor_id:
                raise ValueError("updated Human model requires predecessor lineage")
            if self.predecessor_model_id != self.rollback_predecessor_id:
                raise ValueError("rollback predecessor must be immediate predecessor")
        if self.candidate_evidence_id is not None and not self.candidate_evidence_id:
            raise ValueError("candidate evidence id cannot be empty")

    @classmethod
    def create(
        cls,
        *,
        session_id: str,
        update_index: int,
        theta: Any,
        predecessor_model_id: str | None,
        provenance: str,
        activation_repetition: int,
        activation_time_s: float,
        rollback_predecessor_id: str | None,
        candidate_evidence_id: str | None,
        bounded_transition_delta: Any = (0.0, 0.0, 0.0),
        qualification_repetition: int | None = None,
        qualification_time_s: float | None = None,
        post_update_support: PostUpdateSupport = PostUpdateSupport.NEUTRAL,
    ) -> "ActiveHumanModel":
        values = _theta(theta)
        return cls(
            session_id=str(session_id),
            update_index=int(update_index),
            model_id=human_model_id(session_id, update_index, values),
            theta=values,
            predecessor_model_id=predecessor_model_id,
            provenance=str(provenance),
            activation_repetition=int(activation_repetition),
            activation_time_s=float(activation_time_s),
            rollback_predecessor_id=rollback_predecessor_id,
            candidate_evidence_id=candidate_evidence_id,
            bounded_transition_delta=tuple(
                float(value) for value in np.asarray(bounded_transition_delta)
            ),
            qualification_repetition=qualification_repetition,
            qualification_time_s=qualification_time_s,
            post_update_support=PostUpdateSupport(post_update_support),
        )

    def with_post_update_support(
        self,
        outcome: PostUpdateSupport,
        *,
        evidence_id: str,
        evidence_time_s: float,
    ) -> "ActiveHumanModel":
        if not evidence_id:
            raise ValueError("post-update evidence id must be explicit")
        if evidence_time_s < self.activation_time_s - 1.0e-12:
            raise ValueError("post-update evidence predates model activation")
        return replace(
            self,
            post_update_support=PostUpdateSupport(outcome),
            post_update_evidence_id=str(evidence_id),
            post_update_evidence_time_s=float(evidence_time_s),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["post_update_support"] = self.post_update_support.value
        return payload


@dataclass(frozen=True)
class QueuedHumanModelUpdate:
    predecessor_model_id: str
    predecessor_theta: tuple[float, float, float]
    successor_model_id: str
    successor_theta: tuple[float, float, float]
    candidate_theta: tuple[float, float, float]
    candidate_evidence_id: str
    transition_source: str
    qualification_repetition: int
    qualification_time_s: float
    target_activation_repetition: int
    transition: BoundedHumanModelTransition

    def __post_init__(self) -> None:
        if not self.predecessor_model_id or not self.successor_model_id:
            raise ValueError("queued update requires explicit model identities")
        if not self.candidate_evidence_id or not self.transition_source:
            raise ValueError("queued update requires causal provenance")
        if self.target_activation_repetition != self.qualification_repetition + 1:
            raise ValueError("queued update must target the next repetition")
        if self.transition.predecessor_version != self.predecessor_model_id:
            raise ValueError("queued transition predecessor identity disagrees")
        if self.transition.successor_version != self.successor_model_id:
            raise ValueError("queued transition successor identity disagrees")
        if not np.allclose(
            self.transition.predecessor_scales,
            self.predecessor_theta,
            atol=0.0,
            rtol=0.0,
        ):
            raise ValueError("queued transition predecessor theta disagrees")
        if not np.allclose(
            self.transition.successor_scales,
            self.successor_theta,
            atol=0.0,
            rtol=0.0,
        ):
            raise ValueError("queued transition successor theta disagrees")

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "transition": self.transition.to_dict(),
        }


class ProgressiveHumanModelAuthority:
    """Deterministic progressive authority with repetition-boundary activation."""

    def __init__(
        self,
        geometry: Any,
        active_model: ActiveHumanModel,
        *,
        updates_enabled: bool = True,
        population_prior_theta: Any = POPULATION_PRIOR_THETA,
    ) -> None:
        self.active_model = active_model
        self.updates_enabled = bool(updates_enabled)
        self.population_prior_theta = _theta(
            population_prior_theta, "population prior theta"
        )
        self.service = ReducedShadowHumanIdentificationService(
            geometry,
            initial_incumbent_scales=active_model.theta,
            initial_model_version=active_model.model_id,
            population_prior_scales=self.population_prior_theta,
            defer_qualified_publication=True,
        )
        self.queued_update: QueuedHumanModelUpdate | None = None
        self.current_repetition: int | None = None
        self.current_repetition_start_time_s: float | None = None
        self.lineage: dict[str, ActiveHumanModel] = {
            active_model.model_id: active_model
        }
        self.history: list[dict[str, Any]] = []
        self._transition_repetitions: set[int] = set()
        self._evidence_ids: set[str] = set()
        self.progression_blocked = (
            active_model.post_update_support is PostUpdateSupport.NEGATIVE
        )

    @property
    def can_qualify_next(self) -> bool:
        return bool(
            self.updates_enabled
            and not self.progression_blocked
            and self.queued_update is None
            and self.active_model.post_update_support is PostUpdateSupport.POSITIVE
        )

    @property
    def control_human_model(self) -> Any:
        """Return the dynamics object bound to the one authorized active state."""

        self._assert_service_alignment()
        return self.service.retained_model

    def _assert_service_alignment(self) -> None:
        if self.service.retained_model_version != self.active_model.model_id:
            raise RuntimeError("Human-ID incumbent version disagrees with active model")
        if not np.allclose(
            self.service.retained_scales,
            self.active_model.theta,
            atol=0.0,
            rtol=0.0,
        ):
            raise RuntimeError("Human-ID incumbent theta disagrees with active model")

    def begin_repetition(
        self, repetition: int, session_time_s: float
    ) -> dict[str, Any]:
        repetition = int(repetition)
        timestamp = float(session_time_s)
        if repetition < 1 or not np.isfinite(timestamp):
            raise ValueError("repetition boundary must be finite and positive")
        if self.current_repetition is None:
            if repetition != self.active_model.activation_repetition:
                raise ValueError("first repetition must match active-model activation")
        elif repetition != self.current_repetition + 1:
            raise ValueError("repetition indices must increase one at a time")
        if (
            self.current_repetition_start_time_s is not None
            and timestamp <= self.current_repetition_start_time_s
        ):
            raise ValueError("repetition session times must increase")

        activation = None
        if self.queued_update is not None:
            queued = self.queued_update
            if queued.target_activation_repetition != repetition:
                raise RuntimeError("queued update reached the wrong repetition boundary")
            if queued.predecessor_model_id != self.active_model.model_id:
                raise RuntimeError("queued update predecessor is stale")
            if repetition in self._transition_repetitions:
                raise RuntimeError("more than one model transition in a repetition")
            previous = self.active_model
            activated = ActiveHumanModel.create(
                session_id=previous.session_id,
                update_index=previous.update_index + 1,
                theta=queued.successor_theta,
                predecessor_model_id=previous.model_id,
                provenance=queued.transition_source,
                activation_repetition=repetition,
                activation_time_s=timestamp,
                rollback_predecessor_id=previous.model_id,
                candidate_evidence_id=queued.candidate_evidence_id,
                bounded_transition_delta=queued.transition.applied_bounded_displacement,
                qualification_repetition=queued.qualification_repetition,
                qualification_time_s=queued.qualification_time_s,
                post_update_support=PostUpdateSupport.NEUTRAL,
            )
            if activated.model_id != queued.successor_model_id:
                raise RuntimeError("queued successor identity changed before activation")
            self.service.activate_incumbent(
                scales=activated.theta,
                model_version=activated.model_id,
                expected_predecessor_version=previous.model_id,
                activation_time_s=timestamp,
                qualification_evidence_id=queued.candidate_evidence_id,
            )
            self.active_model = activated
            self.lineage[activated.model_id] = activated
            self.queued_update = None
            self._transition_repetitions.add(repetition)
            activation = {
                "predecessor_model_id": previous.model_id,
                "active_model_id": activated.model_id,
                "activation_repetition": repetition,
                "activation_time_s": timestamp,
            }
            self.history.append({"event": "model_activated", **activation})

        self.current_repetition = repetition
        self.current_repetition_start_time_s = timestamp
        self.service.begin_episode(repetition - 1, timestamp)
        self._assert_service_alignment()
        self.history.append(
            {
                "event": "repetition_started",
                "repetition": repetition,
                "session_time_s": timestamp,
                "active_model_id": self.active_model.model_id,
            }
        )
        return {
            "active_model": self.active_model.to_dict(),
            "activation": activation,
            "gamma": PROGRESSIVE_FIXED_GAMMA,
        }

    def _queue_qualified_successor(
        self,
        *,
        predecessor_model_id: str,
        candidate_theta: Any,
        candidate_evidence_id: str,
        transition_source: str,
        qualification_repetition: int,
        qualification_time_s: float,
    ) -> QueuedHumanModelUpdate:
        self._assert_service_alignment()
        if not self.updates_enabled:
            raise RuntimeError("fixed-model arm cannot queue Human-model updates")
        if self.current_repetition is None:
            raise RuntimeError("cannot qualify a model outside a repetition")
        if self.progression_blocked:
            raise RuntimeError("progressive updates are blocked by negative evidence")
        if self.active_model.post_update_support is not PostUpdateSupport.POSITIVE:
            raise RuntimeError("active model lacks POSITIVE post-update support")
        if predecessor_model_id != self.active_model.model_id:
            raise RuntimeError("candidate predecessor is stale or incorrect")
        if int(qualification_repetition) != self.current_repetition:
            raise ValueError("qualification repetition is not current")
        if (
            self.current_repetition_start_time_s is None
            or float(qualification_time_s)
            < self.current_repetition_start_time_s - 1.0e-12
        ):
            raise ValueError("qualification time predates current repetition")
        if self.queued_update is not None:
            raise RuntimeError("one successor is already queued")
        if not candidate_evidence_id or candidate_evidence_id in self._evidence_ids:
            raise ValueError("candidate evidence id must be new and explicit")

        candidate = _theta(candidate_theta, "candidate theta")
        successor_index = self.active_model.update_index + 1
        provisional = self.service.identifier.bounded_smoothed_step(
            np.asarray(self.active_model.theta), np.asarray(candidate)
        )
        successor_id = human_model_id(
            self.active_model.session_id, successor_index, provisional
        )
        transition = build_bounded_human_model_transition(
            self.service.identifier,
            np.asarray(self.active_model.theta),
            np.asarray(candidate),
            predecessor_version=self.active_model.model_id,
            candidate_version=str(candidate_evidence_id),
            successor_version=successor_id,
        )
        queued = QueuedHumanModelUpdate(
            predecessor_model_id=self.active_model.model_id,
            predecessor_theta=self.active_model.theta,
            successor_model_id=successor_id,
            successor_theta=_theta(transition.successor_scales),
            candidate_theta=candidate,
            candidate_evidence_id=str(candidate_evidence_id),
            transition_source=str(transition_source),
            qualification_repetition=self.current_repetition,
            qualification_time_s=float(qualification_time_s),
            target_activation_repetition=self.current_repetition + 1,
            transition=transition,
        )
        self.queued_update = queued
        self._evidence_ids.add(str(candidate_evidence_id))
        self.history.append(
            {
                "event": "successor_queued",
                "repetition": self.current_repetition,
                "predecessor_model_id": self.active_model.model_id,
                "successor_model_id": successor_id,
                "candidate_evidence_id": str(candidate_evidence_id),
                "qualification_time_s": float(qualification_time_s),
            }
        )
        return queued

    def queue_service_qualified_successor(
        self,
        *,
        transition_source: str,
        qualification_repetition: int,
    ) -> QueuedHumanModelUpdate:
        """Consume the service's causally qualified deferred proposal."""

        proposal = self.service.queued_publication
        if proposal is None:
            raise RuntimeError("Human-ID service has no qualified deferred proposal")
        if proposal["predecessor_model_version"] != self.active_model.model_id:
            raise RuntimeError("Human-ID qualified proposal has a stale predecessor")
        queued = self._queue_qualified_successor(
            predecessor_model_id=str(proposal["predecessor_model_version"]),
            candidate_theta=proposal["candidate_scales"],
            candidate_evidence_id=str(proposal["qualification_evidence_id"]),
            transition_source=transition_source,
            qualification_repetition=qualification_repetition,
            qualification_time_s=float(proposal["qualification_time_s"]),
        )
        if not np.allclose(
            queued.successor_theta,
            np.asarray(proposal["proposed_model_scales"], dtype=float),
            atol=1.0e-12,
            rtol=0.0,
        ):
            self.queued_update = None
            raise RuntimeError("authority successor differs from Human-ID proposal")
        return queued

    def record_post_update_evidence(
        self,
        outcome: PostUpdateSupport,
        *,
        target_model_id: str,
        predecessor_model_id: str,
        evidence_id: str,
        evidence_repetition: int,
        evidence_time_s: float,
    ) -> ActiveHumanModel:
        if self.current_repetition is None:
            raise RuntimeError("post-update evidence requires an active repetition")
        if target_model_id != self.active_model.model_id:
            raise RuntimeError("post-update evidence targets a stale model")
        if predecessor_model_id != self.active_model.predecessor_model_id:
            raise RuntimeError("post-update evidence predecessor disagrees with lineage")
        if int(evidence_repetition) != self.current_repetition:
            raise ValueError("post-update evidence repetition is not current")
        if not evidence_id or evidence_id in self._evidence_ids:
            raise ValueError("post-update evidence id must be new and explicit")
        classified = PostUpdateSupport(outcome)
        self.active_model = self.active_model.with_post_update_support(
            classified,
            evidence_id=evidence_id,
            evidence_time_s=float(evidence_time_s),
        )
        self.lineage[self.active_model.model_id] = self.active_model
        self._evidence_ids.add(str(evidence_id))
        if classified is PostUpdateSupport.NEGATIVE:
            self.progression_blocked = True
        self.history.append(
            {
                "event": "post_update_evidence",
                "repetition": int(evidence_repetition),
                "target_model_id": target_model_id,
                "predecessor_model_id": predecessor_model_id,
                "outcome": classified.value,
                "evidence_id": str(evidence_id),
                "evidence_time_s": float(evidence_time_s),
            }
        )
        return self.active_model

    def pacing_status(self) -> dict[str, float]:
        return {"gamma": PROGRESSIVE_FIXED_GAMMA, "gamma_rate_per_s": 0.0}

    def summary(self) -> dict[str, Any]:
        return {
            "active_model": self.active_model.to_dict(),
            "population_prior": {
                "theta": list(self.population_prior_theta),
                "transition_authority": False,
                "regularization_reference": True,
            },
            "queued_update": (
                None if self.queued_update is None else self.queued_update.to_dict()
            ),
            "lineage": {
                model_id: model.to_dict() for model_id, model in self.lineage.items()
            },
            "history": list(self.history),
            "updates_enabled": self.updates_enabled,
            "progression_blocked": self.progression_blocked,
            "can_qualify_next": self.can_qualify_next,
            "gamma_authority": False,
            "truth_available": False,
        }


__all__ = [
    "ActiveHumanModel",
    "POPULATION_PRIOR_THETA",
    "PROGRESSIVE_FIXED_GAMMA",
    "PostUpdateSupport",
    "ProgressiveHumanModelAuthority",
    "QueuedHumanModelUpdate",
    "human_model_id",
]
