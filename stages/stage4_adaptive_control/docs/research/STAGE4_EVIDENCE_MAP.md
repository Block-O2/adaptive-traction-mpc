# Stage-4 Canonical Evidence Map

This map identifies the canonical evidence for the Stage-4 closeout. Unless
stated otherwise, saved run files retain `formal_user_run_unreviewed`; the
repository-level review promotes the listed complete evidence sets without
mutating their historical labels.

## Controller contract shared by formal A/B evidence

- 3D torque-actuated UR10e surrogate + Human V2 + six-constraint rigid cuff.
- Causal robot/cuff measurement boundary; Human truth is evaluation-only.
- Accumulated integral 11-base estimator with frozen bounds and update rules.
- L1-L4 single-incumbent/at-most-one-challenger trust with embargoed future
  validation and anytime alpha spending.
- Confidence pacing and frozen 1:1 cuff-aware allocator.
- Batched feasible-first CEM MPC: horizon 15, 32 candidates, two iterations,
  six elites, seed 20260824, original cost/constraints, interaction weights 0.

The controller supports interaction-aware objective terms in code, but those
terms are not active in the formal evidence below.

## Evidence inventory

| evidence | what it established | canonical location | key integrity fingerprint |
|---|---|---|---|
| Registered adaptive A/B | Causal trusted adaptation improved tracking RMSE 6.85% and torque prediction 10.30%; cuff interaction did not materially improve. | `results/robustness/adaptive_ab/` | comparison JSON `870d546a...a6b3`; prior/adaptive trace `2ef8e9b9...81b2` / `7dd4da7f...55c70` |
| Realtime replay | Batched MPC 9.422 ms mean and full cycle 16.524 ms mean; >30 Hz supported on the audited desktop replay. | `results/robustness/realtime_replay/` | optimized timing `3ed2fc44...a97` |
| Patient/model mismatch | 13/13 promotion; tracking improved 13/13, prediction 9/13; 10/13 pairs completed, three shared late-qualification incompletion; no recorded safety event. | `results/robustness/patient_mismatch/` | config `a51d3cb0...129b`; aggregate `fde83874...e4f` |
| Nominal sensor decomposition | For seed 44104, systematic bias+drift—not ideal or noise-only—produced measured-domain trusted compensation and clean-oracle degradation. | `results/robustness/sensor_robustness/nominal_decomposition/` | aggregate `77c281cb...b924`; manifest `a165ae7b...0739` |
| Nominal sensor multiseed | Promotion 0/5 ideal, 2/5 noise-only, 5/5 bias+drift; all seven promoted nominal cases improved measured loss while degrading clean-oracle prediction. | `results/robustness/sensor_robustness/nominal_multiseed/` | aggregate `01143a08...29b`; manifest `d4dd2cb7...1e01` |
| Trajectory excitation | 5/6 promotion and RMSE benefit; full rank alone was insufficient; poor conditioning delayed usefulness; one shared force-gate negative case retained. | `results/robustness/trajectory_excitation/formal/` and `results/robustness/trajectory_excitation/summary/` | trajectory config `3024919e...c14`; offline audit `46e78190...458`; aggregate `27f031cc...90b` |
| Crossed patient × trajectory × seed replication | 18/18 promotion, completion, tracking improvement, and prediction improvement; no recorded safety event; H1/H2/H5 supported, H3/H4 conditional. | `results/robustness/crossed_replication/formal/` and `results/robustness/crossed_replication/summary/` | matrix `00019282...c81`; final aggregate `14f5ffb9...e922` |

Full SHA-256 values:

```text
00019282e188a1dca8d182b15ad9dd74d44c33312be5ad88f2f2c73efe1bbc81  configs/stage4_crossed_excitation_replication.json
a51d3cb086ebeb21ea01b59c7cb6d7cb8a422fa3e9bab0028d84002cf2ed129b  configs/stage4_patient_mismatch_cases.json
3024919e822297af06f01afa0a775f1453fe08abc0ed12cc313339811706ac14  configs/stage4_trajectory_excitation_suite.json
fde838741f23db59bd749ee3f85c59e3a230affd743bfa214a86bfc3bca88e4f  results/robustness/patient_mismatch/aggregate_summary.json
77c281cbf84a9b78b3a945a5033ad5e56281610df1d76919b7ba01a5c368b924  results/robustness/sensor_robustness/nominal_decomposition/aggregate_summary.json
01143a08e8793581b06241460e8b8929edb465d4063c7947c6fe3d6eed13b5c8  results/robustness/sensor_robustness/nominal_multiseed/aggregate_summary.json
27f031ccba4099f387ee449669686e9b1148181eb4798b91fe610e2f7c44190b  results/robustness/trajectory_excitation/summary/aggregate_summary.json
14f5ffb94a4d261eade3601f661d46effa910bbbc2c53e7834a27ff85888e922  results/robustness/crossed_replication/summary/aggregate_summary.json
```

