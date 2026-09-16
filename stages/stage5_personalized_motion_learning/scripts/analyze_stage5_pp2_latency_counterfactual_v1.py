#!/usr/bin/env python3
"""Saved-trace-only PP2-A latency and bounded-update counterfactual audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from traction_mpc_stage4.integral_identifier import integral_regression_block
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.minimal_adaptation import dynamic_scale_projection
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification_reduced import (
    Stage5ReducedHumanIDConfig,
    progressive_transition_evidence,
)
from traction_mpc_stage5.human_model_update import classify_post_update_evidence


DEPLOYABLE_TRACE_KEYS = (
    "time_s",
    "estimated_state_rad_rad_s",
    "deployable_measured_generalized_input_nm",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounded_successor(
    predecessor: Iterable[float],
    candidate: Iterable[float],
    *,
    alpha: float,
    maximum_step: float = 0.03,
    lower: float = 0.5,
    upper: float = 1.5,
) -> tuple[np.ndarray, np.ndarray]:
    old = np.asarray(tuple(predecessor), dtype=float)
    raw = np.asarray(tuple(candidate), dtype=float)
    if old.shape != (3,) or raw.shape != (3,):
        raise ValueError("bounded update requires two three-scale vectors")
    delta = np.clip(alpha * (raw - old), -maximum_step, maximum_step)
    return np.clip(old + delta, lower, upper), np.abs(alpha * (raw - old)) > maximum_step


def load_deployable_trace(path: Path, session_start_s: float) -> dict[str, np.ndarray]:
    with np.load(path) as archive:
        missing = sorted(set(DEPLOYABLE_TRACE_KEYS) - set(archive.files))
        if missing:
            raise KeyError(f"deployable trace fields missing: {missing}")
        trace = {key: np.asarray(archive[key]).copy() for key in DEPLOYABLE_TRACE_KEYS}
    trace["session_time_s"] = trace.pop("time_s") + float(session_start_s)
    return trace


def regression_block_for_window(
    trace: dict[str, np.ndarray], start_s: float, end_s: float
) -> dict[str, Any]:
    time_s = trace["session_time_s"]
    selected = np.flatnonzero(
        (time_s >= float(start_s) - 1.0e-12)
        & (time_s <= float(end_s) + 1.0e-12)
    )
    if len(selected) < 3 or time_s[selected[-1]] - time_s[selected[0]] < 0.18:
        raise ValueError(f"saved deployable trace cannot reconstruct {start_s}..{end_s}")
    regressor, target = integral_regression_block(
        time_s[selected],
        trace["estimated_state_rad_rad_s"][selected],
        trace["deployable_measured_generalized_input_nm"][selected],
    )
    return {
        "start_time_s": float(time_s[selected[0]]),
        "end_time_s": float(time_s[selected[-1]]),
        "regressor": regressor,
        "target": target,
    }


def block_losses(
    scales: Iterable[float], blocks: list[dict[str, Any]], projection: np.ndarray
) -> np.ndarray:
    theta = np.asarray(tuple(scales), dtype=float)
    return np.asarray(
        [
            float(
                np.mean(
                    (block["regressor"] @ projection @ theta - block["target"])
                    ** 2
                )
            )
            for block in blocks
        ],
        dtype=float,
    )


def summarize_losses(values: np.ndarray) -> dict[str, Any]:
    return {
        "block_count": int(len(values)),
        "mean_nms2": float(np.mean(values)),
        "values_nms2": np.asarray(values, dtype=float).tolist(),
    }


def _windows_from_attempt(attempt: dict[str, Any]) -> list[tuple[int, float, float]]:
    evidence = attempt["evidence_history"][-1]
    return [
        (int(episode), float(window[0]), float(window[1]))
        for episode, window in zip(
            evidence["validation_episode_indices"],
            evidence["validation_windows"],
            strict=True,
        )
    ]


def _windows_from_post_update(row: dict[str, Any]) -> list[tuple[int, float, float]]:
    evidence = row["authority_end"]["post_update_evidence"]
    if not evidence.get("available"):
        return []
    return [
        (
            int(block["episode_index"]),
            float(block["start_time_s"]),
            float(block["end_time_s"]),
        )
        for block in evidence["blocks"]
    ]


def analyze(source: Path) -> dict[str, Any]:
    source = Path(source)
    source_hash_before = sha256(source)
    payload = json.loads(source.read_text(encoding="utf-8"))
    rows = payload["arms"]["progressive"]
    if len(rows) != 5:
        raise ValueError("PP2-A saved result must contain five progressive repetitions")
    root = source.parent
    traces: dict[int, dict[str, np.ndarray]] = {}
    trace_hashes_before: dict[int, str] = {}
    for row in rows:
        repetition = int(row["repetition"])
        trace_path = root / row["artifacts"]["trace"]
        trace_hashes_before[repetition] = sha256(trace_path)
        traces[repetition - 1] = load_deployable_trace(
            trace_path, float(row["session_start_time_s"])
        )

    prior = np.ones(3)
    projection = dynamic_scale_projection(nominal_base_parameters(STAGE5_HUMAN))
    trust = Stage5ReducedHumanIDConfig().trust
    authority_history = payload["arm_authority_summaries"]["progressive"]["history"]
    activations = {
        int(event["activation_repetition"]): float(event["activation_time_s"])
        for event in authority_history
        if event["event"] == "model_activated"
    }
    post_support_times = {
        int(event["repetition"]): float(event["evidence_time_s"])
        for event in authority_history
        if event["event"] == "post_update_evidence"
    }
    session_end_s = float(rows[-1]["session_start_time_s"]) + float(
        rows[-1]["control"]["task_duration_s"]
    )

    transitions: list[dict[str, Any]] = []
    counterfactual_chain = np.asarray(rows[0]["active_theta"], dtype=float)
    counterfactual_chain_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        repetition = int(row["repetition"])
        attempts = row["human_identification"]["new_attempts"]
        if len(attempts) != 1:
            raise ValueError("each PP2-A repetition must contain one accepted challenger")
        attempt = attempts[0]
        predecessor = np.asarray(attempt["reference_incumbent_scales"], dtype=float)
        raw_candidate = np.asarray(attempt["candidate_scales"], dtype=float)
        actual = np.asarray(attempt["proposed_model_scales"], dtype=float)
        recomputed_actual, actual_cap = bounded_successor(
            predecessor, raw_candidate, alpha=0.10
        )
        if not np.allclose(actual, recomputed_actual, atol=1.0e-14, rtol=0.0):
            raise RuntimeError("saved alpha=0.10 successor does not match bounded rule")
        hypothetical, hypothetical_cap = bounded_successor(
            predecessor, raw_candidate, alpha=0.25
        )

        qualification_windows = _windows_from_attempt(attempt)
        qualification_blocks = [
            regression_block_for_window(traces[episode], start, end)
            for episode, start, end in qualification_windows
        ]
        predecessor_q = block_losses(predecessor, qualification_blocks, projection)
        actual_q = block_losses(actual, qualification_blocks, projection)
        hypothetical_q = block_losses(
            hypothetical, qualification_blocks, projection
        )
        prior_q = block_losses(prior, qualification_blocks, projection)
        actual_q_evidence = progressive_transition_evidence(
            actual_q,
            prior_q,
            predecessor_q,
            config=trust,
            challenger_index=int(attempt["challenger_index"]),
            seed_offset=10000 * int(attempt["challenger_index"]),
        )
        hypothetical_q_evidence = progressive_transition_evidence(
            hypothetical_q,
            prior_q,
            predecessor_q,
            config=trust,
            challenger_index=int(attempt["challenger_index"]),
            seed_offset=10000 * int(attempt["challenger_index"]),
        )
        saved_evidence = attempt["evidence_history"][-1]
        if not np.allclose(
            actual_q - predecessor_q,
            saved_evidence["against_last_valid"]["differences_nms2"],
            atol=2.0e-15,
            rtol=0.0,
        ):
            raise RuntimeError("reconstructed qualification blocks disagree with saved evidence")

        post_windows: list[tuple[int, float, float]] = []
        if index + 1 < len(rows):
            post_windows = _windows_from_post_update(rows[index + 1])
        post: dict[str, Any] | None = None
        if post_windows:
            post_blocks = [
                regression_block_for_window(traces[episode], start, end)
                for episode, start, end in post_windows
            ]
            predecessor_p = block_losses(predecessor, post_blocks, projection)
            actual_p = block_losses(actual, post_blocks, projection)
            hypothetical_p = block_losses(hypothetical, post_blocks, projection)
            transition_index = index + 2
            actual_p_evidence = classify_post_update_evidence(
                actual_p - predecessor_p,
                config=trust,
                transition_index=transition_index,
            )
            hypothetical_p_evidence = classify_post_update_evidence(
                hypothetical_p - predecessor_p,
                config=trust,
                transition_index=transition_index,
            )
            post = {
                "window_ids": [list(item) for item in post_windows],
                "predecessor": summarize_losses(predecessor_p),
                "alpha_0_10": summarize_losses(actual_p),
                "alpha_0_25": summarize_losses(hypothetical_p),
                "alpha_0_10_classification": actual_p_evidence["outcome"],
                "alpha_0_25_classification": hypothetical_p_evidence["outcome"],
            }

        qualification_time = float(attempt["decision_time_s"])
        support_time = (
            float(row["session_start_time_s"])
            if repetition == 1
            else post_support_times[repetition]
        )
        queue_time = max(qualification_time, support_time)
        next_activation = activations.get(repetition + 1)
        active_start = float(row["session_start_time_s"])
        active_end = next_activation if next_activation is not None else session_end_s
        transitions.append(
            {
                "transition": f"theta_{repetition}->theta_{repetition + 1}",
                "repetition": repetition,
                "repetition_start_time_s": active_start,
                "first_valid_fit_time_s": float(attempt["fit_end_time_s"]),
                "candidate_creation_time_s": float(attempt["fit_end_time_s"]),
                "qualification_time_s": qualification_time,
                "post_update_positive_time_s": support_time,
                "neutral_gate_block_s": max(0.0, support_time - qualification_time),
                "queue_time_s": queue_time,
                "activation_boundary_s": next_activation,
                "active_duration_before_next_activation_or_budget_end_s": float(
                    active_end - active_start
                ),
                "latency_components_s": {
                    "data_acquisition": float(attempt["fit_end_time_s"] - active_start),
                    "candidate_future_validation": float(
                        qualification_time - float(attempt["fit_end_time_s"])
                    ),
                    "post_update_support_after_active_start": float(
                        support_time - active_start
                    ),
                    "neutral_block_after_qualification": max(
                        0.0, support_time - qualification_time
                    ),
                    "boundary_wait_after_queue": (
                        None
                        if next_activation is None
                        else float(next_activation - queue_time)
                    ),
                },
                "predecessor_theta": predecessor.tolist(),
                "raw_candidate_theta": raw_candidate.tolist(),
                "alpha_0_10_successor_theta": actual.tolist(),
                "alpha_0_25_successor_theta": hypothetical.tolist(),
                "alpha_0_10_delta": (actual - predecessor).tolist(),
                "alpha_0_25_delta": (hypothetical - predecessor).tolist(),
                "alpha_0_10_step_cap_active": actual_cap.tolist(),
                "alpha_0_25_step_cap_active": hypothetical_cap.tolist(),
                "bounded_step_norm_alpha_0_10": float(
                    np.linalg.norm(actual - predecessor)
                ),
                "bounded_step_norm_alpha_0_25": float(
                    np.linalg.norm(hypothetical - predecessor)
                ),
                "qualification": {
                    "window_ids": [list(item) for item in qualification_windows],
                    "predecessor": summarize_losses(predecessor_q),
                    "alpha_0_10": summarize_losses(actual_q),
                    "alpha_0_25": summarize_losses(hypothetical_q),
                    "alpha_0_10_supported": bool(
                        actual_q_evidence["transition_authority_supported"]
                    ),
                    "alpha_0_25_supported": bool(
                        hypothetical_q_evidence["transition_authority_supported"]
                    ),
                },
                "post_update_like": post,
            }
        )

        chained_next, chained_cap = bounded_successor(
            counterfactual_chain, raw_candidate, alpha=0.25
        )
        counterfactual_chain_rows.append(
            {
                "transition": f"theta25_{repetition}->theta25_{repetition + 1}",
                "predecessor_theta": counterfactual_chain.tolist(),
                "raw_candidate_theta": raw_candidate.tolist(),
                "successor_theta": chained_next.tolist(),
                "step_cap_active": chained_cap.tolist(),
                "observed_trajectory_reused_for_closed_loop_claim": False,
            }
        )
        counterfactual_chain = chained_next

    hashes_after = {
        int(row["repetition"]): sha256(root / row["artifacts"]["trace"])
        for row in rows
    }
    if source_hash_before != sha256(source) or trace_hashes_before != hashes_after:
        raise RuntimeError("saved PP2-A evidence changed during offline analysis")

    qualification_better = [
        100.0
        * (
            item["qualification"]["alpha_0_10"]["mean_nms2"]
            - item["qualification"]["alpha_0_25"]["mean_nms2"]
        )
        / item["qualification"]["alpha_0_10"]["mean_nms2"]
        for item in transitions
    ]
    post_better = [
        100.0
        * (
            item["post_update_like"]["alpha_0_10"]["mean_nms2"]
            - item["post_update_like"]["alpha_0_25"]["mean_nms2"]
        )
        / item["post_update_like"]["alpha_0_10"]["mean_nms2"]
        for item in transitions
        if item["post_update_like"] is not None
    ]
    return {
        "schema": "stage5_pp2_saved_trace_latency_counterfactual_v1",
        "source": str(source),
        "source_sha256": source_hash_before,
        "analysis_boundary": {
            "saved_traces_only": True,
            "deployable_trace_keys_used": list(DEPLOYABLE_TRACE_KEYS),
            "evaluation_truth_used": False,
            "online_evidence_modified": False,
            "counterfactual_is_closed_loop_evidence": False,
        },
        "transitions": transitions,
        "counterfactual_alpha_0_25_arithmetic_chain": counterfactual_chain_rows,
        "aggregate": {
            "mean_data_acquisition_latency_s": float(
                np.mean([item["latency_components_s"]["data_acquisition"] for item in transitions])
            ),
            "mean_candidate_validation_latency_s": float(
                np.mean([item["latency_components_s"]["candidate_future_validation"] for item in transitions])
            ),
            "mean_post_update_support_latency_s_excluding_inherited_theta1": float(
                np.mean(
                    [
                        item["latency_components_s"]["post_update_support_after_active_start"]
                        for item in transitions[1:]
                    ]
                )
            ),
            "total_neutral_gate_block_s": float(
                sum(item["latency_components_s"]["neutral_block_after_qualification"] for item in transitions)
            ),
            "mean_boundary_wait_s_activated_transitions": float(
                np.mean(
                    [
                        item["latency_components_s"]["boundary_wait_after_queue"]
                        for item in transitions
                        if item["latency_components_s"]["boundary_wait_after_queue"] is not None
                    ]
                )
            ),
            "alpha_0_25_qualification_loss_improvement_percent_vs_0_10": qualification_better,
            "alpha_0_25_post_update_like_loss_improvement_percent_vs_0_10": post_better,
            "alpha_0_25_final_arithmetic_chain_theta": counterfactual_chain.tolist(),
            "actual_final_active_theta": rows[-1]["active_theta"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    result = analyze(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["aggregate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
