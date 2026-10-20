"""Versioned, evaluation-only RETURN endpoint scorer.

The original scorer-v1 remains in summarize_phase_b.py. This module changes
only the RETURN endpoint sample to the exact native physics COMPLETE commit.
No interpolation, post-hoc threshold search, or control input is involved.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import numpy as np

from summarize_phase_b import score as score_v1

SCORER_VERSION = "scorer-v2-return-physical-commit"


class EndpointMappingError(ValueError):
    """The recorded physical COMPLETE commit has no exact native state."""


def _state(q: Any, dq: Any) -> np.ndarray:
    value = np.r_[np.asarray(q, dtype=float), np.asarray(dq, dtype=float)]
    if value.shape != (4,) or not np.all(np.isfinite(value)):
        raise EndpointMappingError("invalid native Human q/dq")
    return value


def _require_same(left: Any, right: Any, label: str) -> None:
    if left != right:
        raise EndpointMappingError(f"{label} does not match exactly")


def endpoint_from_records(summary: dict, artifacts: dict, trace: Any) -> dict:
    """Map a COMPLETE transition to its exact recorded native physics node."""
    if summary.get("status") != "COMPLETE":
        raise EndpointMappingError("runner is not COMPLETE")
    transitions = [row for row in summary["task"]["phase_transitions"]
                   if row.get("from") == "RETURN" and row.get("to") == "COMPLETE"]
    if len(transitions) != 1:
        raise EndpointMappingError("requires exactly one RETURN to COMPLETE transition")
    transition = transitions[0]
    commits = [row for row in artifacts.get("return_commit_attempts", [])
               if row.get("accepted") is True and row.get("action") == "COMPLETE"]
    if len(commits) != 1:
        raise EndpointMappingError("requires exactly one accepted physical COMPLETE commit")
    commit = commits[0]
    source_s = float(transition["state_source_time_s"])
    commit_s = float(transition["time_s"])
    _require_same(source_s, float(commit["source_sample_time_s"]), "proposal source timestamp")
    _require_same(commit_s, float(commit["final_native_time_s"]), "physical commit timestamp")
    _require_same(int(transition["actual_completion_commit_ns"]),
                  int(commit["final_host_ns"]), "physical commit host timestamp")
    trace_time = np.asarray(trace["time_s"], dtype=float)
    if trace_time.ndim != 1 or not len(trace_time):
        raise EndpointMappingError("empty or malformed scorer-v1 trace")
    _require_same(float(trace_time[-1]), source_s, "scorer-v1 source timestamp")
    source_true = np.asarray(trace["evaluation_only_human_state_rad_rad_s"][-1], dtype=float)
    source_estimated = np.asarray(trace["estimated_human_state_rad_rad_s"][-1], dtype=float)
    if source_true.shape != (4,) or source_estimated.shape != (4,):
        raise EndpointMappingError("malformed source state")
    if not np.array_equal(source_estimated, np.asarray(transition["estimated_state"], dtype=float)):
        raise EndpointMappingError("COMPLETE proposal estimate differs from source trace")
    wall = artifacts["wall_physics"]
    nodes = wall["native_states_evaluation_only"]
    if not nodes:
        raise EndpointMappingError("no native physics nodes")
    final_node = nodes[-1]
    final_boundary = wall["final_native_boundary_evaluation_only"]
    _require_same(float(final_node["time_s"]), commit_s, "last native physics node timestamp")
    _require_same(float(final_boundary["time_s"]), commit_s,
                  "final native boundary timestamp")
    commit_state = _state(final_node["qpos_evaluation_only"][:2],
                          final_node["qvel_evaluation_only"][:2])
    boundary_state = _state(final_boundary["qpos_evaluation_only"][:2],
                            final_boundary["qvel_evaluation_only"][:2])
    if not np.array_equal(commit_state, boundary_state):
        raise EndpointMappingError("last native node differs from final boundary state")
    # The source row must be an exact native sample too; this checks v1-v2
    # provenance without choosing a more favorable nearby physics instant.
    source_matches = [row for row in reversed(nodes) if row["time_s"] == source_s]
    if len(source_matches) != 1:
        raise EndpointMappingError("source has no unique exact native physics node")
    source_native = _state(source_matches[0]["qpos_evaluation_only"][:2],
                           source_matches[0]["qvel_evaluation_only"][:2])
    if not np.array_equal(source_true, source_native):
        raise EndpointMappingError("scorer-v1 source truth differs from native node")
    return {
        "scorer_version": SCORER_VERSION,
        "proposal_source_time_s": source_s,
        "proposal_estimated_state_rad_rad_s": source_estimated.tolist(),
        "proposal_true_state_evaluation_only_rad_rad_s": source_true.tolist(),
        "physical_complete_commit_time_s": commit_s,
        "physical_complete_commit_host_ns": int(commit["final_host_ns"]),
        "scorer_time_s": commit_s,
        "scorer_true_state_evaluation_only_rad_rad_s": commit_state.tolist(),
        "scorer_v1_time_s": source_s,
        "scorer_v1_true_state_evaluation_only_rad_rad_s": source_true.tolist(),
        "mapping": "exact last native physics node equals final native boundary and accepted COMPLETE commit",
        "truth_consumed_by_control": False,
    }


def endpoint_from_run(path: Path) -> dict:
    summary = json.loads((path / "summary.json").read_text())
    artifacts = json.loads((path / "runtime_artifacts.json").read_text())
    with np.load(path / "trace.npz", allow_pickle=False) as trace:
        return endpoint_from_records(summary, artifacts, trace)


def score_v2(path: Path, case: dict, contract: dict, *,
             goal_deg=(120., 120.), start_deg=(5., 10.)) -> dict:
    """Retain every v1 rule; replace only its RETURN endpoint sample fields."""
    original = score_v1(path, case, contract, goal_deg=goal_deg, start_deg=start_deg)
    if original.get("status") != "COMPLETE" or "conditions" not in original:
        raise EndpointMappingError("v2 requires a complete scorer-v1 case")
    endpoint = endpoint_from_run(path)
    state = np.asarray(endpoint["scorer_true_state_evaluation_only_rad_rad_s"])
    start = np.radians(np.asarray(start_deg, dtype=float))
    angle = np.radians(np.asarray(contract["angle_completion_tolerance_deg"], dtype=float))
    velocity = np.radians(np.asarray(contract["velocity_completion_tolerance_deg_s"], dtype=float))
    returned = bool(np.all(np.abs(state[:2] - start) <= angle)
                    and np.all(np.abs(state[2:]) <= velocity))
    result = copy.deepcopy(original)
    result["conditions"]["true_return"] = returned
    result["true_return"] = returned
    result["final_true_q_deg"] = np.degrees(state[:2]).tolist()
    result["final_true_dq_deg_s"] = np.degrees(state[2:]).tolist()
    result["pass"] = all(result["conditions"].values())
    result["scorer_version"] = SCORER_VERSION
    result["rescore_status"] = "RESCORED_UNDER_SCORER_V2"
    result["return_endpoint_provenance"] = endpoint
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case_data = json.loads(args.case.read_text())
    contract = json.loads(args.contract.read_text())
    if "scoring" in contract:
        contract = contract["scoring"]
    case = {"case_key": case_data["case_key"], "physical_variant": case_data.get("physical_variant", "registered_case"),
            "candidate": case_data.get("candidate", "registered_candidate"),
            "path": str(args.case), "sha256": __import__("hashlib").sha256(args.case.read_bytes()).hexdigest()}
    result = score_v2(args.run, case, contract, goal_deg=case_data["task"]["goal_deg"],
                      start_deg=case_data["task"]["start_deg"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["rescore_status"], "pass": result["pass"]}))


if __name__ == "__main__":
    main()
