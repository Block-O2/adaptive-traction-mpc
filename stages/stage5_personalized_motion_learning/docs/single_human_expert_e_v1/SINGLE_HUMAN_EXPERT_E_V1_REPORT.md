# Single-Human Expert E v1 — bounded CEM search closeout

STATUS: E_SEARCH_COMPLETE. **QUALIFIED STRONG EXPERT (E_SEARCH)**.

User budget revision cancels the 50k SAC requirement and replaces it with a hard four-hour work-package cap and bounded CEM search. Earlier K=2 contract, references, BC/Gym/reward gates and checkpoint-0 evidence remain unchanged. SAC was cleanly interrupted at 49 returned transitions and preserved with replay/optimizer/RNG state; this is an authorized budget cancellation, not evidence of SAC instability.

## Frozen shared action and scientific scope

K=2, fixed remaining-progress knot fractions [.1,.7], normalized residual bounds [-.2,.2]. Chunks start at max(0,current causal reference common progress), end at the registered phase endpoint, with zero residual endpoints. Only original B native interior request points can update a chunk; HOLD and terminal/settle ownership generate no action. Positive delta leads hip in each phase direction; RETURN uses goal-to-start coordinates. Native B owns all q/dq/ddq, common target, governor, wait and safety decisions.

Search uses a causal phase/native-interior-decision-index lookup of K=2 chunks (20 search parameters for ten opportunities). It contains no reference tape or time-based task executor. Extra native opportunities explicitly use zero B. Only complete independent physical PASS, frozen Human/initial condition, zero task model updates and R2 MATCHED 9/1/9 with the original 20 ms allowance enter search rank. Primary objective remains complete cuff force integral J_F; F/M/tracking/clearance remain recorded secondary metrics and existing safety gates.

CEM: population 8, max 14 generations, elite 3, smoothing .5, std .06 / floor .006, global elite memory, bounded Gaussian rejection sampling, seed 20261005. This reuses the existing smoothed diagonal CEM approach and does not claim full iCEM implementation. Max 120 new attempts; four consecutive generations without >.1% improvement can stop after at least five generations. Reserve 420 seconds and three rollouts for cold confirmation/closeout. Cap starts at original work-package epoch, so earlier work also counts.

## Current-interface deterministic references

| Reference | J_F N s | F peak N | M integral / peak | Clearance m | OUT/HOLD/RETURN s |
|---|---:|---:|---|---:|---|
| B | 1438.613498467 | 115.479119 | 100.417251 / 15.711377 | 0.006455226 | 9.005 / 1.020 / 9.005 |
| fixed_hip_segment_MATCHED | 1419.322653673 | 111.753670 | 107.000814 / 15.232263 | 0.006435216 | 9.005 / 1.020 / 9.005 |
| CEM_segment_MATCHED | 1410.334056253 | 110.648473 | 109.738295 / 15.192494 | 0.006356612 | 9.005 / 1.020 / 9.005 |
| E_RL_checkpoint_0_BC_mean | 1410.334700636 | 110.648449 | 109.738197 / 15.192494 | 0.006356704 | 9.005 / 1.020 / 9.005 |
| E_SEARCH_confirmed | 1360.602793031 | 110.822913 | 122.687605 / 15.167854 | 0.011156570 | 9.005 / 1.020 / 9.005 |

Teacher: current CEM, J_F=1410.334056253. BC first-round PASS, J_F=1410.334700636, path normalized RMS=5.630114e-07, no DAgger corrections. Gym qualification 10 residual interactions with complete force-reward sum exact to numerical tolerance. Checkpoint-0 deterministic cold evaluations 2/2 VALID and exactly repeatable; stochastic diagnostic is preserved separately and never used to rank a deterministic actor.

## Expert result

Best known J_F=1360.602793031367; improvement vs B=5.422631270957979%; vs teacher=3.526204518816778%. Search confirmation=True. Stop reason=FOUR_GENERATION_PLATEAU.

Confirmed source `search_g09_c07`; native metric and full trace in `/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/single_human_expert_e_v1/search_g09_c07`. Complete deployable residual table, confirmation records and contract hashes: `E_SEARCH_BEST_KNOWN.json`. Tracking: {'estimated_tracking_rms_rad': [0.007658040243880894, 0.014792011719166755], 'estimated_tracking_peak_rad': [0.01540195982575443, 0.03627322753265083]}. Primary future V reference is frozen in `EXPERT_BENCHMARK_VERSION.json`; no V training/dataset, multi-Human or hardware work occurred.

Residual proposal/execution audit: {'proposals': 10, 'accepted': 9, 'activated': 9, 'proposal_rejections': 1, 'proposal_rejection_rate': 0.1, 'physical_activation_rejections': 0, 'maximum_proposed_residual': 0.055770389143873174, 'action_smoothness_L2': 0.2360696404564034}. Secondary changes versus B (%): {'force_peak': -4.03207575527823, 'moment_integral': 22.1778166004571, 'moment_peak': -3.4594268904508563, 'clearance': 72.83004572810097}. Moment integral increases by 22.178% while force integral decreases; the scientific objective remains force integral.

