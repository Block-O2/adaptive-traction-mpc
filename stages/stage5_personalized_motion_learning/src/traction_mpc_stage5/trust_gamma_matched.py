"""Frozen contract helpers for the formal Stage-5 trust-to-gamma A/B."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    nominal_base_parameters,
)
from traction_mpc_stage4.minimal_adaptation import effective_base_parameters

from .confidence_pacing import (
    CurrentModelTrustEvidence,
    CurrentModelTrustOutcome,
    Stage5ConfidencePacing,
    Stage5CurrentModelTrust,
)
from .config import STAGE5_ROOT
from .human import STAGE5_HUMAN
from .progressive_human_model import human_model_id


TRUST_GAMMA_CONFIG_PATH = (
    STAGE5_ROOT / "configs" / "stage5_trust_gamma_matched_v1.json"
)
TRUST_GAMMA_CEM_SEEDS = (20260917, 20260918, 20260919)
TRUST_GAMMA_ARMS = ("fixed_pacing", "trust_driven_pacing")


@dataclass(frozen=True)
class FrozenSupportedHumanModel:
    """Exact personalized model and causal support imported from formal evidence."""

    model_id: str
    theta: tuple[float, float, float]
    session_id: str
    update_index: int
    predecessor_model_id: str
    activation_repetition: int
    activation_time_s: float
    support_evidence_id: str
    support_evidence_time_s: float
    support_outcome: str
    provenance: str
    source_artifact_sha256: str


def load_trust_gamma_contract(
    path: Path = TRUST_GAMMA_CONFIG_PATH,
) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_trust_gamma_matched_v1":
        raise ValueError("unexpected trust-gamma contract schema")
    if payload.get("status") != "PREREGISTERED_FORMAL_EXECUTION_AUTHORIZED":
        raise ValueError("trust-gamma formal execution is not authorized")
    policy = payload["source_personalization_policy"]
    if (
        float(policy["model_update_alpha"]) != 0.25
        or float(policy["maximum_per_scale_step"]) != 0.04
        or policy["frozen_for_this_study"] is not True
    ):
        raise ValueError("frozen personalization policy changed")
    repetitions = payload["repetitions"]
    if int(repetitions["per_arm"]) != 3:
        raise ValueError("trust-gamma comparison requires three repetitions per arm")
    if tuple(repetitions["matched_cem_seeds"]) != TRUST_GAMMA_CEM_SEEDS:
        raise ValueError("trust-gamma seed schedule changed")
    if not repetitions["same_seed_for_both_arms_at_each_repetition"]:
        raise ValueError("trust-gamma comparison requires matched seeds")
    fixed = payload["fixed_conditions"]
    if (
        fixed["human_truth_condition"] != "damping_plus_20pct"
        or fixed["interface"] != "fixed_nominal"
        or fixed["prefix_backend"] != "native"
        or fixed["prefix_times_ms"] != [5, 10, 15, 20]
        or fixed["human_model_updates_enabled"]
        or fixed["successor_activation_enabled"]
        or fixed["human_identification_control_authority"]
        or fixed["task_interface_acceleration_monitor_limits_safety_filter_brake_changed"]
    ):
        raise ValueError("one or more fixed trust-gamma conditions changed")
    trust_arm = payload["arms"]["trust_driven_pacing"]
    expected = {
        "initial_gamma": 0.5,
        "initial_filtered_confidence": 0.0,
        "gamma_min": 0.5,
        "gamma_max": 1.0,
        "filter_time_constant_s": 0.75,
        "high_confidence_enter": 0.75,
        "high_confidence_exit": 0.25,
        "recovery_rate_per_s": 0.25,
        "slowdown_rate_per_s": 1.0,
    }
    if any(float(trust_arm[key]) != value for key, value in expected.items()):
        raise ValueError("existing trust-pacing parameters changed")
    return payload


def source_artifact_path(contract: dict[str, Any]) -> Path:
    return STAGE5_ROOT / str(contract["source_artifact"]["relative_path"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_supported_model(
    contract: dict[str, Any] | None = None,
) -> FrozenSupportedHumanModel:
    """Extract, never approximate, the supported final active step=0.04 model."""

    frozen = load_trust_gamma_contract() if contract is None else contract
    artifact_path = source_artifact_path(frozen)
    observed_hash = _sha256(artifact_path)
    expected_hash = str(frozen["source_artifact"]["sha256"])
    if observed_hash != expected_hash:
        raise ValueError("formal max-step source artifact hash changed")
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_model_update_max_step_comparison_v1_results":
        raise ValueError("unexpected source personalization artifact schema")
    if payload.get("fixed_model_update_alpha") != 0.25:
        raise ValueError("source artifact alpha is not the frozen 0.25")
    arm_name = str(frozen["source_artifact"]["arm"])
    arm = payload["arms"][arm_name]
    if float(arm["maximum_per_scale_step"]) != 0.04:
        raise ValueError("source artifact is not the supported step=0.04 arm")
    active = arm["authority_summary"]["active_model"]
    row = arm["rows"][-1]
    evidence = row["authority_end"]["post_update_evidence"]
    classification = evidence["classification"]
    if (
        active["model_id"] != row["active_model_id"]
        or active["model_id"] != evidence["target_model_id"]
        or active["post_update_support"] != "positive"
        or classification["outcome"] != "positive"
        or active["post_update_evidence_id"] is None
        or active["post_update_evidence_time_s"] is None
    ):
        raise ValueError("source active model lacks matching post-update support")
    theta = tuple(float(value) for value in active["theta"])
    if human_model_id(active["session_id"], active["update_index"], theta) != active[
        "model_id"
    ]:
        raise ValueError("source model id does not bind the recorded theta")
    queued = arm["authority_summary"].get("queued_update")
    if queued is not None and queued["successor_model_id"] == active["model_id"]:
        raise ValueError("source artifact active/queued identities are ambiguous")
    return FrozenSupportedHumanModel(
        model_id=str(active["model_id"]),
        theta=theta,
        session_id=str(active["session_id"]),
        update_index=int(active["update_index"]),
        predecessor_model_id=str(active["predecessor_model_id"]),
        activation_repetition=int(active["activation_repetition"]),
        activation_time_s=float(active["activation_time_s"]),
        support_evidence_id=str(active["post_update_evidence_id"]),
        support_evidence_time_s=float(active["post_update_evidence_time_s"]),
        support_outcome=str(classification["outcome"]),
        provenance=str(active["provenance"]),
        source_artifact_sha256=observed_hash,
    )


def build_control_human_model(
    geometry: Any, frozen: FrozenSupportedHumanModel
) -> BaseParameterHumanModel:
    return BaseParameterHumanModel(
        geometry,
        effective_base_parameters(
            np.asarray(frozen.theta, dtype=float),
            nominal_base_parameters(STAGE5_HUMAN),
        ),
        STAGE5_HUMAN,
    )


def initialize_supported_trust(
    frozen: FrozenSupportedHumanModel,
) -> tuple[Stage5CurrentModelTrust, Stage5ConfidencePacing]:
    """Restore raw support; deliberately leave filtered confidence at zero."""

    trust = Stage5CurrentModelTrust(frozen.model_id)
    trust.observe(
        CurrentModelTrustEvidence(
            session_time_s=0.0,
            current_model_version=frozen.model_id,
            outcome=CurrentModelTrustOutcome.SUPPORT,
            evidence_version=frozen.support_evidence_id,
            reason=(
                "restored_exact_post_update_positive_support_from_"
                "formal_step_0p04_artifact"
            ),
        )
    )
    pacing = Stage5ConfidencePacing(initial_session_time_s=0.0)
    if pacing.filtered_current_model_confidence != 0.0:
        raise RuntimeError("filtered confidence must not be hand-initialized")
    if pacing.status(0.0)["gamma"] != 0.5:
        raise RuntimeError("trust-driven pacing must start at gamma=0.5")
    return trust, pacing


__all__ = [
    "FrozenSupportedHumanModel",
    "TRUST_GAMMA_ARMS",
    "TRUST_GAMMA_CEM_SEEDS",
    "TRUST_GAMMA_CONFIG_PATH",
    "build_control_human_model",
    "extract_supported_model",
    "initialize_supported_trust",
    "load_trust_gamma_contract",
    "source_artifact_path",
]
