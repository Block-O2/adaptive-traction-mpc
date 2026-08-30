# Stage-4 Report-Validation Infrastructure

Status: v2 coupled-PD amendment implemented; the failed v1 formal gain
selection is preserved; formal v2 gain selection, scientific benchmark, demo
execution, and final rendering have not run.

This implementation consumes the frozen
[`STAGE4_REPORT_VALIDATION_SPEC.md`](STAGE4_REPORT_VALIDATION_SPEC.md) and
[`stage4_report_validation_matrix_v2_coupled_pd.json`](../../configs/stage4_report_validation_matrix_v2_coupled_pd.json).
The v1 matrix and failed formal evidence remain immutable. The amendment does
not modify the Stage-4 controller.

## Architecture

- `traction_mpc_stage4.report_validation` provides strict matrix/source-hash
  validation, the exact nine-point gain grid, deterministic mechanical-first
  gain selection, hashed gain locks, the read-only external phase clock,
  Human-space PD/PD+FF adapters, patient/trajectory resolution, provenance,
  overwrite protection, and structural smoke orchestration.
- `scripts/run_stage4_report_validation.py` exposes `gain-tuning`, `benchmark`,
  `demo`, the general duration-capped `smoke`, and the three-arm v2
  `gain-smoke` diagnostic.
- The existing `run_sensor_realism_case` continues to own the plant,
  measurement layers, geometry frontend, estimator/trust lifecycle, cuff
  allocator, safety gates, and robot low level. Only the injected Human-space
  controller law differs.
- `traction_mpc_stage4.report_validation_renderer` consumes saved traces and
  produces synchronized 2 x 2 GIF, still, and timeseries PNG/PDF outputs. MP4
  is exposed only when `imageio-ffmpeg` is available.

The renderer first attempts the existing MuJoCo fixed-camera framebuffer. In a
headless macOS session without a CoreGraphics connection, it uses a fixed
MuJoCo-FK schematic projection and records that backend in the render manifest.
The fallback still shows the robot, Human, cuff, actual/reference leg overlay,
controller metrics, and adaptive state; it is not mislabeled as a 3D render.

## Output and provenance contract

Every arm writes strict JSON summary and manifest plus a compressed NPZ trace.
The manifest records controller, applicable gain-lock hash, experiment gain
lock, patient, trajectory, sensor seed, external-clock hash, matrix hash,
controller fingerprint, frozen base tag/commit, evidence category, formal or
smoke status, common allocator/low-level path, and Git provenance.

Every arm creates fresh plant, estimator, controller, clock, and seeded
measurement layers. Output roots and arm directories refuse overwrite.

PD and PD+FF accept only the same constant nominal-inertia-derived coupled
torque-PD matrices and locked scales. PD/PD+FF/fixed MPC are
runtime-checked to retain the population-prior beta for the complete trace.
Adaptive promotions are runtime-checked against preceding applied
qualifications from the unchanged trust lifecycle.

## Structural smoke command

This command is non-scientific and capped at 0.5 s:

```bash
cd stages/stage4_adaptive_control
PYTHONPATH=src:. conda run -n mpc_learn python \
  scripts/run_stage4_report_validation.py \
  --matrix-config configs/stage4_report_validation_matrix.json \
  --phase smoke \
  --smoke-duration-s 0.1 \
  --output-dir <fresh-smoke-output>
```

It covers all four controllers on nominal high flexion and on the report-only
+3% geometry, hip-dominant case. It creates a clearly non-formal 1.0/1.0 smoke
gain artifact; that artifact cannot be accepted by benchmark or demo phases.

The amended gain-definition diagnostic is non-scientific and capped at 1.5 s:

```bash
PYTHONPATH=src:. conda run -n mpc_learn python \
  scripts/run_stage4_report_validation.py \
  --matrix-config configs/stage4_report_validation_matrix_v2_coupled_pd.json \
  --phase gain-smoke \
  --smoke-duration-s 1.5 \
  --output-dir <fresh-v2-gain-smoke-output>
```

## Formal commands reserved for the user

Run gain selection first. This executes exactly nine full 32 s nominal,
moderate-ROM PD rollouts and either writes the formal lock or stops with all
candidate outputs preserved.

```bash
cd stages/stage4_adaptive_control
PYTHONPATH=src:. conda run -n mpc_learn python \
  scripts/run_stage4_report_validation.py \
  --matrix-config configs/stage4_report_validation_matrix_v2_coupled_pd.json \
  --phase gain-tuning \
  --output-dir results/controller_validation/gain_selection
```

After reviewing the gain-selection artifact, the user may run the 16-arm
scientific benchmark:

```bash
PYTHONPATH=src:. conda run -n mpc_learn python \
  scripts/run_stage4_report_validation.py \
  --matrix-config configs/stage4_report_validation_matrix_v2_coupled_pd.json \
  --phase benchmark \
  --gain-lock results/controller_validation/gain_selection/frozen_pd_gains.json \
  --output-dir results/controller_validation/baseline_comparison
```

The eight new demo-only arms remain a separate user action:

```bash
PYTHONPATH=src:. conda run -n mpc_learn python \
  scripts/run_stage4_report_validation.py \
  --matrix-config configs/stage4_report_validation_matrix_v2_coupled_pd.json \
  --phase demo \
  --gain-lock results/controller_validation/gain_selection/frozen_pd_gains.json \
  --output-dir results/controller_validation/trajectory_generalization/demo_sources
```

Final rendering is also a separate action. For example, after the benchmark:

```bash
PYTHONPATH=src:. conda run -n mpc_learn python \
  scripts/render_stage4_report_validation.py \
  --matrix-config configs/stage4_report_validation_matrix_v2_coupled_pd.json \
  --case-dir results/controller_validation/baseline_comparison/nominal_reference__registered_high_flexion_23s \
  --output-dir results/media/professor_visualizations/nominal_high_flexion \
  --fps 8
```

Add `--mp4` only when the renderer manifest/environment reports
`mp4_dependency_available: true`.
