# Single-Human SAC Expert v1 R2

Status: **PARTIAL**. Formal steps 12194; additional wall 1.029 h. Stop/blocker: ['RESOURCE_RISK'].

## Timing repair and qualification

R1 blocked qualification is preserved byte-for-byte. The physical task requires minimum 0.5s continuously valid HOLD. The prior MATCHED 1s minimum is a comparison clock, not a new physical dwell requirement. The 1.020s old-controller HOLD is caused by two 0.5s references with one 5ms activation wait and one 5ms receipt-owned endpoint recognition each. Source plus transparent deterministic probe confirm this chain; no production controller or physical task edit was made.

R2 common phase clocks are 9/1/9s. Each method must pass the unchanged independent physical evaluator and meet T_min-1e-9 <= actual T <= T_min+.020+1e-9. Slack is max(.020 policy tick, ceil(1/.5)*(.005 activation+.005 receipt confirmation)). Frozen at zero SAC training steps; all methods use exactly the same bounds. Every physical waiting interval remains in force cost.

The 55-D causal observation, independent 2-D full-ROM target action, reward, fixed normalization, 20ms policy cadence, commissioning-only Human model, CR12/cuff/Human plant, safety and evaluator are unchanged. Already passed action/reward/reset/CUDA/normalization evidence is reused by hash. Only affected timing/comparator gates are requalified. Native and matched are separate scopes.

## Comparator requalification

[
  {
    "name": "online_reference",
    "scope": "NATIVE",
    "task_valid": true,
    "matched_eligible": false,
    "valid": true,
    "phase_durations": {
      "HOLD": 0.7049999999996697,
      "OUTBOUND": 5.429999999987345,
      "RETURN": 5.7050000000272405
    },
    "duration_s": 11.840000000014255,
    "J_F": 904.734175177766,
    "force_peak": 125.9408792656329,
    "moment_peak": 18.092599129383007,
    "clearance": 0.006532101542514543
  },
  {
    "name": "old_nominal",
    "scope": "NATIVE",
    "task_valid": true,
    "matched_eligible": false,
    "valid": true,
    "phase_durations": {
      "HOLD": 1.0200000000048703,
      "OUTBOUND": 7.524999999993652,
      "RETURN": 7.4550000000355965
    },
    "duration_s": 16.00000000003412,
    "J_F": 1237.487621557985,
    "force_peak": 115.47911864309106,
    "moment_peak": 15.711377245106318,
    "clearance": 0.006455439597061488
  },
  {
    "name": "fixed_hip_lead",
    "scope": "NATIVE",
    "task_valid": true,
    "matched_eligible": false,
    "valid": true,
    "phase_durations": {
      "HOLD": 0.6999999999996458,
      "OUTBOUND": 5.429999999987345,
      "RETURN": 5.7050000000272405
    },
    "duration_s": 11.835000000014231,
    "J_F": 877.7225532079905,
    "force_peak": 118.42539837555772,
    "moment_peak": 17.018578508696926,
    "clearance": 0.006532101493002315
  },
  {
    "name": "cem_reference_transfer",
    "scope": "NATIVE",
    "task_valid": true,
    "matched_eligible": false,
    "valid": true,
    "phase_durations": {
      "HOLD": 0.6550000000031275,
      "OUTBOUND": 7.41999999999315,
      "RETURN": 7.345000000035071
    },
    "duration_s": 15.420000000031349,
    "J_F": 1194.0620072796557,
    "force_peak": 124.36453999824371,
    "moment_peak": 18.092599129383007,
    "clearance": 0.007407143560686791
  },
  {
    "name": "online_reference",
    "scope": "MATCHED",
    "task_valid": true,
    "matched_eligible": true,
    "valid": true,
    "phase_durations": {
      "HOLD": 1.0050000000047987,
      "OUTBOUND": 9.005000000000718,
      "RETURN": 9.005000000042997
    },
    "duration_s": 19.015000000048516,
    "J_F": 1371.6417786876261,
    "force_peak": 125.9408792656329,
    "moment_peak": 18.092599129383007,
    "clearance": 0.006532101712272223
  },
  {
    "name": "old_nominal",
    "scope": "MATCHED",
    "task_valid": true,
    "matched_eligible": true,
    "valid": true,
    "phase_durations": {
      "HOLD": 1.0200000000048703,
      "OUTBOUND": 9.005000000000718,
      "RETURN": 9.005000000042997
    },
    "duration_s": 19.030000000048588,
    "J_F": 1438.6134984674875,
    "force_peak": 115.47911864309106,
    "moment_peak": 15.711377245106318,
    "clearance": 0.006455226133651249
  },
  {
    "name": "fixed_hip_lead",
    "scope": "MATCHED",
    "task_valid": true,
    "matched_eligible": true,
    "valid": true,
    "phase_durations": {
      "HOLD": 1.0050000000047987,
      "OUTBOUND": 9.005000000000718,
      "RETURN": 9.005000000042997
    },
    "duration_s": 19.015000000048516,
    "J_F": 1344.8967959511835,
    "force_peak": 118.42539837555772,
    "moment_peak": 17.018578508696926,
    "clearance": 0.006532101498540788
  },
  {
    "name": "cem_reference_transfer",
    "scope": "MATCHED",
    "task_valid": true,
    "matched_eligible": true,
    "valid": true,
    "phase_durations": {
      "HOLD": 1.0050000000047987,
      "OUTBOUND": 9.005000000000718,
      "RETURN": 9.005000000042997
    },
    "duration_s": 19.015000000048516,
    "J_F": 1428.1427191962223,
    "force_peak": 124.36453999824371,
    "moment_peak": 18.092599129383007,
    "clearance": 0.007407143357851584
  }
]

