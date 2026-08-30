"""Preregistered professor-report validation infrastructure.

This module adds orchestration and adapter layers around the frozen Stage-4
plant, estimator, allocator, and MPC.  It does not redefine those components
and does not authorize formal execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Callable, Iterable

import numpy as np

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage3.reference import CuffPoseReference

from .artifact_paths import resolve_stage_artifact
from .cuff_allocator import REGISTERED_CUFF_AWARE_ALLOCATOR_CONFIG
from .estimator_v2 import nominal_base_parameters
from .human_model import inverse_dynamics
from .measurement import MeasurementCase, sensor_realism_cases
from .mpc import HumanMPCConfig, HumanSpaceMPC
from .online_trust import OnlineSingleChallengerTrustEstimator
from .patient_mismatch import (
    PatientCaseSpec,
    load_patient_case_specs,
    patient_case_record,
)
from .sensor_realism import run_sensor_realism_case
from .trajectory_excitation import (
    load_trajectory_suite,
    trajectory_case,
    trajectory_reference,
    trajectory_waypoints,
)


MATRIX_SCHEMA_VERSION_V1 = "stage4_report_validation_matrix_v1"
MATRIX_SCHEMA_VERSION_V2 = "stage4_report_validation_matrix_v2_coupled_pd"
MATRIX_SCHEMA_VERSION = MATRIX_SCHEMA_VERSION_V1
MATRIX_SCHEMA_VERSIONS = {MATRIX_SCHEMA_VERSION_V1, MATRIX_SCHEMA_VERSION_V2}
GAIN_LOCK_SCHEMA_VERSION_V1 = "stage4_report_validation_pd_gain_lock_v1"
GAIN_LOCK_SCHEMA_VERSION_V2 = "stage4_report_validation_pd_gain_lock_v2_coupled_pd"
GAIN_LOCK_SCHEMA_VERSION = GAIN_LOCK_SCHEMA_VERSION_V1
GAIN_LOCK_SCHEMA_VERSIONS = {
    GAIN_LOCK_SCHEMA_VERSION_V1,
    GAIN_LOCK_SCHEMA_VERSION_V2,
}
RUN_MANIFEST_SCHEMA_VERSION = "stage4_report_validation_run_manifest_v1"
SMOKE_MANIFEST_SCHEMA_VERSION = "stage4_report_validation_smoke_manifest_v1"
REPORT_CONTROLLER_PERIOD_S = 0.02
STRUCTURAL_SMOKE_MAX_DURATION_S = 0.5
GAIN_DIAGNOSTIC_SMOKE_MAX_DURATION_S = 1.5


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def strict_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): strict_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [strict_json(item) for item in value]
    if isinstance(value, np.ndarray):
        return strict_json(value.tolist())
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def write_strict_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            strict_json(value),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def report_root(matrix_path: Path) -> Path:
    return Path(matrix_path).resolve().parent.parent


def load_report_validation_matrix(matrix_path: Path) -> dict[str, Any]:
    path = Path(matrix_path).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema_version = payload.get("schema_version")
    if schema_version not in MATRIX_SCHEMA_VERSIONS:
        raise ValueError("unsupported report-validation matrix schema")
    expected_status = {
        MATRIX_SCHEMA_VERSION_V1: "preregistered_design_only_no_formal_execution",
        MATRIX_SCHEMA_VERSION_V2: (
            "approved_preregistration_amendment_v2_no_formal_execution_yet"
        ),
    }[schema_version]
    if payload.get("design_status") != expected_status:
        raise ValueError("report-validation matrix is not the frozen design")
    root = report_root(path)
    if schema_version == MATRIX_SCHEMA_VERSION_V2:
        base = payload["base_v1_contract"]
        base_path = resolve_stage_artifact(root, base["path"])
        if base.get("immutable") is not True or sha256_file(base_path) != base["sha256"]:
            raise ValueError("immutable v1 report-validation contract hash mismatch")
        v1 = payload["amendment"]["v1_formal_gain_selection"]
        status_path = resolve_stage_artifact(root, v1["status_path"])
        if (
            v1.get("immutable") is not True
            or not status_path.is_file()
            or sha256_file(status_path) != v1["status_sha256"]
        ):
            raise ValueError("preserved v1 failed gain-selection evidence mismatch")
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if (
            status.get("status") != "no_mechanically_eligible_candidate"
            or status.get("formal_gain_lock_created") is not False
        ):
            raise ValueError("preserved v1 gain-selection status is inconsistent")
    for name, source in payload["source_artifacts"].items():
        source_path = resolve_stage_artifact(root, source["path"])
        if not source_path.is_file():
            raise FileNotFoundError(f"missing frozen source artifact {name}: {source_path}")
        actual = sha256_file(source_path)
        if actual != source["sha256"]:
            raise ValueError(
                f"frozen source artifact hash mismatch for {name}: "
                f"{actual} != {source['sha256']}"
            )
    return payload


def gain_candidates(matrix: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    tuning = matrix["gain_tuning"]
    coupled = matrix["schema_version"] == MATRIX_SCHEMA_VERSION_V2
    if coupled:
        base_kp = np.asarray(tuning["base_kp_tau_matrix_nm_per_rad"], dtype=float)
        base_kd = np.asarray(tuning["base_kd_tau_matrix_nms_per_rad"], dtype=float)
        if base_kp.shape != (2, 2) or base_kd.shape != (2, 2):
            raise ValueError("v2 coupled PD gains must be 2 by 2 matrices")
    else:
        base_kp = np.asarray(tuning["base_kp_tau_nm_per_rad"], dtype=float)
        base_kd = np.asarray(tuning["base_kd_tau_nms_per_rad"], dtype=float)
    candidates = tuple(
        {
            "candidate_id": f"kp_{kp_scale:g}__kd_{kd_scale:g}",
            "kp_scale": float(kp_scale),
            "kd_scale": float(kd_scale),
            **(
                {
                    "gain_definition": (
                        "constant_nominal_inertia_derived_coupled_torque_pd_v2"
                    ),
                    "kp_tau_matrix_nm_per_rad": (
                        float(kp_scale) * base_kp
                    ).tolist(),
                    "kd_tau_matrix_nms_per_rad": (
                        float(kd_scale) * base_kd
                    ).tolist(),
                }
                if coupled
                else {
                    "kp_tau_nm_per_rad": (float(kp_scale) * base_kp).tolist(),
                    "kd_tau_nms_per_rad": (float(kd_scale) * base_kd).tolist(),
                }
            ),
        }
        for kp_scale, kd_scale in itertools.product(
            tuning["kp_scales"], tuning["kd_scales"]
        )
    )
    if len(candidates) != int(tuning["candidate_count"]):
        raise RuntimeError("gain grid differs from preregistered candidate count")
    return candidates


def _event_free(events: dict[str, Any]) -> bool:
    for value in events.values():
        if isinstance(value, dict) and value:
            return False
        if isinstance(value, (list, tuple)) and value:
            return False
        if isinstance(value, (int, float)) and float(value) != 0.0:
            return False
    return True


def candidate_mechanically_eligible(record: dict[str, Any]) -> bool:
    required = (
        "tracking_combined_rmse_deg",
        "tracking_max_abs_error_deg",
        "cuff_force_rms_n",
    )
    return bool(
        record.get("termination_reason") == "completed"
        and math.isclose(
            float(record.get("reference_progress_fraction", 0.0)),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        and _event_free(dict(record.get("safety_events", {})))
        and all(
            isinstance(record.get(key), (int, float))
            and math.isfinite(float(record[key]))
            for key in required
        )
    )


def select_gain_candidate(
    records: Iterable[dict[str, Any]], *, tie_tolerance: float
) -> dict[str, Any]:
    eligible = [dict(record) for record in records if candidate_mechanically_eligible(record)]
    if not eligible:
        raise RuntimeError(
            "no preregistered gain candidate is mechanically eligible; "
            "preserve outputs and request user direction"
        )
    for key in (
        "tracking_combined_rmse_deg",
        "tracking_max_abs_error_deg",
        "cuff_force_rms_n",
    ):
        best = min(float(item[key]) for item in eligible)
        eligible = [
            item
            for item in eligible
            if abs(float(item[key]) - best) <= float(tie_tolerance)
        ]
    eligible.sort(key=lambda item: (float(item["kp_scale"]), float(item["kd_scale"])))
    return eligible[0]


def gain_lock_payload(
    *,
    matrix_sha256: str,
    candidate_records: Iterable[dict[str, Any]],
    selected: dict[str, Any],
    lock_kind: str,
) -> dict[str, Any]:
    if lock_kind not in {"formal", "structural_smoke"}:
        raise ValueError("gain-lock kind must be formal or structural_smoke")
    records = [strict_json(item) for item in candidate_records]
    gain_definition = selected.get("gain_definition", "diagonal_torque_pd_v1")
    coupled = gain_definition == (
        "constant_nominal_inertia_derived_coupled_torque_pd_v2"
    )
    payload: dict[str, Any] = {
        "schema_version": (
            GAIN_LOCK_SCHEMA_VERSION_V2 if coupled else GAIN_LOCK_SCHEMA_VERSION_V1
        ),
        "lock_kind": lock_kind,
        "scientific_interpretation_permitted": False,
        "formal_gain_lock": lock_kind == "formal",
        "report_validation_config_sha256": matrix_sha256,
        "candidate_count": len(records),
        "candidate_records": records,
        "selected_candidate_id": selected["candidate_id"],
        "selected_kp_scale": float(selected["kp_scale"]),
        "selected_kd_scale": float(selected["kd_scale"]),
        "gains_shared_by": ["pd_feedback", "pd_nominal_inverse_dynamics_ff"],
        "selection_rule": (
            "mechanical_eligibility_then_tracking_rmse_then_max_error_then_"
            "cuff_force_rms_then_lower_kp_then_lower_kd"
        ),
    }
    if coupled:
        payload["gain_definition"] = gain_definition
        payload["kp_tau_matrix_nm_per_rad"] = strict_json(
            selected["kp_tau_matrix_nm_per_rad"]
        )
        payload["kd_tau_matrix_nms_per_rad"] = strict_json(
            selected["kd_tau_matrix_nms_per_rad"]
        )
    else:
        payload["kp_tau_nm_per_rad"] = [
            float(value) for value in selected["kp_tau_nm_per_rad"]
        ]
        payload["kd_tau_nms_per_rad"] = [
            float(value) for value in selected["kd_tau_nms_per_rad"]
        ]
    payload["payload_sha256"] = canonical_json_sha256(payload)
    return payload


def write_gain_lock(path: Path, payload: dict[str, Any]) -> str:
    target = Path(path)
    sidecar = target.with_suffix(target.suffix + ".sha256")
    if target.exists() or sidecar.exists():
        raise FileExistsError(f"refusing to overwrite gain lock {target}")
    expected = payload.get("payload_sha256")
    unsigned = {key: value for key, value in payload.items() if key != "payload_sha256"}
    if expected != canonical_json_sha256(unsigned):
        raise ValueError("gain-lock payload hash is invalid")
    write_strict_json(target, payload)
    artifact_hash = sha256_file(target)
    sidecar.write_text(f"{artifact_hash}  {target.name}\n", encoding="utf-8")
    return artifact_hash


def load_gain_lock(path: Path, *, required_kind: str | None = None) -> tuple[dict[str, Any], str]:
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema_version") not in GAIN_LOCK_SCHEMA_VERSIONS:
        raise ValueError("unsupported gain-lock schema")
    unsigned = {key: value for key, value in payload.items() if key != "payload_sha256"}
    if payload.get("payload_sha256") != canonical_json_sha256(unsigned):
        raise ValueError("gain-lock payload hash mismatch")
    if required_kind is not None and payload.get("lock_kind") != required_kind:
        raise ValueError(
            f"gain-lock kind {payload.get('lock_kind')!r} is not {required_kind!r}"
        )
    return payload, sha256_file(target)


class ExternalPhaseReferenceClock:
    """Read-only, controller-independent replay of the frozen phase trace."""

    def __init__(
        self,
        base_reference: Callable[[float], CuffPoseReference],
        *,
        source_path: Path,
        expected_sha256: str,
        source_duration_s: float,
        trajectory_duration_s: float,
    ) -> None:
        self.base_reference = base_reference
        self.source_path = Path(source_path).resolve()
        self.expected_sha256 = str(expected_sha256)
        self.source_duration_s = float(source_duration_s)
        self.trajectory_duration_s = float(trajectory_duration_s)
        if self.source_duration_s <= 0.0 or self.trajectory_duration_s <= 0.0:
            raise ValueError("reference durations must be positive")
        actual_hash = sha256_file(self.source_path)
        if actual_hash != self.expected_sha256:
            raise ValueError("external reference-clock source hash mismatch")
        with np.load(self.source_path, allow_pickle=False) as archive:
            self.source_time_s = np.asarray(archive["time_s"], dtype=float).copy()
            self.source_phase_s = np.asarray(
                archive["reference_phase_time_s"], dtype=float
            ).copy()
        if (
            self.source_time_s.ndim != 1
            or self.source_phase_s.shape != self.source_time_s.shape
            or len(self.source_time_s) < 3
            or not np.all(np.isfinite(self.source_time_s))
            or not np.all(np.isfinite(self.source_phase_s))
            or np.any(np.diff(self.source_time_s) <= 0.0)
            or np.any(np.diff(self.source_phase_s) < -1e-12)
        ):
            raise ValueError("external reference-clock trace is invalid")
        self.phase_scale = self.trajectory_duration_s / self.source_duration_s
        self.source_speed = np.gradient(
            self.source_phase_s, self.source_time_s, edge_order=2
        )
        self.source_acceleration = np.gradient(
            self.source_speed, self.source_time_s, edge_order=2
        )
        self.update_count = 0

    def _state(self, wall_time_s: float) -> tuple[float, float, float]:
        time_s = float(wall_time_s)
        phase = self.phase_scale * float(
            np.interp(
                time_s,
                self.source_time_s,
                self.source_phase_s,
                left=self.source_phase_s[0],
                right=self.source_phase_s[-1],
            )
        )
        speed = self.phase_scale * float(
            np.interp(time_s, self.source_time_s, self.source_speed)
        )
        acceleration = self.phase_scale * float(
            np.interp(time_s, self.source_time_s, self.source_acceleration)
        )
        return (
            float(np.clip(phase, 0.0, self.trajectory_duration_s)),
            max(0.0, speed),
            acceleration,
        )

    def phase_time_s(self, wall_time_s: float) -> float:
        return self._state(wall_time_s)[0]

    def reference(self, wall_time_s: float) -> CuffPoseReference:
        phase, speed, acceleration = self._state(wall_time_s)
        base = self.base_reference(phase)
        return CuffPoseReference(
            q_rad=base.q_rad.copy(),
            dq_rad_s=speed * base.dq_rad_s,
            ddq_rad_s2=(
                speed**2 * base.ddq_rad_s2 + acceleration * base.dq_rad_s
            ),
            world_from_cuff=base.world_from_cuff,
        )

    def update_from_estimator(self, *_: Any, **__: Any) -> None:
        # Deliberate no-op: controller, confidence, and estimator state cannot
        # alter the preregistered phase replay.
        self.update_count += 1

    def status(self, wall_time_s: float) -> dict[str, float]:
        phase, speed, acceleration = self._state(wall_time_s)
        return {
            "reference_phase_time_s": phase,
            "speed_scale": speed,
            "speed_scale_rate_per_s": acceleration,
            "geometry_confidence": 0.0,
            "dynamic_confidence": 0.0,
            "combined_confidence": 0.0,
            "geometry_model_confidence": 0.0,
            "dynamic_model_confidence": 0.0,
            "combined_model_confidence_raw": 0.0,
            "filtered_model_confidence": 0.0,
            "execution_confidence_high": 0.0,
            "geometry_information_confidence": 0.0,
            "dynamic_information_confidence": 0.0,
            "combined_information_confidence": 0.0,
        }

    def summary(self, wall_time_s: float) -> dict[str, Any]:
        return {
            "mode": "frozen_exogenous_phase_replay",
            "config": {
                "source_path": str(self.source_path),
                "source_sha256": self.expected_sha256,
                "source_duration_s": self.source_duration_s,
                "trajectory_duration_s": self.trajectory_duration_s,
                "interpolation": "linear_on_recorded_time_grid",
                "derivatives": "deterministic_finite_difference_of_phase_only",
            },
            "final_status": self.status(wall_time_s),
            "confidence_update_count": self.update_count,
            "controller_confidence_affects_phase": False,
            "controller_state_affects_phase": False,
            "reads_source_keys": ["time_s", "reference_phase_time_s"],
            "estimator_modified": False,
            "mpc_modified": False,
            "safety_limits_modified": False,
        }


@dataclass(frozen=True)
class HumanActionAdapterConfig:
    controller_id: str
    prediction_dt_s: float = REPORT_CONTROLLER_PERIOD_S

    @property
    def interaction_aware(self) -> bool:
        return False

    def objective_contract(self) -> dict[str, Any]:
        return {
            "controller_id": self.controller_id,
            "interface": "human_generalized_cuff_action_nm",
            "optimization": "none",
            "shared_low_level_cartesian_feedback_retained": True,
        }


class PDHumanActionController:
    """Constant Human-space torque PD, optionally plus nominal feedforward."""

    def __init__(
        self,
        *,
        controller_id: str,
        kp_tau_nm_per_rad: np.ndarray,
        kd_tau_nms_per_rad: np.ndarray,
        nominal_feedforward: bool,
    ) -> None:
        if controller_id not in {
            "pd_feedback",
            "pd_nominal_inverse_dynamics_ff",
        }:
            raise ValueError("unsupported PD controller id")
        self.config = HumanActionAdapterConfig(controller_id)
        self.kp = np.asarray(kp_tau_nm_per_rad, dtype=float)
        self.kd = np.asarray(kd_tau_nms_per_rad, dtype=float)
        if self.kp.shape != self.kd.shape or self.kp.shape not in {(2,), (2, 2)}:
            raise ValueError("PD gains must be matching two-vectors or 2 by 2 matrices")
        if not np.all(np.isfinite(self.kp)) or not np.all(np.isfinite(self.kd)):
            raise ValueError("PD gains must be finite")
        if self.kp.shape == (2,):
            if np.any(self.kp < 0.0) or np.any(self.kd < 0.0):
                raise ValueError("diagonal PD gains must be nonnegative")
        elif np.any(np.diag(self.kp) <= 0.0) or np.any(np.diag(self.kd) <= 0.0):
            raise ValueError("coupled PD gain matrices must have positive diagonals")
        self.nominal_feedforward = bool(nominal_feedforward)
        self.gain_definition = (
            "constant_nominal_inertia_derived_coupled_torque_pd_v2"
            if self.kp.shape == (2, 2)
            else "diagonal_torque_pd_v1"
        )
        self.solve_count = 0
        self.failure_count = 0
        self.last_diagnostics: dict[str, Any] = {}

    def solve(
        self,
        state: np.ndarray,
        time_s: float,
        reference_fn: Callable[[float], CuffPoseReference],
        human: Any,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        x = np.asarray(state, dtype=float)
        reference = reference_fn(float(time_s))
        q_error = np.asarray(reference.q_rad) - x[:2]
        dq_error = np.asarray(reference.dq_rad_s) - x[2:]
        if self.kp.shape == (2, 2):
            proportional = self.kp @ q_error
            derivative = self.kd @ dq_error
        else:
            proportional = self.kp * q_error
            derivative = self.kd * dq_error
        feedback = proportional + derivative
        feedforward = np.zeros(2)
        if self.nominal_feedforward:
            if hasattr(human, "inverse_dynamics"):
                feedforward = np.asarray(
                    human.inverse_dynamics(
                        reference.q_rad,
                        reference.dq_rad_s,
                        reference.ddq_rad_s2,
                    ),
                    dtype=float,
                )
            else:
                feedforward = inverse_dynamics(
                    reference.q_rad,
                    reference.dq_rad_s,
                    reference.ddq_rad_s2,
                    HUMAN,
                )
        action = feedback + feedforward
        self.solve_count += 1
        if not np.all(np.isfinite(action)):
            self.failure_count += 1
            raise FloatingPointError("nonfinite PD Human-space action")
        self.last_diagnostics = {
            "accepted": True,
            "controller_id": self.config.controller_id,
            "gain_definition": self.gain_definition,
            "proportional_action_nm": proportional.tolist(),
            "derivative_action_nm": derivative.tolist(),
            "feedback_action_nm": feedback.tolist(),
            "nominal_feedforward_action_nm": feedforward.tolist(),
            "human_action_nm": action.tolist(),
            "population_prior_feedforward": self.nominal_feedforward,
        }
        return action.copy(), dict(self.last_diagnostics)


def controller_factory(
    controller_id: str,
    gain_lock: dict[str, Any],
) -> Callable[[], Any]:
    coupled = gain_lock.get("gain_definition") == (
        "constant_nominal_inertia_derived_coupled_torque_pd_v2"
    )
    if coupled:
        kp = np.asarray(gain_lock["kp_tau_matrix_nm_per_rad"], dtype=float)
        kd = np.asarray(gain_lock["kd_tau_matrix_nms_per_rad"], dtype=float)
    else:
        kp = np.asarray(gain_lock["kp_tau_nm_per_rad"], dtype=float)
        kd = np.asarray(gain_lock["kd_tau_nms_per_rad"], dtype=float)
    if controller_id == "pd_feedback":
        return lambda: PDHumanActionController(
            controller_id=controller_id,
            kp_tau_nm_per_rad=kp,
            kd_tau_nms_per_rad=kd,
            nominal_feedforward=False,
        )
    if controller_id == "pd_nominal_inverse_dynamics_ff":
        return lambda: PDHumanActionController(
            controller_id=controller_id,
            kp_tau_nm_per_rad=kp,
            kd_tau_nms_per_rad=kd,
            nominal_feedforward=True,
        )
    if controller_id in {"fixed_mpc_prior_only", "trusted_adaptive_mpc"}:
        return lambda: HumanSpaceMPC()
    raise KeyError(f"unknown report-validation controller {controller_id!r}")


def controller_applies_qualified_model(controller_id: str) -> bool:
    if controller_id not in {
        "pd_feedback",
        "pd_nominal_inverse_dynamics_ff",
        "fixed_mpc_prior_only",
        "trusted_adaptive_mpc",
    }:
        raise KeyError(f"unknown report-validation controller {controller_id!r}")
    return controller_id == "trusted_adaptive_mpc"


def controller_fingerprint_payload(
    controller_id: str,
    *,
    gain_lock_sha256: str,
    gain_definition: str,
    matrix_sha256: str,
    matrix_schema_version: str,
    reference_clock_sha256: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "experiment_schema": matrix_schema_version,
        "controller_id": controller_id,
        "human_action_boundary": "human_generalized_cuff_action_nm",
        "apply_qualified_model_to_control": controller_applies_qualified_model(
            controller_id
        ),
        "gain_lock_sha256": (
            gain_lock_sha256
            if controller_id
            in {"pd_feedback", "pd_nominal_inverse_dynamics_ff"}
            else None
        ),
        "report_validation_config_sha256": matrix_sha256,
        "external_reference_clock_sha256": reference_clock_sha256,
        "external_reference_clock_controller_independent": True,
        "allocator": REGISTERED_CUFF_AWARE_ALLOCATOR_CONFIG.as_dict(),
        "low_level_execution": "existing_measured_nominal_cartesian_control",
        "safety_limits_modified": False,
    }
    if controller_id in {"pd_feedback", "pd_nominal_inverse_dynamics_ff"}:
        coupled = gain_definition == (
            "constant_nominal_inertia_derived_coupled_torque_pd_v2"
        )
        payload["gain_definition"] = gain_definition
        if coupled:
            payload["law"] = (
                "constant_coupled_matrix_pd_plus_population_prior_reference_inverse_dynamics"
                if controller_id == "pd_nominal_inverse_dynamics_ff"
                else "constant_coupled_matrix_pd_feedback_only"
            )
        else:
            payload["law"] = (
                "diagonal_pd_plus_population_prior_reference_inverse_dynamics"
                if controller_id == "pd_nominal_inverse_dynamics_ff"
                else "diagonal_pd_feedback_only"
            )
    else:
        payload["mpc_config"] = asdict(HumanMPCConfig())
        payload["mpc_implementation"] = "batched"
    return payload


def patient_spec_for_id(
    matrix: dict[str, Any], matrix_path: Path, patient_id: str
) -> tuple[PatientCaseSpec, str]:
    patient_source = report_root(matrix_path) / matrix["source_artifacts"][
        "patient_config"
    ]["path"]
    existing = {item.case_id: item for item in load_patient_case_specs(patient_source)}
    if patient_id in existing:
        return existing[patient_id], "existing_stage4_definition_read_only"
    report_only = {
        item["case_id"]: item for item in matrix["patient_cases"]["report_only"]
    }
    if patient_id not in report_only:
        raise KeyError(f"patient {patient_id!r} is not in report-validation matrix")
    raw = dict(report_only[patient_id])
    if raw.pop("stage4_canonical_evidence", None) is not False:
        raise ValueError("report-only patient must explicitly reject Stage-4 status")
    return PatientCaseSpec.from_dict(raw), "report_validation_only"


def trajectory_for_id(
    matrix: dict[str, Any], matrix_path: Path, trajectory_id: str
) -> dict[str, Any]:
    trajectory_source = report_root(matrix_path) / matrix["source_artifacts"][
        "trajectory_config"
    ]["path"]
    suite = load_trajectory_suite(trajectory_source)
    if trajectory_id not in matrix["selected_trajectories"]:
        raise KeyError(f"trajectory {trajectory_id!r} is not report-selected")
    return trajectory_case(trajectory_id, suite)


def measurement_case(
    matrix: dict[str, Any], *, measurement_seed: int | None = None
) -> MeasurementCase:
    matches = [
        item
        for item in sensor_realism_cases()
        if item.name == matrix["shared_contract"]["sensor_case"]
    ]
    if len(matches) != 1:
        raise RuntimeError("frozen report sensor case is unavailable")
    seed = (
        int(matrix["shared_contract"]["measurement_seed"])
        if measurement_seed is None
        else int(measurement_seed)
    )
    return replace(matches[0], seed=seed)


def _git_provenance(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    try:
        return {
            "code_commit": run("rev-parse", "HEAD"),
            "working_tree_dirty": bool(run("status", "--porcelain")),
        }
    except (OSError, subprocess.CalledProcessError):
        return {"code_commit": None, "working_tree_dirty": None}


def _summary_metrics(summary: dict[str, Any], duration_s: float) -> dict[str, Any]:
    tracking = summary["tracking"]
    interaction = summary["interaction_metrics_engineering_not_clinical"]
    phase = float(summary["reference_execution"]["final_reference_phase_time_s"])
    return {
        "termination_reason": summary["termination_reason"],
        "reference_progress_fraction": min(1.0, phase / float(duration_s)),
        "tracking_combined_rmse_deg": float(tracking["combined_rmse_deg"]),
        "tracking_max_abs_error_deg": float(max(tracking["max_abs_error_deg"])),
        "cuff_force_peak_n": float(interaction["peak_total_translational_force_n"]),
        "cuff_force_rms_n": float(interaction["rms_total_translational_force_n"]),
        "cuff_moment_peak_nm": float(interaction["peak_total_cuff_moment_nm"]),
        "cuff_moment_rms_nm": float(interaction["rms_total_cuff_moment_nm"]),
        "robot_torque_peak_abs_nm": summary["robot"][
            "peak_abs_commanded_joint_torque_nm"
        ],
        "safety_events": summary["events"],
        "rollout_wall_time_s": summary["computational_cost"]["rollout_wall_time_s"],
        "controller_compute_mean_ms": summary["computational_cost"]["mpc_mean_ms"],
        "controller_compute_p95_ms": summary["computational_cost"]["mpc_p95_ms"],
    }


def prepare_fresh_output_directory(path: Path) -> None:
    target = Path(path)
    if target.exists():
        raise FileExistsError(f"refusing to overwrite report-validation output {target}")
    target.mkdir(parents=True)


def _save_arm(
    output_dir: Path,
    controller_id: str,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
) -> None:
    write_strict_json(output_dir / f"{controller_id}.json", summary)
    np.savez_compressed(output_dir / f"{controller_id}_trace.npz", **trace)


def run_report_arm(
    *,
    matrix: dict[str, Any],
    matrix_path: Path,
    gain_lock: dict[str, Any],
    gain_lock_sha256: str,
    controller_id: str,
    patient_id: str,
    trajectory_id: str,
    evidence_category: str,
    formal_execution: bool,
    duration_s: float,
    output_dir: Path,
    measurement_seed: int | None = None,
    extra_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    matrix_path = Path(matrix_path).resolve()
    matrix_hash = sha256_file(matrix_path)
    root = report_root(matrix_path)
    patient_spec, patient_source = patient_spec_for_id(
        matrix, matrix_path, patient_id
    )
    trajectory = trajectory_for_id(matrix, matrix_path, trajectory_id)
    true_human = patient_spec.build_human()
    patient_record = patient_case_record(patient_spec)
    clock_source = matrix["source_artifacts"]["shared_reference_phase_trace"]
    source_path = resolve_stage_artifact(root, clock_source["path"])
    reference_fn = lambda time_s: trajectory_reference(trajectory, time_s)
    clock = ExternalPhaseReferenceClock(
        reference_fn,
        source_path=source_path,
        expected_sha256=clock_source["sha256"],
        source_duration_s=float(matrix["shared_contract"]["reference_clock"]["source_duration_s"]),
        trajectory_duration_s=float(trajectory["duration_s"]),
    )
    case = measurement_case(matrix, measurement_seed=measurement_seed)
    apply_model = controller_applies_qualified_model(controller_id)

    def estimator_factory(measurement: Any, q_prior: np.ndarray) -> Any:
        return OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=case,
            apply_qualified_model=apply_model,
        )

    summary, trace = run_sensor_realism_case(
        case,
        duration_s=float(duration_s),
        estimator_architecture="integral_minimal",
        result_case_name=controller_id,
        true_human_override=true_human,
        true_metadata_override={
            "case": patient_id,
            "patient_case_id": patient_id,
            "patient_definition_source": patient_source,
            "variation_spec": patient_record["variation_spec"],
            "raw_human_parameters": patient_record["raw_human_parameters"],
            "stage4_canonical_evidence": False
            if patient_source == "report_validation_only"
            else None,
        },
        reference_fn=reference_fn,
        trajectory_label=trajectory_id,
        trajectory_waypoints=trajectory_waypoints(trajectory),
        reference_execution=clock,
        mpc_factory=controller_factory(controller_id, gain_lock),
        estimator_factory=estimator_factory,
    )
    prior_beta = nominal_base_parameters(HUMAN)
    beta_trace = np.asarray(trace["dynamic_base_estimate"], dtype=float)
    if not apply_model:
        np.testing.assert_allclose(
            beta_trace,
            np.broadcast_to(prior_beta, beta_trace.shape),
            rtol=0.0,
            atol=1e-12,
        )
    else:
        qualifications = {
            int(item["challenger_index"]): float(item["qualification_time_s"])
            for item in summary["hierarchical_trust"]["qualifications"]
            if item["applied_to_control"]
        }
        for promotion in summary["hierarchical_trust"]["control_promotions"]:
            challenger = int(promotion["challenger_index"])
            if challenger not in qualifications:
                raise RuntimeError("adaptive promotion lacks applied qualification")
            if float(promotion["promotion_time_s"]) < qualifications[challenger] - 1e-12:
                raise RuntimeError("adaptive promotion precedes qualification")
    fingerprint_payload = controller_fingerprint_payload(
        controller_id,
        gain_lock_sha256=gain_lock_sha256,
        gain_definition=str(
            gain_lock.get("gain_definition", "diagonal_torque_pd_v1")
        ),
        matrix_sha256=matrix_hash,
        matrix_schema_version=matrix["schema_version"],
        reference_clock_sha256=clock_source["sha256"],
    )
    fingerprint = canonical_json_sha256(fingerprint_payload)
    provenance = {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "controller": controller_id,
        "gain_lock_sha256": (
            gain_lock_sha256
            if controller_id
            in {"pd_feedback", "pd_nominal_inverse_dynamics_ff"}
            else None
        ),
        "experiment_gain_lock_sha256": gain_lock_sha256,
        "patient": patient_id,
        "patient_definition_source": patient_source,
        "trajectory": trajectory_id,
        "measurement_seed": int(case.seed),
        "reference_clock_sha256": clock_source["sha256"],
        "report_validation_config_sha256": matrix_hash,
        "controller_fingerprint_sha256": fingerprint,
        "controller_fingerprint_payload": fingerprint_payload,
        "frozen_stage4_base_commit": matrix["frozen_start"]["commit"],
        "frozen_stage4_base_tag": matrix["frozen_start"]["tag"],
        "evidence_category": evidence_category,
        "formal_execution": bool(formal_execution),
        "structural_smoke": not bool(formal_execution),
        "fresh_plant_estimator_controller_clock_per_arm": True,
        "authoritative_stage4_evidence": False,
        "external_reference_clock_controller_independent": True,
        "control_beta_constant_population_prior": not apply_model,
        "common_allocator": REGISTERED_CUFF_AWARE_ALLOCATOR_CONFIG.as_dict(),
        "common_low_level_execution": "existing_measured_nominal_cartesian_control",
        **_git_provenance(root.parents[1]),
    }
    if extra_provenance:
        overlap = set(provenance) & set(extra_provenance)
        if overlap:
            raise ValueError(
                "extra provenance cannot replace report-validation fields: "
                f"{sorted(overlap)}"
            )
        provenance.update(strict_json(extra_provenance))
    summary["evidence_category"] = evidence_category
    summary["report_validation_provenance"] = provenance
    summary["report_validation_metrics"] = _summary_metrics(
        summary, float(trajectory["duration_s"])
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    _save_arm(output_dir, controller_id, summary, trace)
    write_strict_json(output_dir / f"{controller_id}_manifest.json", provenance)
    return {
        "summary": summary,
        "trace": trace,
        "provenance": provenance,
        "metrics": summary["report_validation_metrics"],
    }


def structural_smoke_gain_lock(
    matrix: dict[str, Any], matrix_sha256: str
) -> dict[str, Any]:
    candidate = next(
        item
        for item in gain_candidates(matrix)
        if item["kp_scale"] == 1.0 and item["kd_scale"] == 1.0
    )
    record = {
        **candidate,
        "termination_reason": "not_executed_structural_default",
        "reference_progress_fraction": 0.0,
        "tracking_combined_rmse_deg": None,
        "tracking_max_abs_error_deg": None,
        "cuff_force_rms_n": None,
        "safety_events": {},
    }
    return gain_lock_payload(
        matrix_sha256=matrix_sha256,
        candidate_records=[record],
        selected=candidate,
        lock_kind="structural_smoke",
    )


def run_coupled_pd_gain_smoke(
    *,
    matrix_path: Path,
    output_dir: Path,
    duration_s: float,
) -> dict[str, Any]:
    """Run three preregistered v2 PD scales as non-scientific diagnostics."""

    if not 0.0 < float(duration_s) <= GAIN_DIAGNOSTIC_SMOKE_MAX_DURATION_S:
        raise ValueError(
            "coupled-PD gain smoke duration must be in "
            f"(0,{GAIN_DIAGNOSTIC_SMOKE_MAX_DURATION_S}] s"
        )
    matrix_path = Path(matrix_path).resolve()
    matrix = load_report_validation_matrix(matrix_path)
    if matrix["schema_version"] != MATRIX_SCHEMA_VERSION_V2:
        raise ValueError("coupled-PD gain smoke requires the amended v2 matrix")
    prepare_fresh_output_directory(output_dir)
    tuning = matrix["gain_tuning"]
    requested_scales = {(0.5, 0.5), (1.0, 1.0), (1.5, 1.5)}
    selected = [
        candidate
        for candidate in gain_candidates(matrix)
        if (candidate["kp_scale"], candidate["kd_scale"]) in requested_scales
    ]
    if len(selected) != 3:
        raise RuntimeError("v2 diagnostic smoke scale set is incomplete")
    arms: list[dict[str, Any]] = []
    for candidate in selected:
        candidate_hash = canonical_json_sha256(candidate)
        result = run_report_arm(
            matrix=matrix,
            matrix_path=matrix_path,
            gain_lock=candidate,
            gain_lock_sha256=candidate_hash,
            controller_id="pd_feedback",
            patient_id=tuning["patient_id"],
            trajectory_id=tuning["trajectory_id"],
            evidence_category=(
                "report_validation_v2_coupled_pd_diagnostic_smoke_non_scientific"
            ),
            formal_execution=False,
            duration_s=float(duration_s),
            output_dir=Path(output_dir) / candidate["candidate_id"],
        )
        trace = result["trace"]
        actions = np.asarray(trace["desired_human_action_nm"], dtype=float)
        nonzero = np.flatnonzero(np.linalg.norm(actions, axis=1) > 1e-12)
        representative_action = (
            actions[int(nonzero[-1])] if len(nonzero) else np.zeros(2)
        )
        arms.append(
            {
                "candidate_id": candidate["candidate_id"],
                "kp_scale": candidate["kp_scale"],
                "kd_scale": candidate["kd_scale"],
                "candidate_definition_sha256": candidate_hash,
                "gain_definition": candidate["gain_definition"],
                "termination_reason": result["summary"]["termination_reason"],
                "completed_duration_s": result["summary"]["completed_duration_s"],
                "finite_trace": all(
                    np.all(np.isfinite(value))
                    for value in trace.values()
                    if np.issubdtype(np.asarray(value).dtype, np.number)
                ),
                "representative_human_action_nm": representative_action.tolist(),
                "opposite_sign_coupled_action_observed": bool(
                    representative_action[0] > 0.0
                    and representative_action[1] < 0.0
                ),
                "reference_trace_sha256": canonical_json_sha256(
                    np.asarray(trace["reference_phase_time_s"]).tolist()
                ),
                "measurement_schedule_sha256": canonical_json_sha256(
                    np.asarray(trace["measurement_new_sample"], dtype=bool).tolist()
                ),
                "allocation_residual_peak_nm": float(
                    np.max(np.abs(trace["allocation_equality_residual_nm"]))
                ),
                "cuff_force_peak_n": result["summary"][
                    "report_validation_metrics"
                ]["cuff_force_peak_n"],
                "tracking_combined_rmse_deg": result["summary"][
                    "report_validation_metrics"
                ]["tracking_combined_rmse_deg"],
                "controller_fingerprint_sha256": result["provenance"][
                    "controller_fingerprint_sha256"
                ],
            }
        )
    manifest = {
        "schema_version": "stage4_report_validation_v2_coupled_pd_smoke_v1",
        "evidence_category": (
            "report_validation_v2_coupled_pd_diagnostic_smoke_non_scientific"
        ),
        "formal_execution": False,
        "scientific_interpretation_permitted": False,
        "duration_s": float(duration_s),
        "matrix_path": str(matrix_path),
        "matrix_sha256": sha256_file(matrix_path),
        "v1_evidence_status_sha256": matrix["amendment"][
            "v1_formal_gain_selection"
        ]["status_sha256"],
        "arms": arms,
    }
    write_strict_json(Path(output_dir) / "coupled_pd_gain_smoke_manifest.json", manifest)
    return manifest


def run_structural_smoke(
    *,
    matrix_path: Path,
    output_dir: Path,
    duration_s: float,
) -> dict[str, Any]:
    if not 0.0 < float(duration_s) <= STRUCTURAL_SMOKE_MAX_DURATION_S:
        raise ValueError(
            f"structural smoke duration must be in (0,{STRUCTURAL_SMOKE_MAX_DURATION_S}] s"
        )
    matrix_path = Path(matrix_path).resolve()
    matrix = load_report_validation_matrix(matrix_path)
    matrix_hash = sha256_file(matrix_path)
    prepare_fresh_output_directory(output_dir)
    lock_path = Path(output_dir) / "structural_smoke_pd_gains.json"
    lock = structural_smoke_gain_lock(matrix, matrix_hash)
    lock_hash = write_gain_lock(lock_path, lock)
    controllers = [item["controller_id"] for item in matrix["controllers"]]
    smoke_cases = (
        {
            "case_id": "nominal_high_flexion",
            "patient_id": "nominal_reference",
            "trajectory_id": "registered_high_flexion_23s",
        },
        {
            "case_id": "report_only_geometry_hip_dominant",
            "patient_id": "height_moderate_plus_03pct_report_only",
            "trajectory_id": "hip_dominant_low_knee_23s",
        },
    )
    arms: list[dict[str, Any]] = []
    for case_record in smoke_cases:
        for controller_id in controllers:
            arm_dir = (
                Path(output_dir)
                / case_record["case_id"]
                / controller_id
            )
            result = run_report_arm(
                matrix=matrix,
                matrix_path=matrix_path,
                gain_lock=lock,
                gain_lock_sha256=lock_hash,
                controller_id=controller_id,
                patient_id=case_record["patient_id"],
                trajectory_id=case_record["trajectory_id"],
                evidence_category="report_validation_structural_smoke_non_scientific",
                formal_execution=False,
                duration_s=float(duration_s),
                output_dir=arm_dir,
            )
            trace = result["trace"]
            arms.append(
                {
                    **case_record,
                    "controller_id": controller_id,
                    "output_dir": str(arm_dir),
                    "finite_trace": all(
                        np.all(np.isfinite(value))
                        for value in trace.values()
                        if np.issubdtype(np.asarray(value).dtype, np.number)
                    ),
                    "termination_reason": result["summary"]["termination_reason"],
                    "reference_trace_sha256": canonical_json_sha256(
                        np.asarray(trace["reference_phase_time_s"]).tolist()
                    ),
                    "measurement_schedule_sha256": canonical_json_sha256(
                        np.asarray(trace["measurement_new_sample"], dtype=bool).tolist()
                    ),
                    "sensor_realization_definition_sha256": canonical_json_sha256(
                        result["summary"]["measurement_model"]
                    ),
                    "initial_measured_cuff_force_world_n": np.asarray(
                        trace["measured_cuff_force_world_n"][0]
                    ).tolist(),
                    "initial_measured_cuff_moment_world_nm": np.asarray(
                        trace["measured_cuff_moment_world_nm"][0]
                    ).tolist(),
                    "initial_human_q_deg": np.asarray(
                        trace["human_q_deg_god_view"][0]
                    ).tolist(),
                    "initial_robot_q_rad": np.asarray(trace["robot_q_rad"][0]).tolist(),
                    "initial_control_beta": np.asarray(
                        trace["dynamic_base_estimate"][0]
                    ).tolist(),
                    "allocation_residual_peak_nm": float(
                        np.max(np.asarray(trace["allocation_equality_residual_nm"]))
                    ),
                    "apply_qualified_model_to_control": bool(
                        result["summary"]["hierarchical_trust"][
                            "apply_qualified_model_to_control"
                        ]
                    ),
                    "control_promotion_count": len(
                        result["summary"]["hierarchical_trust"][
                            "control_promotions"
                        ]
                    ),
                }
            )
    for case_record in smoke_cases:
        selected = [item for item in arms if item["case_id"] == case_record["case_id"]]
        if len({item["reference_trace_sha256"] for item in selected}) != 1:
            raise RuntimeError("four controllers received different external reference traces")
        if len({item["measurement_schedule_sha256"] for item in selected}) != 1:
            raise RuntimeError("four controllers received different sensor schedules")
        if len({item["sensor_realization_definition_sha256"] for item in selected}) != 1:
            raise RuntimeError("four controllers received different sensor definitions")
        if len(
            {
                tuple(item["initial_measured_cuff_force_world_n"])
                for item in selected
            }
        ) != 1:
            raise RuntimeError("initial force measurement realization differs")
        if len(
            {
                tuple(item["initial_measured_cuff_moment_world_nm"])
                for item in selected
            }
        ) != 1:
            raise RuntimeError("initial moment measurement realization differs")
        if len({tuple(item["initial_human_q_deg"]) for item in selected}) != 1:
            raise RuntimeError("Human initial state leaked or differed across arms")
        if len({tuple(item["initial_robot_q_rad"]) for item in selected}) != 1:
            raise RuntimeError("robot initial state leaked or differed across arms")
        for item in selected:
            np.testing.assert_allclose(
                item["initial_control_beta"],
                nominal_base_parameters(HUMAN),
                rtol=0.0,
                atol=1e-12,
            )
    fixed = [item for item in arms if item["controller_id"] == "fixed_mpc_prior_only"]
    adaptive = [
        item for item in arms if item["controller_id"] == "trusted_adaptive_mpc"
    ]
    if any(item["apply_qualified_model_to_control"] for item in fixed):
        raise RuntimeError("fixed MPC is allowed to apply an adaptive beta")
    if not all(item["apply_qualified_model_to_control"] for item in adaptive):
        raise RuntimeError("adaptive MPC lost frozen trust application semantics")
    manifest = {
        "schema_version": SMOKE_MANIFEST_SCHEMA_VERSION,
        "evidence_category": "report_validation_structural_smoke_non_scientific",
        "scientific_interpretation_permitted": False,
        "duration_s": float(duration_s),
        "gain_lock_path": str(lock_path),
        "gain_lock_sha256": lock_hash,
        "cases": list(smoke_cases),
        "arms": arms,
        "all_finite": all(item["finite_trace"] for item in arms),
        "allocation_path": "registered_1_to_1_cuff_aware_memoryless_allocator",
        "low_level_path": "existing_measured_nominal_cartesian_control",
        "formal_gain_selection_executed": False,
        "scientific_benchmark_executed": False,
        "demo_experiment_executed": False,
    }
    write_strict_json(Path(output_dir) / "smoke_manifest.json", manifest)
    return manifest
