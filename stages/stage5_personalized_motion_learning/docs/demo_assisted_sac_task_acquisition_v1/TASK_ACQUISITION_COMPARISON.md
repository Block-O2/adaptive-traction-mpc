# Demo-Assisted SAC Task Acquisition v1

STATUS: PAIRED_50K_COMPLETE_STOP

No completed task or settled phase progression benefit demonstrated at 50k; do not extend the budget automatically.

Historical Scratch300k, Paired Scratch50k (A) and Demo-Assisted50k (B) are distinct experiments. All R2 scientific variables stayed byte-identical. No old actor, critics, replay, optimizer or normalization statistics were inherited. Same fresh weights/empty Adam, seed20261003, first5000 random actions, hyperparameters, single advancing physics owner, evaluation schedule. B executed before A; no parallel training.

The NATIVE teacher archive has593 transitions: OUTBOUND272/HOLD35/RETURN286. Exact same-wrapper reproduction verified every observation, raw/executed action, reward, next observation, phase and termination flag and remained independently VALID. B batches always128 demo+128 online; A standard256 online. No demo-triggered early updates, BC, teacher override, pretraining, curriculum or hyperparameter change. Original installed SB3 SAC.train remains unchanged.

|Arm|Online steps|Updates|First settled HOLD|First RETURN|First VALID|Final NATIVE|Final MATCHED|
|---|---:|---:|---|---|---|---|---|
|A|50000|45000|not observed|not observed|not observed|TIMEOUT_OUTBOUND|TIMEOUT_OUTBOUND|
|B|50000|45000|not observed|not observed|not observed|TIMEOUT_OUTBOUND|TIMEOUT_OUTBOUND|

Only full independently VALID tasks enter J_F rankings. Max synchronized positional progress is diagnostic; arrival requires the original position, velocity and reference readiness. Online stochastic endpoints and deterministic scope-specific endpoints remain distinguished in FIRST_SUCCESS_EVIDENCE.json.

## Deterministic checkpoints

|Arm|Step|Scope|Tag|Reason|Progress|HOLD|RETURN|VALID|J_F (unranked when invalid)|
|---|---:|---|---|---|---:|---|---|---|---:|
|B|10000|NATIVE|periodic|TIMEOUT_OUTBOUND|0.80874|False|False|False|785.416903|
|B|10000|MATCHED|periodic|TIMEOUT_OUTBOUND|0.80874|False|False|False|785.416903|
|B|20000|NATIVE|periodic|TIMEOUT_OUTBOUND|0.75078|False|False|False|674.244616|
|B|20000|MATCHED|periodic|TIMEOUT_OUTBOUND|0.75078|False|False|False|674.244616|
|B|30000|NATIVE|periodic|TIMEOUT_OUTBOUND|0.72651|False|False|False|744.629330|
|B|30000|MATCHED|periodic|TIMEOUT_OUTBOUND|0.72651|False|False|False|744.629330|
|B|40000|NATIVE|periodic|TIMEOUT_OUTBOUND|0.92222|False|False|False|753.954327|
|B|40000|MATCHED|periodic|TIMEOUT_OUTBOUND|0.92222|False|False|False|753.954327|
|B|50000|NATIVE|periodic|TIMEOUT_OUTBOUND|1.00000|False|False|False|812.371146|
|B|50000|MATCHED|periodic|TIMEOUT_OUTBOUND|1.00000|False|False|False|812.371146|
|B|50000|NATIVE|final|TIMEOUT_OUTBOUND|1.00000|False|False|False|783.702730|
|B|50000|MATCHED|final|TIMEOUT_OUTBOUND|1.00000|False|False|False|783.702730|
|A|10000|NATIVE|periodic|TIMEOUT_OUTBOUND|0.71412|False|False|False|733.420122|
|A|10000|MATCHED|periodic|TIMEOUT_OUTBOUND|0.71412|False|False|False|733.420122|
|A|20000|NATIVE|periodic|TIMEOUT_OUTBOUND|0.58810|False|False|False|801.407459|
|A|20000|MATCHED|periodic|TIMEOUT_OUTBOUND|0.58810|False|False|False|801.407459|
|A|30000|NATIVE|periodic|TIMEOUT_OUTBOUND|0.65172|False|False|False|788.918457|
|A|30000|MATCHED|periodic|TIMEOUT_OUTBOUND|0.65172|False|False|False|788.918457|
|A|40000|NATIVE|periodic|TIMEOUT_OUTBOUND|0.61627|False|False|False|765.678084|
|A|40000|MATCHED|periodic|TIMEOUT_OUTBOUND|0.61627|False|False|False|765.678084|
|A|50000|NATIVE|periodic|TIMEOUT_OUTBOUND|0.98085|False|False|False|782.065005|
|A|50000|MATCHED|periodic|TIMEOUT_OUTBOUND|0.98085|False|False|False|782.065005|
|A|50000|NATIVE|final|TIMEOUT_OUTBOUND|0.59806|False|False|False|744.674938|
|A|50000|MATCHED|final|TIMEOUT_OUTBOUND|0.59806|False|False|False|744.674938|

