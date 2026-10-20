"""One continuous 30-repetition scientific baseline under mode-aware V2 acceptance."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
for relative in (
    "stages/stage5_personalized_motion_learning/src",
    "stages/stage4_adaptive_control/src",
    "stages/stage3_full3d/src",
    "stages/stage5_personalized_motion_learning/scripts/high_rom_v1",
):
    sys.path.insert(0, str(ROOT / relative))

from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case, advance_inter_rep_boundary, _jsonable
from traction_mpc_stage5.full3d_adaptive_integration_v1.session_state import (
    zero_value_decision_rows,
    PersistentSessionState,
)
from evaluate_execution_mode import evaluate
from summarize_phase_b import DOC
from zero_value_30rep_checkpoint import save_checkpoint, load_checkpoint
from baseline_acceptance_v2 import assess
from baseline_accounting_v2 import task_wrench_cost

BASELINE = STAGE / "docs/scientific_execution_architecture_v1/WSL_LEARNING_SCIENTIFIC_BASELINE.json"
OPTIONS = STAGE / "configs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/incremental_clearance_terminal_v9.json"
CONTRACT_V2 = STAGE / "docs/zero_value_30rep_baseline_v2/ZERO_VALUE_30REP_BASELINE_CONTRACT_V2.json"
MODE_AWARE_CONTRACT = STAGE / "docs/scientific_execution_architecture_v1/MODE_AWARE_EVALUATION_CONTRACT.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(_jsonable(value), indent=2, sort_keys=True, allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--session-seed", type=int, default=20260918)
    parser.add_argument("--host-monitor-limit-s", type=float, default=300.0)
    parser.add_argument("--resume-checkpoint", type=Path)
    args = parser.parse_args()
    if args.output.exists() and args.resume_checkpoint is None:
        raise FileExistsError(args.output)
    if args.resume_checkpoint is not None and not args.output.is_dir():
        raise FileNotFoundError(args.output)
    case_path = args.case.resolve()
    case = json.loads(case_path.read_text())
    if "research_model" in case:
        raise ValueError("this first smoke is registered low-ROM ordinary")
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        if os.environ.get(key) != "1":
            raise RuntimeError(f"{key} must be 1 in the frozen WSL environment")
    baseline = json.loads(BASELINE.read_text())
    contract_v2 = json.loads(CONTRACT_V2.read_text())
    if (contract_v2["execution_mode"] != "SCIENTIFIC_SIMULATION"
            or contract_v2["repetitions"] != 30):
        raise RuntimeError("V2 frozen contract mismatch")
    if sha(case_path) != baseline["configs"]["low_rom_ordinary"]["sha256"]:
        raise RuntimeError("case hash differs from frozen WSL baseline")
    options = json.loads(OPTIONS.read_text())
    scoring = json.loads((DOC / "PHASE_B_MATRIX.json").read_text())["scoring"]
    source_commit = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    source_hashes = {
        "runtime": sha(STAGE / "src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py"),
        "session_state": sha(STAGE / "src/traction_mpc_stage5/full3d_adaptive_integration_v1/session_state.py"),
        "harness": sha(Path(__file__)),
    }
    if args.resume_checkpoint is None:
        args.output.mkdir(parents=True)
    session_id = args.output.name
    provenance = {
        "schema": "zero_value_continuous_session_provenance_v2",
        "session_id": session_id,
        "execution_mode": "SCIENTIFIC_SIMULATION",
        "source_commit_before_session": source_commit,
        "source_file_sha256": source_hashes,
        "frozen_production_fingerprint": baseline["production_fingerprint"],
        "baseline_contract_v2_sha256": sha(CONTRACT_V2),
        "mode_aware_contract_sha256": sha(MODE_AWARE_CONTRACT),
        "environment": {
            "host": platform.node(),
            "platform": platform.platform(),
            "python": sys.version,
            "thread_settings": {key: os.environ[key] for key in (
                "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
        },
        "case_sha256": sha(case_path),
        "options_sha256": sha(OPTIONS),
        "config_hash": hashlib.sha256((sha(case_path) + sha(OPTIONS)).encode()).hexdigest(),
        "session_seed": args.session_seed,
        "seed_scope": "registered deterministic IK seed; no separate case RNG",
        "zero_value_policy": {"RL": "OFF", "learned_value": 0.0,
                              "selection": "unchanged baseline waypoint policy"},
        "repetition_count_planned": 30,
    }
    if args.resume_checkpoint is None:
        save(args.output / "session_provenance.json", provenance)
    else:
        saved_provenance = json.loads((args.output / "session_provenance.json").read_text())
        for key in ("case_sha256", "options_sha256", "session_seed",
                    "frozen_production_fingerprint", "repetition_count_planned",
                    "baseline_contract_v2_sha256", "mode_aware_contract_sha256"):
            if saved_provenance[key] != provenance[key]:
                raise RuntimeError(f"resume provenance differs: {key}")
        provenance = saved_provenance
    context: dict = {}
    persistent = PersistentSessionState(session_id=session_id)
    rows: list[dict] = []
    checkpoint_manifest_path = args.output / "session_checkpoints_manifest.json"
    checkpoint_manifest: list[dict] = []
    if args.resume_checkpoint is not None:
        checkpoint_manifest = json.loads(checkpoint_manifest_path.read_text())
        receipt = next((x for x in checkpoint_manifest
                        if x["path"] == args.resume_checkpoint.name), None)
        if receipt is None or args.resume_checkpoint.parent.resolve() != args.output.resolve():
            raise RuntimeError("checkpoint not in this session manifest")
        context, rows = load_checkpoint(args.resume_checkpoint, receipt["sha256"],
                                        sha(args.output / "session_provenance.json"))
        if receipt["repetition_index"] != len(rows):
            raise RuntimeError("checkpoint index mismatch")
        if (args.output / f"rep_{len(rows)+1:02d}").exists():
            raise RuntimeError("next repetition already exists; preserve it before recovery")
        persistent.repetition_number = len(rows)
        persistent.human_updater = context["updater"]
        persistent.human_model_state = context["final_belief"]
        persistent.causal_belief = context["runtime"]["observer"]
    fail_reason = None
    for rep_index in range(len(rows) + 1, 31):
        persistent.begin_repetition(rep_index)
        rep_dir = args.output / f"rep_{rep_index:02d}"
        previous = context.get("runtime")
        previous_updater = context.get("updater")
        previous_row = rows[-1] if rows else None
        previous_plant = None if previous is None else previous["plant"]
        previous_end = context.get("end_time_s")
        before_model = None if not context else context["final_belief"].value_state_record()
        inter_rep_boundary = None
        started = time.monotonic()
        stop = STAGE / "docs/high_rom_v1/STOP"
        def stop_check():
            if stop.exists():
                raise RuntimeError("HIGH_ROM_USER_STOP")
            if time.monotonic() - started >= args.host_monitor_limit_s:
                raise RuntimeError("HIGH_ROM_HOST_MONITOR_CUTOFF_INCOMPLETE")
        capture = {"stop_check": stop_check}
        launch = {
            "schema": "high_rom_v1_development_case_result",
            "case_key": case["case_key"],
            "case_sha256": sha(case_path),
            "options_sha256": sha(OPTIONS),
            "execution_mode": "SCIENTIFIC_SIMULATION",
            "scientific_host_delay_ms": 0.0,
            "plant_mode": "low_rom",
            "session_id": session_id,
            "repetition_index": rep_index,
            "command": sys.argv,
        }
        try:
            if previous is not None:
                inter_rep_boundary = advance_inter_rep_boundary(
                    context, max_wait_s=2.0, stop_check=stop_check)
                save(args.output / f"boundary_{rep_index-1:02d}_to_{rep_index:02d}.json",
                     inter_rep_boundary)
                previous_end = context["end_time_s"]
                rows[-1]["inter_rep_boundary_after"] = {
                    "settle_duration_s": inter_rep_boundary["settle_duration_s"],
                    "hold_duration_s": inter_rep_boundary["hold_duration_s"],
                    "J_F_n_s": inter_rep_boundary["cost"]["J_F_n_s"],
                    "moment_integral_nm_s": inter_rep_boundary["cost"]["moment_integral_nm_s"],
                    "peak_force_n": inter_rep_boundary["cost"]["peak_force_n"],
                    "peak_moment_nm": inter_rep_boundary["cost"]["peak_moment_nm"]}
                rows[-1]["J_F_session_n_s"] += inter_rep_boundary["cost"]["J_F_n_s"]
                rows[-1]["moment_session_integral_nm_s"] += (
                    inter_rep_boundary["cost"]["moment_integral_nm_s"])
                save(args.output / "per_repetition.json", rows)
            summary = run_executed_case(
                rep_dir, qualification_case=case,
                qualification_arm="continual_adaptive",
                simulate_planning_latency=True, formal_qualification=False,
                dev_a_recovery=True, dev_c_bumpless_transfer=False,
                dev_d_rigid_table_reference=True, autonomous_recovery_options=options,
                task_timeout_s=30.0, runtime_capture=capture,
                execution_mode="SCIENTIFIC_SIMULATION", scientific_host_delay_s=0.0,
                session_context=context,
            )
            launch["status"] = summary["status"]
            launch["abort_reason"] = summary.get("abort_reason")
        except BaseException as error:
            launch["status"] = "EXCEPTION"
            launch["abort_reason"] = f"{type(error).__name__}:{error}"
            launch["traceback"] = traceback.format_exc()[-8000:]
            fail_reason = launch["abort_reason"]
            summary = None
        finally:
            launch["elapsed_host_s"] = time.monotonic() - started
            rep_dir.mkdir(parents=True, exist_ok=True)
            save(rep_dir / "HIGH_ROM_CASE_RESULT.json", launch)
        if summary is None:
            break
        try:
            case_for_score = {
                "case_key": case["case_key"],
                "physical_variant": case["cell"]["family"],
                "candidate": case.get("coordination_candidate", "low_rom_registered"),
                "path": str(case_path.relative_to(ROOT)),
                "sha256": sha(case_path),
            }
            mode = evaluate(rep_dir, case_for_score, scoring,
                            goal_deg=case["task"]["goal_deg"],
                            start_deg=case["task"]["start_deg"])
            save(rep_dir / "MODE_AWARE_RESULT_V2.json", mode)
            trace = np.load(rep_dir / "trace.npz")
            mask = trace["stage"] == "TASK"
            artifacts = json.loads((rep_dir / "runtime_artifacts.json").read_text())
            native = artifacts["wall_physics"]
            initial_native = native["initial_native_boundary_evaluation_only"]
            final_native = native["final_native_boundary_evaluation_only"]
            task_human = trace["evaluation_only_human_state_rad_rad_s"][mask]
            task_robot_q = trace["cr12_q_rad"][mask]
            task_robot_dq = trace["cr12_dq_rad_s"][mask]
            if rep_index == 1:
                provenance["initial_human_state_evaluation_only"] = {
                    "source": "first saved commissioning boundary; evaluation only",
                    "q_dq_rad_rad_s": trace[
                        "evaluation_only_human_state_rad_rad_s"][0].tolist(),
                }
                save(args.output / "session_provenance.json", provenance)
            costs = task_wrench_cost(trace, mask)
            decisions = zero_value_decision_rows(summary["decisions"])
            for decision in decisions:
                for candidate in decision["candidate_set"]:
                    if not candidate["evaluated"]:
                        candidate["learned_value"] = None
            save(rep_dir / "zero_value_waypoint_decisions.json", decisions)
            acceptance = assess(summary, mode, artifacts, costs, decisions)
            reasons = acceptance["gate_reasons"]
            new_runtime = context["runtime"]
            reset_keys = ("contract", "supervisor", "monitor", "authority",
                          "wall_session", "plan_lifecycle", "true_physics_monitor",
                          "trace", "task_decisions")
            boundary = {
                "from_repetition": rep_index - 1 if previous is not None else None,
                "to_repetition": rep_index,
                "same_physical_plant": previous is None or new_runtime["plant"] is previous_plant,
                "same_human_updater": previous is None or context["updater"] is previous_updater,
                "same_causal_observer": previous is None or new_runtime["observer"] is previous["observer"],
                "same_measurement_layer": previous is None or (
                    new_runtime["measurement_layer"] is previous["measurement_layer"]),
                "same_command_response_history": previous is None or (
                    new_runtime.get("command_response_history") is
                    previous.get("command_response_history")),
                "no_stale_terminal_or_planner_objects": previous is None or all(
                    key not in previous or key not in new_runtime or
                    previous[key] is not new_runtime[key]
                    for key in ("plan_to_activate", "activation_validator",
                                "actual_activation_hook", "return_projection_finalization",
                                "return_projection_guards", "terminal_capture_hook",
                                "future_handoff_bridges", "rolling_splice_events")),
                "fresh_transient_objects": {
                    key: previous is None or (
                        key in previous and key in new_runtime and
                        previous[key] is not new_runtime[key])
                    for key in reset_keys
                },
                "old_plan_closed": previous is None or (
                    previous["plan_lifecycle"]._outstanding is None),
                "old_scientific_epoch_ended": previous is None or (
                    not previous["wall_session"].active),
                "native_boundary_exact": previous_row is None or (
                    inter_rep_boundary is not None
                    and np.array_equal(
                        inter_rep_boundary["terminal_native_qpos_evaluation_only"],
                        previous_row["final_native_state_evaluation_only"]["qpos"])
                    and np.array_equal(
                        inter_rep_boundary["terminal_native_qvel_evaluation_only"],
                        previous_row["final_native_state_evaluation_only"]["qvel"])
                    and np.array_equal(initial_native["qpos_evaluation_only"],
                        inter_rep_boundary["settled_native_qpos_evaluation_only"])
                    and np.array_equal(initial_native["qvel_evaluation_only"],
                        inter_rep_boundary["settled_native_qvel_evaluation_only"])),
                "simulation_time_continuous": previous_end is None or (
                    initial_native["time_s"] == previous_end),
                "model_version_continuous": previous_row is None or (
                    summary["commissioning"]["handoff_belief"]["sequence"] ==
                    previous_row["human_model_sequence_after"]),
                "starts_outbound": bool(np.any(mask) and
                                        trace["task_phase"][mask][0] == "OUTBOUND"),
                "fresh_start_reference": previous is None or np.array_equal(
                    trace["reference_q_rad"][mask][0],
                    np.radians(np.asarray(case["task"]["start_deg"], dtype=float))),
                "new_episode_epoch": previous is None or all(
                    request["source_simulation_version"]["episode_epoch"] ==
                    str(rep_dir.resolve()) for request in summary["timing"]["requests"]),
                "fresh_track_bootstrap": previous is None or (
                    new_runtime.get("fresh_track_bootstrap", {}).get("execution_mode") == "TRACK"
                    and new_runtime["fresh_track_bootstrap"]["reference"]["receipt_index"]
                        == new_runtime["fresh_track_bootstrap"]["receipt_index"]
                    and new_runtime["fresh_track_bootstrap"]["source_sample_time_s"]
                        > new_runtime["fresh_track_bootstrap"]["receipt_source_sample_time_s"]),
            }
            if previous is not None:
                for key, value in boundary.items():
                    if value is False or (key == "fresh_transient_objects"
                                          and not all(value.values())):
                        reasons.append(f"boundary:{key}")
            if not boundary["starts_outbound"]:
                reasons.append("boundary:starts_outbound")
            if reasons:
                acceptance["overall_baseline_scientific_result"] = "FAIL"
            row = {
                "session_id": session_id,
                "repetition_index": rep_index,
                "status": summary["status"],
                "physical": mode["physical_task_result"]["status"],
                "scientific": mode["scientific_validity"]["status"],
                "scorer_v2": mode["raw_scorer_v2"]["pass"],
                "physical_task_validity": acceptance["physical_task_validity"],
                "scientific_validity": acceptance["scientific_validity"],
                "raw_scorer_v2_result": acceptance["raw_scorer_v2_result"],
                "realtime_characterization": acceptance["realtime_characterization"],
                "overall_baseline_scientific_result": (
                    acceptance["overall_baseline_scientific_result"]),
                "J_F_n_s": costs["J_F_n_s"],
                "J_F_task_n_s": costs["J_F_n_s"],
                "J_F_session_n_s": costs["J_F_n_s"] + (
                    0.0 if previous is None else
                    new_runtime["fresh_track_bootstrap"]["cost"]["J_F_n_s"]),
                "moment_integral_nm_s": costs["moment_integral_nm_s"],
                "moment_session_integral_nm_s": costs["moment_integral_nm_s"] + (
                    0.0 if previous is None else
                    new_runtime["fresh_track_bootstrap"]["cost"]["moment_integral_nm_s"]),
                "fresh_track_bootstrap": new_runtime.get("fresh_track_bootstrap"),
                "peak_force_n": costs["peak_force_n"],
                "peak_moment_nm": costs["peak_moment_nm"],
                "completion_time_s": summary["task"]["physics_duration_s"],
                "phase_durations_s": mode["raw_scorer_v2"]["phase_durations_s"],
                "waypoint_sequence": [d["executed_waypoint"] for d in decisions],
                "number_of_waypoint_decisions": len(decisions),
                "human_model_before": before_model,
                "human_model_at_task_start": summary["commissioning"]["handoff_belief"],
                "human_model_after": context["final_belief"].value_state_record(),
                "human_model_sequence_after": context["updater"].sequence,
                "boundary_audit": boundary,
                "physical_start_time_s": context["runtime"]["wall_session"].origin_physics_s,
                "physical_end_time_s": context["end_time_s"],
                "initial_human_q_dq_evaluation_only": task_human[0],
                "final_human_q_dq_evaluation_only": task_human[-1],
                "initial_cr12_q_evaluation_only": task_robot_q[0],
                "initial_cr12_dq_evaluation_only": task_robot_dq[0],
                "final_cr12_q_evaluation_only": task_robot_q[-1],
                "final_cr12_dq_evaluation_only": task_robot_dq[-1],
                "initial_native_state_evaluation_only": {
                    "qpos": initial_native["qpos_evaluation_only"],
                    "qvel": initial_native["qvel_evaluation_only"],
                },
                "final_native_state_evaluation_only": {
                    "qpos": final_native["qpos_evaluation_only"],
                    "qvel": final_native["qvel_evaluation_only"],
                },
                "minimum_session_clearance_m": summary["task"].get(
                    "minimum_session_clearance_m_deployable"),
                "minimum_true_clearance_m_evaluation_only": summary["task"].get(
                    "minimum_true_physical_clearance_m_evaluation_only"),
                "peak_robot_torque_fraction": summary["task"]["peak_robot_torque_fraction"],
                "safety_mode_counts": summary["safety_mode_counts"],
                "gate_reasons": reasons,
            }
            rows.append(row)
            persistent.human_updater = context["updater"]
            persistent.human_model_state = context["final_belief"]
            persistent.causal_belief = new_runtime["observer"]
            persistent.session_history.append({
                "repetition_index": rep_index, "status": row["status"],
                "J_F_task_n_s": row["J_F_task_n_s"],
                "human_model_sequence": row["human_model_sequence_after"]})
            save(args.output / "per_repetition.json", rows)
            if not reasons:
                checkpoint_path = args.output / f"checkpoint_{rep_index:02d}.pkl.z"
                receipt = save_checkpoint(checkpoint_path, context, rows,
                                          sha(args.output / "session_provenance.json"))
                checkpoint_manifest.append(receipt)
                save(checkpoint_manifest_path, checkpoint_manifest)
            print(json.dumps({"rep": rep_index, "status": row["status"],
                              "J_F_n_s": row["J_F_n_s"],
                              "baseline_scientific": row["overall_baseline_scientific_result"],
                              "raw_scorer_v2": row["scorer_v2"],
                              "wall_plan_age_ms": row["realtime_characterization"]["max_wall_plan_age_ms"],
                              "gate_reasons": reasons}), flush=True)
            if reasons:
                fail_reason = f"rep_{rep_index:02d}:" + ",".join(reasons)
                break
        except BaseException as error:
            fail_reason = f"rep_{rep_index:02d}_evaluation:{type(error).__name__}:{error}"
            (rep_dir / "evaluation_exception.txt").write_text(traceback.format_exc())
            break
    status = ("ZERO_VALUE_30REP_BASELINE_COMPLETE"
              if fail_reason is None and len(rows) == 30
              else "ZERO_VALUE_30REP_BASELINE_FAIL" if fail_reason is not None
              else "ZERO_VALUE_30REP_BASELINE_PARTIAL")
    result = {"status": status, "failure": fail_reason,
              "completed_repetitions": len(rows), "per_repetition": rows,
              "raw_data_manifest": "raw_data_manifest.json",
              "session_checkpoints_manifest": "session_checkpoints_manifest.json"}
    save(args.output / "session_result.json", result)
    if rows:
        with (args.output / "per_repetition.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "repetition_index", "status", "physical", "scientific", "scorer_v2",
                "overall_baseline_scientific_result",
                "J_F_n_s", "J_F_task_n_s", "J_F_session_n_s",
                "moment_integral_nm_s", "moment_session_integral_nm_s",
                "peak_force_n", "peak_moment_nm",
                "completion_time_s", "human_model_sequence_after",
            ])
            writer.writeheader()
            writer.writerows({key: row.get(key) for key in writer.fieldnames} for row in rows)
    manifest = {}
    for path in sorted(args.output.rglob("*")):
        if path.is_file() and path.name != "raw_data_manifest.json":
            manifest[str(path.relative_to(args.output))] = sha(path)
    save(args.output / "raw_data_manifest.json", manifest)
    print(json.dumps({"status": status, "failure": fail_reason,
                      "completed_repetitions": len(rows)}), flush=True)


if __name__ == "__main__":
    main()