Best qualified E_RL actor: `/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/single_human_expert_e_v1/sac/step_000000/model.zip` (BC mean; two deterministic cold PASS). Final cancelled SAC actor: `/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/single_human_expert_e_v1/sac/stopped_resumable/model.zip` (49 interactions, not subsequently ranked); replay and optimizer/RNG state are adjacent. No SAC learning occurred after the cancellation.

## Negative and scope-limited results

- The static K=2 full-phase fit misses preferred RMS .01 (max .012289); actual receding chunks pass all historical path RMS below .004. K=1 cannot reverse. Future graph knots are samples for native decisions and may be replaced at the next eligible native request.
- No 10k/25k/50k SAC results exist: the budget was explicitly cancelled. E_RL is the qualified checkpoint-0 BC mean, not a completed RL-trained expert.
- All invalid, rejected and failed search candidates remain in SEARCH_RESULTS.json, per-candidate proposals/results, raw trace/summary/evaluator folders and CSV. Rejected proposals are distinguished from B fallback execution.
- All evidence concerns one previously exposed nominal Human. Repeated cold runs prove replay consistency, not held-out generalization or hardware qualification.

## Exact compute and integrity

{
  "SAC_returned_collected_interactions": 49,
  "SAC_checkpoint0_gradient_updates": 0,
  "SAC_actual_final_gradient_updates": 49,
  "SAC_complete_physics_tasks": 5,
  "SAC_complete_physical_residual_decisions": 50,
  "note": "A final in-flight action can physically finish while cancellation joins the owner; returned replay transitions and physical action decisions are reported separately.",
  "search_new_attempts": 92,
  "search_complete_rollouts": 92,
  "search_valid_rollouts": 92,
  "search_invalid_or_failed_attempts": 0,
  "search_physics_wrapper_host_s": 7453.203451381982,
  "search_elapsed_s": 8401.157058238983,
  "all_named_cold_rollouts": 103,
  "all_complete_work_package_rollouts": 109,
  "all_work_package_physics_host_s": 8590.577093738088,
  "all_work_package_elapsed_wall_s": 11382.470217943192,
  "hard_cap_s": 14400,
  "within_hard_cap": true,
  "deadline_unix": 1791207984.3798375,
  "no_new_SAC_after_cancellation": true,
  "prior_failed_partial_attempts_retained": true,
  "search_isolated_process_host_s": 7715.491638838008,
  "search_worker_normal_exits": 88,
  "search_worker_peak_rss_bytes": 2788343808,
  "resource_stop_and_repair": {
    "change": "fresh subprocess per cold native rollout; joined before next; policy, physical evaluator, ranking, RNG, population and original deadline unchanged",
    "hard_deadline_unix": 1791207984.3798375,
    "original_stop_retained": true,
    "reason": "RESOURCE_STOP:PERSISTENT_COLD_BOUNDARY_MEMORY_GROWTH",
    "resumed_attempts": 4,
    "scientific_change": false,
    "sha256": "07778e787708e00a07693d815b307d232cc75ea4a8322eef81d0d2d74e73a3b7",
    "source": "/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_expert_e_v1/search_isolated_resume.py"
  },
  "earlier_resource_stop_preserved": "RESOURCE_STOP:PERSISTENT_COLD_BOUNDARY_MEMORY_GROWTH",
  "BC_optimizer_updates": 750,
  "BC_label_count": 10,
  "BC_coordination_corrections": 0,
  "search_native_residual_proposals": 920,
  "search_native_residual_activations": 829,
  "search_native_proposal_rejections": 91,
  "prior_partial_reference_failures": 2,
  "prior_partial_failure_evidence": [
    "REFERENCES_ATTEMPT1_FAILURE.json",
    "REFERENCES_ATTEMPT2_FAILURE.json"
  ],
  "prior_partial_host_time": "individual failed-attempt host durations were not logged; included in total wall time, not imputed into measured rollout host sum",
  "registered_wall_origin": 1791193584.3798375,
  "recorded_finish_unix": 1791204970.128541
}

{
  "protected_changed": [],
  "head_unchanged": true,
  "cached_diff_unchanged": true,
  "shared_action_unchanged": true,
  "observation_unchanged": true
}

The original SAC closeout is preserved under SAC_CANCELLED_CLOSEOUT. Original pretraining import/domain failures, all later degraded/invalid results and interrupted-prefix evidence remain. No commit, push, stage, merge, stash, reset or protected B/Human/timing/safety edit.

Resource lifecycle: the original search owner stopped after four completed valid rollouts when the cold memory-growth guard fired. The stop evidence is retained. Operational continuation runs each identical native evaluator in a fresh joined subprocess, reconstructs the exact original RNG candidate sequence, and preserves the original deadline and scientific contracts. Worker exit and peak memory records accompany every continued rollout.

## Exactly one next recommendation

Use the frozen E_SEARCH version as the single-Human V performance benchmark.
