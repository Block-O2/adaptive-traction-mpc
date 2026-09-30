# Per-decision cost-to-go dataset schema

{
  "schema": "value_dataset_schema_v1",
  "decision": "Only actually activated high-level target actions from completed VALID tasks; no whole-pattern benefit assigned to first waypoint",
  "state": {
    "estimated_human_q_dq": [
      0.10194706696223249,
      0.1659657739651847,
      -0.0005395184507328007,
      -0.017686762428215482
    ],
    "reference_q_dq": [
      0.10267209322688563,
      0.16554747268639822,
      0.0,
      0.0
    ],
    "phase_elapsed_s": 0.0,
    "phase_remaining_s": 10.0,
    "deployable_belief": {
      "accepted_beta_update_count": 22,
      "beta": [
        1.5596503840622598,
        0.24444968814842188,
        0.3689331073997303,
        31.92682976648903,
        8.877662068599635,
        10.16126951555425,
        9.786353313890052,
        0.5958269608093406,
        1.2734092026924217,
        4.323179147745417,
        4.621660121919266
      ],
      "deployable_truth_consumed": false,
      "dynamics_sample_count": 626,
      "dynamics_source": "ONLINE_ESTIMATED",
      "effective_geometry": {
        "hip_plane_m": [
          -0.003553836685630789,
          0.06352732691449339
        ],
        "joint_axis_world": [
          0.0,
          1.0,
          0.0
        ],
        "knee_to_cuff_in_cuff_m": [
          0.29858223925811933,
          0.0
        ],
        "origin_world_m": [
          0.0,
          0.0,
          0.0
        ],
        "plane_x_world": [
          1.0,
          0.0,
          0.0
        ],
        "plane_z_world": [
          0.0,
          0.0,
          1.0
        ],
        "thigh_length_m": 0.4473320285177369
      },
      "geometry_source": "ONLINE_ESTIMATED",
      "residual_limit_nm": 12.0,
      "residual_source": "ONLINE_ESTIMATED",
      "residual_update_count": 626,
      "schema": "adaptive_human_belief_v22",
      "sequence": 626,
      "state_residual_weights_nm": [
        [
          0.0234932421346966,
          -0.018425256947591995,
          -0.03717064182464392,
          0.06680741623282771,
          0.12174493214311805
        ],
        [
          0.03644356692443806,
          0.07999013340359096,
          0.0984844696992479,
          -0.028171192380800125,
          -0.0483257769371105
        ]
      ]
    },
    "model_version": 626,
    "previous_executed_delta_q_rad": [
      0.0,
      0.0
    ]
  },
  "action_fields": [
    "target_q_rad",
    "delta_q_rad",
    "proposal_family",
    "legacy_score",
    "schedule"
  ],
  "transition_fields": [
    "next_high_level_state",
    "next_deployable_belief",
    "measured_actual_segment_cost_n_s",
    "native_recorded_segment_cost_n_s",
    "request_time_s",
    "native_recorded_start_time_s",
    "actual_activation_time_s",
    "end_time_s",
    "task_grid_activation_index",
    "terminal",
    "completion",
    "value_model_version_afterward"
  ],
  "return": "Measured cuff-force cumulative sum from actual activation to terminal; separately next 1.5s cost",
  "continuation": "Actual source policy family, declared parameters/schedules, continuation id and active model version; path context used as input, not omitted",
  "feature_names": [
    "estimated_state_0",
    "estimated_state_1",
    "estimated_state_2",
    "estimated_state_3",
    "reference_state_0",
    "reference_state_1",
    "reference_state_2",
    "reference_state_3",
    "start_0",
    "start_1",
    "goal_0",
    "goal_1",
    "phase_0",
    "phase_1",
    "phase_2",
    "time_context_0",
    "time_context_1",
    "time_context_2",
    "progress_0",
    "progress_1",
    "remaining_span_0",
    "remaining_span_1",
    "previous_executed_delta_0",
    "previous_executed_delta_1",
    "beta_0",
    "beta_1",
    "beta_2",
    "beta_3",
    "beta_4",
    "beta_5",
    "beta_6",
    "beta_7",
    "beta_8",
    "beta_9",
    "beta_10",
    "residual_0",
    "residual_1",
    "residual_2",
    "residual_3",
    "residual_4",
    "residual_5",
    "residual_6",
    "residual_7",
    "residual_8",
    "residual_9",
    "geometry_origin_world_m_0",
    "geometry_origin_world_m_1",
    "geometry_origin_world_m_2",
    "geometry_plane_x_world_0",
    "geometry_plane_x_world_1",
    "geometry_plane_x_world_2",
    "geometry_joint_axis_world_0",
    "geometry_joint_axis_world_1",
    "geometry_joint_axis_world_2",
    "geometry_plane_z_world_0",
    "geometry_plane_z_world_1",
    "geometry_plane_z_world_2",
    "geometry_hip_plane_m_0",
    "geometry_hip_plane_m_1",
    "geometry_thigh_length_m_0",
    "geometry_knee_to_cuff_in_cuff_m_0",
    "geometry_knee_to_cuff_in_cuff_m_1",
    "model_summary_0",
    "model_summary_1",
    "model_summary_2",
    "model_summary_3",
    "continuation_parameters_0",
    "continuation_parameters_1",
    "continuation_parameters_2",
    "continuation_parameters_3",
    "continuation_parameters_4",
    "continuation_parameters_5",
    "continuation_parameters_6",
    "continuation_horizon_0",
    "continuation_horizon_1",
    "continuation_horizon_2",
    "continuation_horizon_3",
    "continuation_rule_0",
    "continuation_rule_1",
    "continuation_rule_2",
    "continuation_target_0_0",
    "continuation_target_0_1",
    "continuation_duration_0_0",
    "continuation_target_1_0",
    "continuation_target_1_1",
    "continuation_duration_1_0",
    "continuation_target_2_0",
    "continuation_target_2_1",
    "continuation_duration_2_0",
    "candidate_target_0",
    "candidate_target_1",
    "candidate_delta_0",
    "candidate_delta_1",
    "candidate_schedule_0",
    "candidate_terminal_velocity_0",
    "candidate_terminal_velocity_1"
  ],
  "feature_dimension": 96,
  "truth_firewall": "Only estimated state, deployable belief, receipt/reference, task specification and declared controller memory in X; native q and future force only evaluation labels",
  "split": {
    "limitation": "All source conditions have historical exploration outcomes. Test means held out from fitting/tuning this value model, not previously unseen science. Test reference-search rollouts never enter prior training.",
    "test": [
      "elevated_start",
      "variable_start_120"
    ],
    "train": [
      "low_ordinary_early",
      "low_ordinary_late",
      "balanced_middle",
      "hip_ordinary",
      "sync_120"
    ],
    "unit": "physical condition/session; both low_ordinary adaptation states remain together",
    "validation": [
      "knee_ordinary",
      "balanced_high"
    ]
  },
  "failure_rule": "Rejected/truncated/INVALID/EXCEPTION rows recorded separately, never attractive regression targets",
  "native_schedule_exclusion": "Historical native-time arm excluded from current matched-scheduler cost fit; preserved historical evidence remains untouched"
}
