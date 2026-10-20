# Fixed demo sampling contract

{
  "status": "FROZEN_BEFORE_TRAINING",
  "question": "Does full legal causal successful replay help independent long-horizon task acquisition?",
  "demo_count": 593,
  "batch_size": 256,
  "demo_per_batch": 128,
  "online_per_batch": 128,
  "immutable_demo": true,
  "online_capacity": 100000,
  "replacement_sampling": true,
  "ratio_fixed_entire_50k": true,
  "learning_starts_online_only": 5000,
  "gradient_steps": 1,
  "train_freq": 1,
  "no_extra_updates": true,
  "algorithm": "unmodified installed SB3 SAC.train",
  "batch_logging": "every update: exact count/fraction and each source phase counts",
  "actor": "fully autonomous, no teacher intervention/BC/HER/pretraining/curriculum",
  "training_mode": "NATIVE only",
  "seed": 20261003,
  "order": [
    "B",
    "A"
  ],
  "targets": {
    "B": 50000,
    "A": 50000
  },
  "wall_hours": 9,
  "holdout": "none: previously exposed fixed Human, single paired seed; not a robustness study",
  "endpoints": [
    "settled_outbound",
    "hold_entry",
    "hold_completed",
    "return_entry",
    "valid_complete"
  ],
  "endpoint_order": "actual causal phase transition/independent VALID; position100% never sufficient",
  "selection": "VALID only, separately per NATIVE/MATCHED scope; retain first/best/final",
  "truth_firewall": "only unchanged causal observation and raw actor action in replay; evaluator truth is diagnostic only",
  "excluded": "resource/OOM/simulation runtime/source-corruption pause, never omit failure cases",
  "resource_policy": "existing corrected WSL + Windows commit headroom and joint low-memory; no Windows-only gate",
  "threads": {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1"
  },
  "source_head": "41cdddef117caa4b191a52129c4ff83e481fd5a8",
  "scientific_changes": [],
  "formal_initialization": 0
}
