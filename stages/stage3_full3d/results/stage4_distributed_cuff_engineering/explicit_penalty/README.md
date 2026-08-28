# Explicit four-station distributed cuff diagnostic

Engineering evidence only.  All cases share the perturbed Human, continuous
23 s teaching reference, Architecture A, realistic 200 Hz noise, controller,
gains, estimator gates, ROM, 200 N force gate, and robot limits.  Only physical
cuff length changes; `sc` remains fixed.

Formulation:

- station offsets: `((i + 0.5)/4 - 0.5) Lc`, `i=0..3`;
- each station represents `Lc/4` of uniform axial surface support;
- `Ki = 10 MN/m^2 * Lc/4`;
- `Di = 1 kN s/m^2 * Lc/4`;
- force on shank: `fi = Ki (x_cuff_i - x_shank_i) + Di (v_cuff_i - v_shank_i)`;
- robot receives `-fi` at the corresponding rigid-cuff point;
- `F = sum(fi)` and `M = sum((r_i-r_c) cross fi)`;
- no station transmits a direct moment.

Command:

```bash
PYTHONPATH=src conda run -n mpc_learn python scripts/run_stage4_distributed_cuff.py \
  --output-dir results/stage4_distributed_cuff_engineering/explicit_penalty \
  --case all
```

The nominal 80 mm plant did not reproduce the single-weld run: it crossed the
physical 200 N force gate at 9 ms during the initial hold.  The 60/80/100/120 mm
diagnostic sweep showed the same startup-transient failure, so no mechanically
favorable length is selected.  No controller change, startup ramp, preload, or
per-length tuning was added.
