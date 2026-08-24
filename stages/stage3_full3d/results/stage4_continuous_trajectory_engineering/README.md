# Stage 4 continuous teaching trajectory

One engineering rollout of Architecture A on the registered perturbed Human
with `noise_200hz` and no delay. Only the teaching reference differs from the
validated Stage-4 run. Its internal hip-/knee-dominant knots are C2 spline
pass-through points, not stops; only the initial, high-flexion, and final
postures are held.

Command:

```bash
PYTHONPATH=src conda run -n mpc_learn python scripts/run_stage4_continuous_trajectory.py \
  --output-dir results/stage4_continuous_trajectory_engineering
```

The run completed 23 s with no ROM, force-gate, torque-saturation, unintended
collision, MPC, or MuJoCo solver event. The local trace is ignored by Git; the
JSON and Markdown summaries are the concise evidence.
