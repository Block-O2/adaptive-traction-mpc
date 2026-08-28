# Registered engineering command

```bash
PYTHONPATH=src conda run -n mpc_learn python scripts/run_stage4_rigid_cylindrical_surface_loads.py \
  --output-dir results/stage4_rigid_cylindrical_surface_loads_engineering \
  --baseline-trace results/stage4_continuous_trajectory_engineering/continuous_perturbed_human_one_shot_trace.npz
```

One unchanged rigid-weld rollout is compared with the registered trace. The four lengths are evaluation-only decompositions of that same resultant wrench.