Per-artifact hashes for the large formal matrices are embedded in their
aggregate summaries. The final crossed summary re-verifies both read-only
bridge pairs against their preregistered hashes.

## Negative and mixed findings that must remain visible

- Adaptation did not consistently reduce force, cuff moment, or the cylindrical
  surface proxy in the registered A/B or later suites.
- In the patient suite, torque prediction worsened in 4/13 cases even though
  tracking RMSE improved in all 13; three pairs shared incomplete progress due
  to late first qualification and conservative pacing.
- In the nominal multiseed suite, every trusted compensation moved away from
  the exact clean nominal dynamics; one bias+drift seed slightly worsened
  tracking RMSE.
- In the six-trajectory suite, the knee-dominant pair hit the same force gate
  before candidate formation, two completed cases worsened maximum error, and
  the two-cycle case showed severe practical conditioning and bound pressure.
- In the crossed suite, two cases improved RMSE while worsening maximum error;
  patient mismatch magnitude did not monotonically order tracking benefit.
- Bound pressure is common. It limits physical interpretation of beta and is
  not, by itself, proof of a trust or controller failure.

## Evidence boundary

The listed results qualify the controller only for the recorded simulation
models, configurations, and deterministic measurement realizations. They do
not establish:

- physical identification of anatomy or patient parameters;
- tissue pressure, comfort, injury, or clinical safety;
- CR12 compatibility, actuator authority, communications, or timing;
- target-hardware hard-realtime deadlines;
- population-level efficacy, unrestricted generalization, certification, or
  production readiness.

The UR10e is a surrogate. The cylindrical surface-load value is a mathematical
minimum-norm proxy. No clinical claim is made.

## Reproduction and regeneration

Run from `stages/stage4_adaptive_control`. Formal experiments are reserved for the user
and must target a new directory.

```bash
# Original paired A/B
PYTHONPATH=src conda run -n mpc_learn python \
  scripts/run_stage4_single_challenger_closed_loop_ab.py \
  --output-dir results/stage4_single_challenger_closed_loop_ab_reproduction

# One patient-mismatch case (repeat for each preregistered case id)
PYTHONPATH=src conda run -n mpc_learn python \
  scripts/run_stage4_patient_mismatch_robustness.py \
  --case-config configs/stage4_patient_mismatch_cases.json \
  --case-id <preregistered-case-id> \
  --output-dir results/stage4_patient_mismatch_reproduction

# One trajectory case (repeat for each preregistered trajectory id)
PYTHONPATH=src conda run -n mpc_learn python \
  scripts/run_stage4_trajectory_excitation_generalization.py \
  --trajectory-config configs/stage4_trajectory_excitation_suite.json \
  --trajectory-id <preregistered-trajectory-id> \
  --output-dir results/stage4_trajectory_excitation_reproduction

# One crossed case (repeat for each preregistered case id)
PYTHONPATH=src conda run -n mpc_learn python \
  scripts/run_stage4_crossed_excitation_replication.py \
  --matrix-config configs/stage4_crossed_excitation_replication.json \
  --case-id <preregistered-case-id> \
  --output-dir results/stage4_crossed_excitation_replication_reproduction
```

Use the matching `summarize_stage4_*.py` script to regenerate a summary into a
new output directory. The nominal sensor commands and exact flags are frozen in
`STAGE4_NOMINAL_SENSOR_DECOMPOSITION_SPEC.md` and
`STAGE4_NOMINAL_SENSOR_MULTISEED_SPEC.md`. Realtime replay uses
`scripts/profile_stage4_realtime.py` with the canonical trusted-adaptive trace;
see `CURRENT_STATE.md` at tag `stage4-baseline-v1` for the exact scalar and
batched benchmark command.

## Next scientific boundary

Professor-facing PD, PD+feedforward, fixed-model MPC, and adaptive-MPC
comparisons plus GIF/video visualization belong on a new branch under a new
approved Experiment Spec. Optional out-of-family model-inadequacy work must
vary one unsupported mechanism at a time with this controller frozen. Neither
activity may overwrite or silently relabel this evidence.
