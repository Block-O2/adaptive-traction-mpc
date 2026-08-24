# Stage 6b Safety Filter Diagnosis Report

## Scope
- Old safety filter behavior was kept available as `one_step_projection`.
- New optional mode: `one_step_projection_task_aware`.
- Only the requested four runs were executed: UKF-bias clean/noise_bias with old and task-aware filters.
- Spring2D dynamics, CEM, UKF-bias, Windowed NLS identifier, MPC cost, base constraints, physical parameters, gravity, max_time, and noise/bias settings were unchanged.
- No post-result tuning was performed.

## Commands run
- `python3 -m compileall src scripts`
- `conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py`
- `conda run -n mpc_learn python scripts/run_spring2d_safety_filter_stage6b_diagnosis.py`

Run note: the first Stage 6b script attempt completed the four closed-loop runs but failed while writing `stage6b_summary.csv` because an internal diagnostic field was not listed in the CSV fieldnames. The script was fixed without changing experimental settings, then rerun with the same four requested configurations.

## Sign-convention probe
```text
Stage 6b sign-convention probe
Action probe: F_tan = +/-1.0, F_rad = 0.0
Rollouts use the existing Spring2D step_dynamics / environment step.

zero_F_tan:
  MPC rollout: theta_next-theta=-0.00209268754, omega_next-omega=-0.416932457, contact_y_delta=-0.000652587522
  safety-filter rollout: theta_next-theta=-0.00209268754, omega_next-omega=-0.416932457, contact_y_delta=-0.000652587522
  environment step: theta_next-theta=-0.0020955891, omega_next-omega=-0.417801482, contact_y_delta=-0.000653522019

positive_F_tan:
  MPC rollout: theta_next-theta=-0.00168467812, omega_next-omega=-0.335750359, contact_y_delta=-0.000526941195
  safety-filter rollout: theta_next-theta=-0.00168467812, omega_next-omega=-0.335750359, contact_y_delta=-0.000526941195
  environment step: theta_next-theta=-0.00177224679, omega_next-omega=-0.353430446, contact_y_delta=-0.000553914189

negative_F_tan:
  MPC rollout: theta_next-theta=-0.00250064655, omega_next-omega=-0.498095434, contact_y_delta=-0.000778234293
  safety-filter rollout: theta_next-theta=-0.00250064655, omega_next-omega=-0.498095434, contact_y_delta=-0.000778234293
  environment step: theta_next-theta=-0.00241889992, omega_next-omega=-0.482160615, contact_y_delta=-0.000753130043

mpc_next response relative to zero action:
  positive_F_tan omega response=0.0811820978
  negative_F_tan omega response=-0.0811629768
safety_next response relative to zero action:
  positive_F_tan omega response=0.0811820978
  negative_F_tan omega response=-0.0811629768
env_next response relative to zero action:
  positive_F_tan omega response=0.0643710355
  negative_F_tan omega response=-0.064359133
Sign mismatch detected relative to zero-action response: False
```

## Summary
| condition | filter | target | final theta deg | T_reach | omega viol | alpha viol | max omega sev | max alpha sev | active | feasible cand | failed | mean delta | max delta | sign flips | early flips | mean norm alpha | mean norm omega | pred/true alpha err | runtime |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clean | one_step_projection | False | 40.833 | nan | 0 | 34 | 0.000 | 6.791 | 801 | 774 | 27 | 1.091 | 3.929 | 0 | 0 | 0.014 | 0.000 | 0.157 | 127.228 |
| clean | one_step_projection_task_aware | False | 40.725 | nan | 0 | 37 | 0.000 | 6.791 | 801 | 774 | 27 | 1.114 | 3.929 | 0 | 0 | 0.014 | 0.000 | 0.158 | 127.398 |
| noise_bias | one_step_projection | False | 46.867 | nan | 0 | 124 | 0.000 | 9.875 | 801 | 683 | 118 | 1.933 | 7.855 | 0 | 0 | 0.070 | 0.000 | 0.206 | 124.317 |
| noise_bias | one_step_projection_task_aware | False | 41.826 | nan | 0 | 163 | 0.000 | 6.529 | 801 | 646 | 155 | 2.543 | 8.249 | 0 | 0 | 0.063 | 0.000 | 0.213 | 121.609 |

## clean
- Early F_tan sign flips: old=0, task-aware=0.
- Total F_tan sign flips: old=0, task-aware=0.
- Target reaching: old=False (40.833 deg), task-aware=False (40.725 deg).
- Alpha violations: old=34, task-aware=37; max severity old=6.791, task-aware=6.791.
- Omega violations: old=0, task-aware=0; max severity old=0.000, task-aware=0.000.
- Mean normalized selected alpha violation: old=0.014, task-aware=0.014.
- Mean normalized selected omega violation: old=0.000, task-aware=0.000.

## noise_bias
- Early F_tan sign flips: old=0, task-aware=0.
- Total F_tan sign flips: old=0, task-aware=0.
- Target reaching: old=False (46.867 deg), task-aware=False (41.826 deg).
- Alpha violations: old=124, task-aware=163; max severity old=9.875, task-aware=6.529.
- Omega violations: old=0, task-aware=0; max severity old=0.000, task-aware=0.000.
- Mean normalized selected alpha violation: old=0.070, task-aware=0.063.
- Mean normalized selected omega violation: old=0.000, task-aware=0.000.

## Required answers
1. Does the filter flip F_tan in the early steps?
- The early-step CSVs record this explicitly. Across the four requested runs, early F_tan sign flips over the first 50 active steps totaled 0.

2. Does early F_tan sign flip correlate with motion toward negative y or away from target?
- Use the early-step CSVs and figures to inspect this directly. If early flips are zero or rare, the observed early poor motion is not primarily explained by selected-action F_tan sign reversal.

3. Is positive F_tan sign convention consistent across MPC rollout, safety-filter rollout, and environment step?
- The sign probe reports no sign mismatch relative to the zero-action response: positive F_tan increases omega relative to zero action and negative F_tan decreases it in MPC rollout, safety-filter rollout, and environment step. Absolute theta/omega still move negative at the initial state because gravity/base terms dominate the one-step motion.

4. Do predicted omega/alpha match true executed omega/alpha closely?
- The report table includes mean absolute predicted-vs-true alpha error. Differences remain nonzero because the filter predicts from filtered state and adaptive model parameters while execution uses the true simulator state and parameters.

5. Is alpha violation dominating the filter decision?
- The selected-action normalized alpha component is much larger than normalized omega in the problematic runs, so alpha remains the dominant one-step violation term.

6. Does normalized violation scoring improve behavior?
- Mixed result. It changes the selected candidates and action distortion, but it does not by itself solve target reaching or alpha feasibility in the requested clean/noise_bias runs.

7. Does component-wise F_tan scaling reduce unnecessary action distortion?
- The new candidate set was used: `F_tan_scale_*` was selected 72 times in clean and 354 times in noise_bias. It did not reduce action distortion in this run: mean action delta increased in both requested conditions, and target reaching did not improve.

8. Does soft anti-reversal improve target reaching without increasing omega/alpha violations?
- In these runs there were no early sign reversals to suppress, so the anti-reversal preference was not the main limiting factor. Target reaching and violation counts should be judged from the table.

9. Recommended next step
- Based on the mixed Stage 6b results, the next technical step should be improving the candidate set or moving toward a multi-step safety filter. Tuning `alpha_max`/`omega_max` would change the task constraints and should not be done without explicit approval. MPC constraint tightening is also a candidate, but it changes planning behavior rather than just execution filtering.

This is not a formal safety guarantee. Bad or mixed results are preserved as experimental results.
