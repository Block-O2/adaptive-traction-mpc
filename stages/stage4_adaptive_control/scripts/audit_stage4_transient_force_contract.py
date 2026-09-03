#!/usr/bin/env python3
"""Read-only retrospective audit of the opt-in transient force contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from audit_stage4_phase_a_high_rom_interaction import run_sensitivity_replay
from run_stage4_high_rom_time_scale_audit import HIGH_ROM_HUMAN, SnapshotCapturePlant
from traction_mpc_stage3.coupled import LYING_BED_SCENARIO
from traction_mpc_stage4.physical_force_contract import (
    EXACT_REPLAY_UNAVAILABLE,
    FINE_REPLAY_CONFIRMED,
    RUNTIME_OBSERVATION,
    SIMULATION_ENGINEERING_TRANSIENT_V1,
    STRICT_PHYSICAL_FORCE_V1,
    evaluate_physical_force_trace,
)
from traction_mpc_stage4.surface_loads import (
    CylindricalSurfaceConfig,
    CylindricalSurfaceLoadModel,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = STAGE_ROOT / "results"
DEFAULT_OUTPUT = (
    RESULTS_ROOT
    / "engineering_validation"
    / "transient_force_contract_audit_20260904"
)
CONTRACT_PATH = STAGE_ROOT / "configs" / "simulation_engineering_transient_v1.json"
CONTRACT_SHA_PATH = STAGE_ROOT / "configs" / "simulation_engineering_transient_v1.sha256"
PHASE5_KNEE_TRACE = (
    RESULTS_ROOT
    / "engineering_validation"
    / "phase5_high_rom_system_pilot_20260902"
    / "knee_high_folding_90_120"
    / "trace.npz"
)
PHASE_A_REPLAY = (
    RESULTS_ROOT
    / "engineering_validation"
    / "phase_a_high_rom_interaction_audit_20260902"
)
TIME_SCALE_KNEE_TRACE = (
    RESULTS_ROOT
    / "engineering_validation"
    / "high_rom_time_scale_audit_20260902"
    / "knee_high_folding_90_120"
    / "alpha_0p25"
    / "compact_trace.npz"
)
TIME_SCALE_KNEE_DIR = TIME_SCALE_KNEE_TRACE.parent


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _surface_proxy(force_local: np.ndarray, moment_local: np.ndarray) -> np.ndarray:
    model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    wrench = np.column_stack([force_local, moment_local])
    patch = np.einsum("ij,tj->ti", model.minimum_norm_operator, wrench)
    return np.linalg.norm(patch, axis=1)


def _category(path: Path) -> str:
    text = path.as_posix()
    if "/phase5_high_rom_system_pilot_" in text:
        return "phase5_high_rom_lying_bed"
    if "/phase_a1_suspended_" in text or "/high_rom_time_scale_audit_" in text:
        return "suspended_high_rom"
    if "/controller_validation/" in text or "/robustness/" in text:
        return "original_low_medium_rom_validation"
    if "/negative_evidence/" in text:
        return "retained_negative_evidence"
    return "other_retained_compatible"


def _compatible_traces() -> list[Path]:
    paths: list[Path] = []
    for path in sorted(RESULTS_ROOT.rglob("*.npz")):
        with np.load(path, allow_pickle=False) as trace:
            if "time_s" not in trace or "cuff_force_local_n_god_view" not in trace:
                continue
            time = np.asarray(trace["time_s"])
            force = np.asarray(trace["cuff_force_local_n_god_view"])
            if time.ndim == 1 and len(time) > 1 and force.shape == (len(time), 3):
                paths.append(path)
    return paths


def _load_trace(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with np.load(path, allow_pickle=False) as trace:
        time = np.asarray(trace["time_s"], dtype=float)
        force = np.asarray(trace["cuff_force_local_n_god_view"], dtype=float)
        moment = np.asarray(trace["cuff_moment_local_nm_god_view"], dtype=float)
    return time, force, moment, _surface_proxy(force, moment)


def _phase5_fine_replay() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    with np.load(PHASE_A_REPLAY / "pre_spike_replay_snapshot.npz", allow_pickle=False) as snapshot:
        state = np.asarray(snapshot["mujoco_integration_state"], dtype=float)
    manifest = json.loads((PHASE_A_REPLAY / "pre_spike_replay_snapshot.json").read_text())
    replay = run_sensitivity_replay(
        state,
        manifest["previous_safe_command"],
        scenario=LYING_BED_SCENARIO,
        timestep_s=0.00025,
        iterations=100,
        tolerance=1.0e-8,
    )
    source_time, source_force, source_moment, _ = _load_trace(PHASE5_KNEE_TRACE)
    start = float(manifest["snapshot_time_s"])
    context = (source_time >= start - 0.100 - 1.0e-12) & (source_time <= start + 1.0e-12)
    # The restored-state mj_forward reports the post-command equality force at
    # the same timestamp.  Retain the actual saved pre-command sample at t0 and
    # append only the fine post-step samples.
    records = replay["records"][1:]
    fine_time = np.asarray([item["time_s"] for item in records], dtype=float)
    fine_force = np.asarray(
        [item["physical_cuff_force_local_n"] for item in records], dtype=float
    )
    fine_moment = np.asarray(
        [item["physical_cuff_moment_local_nm"] for item in records], dtype=float
    )
    time = np.concatenate([source_time[context], fine_time])
    force = np.vstack([source_force[context], fine_force])
    moment = np.vstack([source_moment[context], fine_moment])
    surface = _surface_proxy(force, moment)
    confirmed = evaluate_physical_force_trace(
        time,
        force,
        policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,
        numerical_confirmation=FINE_REPLAY_CONFIRMED,
        moment_vectors_nm=moment,
        surface_proxy_n=surface,
    )
    # The event remains above 200 N at the end of the only exactly replayable
    # command interval.  The snapshot cannot exactly resume the next closed-loop
    # cycle, so final qualification would guess the event closure.
    unresolved = evaluate_physical_force_trace(
        time,
        force,
        policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,
        numerical_confirmation=EXACT_REPLAY_UNAVAILABLE,
        moment_vectors_nm=moment,
        surface_proxy_n=surface,
    )
    details = {
        "source_trace": str(PHASE5_KNEE_TRACE.relative_to(STAGE_ROOT)),
        "snapshot": str((PHASE_A_REPLAY / "pre_spike_replay_snapshot.npz").relative_to(STAGE_ROOT)),
        "timestep_s": 0.00025,
        "replay_window_s": replay["window_duration_s"],
        "same_pre_spike_integration_state": True,
        "same_already_issued_joint_torque_command": True,
        "fine_window_mechanical_report": confirmed.as_dict(),
        "event_open_at_exact_replay_end": bool(confirmed.events[-1].open_at_trace_end),
        "exact_next_controller_cycle_replay_available": False,
        "final_report": unresolved.as_dict(),
    }
    arrays = {
        "time_s": time,
        "physical_cuff_force_local_n": force,
        "physical_cuff_moment_local_nm": moment,
        "surface_proxy_n": surface,
    }
    return details, arrays


def _time_scale_fine_replay() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    snapshot_path = TIME_SCALE_KNEE_DIR / "last_safe_snapshot.npz"
    with np.load(snapshot_path, allow_pickle=False) as snapshot:
        state = np.asarray(snapshot["mujoco_integration_state"], dtype=float)
        start = float(snapshot["time_s"])
        start_force_world = np.asarray(snapshot["physical_cuff_force_world_n"], dtype=float)
        start_moment_world = np.asarray(snapshot["physical_cuff_moment_world_nm"], dtype=float)
    source_time, source_force, source_moment, _ = _load_trace(TIME_SCALE_KNEE_TRACE)
    context = (source_time >= start - 0.100 - 1.0e-12) & (source_time <= start + 1.0e-12)
    plant = SnapshotCapturePlant(HIGH_ROM_HUMAN)
    plant.model.opt.timestep = 0.00025
    mujoco.mj_setState(
        plant.model,
        plant.data,
        state,
        mujoco.mjtState.mjSTATE_INTEGRATION,
    )
    mujoco.mj_forward(plant.model, plant.data)
    rotation = plant.observe().attachment_rotation_matrix
    # The compact source includes the exact last-safe sample.  Its stored force
    # is the authoritative t0 value; fine samples begin after the first step.
    if not np.isclose(source_time[context][-1], start, rtol=0.0, atol=1.0e-9):
        raise RuntimeError("compact trace does not contain the last-safe snapshot time")
    if not np.isclose(
        np.linalg.norm(source_force[context][-1]),
        np.linalg.norm(start_force_world),
        rtol=0.0,
        atol=1.0e-9,
    ):
        raise RuntimeError("compact trace and last-safe snapshot force disagree")
    fine_time: list[float] = []
    fine_force: list[np.ndarray] = []
    fine_moment: list[np.ndarray] = []
    for _ in range(20):
        mujoco.mj_step(plant.model, plant.data)
        observation = plant.observe()
        fine_time.append(float(observation.time_s))
        fine_force.append(
            observation.attachment_rotation_matrix.T @ observation.cuff_force_vector_n
        )
        fine_moment.append(
            observation.attachment_rotation_matrix.T @ observation.cuff_moment_vector_nm
        )
    time = np.concatenate([source_time[context], np.asarray(fine_time)])
    force = np.vstack([source_force[context], np.asarray(fine_force)])
    moment = np.vstack([source_moment[context], np.asarray(fine_moment)])
    surface = _surface_proxy(force, moment)
    report = evaluate_physical_force_trace(
        time,
        force,
        policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,
        numerical_confirmation=FINE_REPLAY_CONFIRMED,
        moment_vectors_nm=moment,
        surface_proxy_n=surface,
    )
    details = {
        "source_trace": str(TIME_SCALE_KNEE_TRACE.relative_to(STAGE_ROOT)),
        "snapshot": str(snapshot_path.relative_to(STAGE_ROOT)),
        "timestep_s": 0.00025,
        "replay_window_s": 0.005,
        "same_last_safe_integration_state": True,
        "held_already_issued_control": True,
        "event_open_at_exact_replay_end": bool(report.events[-1].open_at_trace_end),
        "final_report": report.as_dict(),
    }
    arrays = {
        "time_s": time,
        "physical_cuff_force_local_n": force,
        "physical_cuff_moment_local_nm": moment,
        "surface_proxy_n": surface,
    }
    return details, arrays


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "minimum": None, "median": None, "p95": None, "maximum": None}
    data = np.asarray(values, dtype=float)
    return {
        "count": len(values),
        "minimum": float(np.min(data)),
        "median": float(np.median(data)),
        "p95": float(np.quantile(data, 0.95, method="linear")),
        "maximum": float(np.max(data)),
    }


def _classification_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    statuses = (
        "STRICT_PASS",
        "TRANSIENT_ENGINEERING_QUALIFIED",
        "HARD_PHYSICAL_VIOLATION",
        "NUMERICALLY_UNRESOLVED",
    )
    return {status: sum(row[key] == status for row in rows) for status in statuses}


def _report_markdown(summary: dict[str, Any]) -> str:
    counts = summary["classification_counts"]["engineering_policy"]
    by_category = summary["classification_counts"]["by_category"]
    distributions = summary["event_distributions"]
    phase5 = summary["fine_timestep_confirmation"]["phase5_218p44n_event"]["final_report"]
    time_scale = summary["fine_timestep_confirmation"]["time_scale_200p35n_event"]["final_report"]
    lines = [
        "# Simulation Engineering Transient Force Contract Audit",
        "",
        "This is a simulation-engineering audit, not a clinical safety claim.",
        "Historical artifacts were read only and were not relabeled in place.",
        "",
        "## Retrospective classification",
        "",
        "| Status | Cases |",
        "|---|---:|",
    ]
    lines.extend(f"| {key} | {value} |" for key, value in counts.items())
    lines.extend(
        [
            "",
            "| Evidence group | Cases | Strict pass | Transient qualified | Hard violation | Unresolved |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for category, item in by_category.items():
        values = item["engineering_policy"]
        lines.append(
            f"| {category} | {item['case_count']} | {values['STRICT_PASS']} | "
            f"{values['TRANSIENT_ENGINEERING_QUALIFIED']} | "
            f"{values['HARD_PHYSICAL_VIOLATION']} | {values['NUMERICALLY_UNRESOLVED']} |"
        )
    lines.extend(
        [
            "",
            "## Fine-timestep confirmation",
            "",
            "| Event | Final status | Peak N | Max contiguous ms | Rolling excess impulse N s | Max trailing 20 ms mean N | Open at replay end |",
            "|---|---|---:|---:|---:|---:|---|",
            (
                f"| Phase-5 90/120 | {phase5['classification']} | "
                f"{phase5['peak_force_n']:.9f} | "
                f"{1000.0 * phase5['maximum_contiguous_exceedance_duration_s']:.9f} | "
                f"{phase5['maximum_rolling_excess_impulse_ns']:.9f} | "
                f"{phase5['maximum_causal_trailing_20ms_mean_n']:.9f} | yes |"
            ),
            (
                f"| Time-scale 90/120 | {time_scale['classification']} | "
                f"{time_scale['peak_force_n']:.9f} | "
                f"{1000.0 * time_scale['maximum_contiguous_exceedance_duration_s']:.9f} | "
                f"{time_scale['maximum_rolling_excess_impulse_ns']:.9f} | "
                f"{time_scale['maximum_causal_trailing_20ms_mean_n']:.9f} | no |"
            ),
            "| Retained PD gain event | NUMERICALLY_UNRESOLVED | 204.130357349 | 0.062376171 | 0.000128818 | see CSV | no exact snapshot |",
            "",
            "## Event distributions",
            "",
            "| Metric | Count | Min | Median | P95 | Max |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for label, key in (
        ("Peak force N", "event_peak_force_n"),
        ("Contiguous duration ms", "event_contiguous_duration_ms"),
        ("Case rolling excess impulse N s", "case_maximum_rolling_excess_impulse_ns"),
    ):
        item = distributions[key]
        lines.append(
            f"| {label} | {item['count']} | {item['minimum']:.9f} | "
            f"{item['median']:.9f} | {item['p95']:.9f} | {item['maximum']:.9f} |"
        )
    lines.extend(
        [
            "",
            "The registered 218.441 N event is numerically unresolved: its fine",
            "0.25 ms replay satisfies every threshold through the exactly replayable",
            "command interval, but the event is still open at that interval's end and",
            "the snapshot cannot exactly resume the next closed-loop cycle.",
            "",
            "The 200.352 N time-scale event closes in its 0.25 ms local replay and",
            "is transient-engineering-qualified. The original strict-gate termination",
            "and incomplete-task conclusion remain unchanged.",
            "The 204.130 N retained PD gain-selection event has no exact replay snapshot",
            "and is therefore unresolved rather than guessed from its single saved spike.",
            "",
            "No controller, allocator, Reference Manager, BRAKE, trust, gain, command",
            "limit, or capability-envelope rollout was changed or run.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite retrospective audit: {output_dir}")
    expected_sha = CONTRACT_SHA_PATH.read_text().split()[0]
    actual_sha = _sha256(CONTRACT_PATH)
    if actual_sha != expected_sha:
        raise RuntimeError("transient-force contract hash mismatch")

    paths = _compatible_traces()
    phase5_details, phase5_arrays = _phase5_fine_replay()
    time_scale_details, time_scale_arrays = _time_scale_fine_replay()
    fine_reports = {
        PHASE5_KNEE_TRACE.resolve(): phase5_details["final_report"],
        TIME_SCALE_KNEE_TRACE.resolve(): time_scale_details["final_report"],
    }
    rows: list[dict[str, Any]] = []
    event_peaks: list[float] = []
    event_durations_ms: list[float] = []
    case_impulses_ns: list[float] = []
    for path in paths:
        time, force, moment, surface = _load_trace(path)
        strict = evaluate_physical_force_trace(
            time,
            force,
            policy_id=STRICT_PHYSICAL_FORCE_V1,
            numerical_confirmation=RUNTIME_OBSERVATION,
            moment_vectors_nm=moment,
            surface_proxy_n=surface,
        )
        engineering = evaluate_physical_force_trace(
            time,
            force,
            policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,
            numerical_confirmation=EXACT_REPLAY_UNAVAILABLE,
            moment_vectors_nm=moment,
            surface_proxy_n=surface,
        ).as_dict()
        if path.resolve() in fine_reports:
            engineering = fine_reports[path.resolve()]
        for event in engineering["events"]:
            event_peaks.append(float(event["peak_force_n"]))
            event_durations_ms.append(1000.0 * float(event["duration_s"]))
        if engineering["event_count"]:
            case_impulses_ns.append(float(engineering["maximum_rolling_excess_impulse_ns"]))
        row = {
            "trace": str(path.relative_to(STAGE_ROOT)),
            "category": _category(path),
            "sample_count": len(time),
            "strict_policy_status": strict.classification,
            "engineering_policy_status": engineering["classification"],
            "engineering_mechanical_status": engineering["mechanical_classification"],
            "peak_force_n": engineering["peak_force_n"],
            "maximum_contiguous_exceedance_duration_ms": 1000.0 * engineering["maximum_contiguous_exceedance_duration_s"],
            "maximum_rolling_exceedance_duration_ms": 1000.0 * engineering["maximum_rolling_exceedance_duration_s"],
            "maximum_rolling_excess_impulse_ns": engineering["maximum_rolling_excess_impulse_ns"],
            "maximum_causal_trailing_20ms_mean_n": engineering["maximum_causal_trailing_20ms_mean_n"],
            "event_count": engineering["event_count"],
            "violated_rule": engineering["violated_rule"],
            "numerical_confirmation_required": engineering["numerical_confirmation_required"],
            "numerical_confirmation": engineering["numerical_confirmation"],
            "original_trace_terminated_at_strict_gate": path.resolve()
            in {PHASE5_KNEE_TRACE.resolve(), TIME_SCALE_KNEE_TRACE.resolve()},
        }
        rows.append(row)

    by_category: dict[str, Any] = {}
    for category in sorted({row["category"] for row in rows}):
        selected = [row for row in rows if row["category"] == category]
        by_category[category] = {
            "case_count": len(selected),
            "strict_policy": _classification_counts(selected, "strict_policy_status"),
            "engineering_policy": _classification_counts(selected, "engineering_policy_status"),
        }
    summary = {
        "schema_version": "simulation_engineering_transient_v1_retrospective_audit_v1",
        "evidence_category": "read_only_retrospective_engineering_audit_not_formal_or_authoritative",
        "simulation_engineering_only_not_clinical_safety": True,
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(STAGE_ROOT)),
            "sha256": actual_sha,
            "hash_verified_before_trace_evaluation": True,
        },
        "compatible_trace_definition": (
            "retained NPZ under Stage-4 results with one-dimensional time_s and "
            "same-length cuff_force_local_n_god_view N-by-3 physical trace"
        ),
        "compatible_trace_count": len(rows),
        "reproduction": {
            "command": (
                "PYTHONPATH=stages/stage3_full3d/src:"
                "stages/stage4_adaptive_control/src:"
                "stages/stage4_adaptive_control/scripts "
                "python stages/stage4_adaptive_control/scripts/"
                "audit_stage4_transient_force_contract.py"
            ),
            "output_directory": str(output_dir.relative_to(STAGE_ROOT)),
            "historical_trace_files_modified": False,
            "controller_or_scientific_configuration_modified": False,
        },
        "classification_counts": {
            "strict_policy": _classification_counts(rows, "strict_policy_status"),
            "engineering_policy": _classification_counts(rows, "engineering_policy_status"),
            "by_category": by_category,
        },
        "event_distributions": {
            "event_peak_force_n": _distribution(event_peaks),
            "event_contiguous_duration_ms": _distribution(event_durations_ms),
            "case_maximum_rolling_excess_impulse_ns": _distribution(case_impulses_ns),
        },
        "fine_timestep_confirmation": {
            "phase5_218p44n_event": phase5_details,
            "time_scale_200p35n_event": time_scale_details,
            "retained_pd_gain_204p13n_event": {
                "exact_replay_snapshot_available": False,
                "final_status": "NUMERICALLY_UNRESOLVED",
            },
        },
        "historical_outcome_effect": {
            "force_label_changed_under_opt_in_policy": [
                str(TIME_SCALE_KNEE_TRACE.relative_to(STAGE_ROOT))
            ],
            "218p44n_event": (
                "no final label change; fine replay remains open at the exact-window "
                "end, so the engineering result is NUMERICALLY_UNRESOLVED"
            ),
            "task_completion_conclusions_changed": [],
            "strict_historical_labels_changed": [],
            "reason": (
                "an opt-in event label does not infer completion after a strict-gate "
                "termination and historical evidence is not rewritten"
            ),
        },
        "controller_or_scientific_changes": {
            "controller_modified": False,
            "allocator_modified": False,
            "reference_manager_modified": False,
            "brake_modified": False,
            "trust_modified": False,
            "gains_modified": False,
            "command_force_limit_modified": False,
            "capability_envelope_rollout_run": False,
            "full_trajectory_rerun": False,
        },
        "rows": rows,
    }
    output_dir.mkdir(parents=True)
    _strict_json(output_dir / "retrospective_audit.json", summary)
    with (output_dir / "retrospective_classification.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    np.savez_compressed(
        output_dir / "fine_replay_traces.npz",
        **{f"phase5_{key}": value for key, value in phase5_arrays.items()},
        **{f"time_scale_{key}": value for key, value in time_scale_arrays.items()},
    )
    (output_dir / "research_report.md").write_text(
        _report_markdown(summary), encoding="utf-8"
    )
    print(json.dumps(summary["classification_counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