## Best VALID by scope

{
  "NATIVE": null,
  "MATCHED": null
}

## SAC diagnostics

{
  "A": {
    "final": {
      "arm": "A",
      "step": 50000,
      "updates": 45000,
      "finite": true,
      "alpha": 0.2553585171699524,
      "sample_entropy": -2.0655300617218018,
      "Q_scale": {
        "mean": -399.49086178280413,
        "min": -1102.55078125,
        "max": 184.5336151123047,
        "rms": 591.9695869187489
      },
      "TD_error": {
        "mean": -2.2113003130070865,
        "min": -173.75184631347656,
        "max": 28.00311279296875,
        "rms": 14.334968331706163
      },
      "td_abs_mean": 7.510575294494629,
      "teacher_Q_mean": -177.33724975585938,
      "same_teacher_states_online_action_Q_mean": -182.21954345703125,
      "teacher_minus_online_action_Q_mean": 4.882272720336914,
      "teacher_preferred_rate": 0.5632377862930298,
      "actor_on_teacher_Q_mean": -174.6082000732422,
      "actor_teacher_action_MAE": [
        0.9241618514060974,
        0.7939167618751526
      ],
      "actor_teacher_near_bound_rate": 0.5345699787139893,
      "online_phase": {
        "OUTBOUND": 50000,
        "HOLD": 0,
        "RETURN": 0
      },
      "demo_sample_phase": {
        "OUTBOUND": 0,
        "HOLD": 0,
        "RETURN": 0
      },
      "online_sample_phase": {
        "OUTBOUND": 11520000,
        "HOLD": 0,
        "RETURN": 0
      },
      "critic_comparison_limit": "Counterfactual raw actions sampled from online replay at identical teacher states; Q ranking alone is not physical success",
      "losses": {
        "train/learning_rate": 0.0003,
        "train/n_updates": 45000.0,
        "train/ent_coef": 0.25531426072120667,
        "train/actor_loss": 399.0859680175781,
        "train/critic_loss": 241.15872192382812,
        "train/ent_coef_loss": -0.05157126486301422
      }
    },
    "terminations": {
      "TIMEOUT_OUTBOUND": 99,
      "ONLINE_NO_CURRENT_CERTIFIED_CONTINUATION": 3,
      "LOW_LEVEL_EXECUTION:waypoint moves away from the registered phase goal": 27
    },
    "online_phase": {
      "HOLD": 0,
      "OUTBOUND": 50000,
      "RETURN": 0
    },
    "sampling": {
      "status": "PASS",
      "batch_count": 45000,
      "min_demo_fraction": 0.0,
      "max_demo_fraction": 0.0,
      "demo_samples": 0,
      "online_samples": 11520000,
      "demo_phase_counts": {
        "OUTBOUND": 0,
        "HOLD": 0,
        "RETURN": 0
      },
      "online_phase_counts": {
        "OUTBOUND": 11520000,
        "HOLD": 0,
        "RETURN": 0
      },
      "first_learning_online_step": 5001,
      "unique_demo_data": 0,
      "repeated_samples_not_new_data": true
    },
    "success_then_regression": false
  },
  "B": {
    "final": {
      "arm": "B",
      "step": 50000,
      "updates": 45000,
      "finite": true,
      "alpha": 0.888843834400177,
      "sample_entropy": -1.942314624786377,
      "Q_scale": {
        "mean": -12.937881101388484,
        "min": -1149.686279296875,
        "max": 1260.6324462890625,
        "rms": 664.9204581929755
      },
      "TD_error": {
        "mean": 2.446404132992029,
        "min": -59.37919616699219,
        "max": 41.80029296875,
        "rms": 9.28291609271655
      },
      "td_abs_mean": 5.965890407562256,
      "teacher_Q_mean": 432.1650085449219,
      "same_teacher_states_online_action_Q_mean": 336.4628601074219,
      "teacher_minus_online_action_Q_mean": 95.7021713256836,
      "teacher_preferred_rate": 0.7858347296714783,
      "actor_on_teacher_Q_mean": 441.1449279785156,
      "actor_teacher_action_MAE": [
        0.41672030091285706,
        0.4388245642185211
      ],
      "actor_teacher_near_bound_rate": 0.5446880459785461,
      "online_phase": {
        "OUTBOUND": 50000,
        "HOLD": 0,
        "RETURN": 0
      },
      "demo_sample_phase": {
        "OUTBOUND": 2643574,
        "HOLD": 339523,
        "RETURN": 2776903
      },
      "online_sample_phase": {
        "OUTBOUND": 5760000,
        "HOLD": 0,
        "RETURN": 0
      },
      "critic_comparison_limit": "Counterfactual raw actions sampled from online replay at identical teacher states; Q ranking alone is not physical success",
      "losses": {
        "train/learning_rate": 0.0003,
        "train/n_updates": 45000.0,
        "train/ent_coef": 0.8888611197471619,
        "train/actor_loss": 11.317846298217773,
        "train/critic_loss": 81.67631530761719,
        "train/ent_coef_loss": -0.002057401929050684
      }
    },
    "terminations": {
      "TIMEOUT_OUTBOUND": 82,
      "ONLINE_NO_CURRENT_CERTIFIED_CONTINUATION": 4,
      "LOW_LEVEL_EXECUTION:waypoint moves away from the registered phase goal": 20,
      "Q_BOUNDS": 19,
      "TASK_ACCELERATION_LIMIT": 2,
      "SESSION_CLEARANCE_LIMIT": 1
    },
    "online_phase": {
      "HOLD": 0,
      "OUTBOUND": 50000,
      "RETURN": 0
    },
    "sampling": {
      "status": "PASS",
      "batch_count": 45000,
      "min_demo_fraction": 0.5,
      "max_demo_fraction": 0.5,
      "demo_samples": 5760000,
      "online_samples": 5760000,
      "demo_phase_counts": {
        "OUTBOUND": 2643574,
        "HOLD": 339523,
        "RETURN": 2776903
      },
      "online_phase_counts": {
        "OUTBOUND": 5760000,
        "HOLD": 0,
        "RETURN": 0
      },
      "first_learning_online_step": 5001,
      "unique_demo_data": 593,
      "repeated_samples_not_new_data": true
    },
    "success_then_regression": false
  }
}

