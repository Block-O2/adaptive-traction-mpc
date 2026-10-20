# 可执行动作空间审计

{
  "source_sha256": {
    "/home/hank/coding/adaptive-traction-mpc-side-studies/m2_comprehensive_coordination_search_v1/source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/coordination_residual_v2.py": "28d53aa1a9b011199100b134055e80a59cf2b270c6f4230f1f94e7188e96b428",
    "/home/hank/coding/adaptive-traction-mpc-side-studies/m2_comprehensive_coordination_search_v1/deps/coordination_adapter.py": "f506514e03c30bdc98c69a1dde634ef6ebff3472dc8db7bbe5ed397eed23b7d8",
    "/home/hank/coding/adaptive-traction-mpc-side-studies/m2_comprehensive_coordination_search_v1/deps/representation.py": "13fd5aa68a0d85f049495ec55f1ef1d09720a6fc5c7483c124aa416fe067ef51",
    "/home/hank/coding/adaptive-traction-mpc-side-studies/m2_comprehensive_coordination_search_v1/deps/fork_core.py": "1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4",
    "/home/hank/coding/adaptive-traction-mpc-side-studies/m2_comprehensive_coordination_search_v1/code/interfaces.py": "3fd64029a75052401b094c9570cd269c0e28afe1c0e8d842fd73e028a5330b0f"
  },
  "fixed_K3": "ordinary pool budget6: zero/carry/historical/coherent signs/reversal with seeded noise; sparse 30D coverage",
  "continuous_K3": "2 phases x 5 slots x3 amplitudes [-1,1]*.2 at .1/.4/.7 remaining progress",
  "raw_v2": "arbitrary finite PWL, sorted knots, zero (0,0)/(1,0), native sample at original target common progress; p modified by [delta,-delta]; endpoints and HOLD B owned",
  "physical_execution": "same existing proposal boundary, native scheduler/governor feasibility, current-state admission, lifecycle, original applied receipts/native steps; no new clocks or torque authority",
  "dimensions": {
    "phase": {
      "range": [
        "OUTBOUND",
        "RETURN"
      ],
      "units": "dimensionless progress or issued slot index",
      "native_legal": "parameter validity plus original feasibility/admission; proposed alone insufficient",
      "actual_location": "sampled once at each original native interior target request",
      "execution_verified": true,
      "evaluated_candidate_count": 128,
      "distinct_parameter_values": 2
    },
    "sign": {
      "range": [
        -1,
        0,
        1
      ],
      "units": "dimensionless progress or issued slot index",
      "native_legal": "parameter validity plus original feasibility/admission; proposed alone insufficient",
      "actual_location": "sampled once at each original native interior target request",
      "execution_verified": true,
      "evaluated_candidate_count": 128,
      "distinct_parameter_values": 2
    },
    "amplitude": {
      "range": [
        -0.2,
        0.2
      ],
      "units": "dimensionless progress or issued slot index",
      "native_legal": "parameter validity plus original feasibility/admission; proposed alone insufficient",
      "actual_location": "sampled once at each original native interior target request",
      "execution_verified": true,
      "evaluated_candidate_count": 128,
      "distinct_parameter_values": 26
    },
    "slot_mask": {
      "range": {
        "per_phase_indices": [
          0,
          1,
          2,
          3,
          4
        ],
        "combinations": "registered subsets"
      },
      "units": "dimensionless progress or issued slot index",
      "native_legal": "parameter validity plus original feasibility/admission; proposed alone insufficient",
      "actual_location": "sampled once at each original native interior target request",
      "execution_verified": true,
      "evaluated_candidate_count": 128,
      "distinct_parameter_values": 10
    },
    "remaining_progress_onset": {
      "range": "0 <= lo < hi <= 1",
      "units": "dimensionless progress or issued slot index",
      "native_legal": "parameter validity plus original feasibility/admission; proposed alone insufficient",
      "actual_location": "sampled once at each original native interior target request",
      "execution_verified": true,
      "evaluated_candidate_count": 128,
      "distinct_parameter_values": 3
    },
    "remaining_progress_support": {
      "range": "0 <= lo < hi <= 1",
      "units": "dimensionless progress or issued slot index",
      "native_legal": "parameter validity plus original feasibility/admission; proposed alone insufficient",
      "actual_location": "sampled once at each original native interior target request",
      "execution_verified": true,
      "evaluated_candidate_count": 128,
      "distinct_parameter_values": 5
    },
    "PWL_knot_locations": {
      "range": "strictly ordered interior fractions (0,1), this search uses 3; native accepts arbitrary finite graph",
      "units": "dimensionless progress or issued slot index",
      "native_legal": "parameter validity plus original feasibility/admission; proposed alone insufficient",
      "actual_location": "sampled once at each original native interior target request",
      "execution_verified": true,
      "evaluated_candidate_count": 128,
      "distinct_parameter_values": 7
    },
    "PWL_shape": {
      "range": [
        "flat",
        "ramp",
        "taper",
        "tent",
        "reverse"
      ],
      "units": "dimensionless progress or issued slot index",
      "native_legal": "parameter validity plus original feasibility/admission; proposed alone insufficient",
      "actual_location": "sampled once at each original native interior target request",
      "execution_verified": true,
      "evaluated_candidate_count": 128,
      "distinct_parameter_values": 5
    },
    "joint_phase_independent_parameters": {
      "range": "separate OUTBOUND and RETURN slot graphs",
      "units": "dimensionless progress or issued slot index",
      "native_legal": "parameter validity plus original feasibility/admission; proposed alone insufficient",
      "actual_location": "sampled once at each original native interior target request",
      "execution_verified": true,
      "evaluated_candidate_count": 40,
      "distinct_parameter_values": 40
    },
    "within_phase_slot_combination": {
      "range": "up to 5 registered issued slots per phase",
      "units": "dimensionless progress or issued slot index",
      "native_legal": "parameter validity plus original feasibility/admission; proposed alone insufficient",
      "actual_location": "sampled once at each original native interior target request",
      "execution_verified": true,
      "evaluated_candidate_count": 128,
      "distinct_parameter_values": 16
    }
  },
  "unsupported": [
    "common-progress shift",
    "independent hip/knee offsets",
    "dq/ddq command",
    "phase duration control",
    "HOLD/terminal residual",
    "continuous temporal PWL actuation"
  ],
  "limitation": "different raw shapes with equal sampled delta at a request may be physically equivalent; finite search neither exhaustive nor mathematical optimum",
  "actual_execution_scope": "verified finite registered candidates only; parameter-range endpoints or all graphs are not certified"
}