CEM transfer uses the pre-existing scheduler-screened reference target/phase-clock descriptor through the qualified online interface, never hidden Human trajectory. It is not a reproduction of historical CEM cost. Exact CSV and unchanged/new traces are in SAC_COMPARATOR_REQUALIFICATION.

## Training, throughput and resources

{
  "planned": [
    300000
  ],
  "seeds": [
    {
      "checkpoint": "stages/stage5_personalized_motion_learning/results/single_human_sac_expert_v1_r2/seed_20261003/step_0012194.zip",
      "completed_steps": 12194,
      "error": null,
      "formal": true,
      "gradient_updates": 7193,
      "planned_steps": 300000,
      "seed": 20261003,
      "steps_s": 7.174509576262272,
      "stop_reason": "RESOURCE_RISK",
      "wall_s": 1699.6283676790001
    }
  ],
  "total_steps": 12194
}

Formal config uses SB3 SAC, CUDA, 2x256 ReLU, Adam3e-4, batch256, replay100k, learning_starts5000, gamma exp(-.02/150), tau .005, auto entropy and one environment. Benchmark weights/replay are discarded; training initializes from its seed. Deterministic native/matched checkpoint evaluations run at 25k intervals with optimizer/replay/normalization unchanged; selection uses valid physical J_F and two independent reload confirmations within1e-6 N s.

Mechanical benchmark learning_starts32 measures real CUDA updates; an additional exact formal-config random-action warmup measurement retains learning_starts5000. Resource samples record Windows free RAM, WSL available memory, swap, CPU, GPU/VRAM and other Python owners. No other study is killed, paused, reconfigured or reniced. Additional hard cap is12h from R2 preflight, with closeout reservation. Ordinary failed episodes remain learning data.

## Required scientific questions

1. What caused 1.020s HOLD?

Two .5s stationary certified schedules, each with one 5ms asynchronous activation wait and one 5ms receipt-owned endpoint recognition. Phase transitions are checked every 5ms, before reference progress commit. No controller bug or SAC-period quantization.

2. What timing protocol is frozen and why?

Physical .5s contiguous valid HOLD unchanged; MATCHED minima 9/1/9s, each upper bound +max(.020 policy tick, 2*(.005 activation+.005 receipt recognition))+.000000001s. Same range for every method, source-derived before SAC training.

3. Do original controller and strong comparators qualify fairly?

PASS

4. Is fixed hip-leading ~877.7 primarily timing, coordination, or unresolved?

Native reduction includes substantial duration effects. After common timing eligibility, a smaller matched benefit remains. Coordination versus within-phase pacing is unresolved as a causal decomposition.

5. Did SAC train successfully?

Formal CUDA optimization executed with finite logged losses; the resource stop prevented the meaningful >=300k campaign. No valid learned expert is confirmed.

6. Best SAC NATIVE J_F?

None

7. Best SAC MATCHED J_F?

None

8. Does SAC beat original, fixed, CEM?

No confirmed valid SAC candidate, so no beating claim.

9. Does SAC discover different coordination?

No confirmed valid SAC trajectory exists for this claim.

10. Does integral reduction increase peaks?

No SAC result. Fixed comparator reduces cost while its force/moment peaks exceed old nominal.

11. Is learning still improving at stop?

None

12. Is more SAC justified before TQC/PPO?

Review measured warmup/reset throughput and valid independent checkpoint trend on this unchanged contract first. Do not switch algorithms to bypass an unresolved resource, throughput or valid-task limitation.

## Interpretation limits

{
  "native_improvement_percent": 29.07221551816848,
  "matched_improvement_percent": 6.514376697850922,
  "matched_J_F_difference": 93.71670251630394,
  "matched_residual_duration_s": 0.015000000000071623,
  "maximum_cost_from_that_extra_time_given_200N_limit": 3.0000000000143245,
  "native_fixed_force_peak_change_percent": 2.5513528048067835,
  "native_fixed_moment_peak_change_percent": 8.32009341509361,
  "causal_scope": "Native contrast contains timing; matched contrast still combines coordination and within-phase pacing. Residual 15ms total-time difference alone is bounded by 3 N s under unchanged 200N limit; cannot explain the full ~93.7 N s matched contrast. No pure-coordination causal effect or generalization claim."
}

Matched eligibility leaves within-phase pacing and up to60ms total residual timing variation. A smaller fixed-reference matched benefit does not by itself isolate pure coordination. No hidden-truth policy, held-out Human, generalization, algorithm reliability, hardware, or global-optimum claim follows.

## Provenance and Git

{
  "pass_": true,
  "changed_preexisting_files": [],
  "preexisting_index_entries_preserved": true,
  "preexisting_index_entry_count": 3963,
  "HEAD_unchanged": true,
  "branch": "codex/single-human-sac-expert-v1",
  "no_commit": true,
  "no_push": true,
  "no_merge": true,
  "no_reset": true,
  "no_stash": true
}

Existing staged entries and worktree bytes were preserved exactly. New evidence and R2 scripts are staged individually; raw physics/checkpoints are inventoried outside the index. No commit/push/merge/reset/stash.

## Next recommended step

Review measured warmup/reset throughput and valid deterministic SAC checkpoint evidence before any separately authorized SAC extension or algorithm comparison.
