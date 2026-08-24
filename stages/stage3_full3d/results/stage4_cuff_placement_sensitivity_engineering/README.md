# Stage 4 effective cuff-location sensitivity

Three engineering rollouts share Architecture A, `noise_200hz`, the frozen
Stage-4 23 s trajectory, perturbed Human geometry/dynamics other than `sc`, and
the same nominal population prior. Only the plant's true effective knee-to-cuff
distance changes by -20/0/+20 mm; it is not revealed to the estimator.

Command:

```bash
PYTHONPATH=src conda run -n mpc_learn python scripts/run_stage4_cuff_placement_sensitivity.py \
  --output-dir results/stage4_cuff_placement_sensitivity_engineering --case all
```

The collision-disabled 80 mm cylinder is visual only. The current mechanics are
a single six-constraint weld at the `sleeve_attach_site` placed at `sc`. A real
sleeve-length question requires a later finite-length distributed/compliant
contact, strap, or pressure model. Traces are retained locally and ignored by
Git; JSON and Markdown are the concise evidence.
