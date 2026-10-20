# Single-Human Direct SAC Expert v1

Status: **SINGLE_HUMAN_SAC_EXPERT_V1_BLOCKED**.

Formal agent steps: 0; wall including conservative preflight: 1.192 h. Phase reached: QUALIFICATION_STOP. Blocker/stop: QUALIFICATION_GATE_FAILED:old_nominal_MATCHED.

## Scope and scientific contract

Fixed nominal high-ROM Human; start [5°,10°], goal [120°,120°]. Same protected Human/CR12/cuff plant, endpoints, limits, historical evidence and independent scorer. Commissioning-only estimated beta/residual/effective geometry frozen during each episode; fresh deterministic commissioning resets. Hidden plant truth is used only for construction and post-run independent evaluation. No Human randomization, adaptation comparison, held-out or hardware claims.

The versioned Gym observation has 55 causal fields: validated 47-D state/model/wrench/reference plus phase/dwell clocks, previous proposed/executed action/rejection and remaining task time. Fixed scales have no clipping, running update, evaluation leakage or future episode statistics. Absolute independent two-joint targets span the original ROM through the original certified acceleration-aware realization; the terminal ±0.05-rad smoke adapter was insufficient for the requested freedom and is preserved unchanged.

Reward is negative measured 5-ms cuff-force integral /100 plus bounded potential shaping, +500 complete task, -1000 explicit failure and -0.2 rejected command; no hip-leading/imitation/novelty/moment paper score/early-time bonus. Deadline truncation is a failed finite-horizon episode with replay bootstrap disabled. Final normalization/reward/reset/period evidence is in dedicated artifacts.

Native task duration is free; matched evaluation adds prospective common physical phase clocks 9/1/9 s, retaining original valid continuous 0.5-s HOLD and arrival requirements. Invalid/late cases are not ranked. Same total clocks do not remove within-phase pacing differences. Development revisions and negative attempts are preserved; no formal runs mix contracts.

## Qualification and tests

10/20/50-ms authority rollouts used synchronous, hip/knee lead, reduced progress, reversal and catch-up intentions under real CPU MuJoCo CR12-cuff-Human execution. The slowest 50ms cadence projected 300k above the hard wall cap; 20ms was prospectively selected before formal comparison and retested. Exact reward quadrature, eleven reward adversaries, repeated certified-prefix rejection, alternating extremes, zero/no motion, timeout, invalid HOLD/RETURN and twenty sequential final-period resets are recorded. ADAPTER_TESTS.txt contains the targeted regression checks. Initial 50ms development tests/reset evidence are separately versioned.

## Training, evaluation and comparators

{
  "seeds": [],
  "total_steps": 0
}

Only SB3 SAC is permitted: CUDA optimization, 2×256 ReLU MLP, Adam 3e-4, batch 256, compact 100k replay, formal learning_starts 5000, gamma exp(-0.02/150), tau .005, auto entropy, one collection environment. Exact budgets/config/model/task/source hashes are frozen before formal learning. Mechanical benchmark learning_starts 32 is explicitly nonformal and never initializes formal weights/replay. Independent deterministic complete-task checkpoint evaluation freezes optimizer, replay and normalization; ranking uses physical validity and J_F, never training return.

Fresh comparison uses old nominal controller, constant new-interface reference, explicitly fixed coordination and archived CEM/fixed target descriptors transferred through the same interface. Transfer is a new reference evaluation, not reproduction of old numeric CEM cost or replay of evaluation-only Human motion. Original historical nominal/CEM J_F values are context only if conditions differ. Strong references and failures remain in SAC_COMPARATOR_TABLE.json.

## Results and interpretation

