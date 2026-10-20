"""Preserve failed shortest-duration pilot and freeze revised matched protocol."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOC = ROOT / "stages/stage5_personalized_motion_learning/docs/coordination_pacing_exploration_v1"
RUNS = ROOT / "stages/stage5_personalized_motion_learning/results/coordination_pacing_exploration_v1/runs"
def read(run): return json.loads((RUNS / run / "rollout_result.json").read_text())
base = read("baseline_low_ordinary_early_a")
native = read("pilot_native_hip_mild")
short = read("pilot_matched_hip_mild")
slowbase = read("pilot_matched_baseline_f130")
slowhip = read("pilot_matched_hip_f130")
validation = {
    "schema": "matched_pacing_validation_v1", "status": "PASS_WITH_REVISED_COMMON_DURATION_PROTOCOL",
    "pilot_case": "low_ordinary_early", "scientific_mode": "SCIENTIFIC_SIMULATION",
    "shortest_duration_pilot": {"run_id": short["run_id"],
        "raw_abort_reason": short.get("abort_reason"),
        "logging_exception": short.get("failure_reason"),
        "interpretation": "Original shortest baseline duration is acceleration-infeasible for the altered path; raw abort preserved. Logging code was repaired without changing science."},
    "common_duration_factor": 1.3,
    "matched_baseline": {k: slowbase.get(k) for k in ("run_id", "status", "J_F_task_n_s", "duration_s", "outbound_duration_s", "return_duration_s", "governor_delay_added_s")},
    "matched_hip_candidate": {k: slowhip.get(k) for k in ("run_id", "status", "J_F_task_n_s", "duration_s", "outbound_duration_s", "return_duration_s", "governor_delay_added_s")},
    "native_hip_candidate": {k: native.get(k) for k in ("run_id", "status", "J_F_task_n_s", "duration_s", "outbound_duration_s", "return_duration_s")},
    "realized_outbound_residual_s": slowhip["outbound_duration_s"] - slowbase["outbound_duration_s"],
    "realized_return_residual_s": slowhip["return_duration_s"] - slowbase["return_duration_s"],
    "matched_coordination_benefit_n_s": slowbase["J_F_task_n_s"] - slowhip["J_F_task_n_s"],
    "original_velocity_acceleration_rom_clearance_mechanics_and_scientific_gates": "retained; both longer-duration pilot runs VALID with physical and scientific PASS",
    "fixed_duration_grid": "Each requested duration rounded to the registered 5 ms grid; scheduler confirms exact grid membership and original limits",
    "continuity_and_endpoint": "Original quintic boundary interpolation and runtime activation validation retained; complete phase sequence and no fallback in both valid pilot runs",
    "determinism": "Frozen native baseline replayed exactly twice; matched common-duration baseline determinism remains to be checked in condition matrix validation",
    "limitation": "Nominal segment durations are matched, but receipt-governed realized phase time may differ. Only comparisons within 0.025 s per phase and equal decision/phase sequence support coordination-isolated claims."
}
(DOC / "MATCHED_PACING_VALIDATION.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
(DOC / "MATCHED_PACING_VALIDATION.md").write_text(
    "# Matched Pacing Validation\n\nThe first altered path was infeasible at the baseline's shortest registered duration because the existing acceleration limit rejected it. The abort trace is preserved. A failure-logging error was repaired.\n\n"
    "A common 1.3× baseline segment-duration schedule was then applied with `plan_fixed_duration_reference_contract` to both the original path and a mild hip-leading path. Both completed with physical and scientific PASS. OUTBOUND realized time matched exactly and RETURN differed by 0.005 s. The fixed scheduler retained the original grid, velocity, acceleration, ROM and continuous-clearance checks; the original mechanics and execution screens remained active.\n\n"
    "The candidate's matched J_F_task was 0.502486 N s higher than the common-duration baseline. This is a negative coordination result for this pilot. Nominal matching alone does not guarantee equal realized timing; the frozen analysis requires phase residuals no larger than 0.025 s and matching decision/phase structure.\n")
v1 = json.loads((DOC / "COORDINATION_PACING_EXPLORATION_CONTRACT.json").read_text())
v2 = dict(v1)
v2.update({"schema": "coordination_pacing_exploration_contract_v2",
           "status": "FROZEN_AFTER_PILOT_BEFORE_FORMAL_SWEEP",
           "supersedes": "COORDINATION_PACING_EXPLORATION_CONTRACT.json (v1 shortest-duration pilot rejected by original acceleration limit)",
           "matched_duration_factor": 1.3,
           "matched_baseline_rule": "Each condition receives a separate original-path matched baseline under the same 1.3× registered-grid segment durations; compare matched candidates against this baseline only",
           "arms": {**v1["arms"], "MATCHED": "exact fixed-duration quintic at 1.3× each original baseline segment duration, rounded to the registered 5 ms grid, for both original and deformed paths; all original screens active; record realized phase residuals; reject infeasible schedules"}})
(DOC / "COORDINATION_PACING_EXPLORATION_CONTRACT_V2.json").write_text(json.dumps(v2, indent=2, sort_keys=True) + "\n")
(DOC / "COORDINATION_PACING_EXPLORATION_CONTRACT_V2.md").write_text(
    "# Coordination & Pacing Exploration Contract v2\n\n"
    "The preserved v1 pilot showed that exact shortest baseline segment durations cannot execute a mild changed path within the original acceleration limit. Before any formal sweep, this v2 protocol freezes a common 1.3× duration for the original matched baseline and each matched candidate. Durations stay on the 5 ms grid. All v1 scientific questions, safety screens, condition roles, metrics and stop rules remain in force. Matched benefit is assessed only against each condition's separate common-duration baseline, and realized phase timing residuals are reported.\n")
