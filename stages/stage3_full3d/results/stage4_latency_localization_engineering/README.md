# Stage 4 latency localization

Engineering evidence only. Architecture A, `noise_200hz`, the frozen Stage-4
23 s trajectory, nominal effective cuff placement, and the registered perturbed
Human dynamics are shared. Only the routed 10 ms measurement delay differs.

Commands:

```bash
PYTHONPATH=src conda run -n mpc_learn python scripts/run_stage4_latency_localization.py \
  --output-dir results/stage4_latency_localization_engineering \
  --case all_uncompensated
PYTHONPATH=src conda run -n mpc_learn python scripts/run_stage4_latency_localization.py \
  --output-dir results/stage4_latency_localization_engineering \
  --case all_delay_low_level_extrapolated
```

Low-level feedback delay is the dominant failure source. The permitted minimal
constant-twist timestamp extrapolation did not restore completion and was not
tuned further. Traces are retained locally and ignored by Git; JSON and Markdown
are the concise evidence.
