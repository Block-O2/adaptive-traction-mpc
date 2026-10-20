# Current Human adaptation dataflow

Question A: source audit only; execution qualification is reported separately.

Measured robot/cuff pose, twist and wrench → effective geometry fit → causal state and transmitted-torque reconstruction → 11-parameter dynamic identification and bounded 2×5 state torque residual → immutable belief snapshot → reconstructed Human model → planning, mechanics screening, inverse-dynamics execution and incremental-response mass matrix → continued 20 ms task updates → repetition-boundary updater persistence.

Effective beta names: a_inertia_combination, b_distal_inertia_combination, d_mass_length_com_combination, g1_proximal_gravity_combination, g2_distal_gravity_combination, k1_passive_stiffness, k2_passive_stiffness, rho1_stiffness_rest_combination, rho2_stiffness_rest_combination, bv1_viscous_damping, bv2_viscous_damping.

Geometry estimates hip X/Z, thigh length and knee-to-cuff distance. Full shank length/cuff fraction are not separately identifiable. Task geometry is commissioning-frozen; dynamics and residual continue online. No population generalization follows from this structure.

- commissioning_collection: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:2232`.
- geometry_estimation: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/effective_model.py:70`.
- commissioning_replay: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:990`.
- dynamic_identifier: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/effective_model.py:242`.
- belief: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/phase3_human_waypoint.py:60`.
- continual_update: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:1017`; `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:2555`.
- residual_update: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/phase3_human_waypoint.py:185`.
- model_reconstruction: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/phase3_human_waypoint.py:108`.
- runtime_assignment: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:2346`; `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:2526`; `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:2580`.
- contract_consumption: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:2348`; `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:2528`; `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:2582`.
- planner_consumption: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/phase3_human_waypoint.py:329`.
- mechanics_consumption: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/phase3_human_waypoint.py:262`.
- execution_inverse_dynamics: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/human_waypoint_shadow.py:475`.
- execution_incremental_mass: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:622`; `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:638`; `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:657`.
- execution_supervisor: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:535`; `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:703`.
- repetition_persistence: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:3978`.
- inter_repetition_consumption: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py:1631`.
- observer: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/controller_interface.py:145`.
- residual_model: `stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/functional_benchmark.py:938`.