Q teacher-vs-online-action differences are evaluated at the same teacher states and preserve RNG/optimizer. The alternative raw actions come from online replay; their Q preference is not a physical validation. Actor-vs-teacher MAE is measured on demo states, so it is not by itself evidence of visiting those states. Online replay phase counts and actual task events answer visitation. Actual actor/critic/entropy losses are appended throughout training, with separately labeled read-only Q/TD/entropy diagnostics.

## Resources

{
  "tree_RSS_bytes": 5908512768,
  "tree_PSS_bytes": 5363565568,
  "swap_bytes": 0,
  "min_WSL_available_bytes": 2448580608,
  "min_Windows_available_bytes": 405798912,
  "min_Windows_commit_headroom_bytes": 5763436544,
  "GPU_VRAM_MiB": 160.0,
  "steps_s": {
    "A": 7.606251904177645,
    "B": 7.662603495131954
  },
  "windows_available_only_never_a_stop_gate": true,
  "stop_reasons": [
    [
      "TRAINING_TREE_OVER_4_5_GIB"
    ]
  ]
}

Resource priority: preserve checkpoints and both buffers on pressure; corrected combined host/guest monitor. All high-frequency raw retention decisions are in RAW_DATA_MANIFEST.json. Scalar histories remain; only STATE carries the latest summary.

## Interpretation and next action

No completed task or settled phase progression benefit demonstrated at 50k; do not extend the budget automatically.

One exposed Human/one seed does not establish population robustness or unique causation. No cross-scope J_F comparison. Best checkpoint evidence remains available if later evaluations regress.

Analyze value propagation and absolute-target settling with these preserved checkpoints before any new training budget

STOP after the predefined paired50k budgets. No additional SAC/TQC/PPO/BC/curriculum/multi-Human/hardware work. No commit/push/merge.

## Monitor repair and exact continuation

At A10k, an unconditional process-tree PSS >4.5 GiB gate introduced in the orchestration caused a false pause during evaluation. The existing corrected monitor uses this gate only during training after55k steps; neither arm reaches that condition. The saved original source, stop exception and resource samples retain the defect transparently. See MONITOR_GUARDFIX_V2.md and EXACT_A_PHYSICS_RESTORATION.json.

A resumed from its own10k checkpoint. All419 prior actor transitions in the open episode were reconstructed, with bitwise equality of observation, next observation, float32 reward and done flags. Optimizers, replay, sampler state and global RNG were restored. This reconstruction generated no new online samples or updates. The one pending ordinary update at step10000 was counted once; both arms finish with exactly45000 standard SAC updates. No cold episode reset confound, old300k inheritance, repeated B budget or scientific change. The original9h campaign cap includes the interruption and repair. Arm steps/s sum active process segments and exclude operator repair downtime.

