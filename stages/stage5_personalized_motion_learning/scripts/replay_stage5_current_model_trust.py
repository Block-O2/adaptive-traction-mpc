#!/usr/bin/env python3
"""Causal replay of old and model-versioned trust on saved Stage-5 traces."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage5.confidence_pacing import (
    Stage5ConfidencePacing,
    Stage5CurrentModelTrust,
    Stage5PacingEvidence,
    current_nominal_model_trust_from_shadow_service,
)
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.goal_mpc_smoke import FIXED_HUMAN_MODEL_VERSION


SAVED_ROOT = STAGE5_ROOT / "results" / "human_id_confidence_pacing_v1_attempt_01"
SAVED_SUMMARY = SAVED_ROOT / "confidence_pacing_results.json"


def _causal_service_snapshot(
    final_attempts: list[dict[str, Any]], session_time_s: float
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for source in final_attempts:
        fit_time = float(source.get("fit_end_time_s", float("inf")))
        if fit_time > session_time_s + 1.0e-9:
            continue
        attempt = deepcopy(source)
        decision_time = source.get("decision_time_s")
        evidence = [
            deepcopy(item)
            for item in source.get("evidence_history", [])
            if float(item.get("decision_time_s", float("inf")))
            <= session_time_s + 1.0e-9
        ]
        attempt["evidence_history"] = evidence
        if decision_time is None or float(decision_time) > session_time_s + 1.0e-9:
            if source.get("proposed_model_scales") is not None:
                attempt["status"] = "pending_future_validation"
            else:
                attempt["status"] = str(source.get("status", "rejected_training_gate"))
        attempts.append(attempt)
    return {"attempts": attempts}


def _latest_information(snapshot: dict[str, Any]) -> tuple[int, float]:
    attempts = snapshot["attempts"]
    if not attempts:
        return 0, float("inf")
    information = attempts[-1].get("training_diagnostics", {}).get(
        "information", {}
    )
    return int(information.get("rank", 0)), float(
        information.get("condition_number", float("inf"))
    )


def _challenger_status(snapshot: dict[str, Any]) -> str:
    attempts = snapshot["attempts"]
    return "none" if not attempts else str(attempts[-1].get("status", "none"))


def _publication_count(snapshot: dict[str, Any]) -> int:
    return sum(
        item.get("status") == "published_to_shadow_incumbent"
        for item in snapshot["attempts"]
    )


def replay_case(case: dict[str, Any]) -> dict[str, Any]:
    case_name = str(case["case"]["name"])
    trace_path = SAVED_ROOT / case_name / "episode_01" / "trace.npz"
    with np.load(trace_path) as loaded:
        times = np.asarray(loaded["time_s"], dtype=float)
        saved_gamma = np.asarray(loaded["progress_pacing_gamma"], dtype=float)

    final_attempts = list(case["service_summary"].get("attempts", []))
    old_pacing = Stage5ConfidencePacing()
    new_pacing = Stage5ConfidencePacing()
    trust = Stage5CurrentModelTrust(FIXED_HUMAN_MODEL_VERSION)
    old_gamma = []
    new_gamma = []
    new_filtered = []
    new_hysteresis = []
    new_target = []
    raw_support = []
    old_raw_support = []
    for time_s in times:
        snapshot = _causal_service_snapshot(final_attempts, float(time_s))
        old_supported, old_reason = current_nominal_model_trust_from_shadow_service(
            snapshot
        )
        trust.observe_shadow_service(snapshot, session_time_s=float(time_s))
        rank, condition = _latest_information(snapshot)
        common = dict(
            session_time_s=float(time_s),
            identification_informative=rank == 3,
            information_rank=rank,
            information_condition_number=condition,
            challenger_status=_challenger_status(snapshot),
            shadow_publication_count=_publication_count(snapshot),
        )
        old_pacing.update(
            Stage5PacingEvidence(
                **common,
                current_nominal_model_adequate=old_supported,
                current_model_evidence_reason=old_reason,
            )
        )
        new_status = trust.status()
        new_pacing.update(
            Stage5PacingEvidence(
                **common,
                current_nominal_model_adequate=trust.supported,
                current_model_evidence_reason=str(new_status["state_reason"]),
            )
        )
        old_status = old_pacing.status(float(time_s))
        pacing_status = new_pacing.status(float(time_s))
        old_gamma.append(old_status["gamma"])
        new_gamma.append(pacing_status["gamma"])
        new_filtered.append(pacing_status["filtered_current_model_confidence"])
        new_hysteresis.append(pacing_status["execution_confidence_high"])
        new_target.append(pacing_status["gamma_target"])
        raw_support.append(trust.supported)
        old_raw_support.append(old_supported)

    old_gamma_array = np.asarray(old_gamma)
    new_gamma_array = np.asarray(new_gamma)
    raw_support_array = np.asarray(raw_support, dtype=bool)
    old_raw_support_array = np.asarray(old_raw_support, dtype=bool)
    first_support_index = np.flatnonzero(raw_support_array)
    first_support_time = (
        None if not len(first_support_index) else float(times[first_support_index[0]])
    )
    pre_support = (
        np.ones(len(times), dtype=bool)
        if first_support_time is None
        else times < first_support_time - 1.0e-12
    )
    first_gamma_leave = np.flatnonzero(new_gamma_array > 0.5 + 1.0e-12)
    return {
        "case": case_name,
        "trace_path": str(trace_path.relative_to(STAGE5_ROOT)),
        "sample_count": int(len(times)),
        "saved_vs_replayed_old_gamma_max_abs": float(
            np.max(np.abs(saved_gamma - old_gamma_array))
        ),
        "old_vs_new_pre_support_gamma_max_abs": float(
            np.max(np.abs(old_gamma_array[pre_support] - new_gamma_array[pre_support]))
        ),
        "old_vs_new_pre_support_raw_equal": bool(
            np.array_equal(
                old_raw_support_array[pre_support], raw_support_array[pre_support]
            )
        ),
        "first_valid_current_model_support_time_s": first_support_time,
        "final_persistent_support": bool(raw_support_array[-1]),
        "final_filtered_confidence": float(new_filtered[-1]),
        "final_hysteresis_high": bool(new_hysteresis[-1]),
        "final_gamma_target": float(new_target[-1]),
        "final_gamma": float(new_gamma_array[-1]),
        "first_gamma_above_minimum_time_s": (
            None
            if not len(first_gamma_leave)
            else float(times[first_gamma_leave[0]])
        ),
        "trust_history": trust.history,
        "causal_replay": True,
        "future_samples_used": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "current_model_trust_replay_v1",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    saved = json.loads(SAVED_SUMMARY.read_text(encoding="utf-8"))
    wanted = {"nominal", "stiffness_plus_15pct", "damping_plus_20pct"}
    rows = [
        replay_case(case)
        for case in saved["cases"]
        if case["case"]["name"] in wanted
    ]
    result = {
        "schema": "stage5_current_model_trust_saved_trace_replay_v1",
        "source": str(SAVED_SUMMARY.relative_to(STAGE5_ROOT)),
        "current_control_model_version": FIXED_HUMAN_MODEL_VERSION,
        "cases": rows,
        "acceleration_monitor_changed": False,
        "control_model_changed": False,
        "truth_used_online": False,
    }
    output = args.output_dir / "summary.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
