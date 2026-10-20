# Single-Human Expert E v1 — Strong Coordination SAC Baseline

STATUS: BLOCKED. E STATUS: **BLOCKED**.

Branch: `codex/single-human-expert-e-v1`. HEAD: `41cdddef117caa4b191a52129c4ff83e481fd5a8`.

Nominal exposed Human, sync_120, commissioning-only frozen belief, unchanged native residual v2, R2 MATCHED 9/1/9 minima with original 20 ms per-phase allowance. No held-out, multi-Human, V, hardware or robustness claim.

Action: K=2; knots=[0.1, 0.7]; bounds=[-0.2, 0.2]. remaining spatial phase progress [max(0, causal reference common progress), 1]; origin projection only, no clipping of residual/action/physical reference. one action only at B native request decision with interior original selected nominal target; skip HOLD and terminal/settle requests; no timer-generated actions.

Reward: -delta J_F / 100; gamma=1; terminal invalid penalty -1000. Secondary metrics remain evaluation records. Rejection/fallback and proposed/activated residuals are separate. HOLD and native terminal/settle ownership generate no learning actions.

## Fresh starting references

| Reference | VALID | J_F N s | F peak N | M integral / peak | Clearance m | OUT / HOLD / RETURN s |
|---|---|---:|---:|---|---:|---|
| B | True | 1438.613498467 | 115.479119 | 100.417251 / 15.711377 | 0.006455226 | 9.005 / 1.020 / 9.005 |
| fixed_hip_segment_MATCHED | True | 1419.322653673 | 111.753670 | 107.000814 / 15.232263 | 0.006435216 | 9.005 / 1.020 / 9.005 |
| CEM_segment_MATCHED | True | 1410.334056253 | 110.648473 | 109.738295 / 15.192494 | 0.006356612 | 9.005 / 1.020 / 9.005 |

Teacher: CEM_segment_MATCHED, J_F=1410.3340562533858. Full native reference, trace and residual decisions: `/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/single_human_expert_e_v1/reference_CEM/RESIDUAL_DECISIONS.npz`, `/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/single_human_expert_e_v1/reference_CEM/native_reference.npz`.

BC: PASS; J_F=1410.3347006360275; correction rounds=0; updates=750. Actor never executes teacher fallback.

## SAC and all checkpoint results

Formal interactions: 49; completed training episodes: 5. Fixed checkpoints are not omitted when worse or invalid. Ranking uses only cold complete VALID repeated deterministic MATCHED mean actors.

| Step | Deterministic VALID | Repeated cost consistent | Ranking J_F |
|---:|---:|---|---:|
| 0 | 2/2 | True | 1410.3347006360275 |

Best actor: {'J_F': 1410.3347006360275, 'checkpoint': '/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/single_human_expert_e_v1/sac/step_000000', 'step': 0}. Final actor/checkpoint: /home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/single_human_expert_e_v1/sac/step_000000.

Improvement vs B: 1.965698%; vs teacher: -0.000046%.

## Representation audit and negative evidence

K=1 cannot represent reversal. K=2 static full-phase residual fit misses preferred RMS .01 (max .012289); K=3 gives only .011967. Actual point-constrained causal receding K=2 chunks physically reproduce fixed/CEM geometry with all normalized path RMS below .004. This is an execution expressivity result, not a claim that static future path prediction is exact. A PWL chunk is sampled at the current native selected target; future knot values can be replaced only at the next eligible native request.

Initial import collision and soft-reference chunk-domain failures are preserved in REFERENCES_ATTEMPT1_FAILURE.json and REFERENCES_ATTEMPT2_FAILURE.json; neither was a B/physics scientific failure. The ordinary integration fixes precede formal training.

Current stop reason: . SAC exception: .

Search reference: Current v2 CEM transfer only; no new search refinement run.

Integrity: {'protected_count': 633, 'changed': [], 'HEAD_unchanged': True, 'index_unchanged': True, 'cached_diff_unchanged': True}. No commit, push, stage, stash, reset or protected-source edit.

## Budget and resource accountability

{
  "formal_training_interactions": 49,
  "completed_training_episode_count": 5,
  "completed_training_native_decisions": 50,
  "completed_training_host_s": 408.49844160402426,
  "named_cold_physics_rollouts": [
    {
      "name": "bc_round_0",
      "host_s": 78.92151990999992,
      "J_F": 1410.3347006360275,
      "valid": true
    },
    {
      "name": "nonzero_regression",
      "host_s": 73.5717847289925,
      "J_F": 1442.0097513132282,
      "valid": true
    },
    {
      "name": "reference_B_attempt3",
      "host_s": 75.00614455100731,
      "J_F": 1438.6134984674875,
      "valid": true
    },
    {
      "name": "reference_CEM",
      "host_s": 75.03810691699618,
      "J_F": 1410.3340562533858,
      "valid": true
    },
    {
      "name": "reference_fixed",
      "host_s": 74.11999751201074,
      "J_F": 1419.32265367327,
      "valid": true
    },
    {
      "name": "representation_catchup",
      "host_s": 74.67876160000742,
      "J_F": 1442.9287631954942,
      "valid": true
    },
    {
      "name": "representation_reversal",
      "host_s": 73.11834199698933,
      "J_F": 1438.4448705941063,
      "valid": true
    },
    {
      "name": "sac_eval_000000_deterministic_1",
      "host_s": 79.24098587900517,
      "J_F": 1410.3347006360275,
      "valid": true
    },
    {
      "name": "sac_eval_000000_deterministic_2",
      "host_s": 77.18133261898765,
      "J_F": 1410.3347006360275,
      "valid": true
    },
    {
      "name": "sac_eval_000000_stochastic_1",
      "host_s": 77.58226811699569,
      "J_F": 1408.4125411435475,
      "valid": true
    },
    {
      "name": "zero_v2",
      "host_s": 75.18074799299939,
      "J_F": 1438.6134984674875,
      "valid": true
    }
  ],
  "named_cold_physics_host_s": 833.6399918239913,
  "elapsed_work_package_wall_s": 2358.747784614563,
  "failed_attempts_retained": true,
  "wall_includes_authoring_and_diagnostics": true,
  "missing_checkpoint_steps": [
    10000,
    25000,
    50000
  ]
}

Policy, replay, optimizers and RNG checkpoint are resumable; process-scoped native hidden physical state is not claimed to be a portable disk restart. Any harness-interrupted native task prefix remains unranked and a resumed episode is cold. Single advancing physics owner; worker cleanup joins before evaluations; runtime artifacts retain the existing lossless compression workflow.

## Exactly one next recommendation

Resolve the recorded stop condition before resuming the frozen SAC protocol.
