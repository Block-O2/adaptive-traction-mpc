# adaptive-traction-mpc

This repository keeps completed research phases as independent, frozen stage
snapshots:

- [`stages/stage1/`](stages/stage1/): single-link Spring2D fixed/adaptive MPC,
  estimation, and identification research.
- [`stages/stage2_linkage/`](stages/stage2_linkage/): Human V2 rigid-cuff
  MuJoCo linkage baseline and fixed-model mismatch evaluation.
- Stage 3 is planned but has not started. It will use a complete Menagerie
  six-DoF surrogate rather than reconstructing the CR12 CAD.

Stage 1 and Stage 2 each contain an independent package named `traction_mpc`.
They are not one combined install: create/use the selected stage's environment,
install that stage from its own directory, and run its commands from that stage
directory so imports and relative paths resolve to the intended frozen snapshot.

`third_party/mujoco_menagerie/` is intentionally retained unchanged for the
future Stage 3 robot selection.