{
  "confirmed_SAC": {},
  "comparison": [
    {
      "name": "online_reference",
      "scope": "NATIVE",
      "valid": true,
      "J_F": 904.734175177766,
      "force_mean": 76.41392587468695,
      "force_rms": 80.97693545704902,
      "force_peak": 125.9408792656329,
      "moment_integral": 66.61738233604088,
      "moment_peak": 18.092599129383007,
      "duration_s": 11.840000000014255,
      "clearance": 0.006532101542514543,
      "rejections": 0,
      "modification_fraction": 0.0
    },
    {
      "name": "old_nominal",
      "scope": "NATIVE",
      "valid": true,
      "J_F": 1237.487621557985,
      "force_mean": 77.34313415001414,
      "force_rms": 79.45085080298797,
      "force_peak": 115.47911864309106,
      "moment_integral": 79.03978005575306,
      "moment_peak": 15.711377245106318,
      "duration_s": 16.00000000003412,
      "clearance": 0.006455439597061488,
      "rejections": 0,
      "modification_fraction": 0.0
    },
    {
      "name": "fixed_hip_lead",
      "scope": "NATIVE",
      "valid": true,
      "J_F": 877.7225532079905,
      "force_mean": 74.1648082783602,
      "force_rms": 77.73315098635058,
      "force_peak": 118.42539837555772,
      "moment_integral": 74.42684463361267,
      "moment_peak": 17.018578508696926,
      "duration_s": 11.835000000014231,
      "clearance": 0.006532101493002315,
      "rejections": 0,
      "modification_fraction": 0.0
    },
    {
      "name": "cem_reference_transfer",
      "scope": "NATIVE",
      "valid": true,
      "J_F": 1194.0620072796557,
      "force_mean": 77.43606971930325,
      "force_rms": 80.3186225553242,
      "force_peak": 124.36453999824371,
      "moment_integral": 83.75222798140834,
      "moment_peak": 18.092599129383007,
      "duration_s": 15.420000000031349,
      "clearance": 0.007407143560686791,
      "rejections": 0,
      "modification_fraction": 0.0
    },
    {
      "name": "online_reference",
      "scope": "MATCHED",
      "valid": true,
      "J_F": 1371.6417786876261,
      "force_mean": 72.13650098895188,
      "force_rms": 75.77779047992802,
      "force_peak": 125.9408792656329,
      "moment_integral": 112.99122530046597,
      "moment_peak": 18.092599129383007,
      "duration_s": 19.015000000048516,
      "clearance": 0.006532101712272223,
      "rejections": 0,
      "modification_fraction": 0.0
    },
    {
      "name": "old_nominal",
      "scope": "MATCHED",
      "valid": false,
      "J_F": 1438.6134984674875,
      "force_mean": 75.59800301849465,
      "force_rms": 77.6847311571058,
      "force_peak": 115.47911864309106,
      "moment_integral": 100.41725111044204,
      "moment_peak": 15.711377245106318,
      "duration_s": 19.030000000048588,
      "clearance": 0.006455226133651249,
      "rejections": 0,
      "modification_fraction": 0.0
    }
  ]
}

No lucky training episode is promoted. Confirmed best candidates require two independent reload/replays within inherited J_F tolerance 1e-6 N s, preserving checkpoint, model/task/normalization/contract hashes and trace. A negative or bounded partial result remains evidence; no multi-Human or SAC reliability claim follows.

## Resources, provenance and preservation

Environment stepping, actual CUDA collection/update and independent evaluation throughput, CPU/GPU/VRAM, RAM/peak RSS, disk rate, episode wall time and 100k–2M estimates are in SAC_THROUGHPUT files. Actor CPU/GPU and full-chain latency distributions are scientific characterization, not hardware qualification. MuJoCo remains CPU; no three-or-more environment or paid compute experiments. Full training-episode traces are disabled; sparse checkpoints, scalar curves and selected evaluation/qualification evidence are retained with lossless raw archives.

{
  "pass_": true,
  "changed_protected_files": [],
  "preexisting_index_preserved": true,
  "preexisting_staged_count": 58,
  "source_head": "41cdddef117caa4b191a52129c4ff83e481fd5a8",
  "head_unchanged": true,
  "branch": "codex/single-human-sac-expert-v1",
  "no_merge": true,
  "no_commit": true,
  "no_push": true
}

## Next recommended step

Review the recorded failed qualification gate and preregister a corrected version before authorizing further expert training.

Git: research branch codex/single-human-sac-expert-v1; original staged evidence preserved. New compact campaign files staged individually; no commit, push, merge, reset or stash.
