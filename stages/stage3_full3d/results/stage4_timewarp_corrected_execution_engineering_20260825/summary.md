# Stage 4 split-confidence execution comparison

Engineering comparison only; estimator, MPC, plant, sensing, gains, and safety limits are shared.

| mode | termination | reference complete (s) | phase RMSE (deg) | peak force @ phase | peak moment @ phase | geometry trusted t/phase | dynamics trusted t/phase | safety events |
|---|---|---:|---:|---:|---:|---:|---:|---|
| fixed_speed | completed | 23.000 | 0.701 | 117.29 N @ 8.380 s | 27.10 Nm @ 8.025 s | 2.820/2.820 s | 4.320/4.320 s | {'force_gate_events': 0, 'rom_event_samples': 0, 'unintended_contact_pairs': [], 'mujoco_warning_counts': {}, 'mpc_solver_failures': 0} |
| adaptive_speed | completed | 26.850 | 0.568 | 117.66 N @ 8.380 s | 27.12 Nm @ 8.075 s | 5.680/2.840 s | 5.680/2.840 s | {'force_gate_events': 0, 'rom_event_samples': 0, 'unintended_contact_pairs': [], 'mujoco_warning_counts': {}, 'mpc_solver_failures': 0} |
