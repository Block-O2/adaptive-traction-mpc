# Stage 4 one-shot adaptive Human control closeout

## Frozen scope

Stage 4 starts from the nominal Human-V2 population prior and robot-known cuff
pose. It does not receive the simulated patient's true joint state, joint
centers, geometry, mass properties, or passive parameters. The online chain is:

```text
cuff pose/twist history
  -> accumulated planar geometry identification
  -> reconstructed cuff wrench by estimated virtual work
  -> accumulated 11-base-parameter dynamic identification
  -> constrained Human-space Adaptive MPC
  -> rigid-cuff allocation
  -> UR10e J^T torque execution
```

The original Stage-3C controller gains, Human ROM and soft limits, bed/contact
model, rigid cuff, robot limits, and 200 N translational force gate remain
unchanged. Logged interaction quantities are engineering metrics, not clinical
comfort or safety thresholds.

## Approved evidence

- Structural audit: `results/stage4_estimator_v2_observability/audit.json`.
- Cold-start checks and approved single run:
  `results/stage4_one_shot_adaptive_high_flexion/`.
- Presentation media: `results/final_presentation/stage4_one_shot_adaptive_high_flexion.gif`
  and `.mp4`.

The registered perturbed Human has height scale 1.06, mass scale 1.08,
stiffness scale 1.15, thigh/shank COM scales 1.04/0.96, cuff-center scale 0.94,
and rest offsets `[-2, +3] deg`. It is the only full high-flexion Stage-4 run.

Observed metrics from the preserved JSON/NPZ are:

- completed duration: `23.000000000005127 s`;
- tracking RMSE: hip `0.521242 deg`, knee `0.689320 deg`, combined `0.611087 deg`;
- peak translational cuff force: `117.345055 N`;
- peak robot torque-limit fraction: `0.459457`;
- geometry first accepted at `2.36 s`; dynamic base model first accepted at
  `8.86 s`;
- no force-gate, ROM, torque-saturation, robot joint-limit, unintended-contact,
  MPC-failure, or MuJoCo warning event.

The final dynamic candidate was rejected for a bound hit, so the controller
kept the preceding last-valid model as designed.

## Reproduction commands

Run from `stages/stage3_full3d/` in the recorded `mpc_learn` environment:

```bash
PYTHONPATH=src conda run -n mpc_learn pytest -q
PYTHONPATH=src conda run -n mpc_learn python scripts/run_stage4_estimator_v2_audit.py \
  --output-dir results/stage4_estimator_v2_observability
```

The expensive 23-second rollout is preserved rather than included in pytest.
Its approved result hashes are:

```text
c02e9a1b1de846328a23e4049e699db4c286617a8f7af703868e8ad3d6fcdebf  high_flexion_one_shot_adaptive.json
3822bd2dd9ee2018929fea857cbcd81f2f7e4897c7653563852250343c98aab4  high_flexion_one_shot_adaptive_trace.npz
52d526ab88a3db75ee6a65c1a05a64179b698c10aef36369a16cbe06be729d7b  audit.json
```

## Remaining blocker

This checkpoint does not validate real cuff force/torque bias, noise, latency,
timestamp alignment, or the CR12 torque interface. No real hardware command was
sent. Those measurement and execution boundaries must be validated before a
patient-connected migration.
