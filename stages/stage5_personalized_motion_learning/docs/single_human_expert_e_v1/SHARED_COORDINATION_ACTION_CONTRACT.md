# Shared E/V coordination action contract

{
  "K": 2,
  "action_update": "one action only at B native request decision with interior original selected nominal target; skip HOLD and terminal/settle requests; no timer-generated actions",
  "actor_units": "K values in [-1,1] multiplied by residual bound",
  "after_formal_start_immutable": true,
  "chunk_horizon": "remaining spatial phase progress [max(0, causal reference common progress), 1]; origin projection only, no clipping of residual/action/physical reference",
  "execution": "arbitrary PWL v2 residual_spec sampled at original B target; original scheduler/governor owns q/dq/ddq, wait, safety and feasibility",
  "frozen_before_training": true,
  "knot_fractions": [
    0.1,
    0.7
  ],
  "knot_timing": "fixed interior fractions of remaining normalized-progress horizon; zero at current chunk origin and registered phase endpoint; native scheduler determines physical times",
  "name": "SHARED_COORDINATION_ACTION_CONTRACT",
  "phase_semantics": "OUTBOUND start->goal; RETURN goal->start; positive delta leads hip in phase direction; independent chunks",
  "residual_bounds": [
    -0.2,
    0.2
  ],
  "residual_units": "dimensionless normalized task progress; p_hip=p_hip_B+delta, p_knee=p_knee_B-delta",
  "version": 1,
  "zero": "all-zero graph => exact B",
  "formal_freeze_status": "PHYSICAL_RECEDING_PATH_GATES_PASSED; lock at SAC start"
}
