# Provenance-only 1D line-load command

This rank-5 collinear four-point decomposition is retained only as engineering
provenance.  The active follow-on finite-area formulation is the 4x4
cylindrical-surface audit under
`../stage4_rigid_cylindrical_surface_loads_engineering/`.  Do not promote this
line model or the rejected spring model to the active plant.

```bash
PYTHONPATH=src conda run -n mpc_learn python scripts/run_stage4_rigid_surface_loads.py \
  --output-dir results/stage4_rigid_surface_loads_engineering \
  --baseline-trace results/stage4_continuous_trajectory_engineering/continuous_perturbed_human_one_shot_trace.npz
```

This command reruns one unchanged rigid-weld trajectory, verifies it against the registered trace, then evaluates four cuff lengths without feeding local loads back to simulation, the estimator, or the controller.
