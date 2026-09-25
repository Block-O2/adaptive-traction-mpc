# DEV-C matched-state physical results (development, not fresh qualification)

Each branch starts from the same preserved DEV-B preactivation full MuJoCo,
robot, interface, estimator, reference, controller, RNG, and timestamp state.
`run_dev_c_matched_v1.py` verifies the checkpoint integration-state hash.
The DEV-C-off direct branch reproduces DEV-B's first 40 robot commands with
maximum difference **0.0 Nm** in all four cases. The production `_execute_interval`
then runs 60 real 5 ms CR12–cuff–Human commands; physics is logged at 0.25 ms
boundaries. Simulation truth is evaluated/logged, not passed to the controller.

The four frozen output gates from `CONTINUITY_FREEZE.md` are maxima over **all**
adjacent 5 ms command pairs, including the saved predecessor to first new
command: Human action ≤1.30 Nm, desired total cuff force ≤2.69 N, desired
total moment ≤0.58 Nm, and CR12 torque ≤2.06 Nm. The predecessor wrench is
the previous desired `allocated_wrench_world`, not the measured physical
cuff wrench; previous robot command is `applied_robot_tau_nm`.

| Consumed development case | T (s) | CR12 max step direct→DEV-C (Nm) | Human action max step direct→DEV-C (Nm) | Early 200 ms Human componentwise |q̈| peak direct→DEV-C (rad/s²) | New model fully realized? |
|---|---:|---:|---:|---:|---|
| near upper current ROM | 0.2490 | 34.7804→1.1232 | 18.2380→0.6166 | 9.9182→0.5322 | `belief_310` |
| middle | 0.0721 | 7.6546→1.7576 | 5.2796→0.5676 | 6.9629→1.5726 | `belief_351` |
| ordinary | 0.0500 | 2.2084→1.4684 | 1.1109→0.2506 | 3.0495→1.5175 | `belief_351` |
| nominal reference | no transfer needed | 0.00463→0.00463 | 0.00137→0.00137 | 0.02957→0.02957 | `belief_322` |

All four DEV-C branches pass every frozen gate. Measured DEV-C desired force
max steps are 1.5022, 2.1859, 1.9994, and 0.00785 N respectively; moment
max steps are 0.2198, 0.2292, 0.1220, and 0.000439 Nm. The new model becomes
physically **FULLY_REALIZED** only after unchanged TRACK with unsaturated robot
torque; the state merely reaching `alpha=1` is not counted.

The physical cuff-force peak over the first 200 ms was near-upper
90.585→77.778 N, middle 79.693→79.693 N, ordinary 100.069→100.440 N
(slightly worse), and nominal 79.309→79.309 N. The near-upper branch still
shows the separate simulated bed–thigh normal reaction peak **33,353.295 N**;
contact is present at this checkpoint and is not removed or attributed to
the model-transfer defect. It is a MuJoCo contact result, not a validated
real-human load.

The failed first local design is retained in `matched_v1/`: middle exceeded
the frozen first-boundary action/force/torque gates. `matched_v2/` repaired
that first-edge error with the verified prior-action anchor but used a fixed
0.25 s duration. `matched_v3/` adds only the action-gap-scaled duration; it
is the v2-config local evidence. The later v3 output-envelope revision also
passed the same four checkpoints (`matched_v4/`), but its representative
full-session recovery-start failure means these selected local cases do not
establish global control-output continuity. `matched_summary_v1.json` is an obsolete
analysis draft with incorrect desired-wrench predecessor and acceleration
norm conventions. The corrected authoritative analyses are
`matched_summary_matched_v2.json` and
`matched_summary_matched_v3_with_moment.json` (the latter adds complete
force/moment plots without overwriting earlier figures).

Plots (full source traces and figures in the versioned result namespace):

- [strongest activation plot](../../../results/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1/plots_matched_v3_with_moment/balanced_near_upper_current_rom_r01.png)
- [middle activation plot](../../../results/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1/plots_matched_v3_with_moment/balanced_middle_r01.png)
- [ordinary activation plot](../../../results/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1/plots_matched_v3_with_moment/balanced_ordinary_r01.png)
- [nominal activation plot](../../../results/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1/plots_matched_v3_with_moment/development_nominal.png)
