"""Write the preregistered v1 audit, contract, and condition matrix once."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/coordination_pacing_exploration_v1"
DOC.mkdir(parents=True, exist_ok=True)


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze(name, value):
    path = DOC / name
    if path.exists():
        raise FileExistsError(f"frozen file exists: {path}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


source = "b8a3989f7bd2d96938d0012857499a0321f05d5e"
assert subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", source], text=True).strip() == source
options = STAGE / "configs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/incremental_clearance_terminal_v9.json"
cases = [
    ("low_ordinary_early", "low_rom_regression_cases/balanced_ordinary_r01.json", 1, "discovery", "low_ordinary"),
    ("low_ordinary_late", "low_rom_regression_cases/balanced_ordinary_r01.json", 25, "refinement", "low_ordinary"),
    ("balanced_middle", "low_rom_regression_cases/balanced_middle_r01.json", None, "discovery", "balanced_middle"),
    ("hip_ordinary", "low_rom_regression_cases/hip_dominant_ordinary_r01.json", None, "discovery", "hip_ordinary"),
    ("knee_ordinary", "low_rom_regression_cases/knee_dominant_ordinary_r01.json", None, "discovery", "knee_ordinary"),
    ("elevated_start", "low_rom_regression_cases/elevated_start_ordinary_r01.json", None, "refinement", "elevated_start"),
    ("balanced_high", "low_rom_regression_cases/balanced_near_upper_current_rom_r01.json", None, "refinement", "balanced_high"),
    ("sync_120", "high_rom_nominal_sync_120_v1.json", None, "validation", "sync_120"),
    ("variable_start_120", "high_rom_function_fresh_01_v1.json", None, "validation", "variable_start_120"),
]
matrix = {"schema": "coordination_pacing_condition_matrix_v1", "status": "FROZEN_BEFORE_BASELINE_REPLAY",
          "source_commit": source, "options_path": str(options.relative_to(ROOT)),
          "options_sha256": sha(options), "condition_count": 8,
          "state_row_count": len(cases), "truth_firewall": "case physical parameters are hidden plant inputs; candidate selection sees only deployable runtime state and frozen baseline path/timing; no evaluation-only truth enters planning",
          "baseline_replay_rule": "two identical unmodified scientific runs per condition row; checkpoint rows must also match official V3 J_F_task within 1e-6 N s; exclude individual failed rows with evidence",
          "conditions": []}
for ident, relative, cp, role, physical_id in cases:
    path = STAGE / "configs/high_rom_v1" / relative
    matrix["conditions"].append({"id": ident, "physical_condition_id": physical_id,
        "adaptation_state": "early" if cp == 1 else "late" if cp == 25 else "fresh",
        "checkpoint_rep": cp, "case_path": str(path.relative_to(ROOT)),
        "case_sha256": sha(path), "role": role, "baseline_run_id": f"baseline_{ident}_a",
        "baseline_replay_run_id": f"baseline_{ident}_b"})
freeze("CONDITION_MATRIX.json", matrix)

audit = {"schema": "current_timing_path_audit_v1", "source_commit": source,
    "active_confidence_pacing": False,
    "source_findings": [
        {"component": "waypoint segment duration", "source": "human_waypoint_scheduler.py:_plan", "finding": "Shortest feasible 5 ms registered-grid quintic duration under phase timeout, fixed fractional velocity and acceleration limits, ROM and continuous clearance; endpoint velocity and current emitted reference state enter the polynomial."},
        {"component": "reference velocity/acceleration fractions", "source": "incremental_clearance_terminal_v9.json:11-12; human_waypoint_scheduler.py:629-632", "finding": "0.5 velocity and 0.25 acceleration multiply original task joint limits; same fractions bound pass-through terminal velocity."},
        {"component": "mechanics duration search", "source": "human_waypoint_feedback_mpc.py:305-347", "finding": "After mechanics screen rejects shortest reference-feasible schedule, if enabled, search longer 5 ms grid durations until a mechanics-feasible fixed-duration schedule is found."},
        {"component": "receipt reference governor", "source": "receipt_reference_governor.py:select/commit; runtime.py:3372-3444", "finding": "Selects only receipt-history acceleration-feasible progress; deferred progress delays realized segment completion; runtime completion checks governor is_complete."},
        {"component": "RSS/fallback", "source": "runtime.py:2745-3144; safe_fallback.py", "finding": "Rolling splice, prefetch, fallback and pass-through can alter realized timing while preserving certified reference and safety semantics."},
        {"component": "terminal/HOLD/recovery", "source": "runtime.py:2609-2846,3602-3644", "finding": "Measured-state phase transitions, HOLD dwell, terminal commit, recovery and safe fallback can change total task time."},
        {"component": "confidence/trust", "source": "active runtime, planner, scheduler and v9 options source search", "finding": "No confidence/trust gamma variable enters this active zero-value/safe-action scientific path; historical confidence pacing is outside it."},
    ],
    "fixed_duration_validation_scope": "The fixed-duration scheduler validates grid, velocity, acceleration, ROM and continuous clearance; scientific closed-loop matching and governor residuals still require pilot evidence."}
freeze("CURRENT_TIMING_PATH_AUDIT.json", audit)
(DOC / "CURRENT_TIMING_PATH_AUDIT.md").write_text(
    "# Current Timing Path Audit\n\n" + "\n".join(f"- **{x['component']}** ({x['source']}): {x['finding']}" for x in audit["source_findings"]) +
    "\n\nThe active campaign has no confidence-driven gamma. The existing fixed-duration contract is a candidate for the matched arm, subject to closed-loop validation.\n")

contract = {"schema": "coordination_pacing_exploration_contract_v1", "status": "FROZEN_BEFORE_FORMAL_SWEEP",
    "source_commit": source, "branch": "codex/coordination-pacing-exploration-v1",
    "question_primary": "Does relative hip-knee path coordination reduce interaction cost after nominal pacing is matched?",
    "question_secondary": "How does native scheduling alter that benefit?",
    "arms": {"NATIVE": "deform relative coordination and let all production scheduling, mechanics, governor, RSS and safety act normally",
             "MATCHED": "same path deformation and original execution, with each decision's exact baseline nominal duration requested on the registered grid; infeasible fixed schedules are rejected; realized timing residual is measured and only sufficiently matched comparisons support coordination-isolated claims"},
    "path_family": "baseline phase waypoint sequence plus smooth endpoint-zero normalized-progress relative hip/knee deformation; common start and endpoint retained; separate synchronous comparator; no equal instantaneous velocity assumption",
    "lead_values": [-1, 0, 1], "amplitudes_fraction_of_span": [0.0, 0.02, 0.06, 0.12, 0.18],
    "catch_up_peaks": [0.3, 0.5, 0.7], "horizons": ["H1", "H2", "H3", "H4"],
    "safety": "Original ROM, velocity, acceleration, continuous clearance, mechanics force/moment, controller, RSS, scientific validity and task semantics remain authoritative; no offline time stretching or artificial idle time",
    "primary_cost": "J_F_task = integral norm(measured cuff force) dt for OUTBOUND + HOLD + RETURN",
    "coordination_benefit": "matched baseline J_F_task minus matched candidate J_F_task, only interpret as coordination-isolated when realized OUTBOUND and RETURN duration residuals each <= 0.025 s and same segment count/phase sequence; otherwise label timing-confounded",
    "native_benefit": "native baseline J_F_task minus native candidate J_F_task",
    "secondary_metrics": ["J_F_session", "task duration", "mean/RMS/peak cuff force", "moment integral/peak", "minimum clearance", "q/dq/ddq", "phase durations", "planned/realized segment durations", "governor delays", "duration search", "RSS/fallback/terminal effects", "0.5 s/1.5 s/outbound/full cost"],
    "baseline_rule": matrix["baseline_replay_rule"], "condition_matrix_sha256": sha(DOC / "CONDITION_MATRIX.json"),
    "plan": "freeze coarse pattern list before formal sweep; paired arms where legal; refine informative regions after coarse; validate selected patterns only on validation-role conditions",
    "formal_attempt_minimum": 300, "formal_attempt_target": [500, 800], "maximum_wall_hours": 8,
    "progress_interval_attempts": 50, "repair_limit": 6,
    "individual_outcomes": ["VALID", "INFEASIBLE", "INVALID"],
    "systemic_stop": ["majority baseline-replay failure", "matching requires weakening safety", "controller/Human/planner/scientific semantics change", "unrecoverable raw corruption", "repeated infrastructure failure after six bounded repairs", "eight-hour cap"],
    "truth_firewall": matrix["truth_firewall"],
    "learning": "no RL, supervised policy or value training; no production objective or value-hook modification",
    "held_out_rule": "validation-role conditions are not used to select/refine patterns; reused states are not called held out",
    "decision_rule": "No claim of exact additive timing/path decomposition; report matched residual and native timing associations. No force-intensity claim from integral alone."}
freeze("COORDINATION_PACING_EXPLORATION_CONTRACT.json", contract)
(DOC / "COORDINATION_PACING_EXPLORATION_CONTRACT.md").write_text(
    "# Coordination & Pacing Exploration Contract v1\n\n" +
    "Primary question: " + contract["question_primary"] + "\n\n" +
    "Native arm: " + contract["arms"]["NATIVE"] + ".\n\n" +
    "Matched arm: " + contract["arms"]["MATCHED"] + ".\n\n" +
    "Coordination family: " + contract["path_family"] + ".\n\n" +
    "Safety: " + contract["safety"] + ".\n\n" +
    "Baseline, conditions, outcomes, matched tolerance, budget, validation split and stop rules are frozen in the accompanying JSON and CONDITION_MATRIX.json. No learning is trained.\n")
print(DOC)