## Saved-trace settling diagnostics

Position progress alone did not establish settled arrival. The read-only goal-box audit is in OUTBOUND_SETTLING_AUDIT.md/json; its reference proxy never replaces the original state machine.

Final A NATIVE: position progress=0.598059; goal-box samples=0; position+velocity samples=0; final q=[85.82541420903124, 39.518981140832096]deg; final dq=[-0.11692540606059507, -0.1511643484548098]deg/s; final reference q=[85.87026596069337, 39.5454578101635]deg; HOLD=False; VALID=False.

Final B NATIVE: position progress=1.000000; goal-box samples=0; position+velocity samples=0; final q=[120.61227169058888, 124.6595510322457]deg; final dq=[0.059035635748650665, 0.05858874642960132]deg/s; final reference q=[120.67727744579315, 124.68399107456209]deg; HOLD=False; VALID=False.

## Phase-specific Q and actor evidence

OFFLINE_Q_PHASE_AUDIT.md/json and OFFLINE_Q_PHASE_CURVE.csv compare the final frozen checkpoints at identical causal Native teacher states. These read-only scores diagnose the learned value profile and actor discrepancy; they add no online steps or updates and do not establish physical counterfactual validity or a unique cause.

A OUTBOUND_first64: teacher Q=115.6177; online-action Q=126.7881; actor Q=135.2321; teacher preferred rate=0.3438; actor-teacher raw-action MAE=[0.2595762014389038, 0.6256930828094482].

A HOLD: teacher Q=247.8601; online-action Q=253.2563; actor Q=243.8782; teacher preferred rate=0.1714; actor-teacher raw-action MAE=[0.5787396430969238, 1.82801353931427].

A RETURN_last64: teacher Q=-876.7871; online-action Q=-875.4151; actor Q=-860.0945; teacher preferred rate=0.3750; actor-teacher raw-action MAE=[1.8852664232254028, 0.40474575757980347].

B OUTBOUND_first64: teacher Q=-44.8323; online-action Q=-48.0308; actor Q=-43.4071; teacher preferred rate=0.7656; actor-teacher raw-action MAE=[0.17285287380218506, 0.5499802827835083].

B HOLD: teacher Q=308.8519; online-action Q=292.1749; actor Q=309.2048; teacher preferred rate=1.0000; actor-teacher raw-action MAE=[0.20375283062458038, 0.01271048467606306].

B RETURN_last64: teacher Q=815.5562; online-action Q=639.3287; actor Q=833.8448; teacher preferred rate=0.9531; actor-teacher raw-action MAE=[0.08004748821258545, 0.14633020758628845].

## A50k positional discontinuity

The periodic A50k checkpoint (44999 updates) reached 0.980853 synchronized positional progress; the final checkpoint after the last ordinary update (45000 updates) reached 0.598059. Neither entered HOLD or achieved VALID. This is positional sensitivity, not a prior successful task followed by regression. Both checkpoints, action sequences and original metrics remain preserved. The compact job pruned the periodic high-frequency trace before it was selected as important; IMPORTANT_FAILURE_REHYDRATION_V2.md/json records a separately labeled Native archival replay of its retained actor actions, verified against every saved transition and original force metrics. No extra training or new formal evaluation rows.

The rehydrated trace.npz checksum equals the recorded original SHA-256. Runtime host-timing archives have separately recorded hashes and are not represented as byte-identical originals.

## What the negative acquisition result says

Demo sampling was active and produced a detectable conditional learning signal on later teacher states. In B, teacher-vs-online-action Q advantage averages 194.21 on RETURN, compared with 2.30 on OUTBOUND; teacher actions are preferred in 96.2% versus 57.4% of those states. The overall teacher-Q advantage is therefore dominated by later-phase states and should not be described as uniformly strong early-OUTBOUND action preference.

B's deterministic actor raw-action MAE against teacher actions is [0.08146673440933228, 0.1409217119216919] on RETURN versus [0.7966334819793701, 0.806891679763794] on OUTBOUND; A's RETURN discrepancy is [1.678821086883545, 0.3496297299861908]. These are conditional predictions at archived teacher states, not proof of online visitation or imitation success. Both online buffers contain zero HOLD/RETURN samples, and both final evaluations have zero simultaneous goal-box samples. B's final knee settles near124.66deg rather than120deg.

The evidence points to a gap between learning on successful later-phase states and independently producing the OUTBOUND actions and reference/position/velocity settling needed to reach them. Weak early action preference, absolute-target settling and safety-interface sensitivity are hypotheses to examine from these frozen artifacts, not uniquely established causes or a measured Bellman propagation rate. No training extension follows this result.
