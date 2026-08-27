# adaptive-traction-mpc

This repository keeps research phases as independent stage snapshots:

- [`stages/stage1/`](stages/stage1/): single-link Spring2D fixed/adaptive MPC,
  estimation, and identification research.
- [`stages/stage2_linkage/`](stages/stage2_linkage/): Human V2 rigid-cuff
  MuJoCo linkage baseline and fixed-model mismatch evaluation.
- [`stages/stage3_full3d/`](stages/stage3_full3d/): torque-actuated 3D UR10e
  surrogate, Human V2 rigid cuff, and the current Stage-4 adaptive controller.

Each stage is an independent package and should be installed and executed from
its own directory. Do not combine stage Python packages or retroactively modify
frozen Stage 1-3 scientific code.

## Current Stage-4 baseline

The current checkpoint combines the frozen 1:1 cuff-aware allocator, integral
11-base dynamics estimator, hierarchical single-incumbent/challenger trust,
confidence pacing, and the original 32-candidate CEM MPC scientific definition.
The default batched MPC implementation is regression-equivalent to the retained
scalar reference implementation.

The formal registered simulation showed improved tracking and generalized-
torque prediction after trusted adaptation, but no meaningful cuff-interaction
reduction. Desktop replay timing supports at least 30 Hz and observed more than
50 Hz; this is not a hard-realtime hardware, clinical, or production claim.

See the central repository entry point for the checkpoint manifest,
metrics, evidence status, limitations, and reproduction commands:

- [`stages/stage3_full3d/docs/research/CURRENT_STATE.md`](stages/stage3_full3d/docs/research/CURRENT_STATE.md)

The next planned scientific question is robustness to patient/model mismatch.
