# Phase 3A rigid reproduction gate and timestep contract stop

> [!IMPORTANT]
> **PRE-CORRECTION / RETIRED DIAGNOSTIC EVIDENCE**
>
> This report predates the corrected low-latency robot velocity-feedback
> measurement path and is retained only as diagnostic provenance. Current
> authoritative conclusions are in [CURRENT_STATE](../../../docs/research/CURRENT_STATE.md)
> and the [corrected High-ROM evidence](../../summaries/phase3a_corrected_high_rom/README.md).
> Commands and paths below are frozen historical provenance; they are retired,
> non-current, and must not be treated as executable reproduction instructions.

Experiment baseline: `de23ea3cdf9f0fb078496ba5ba4abb6a205ad955`. Interface donor (not imported): `3ce0129587bae3b9d13c0f581e0e4d8af5779e3a`.
Branch: `codex/interface-phase3a-de23ea3`. This worktree was created directly from the baseline; the donor and original worktrees were preserved.
Evidence: user-authorized engineering reproduction, not formal scientific evidence or clinical validation.

## Observed reproduction

The single new rigid 40/40 gate passed. Both historical repeats were compared separately.
All 66 non-host-timer trace arrays match each historical repeat; maximum numeric absolute difference is 0 with registered rtol=0 and atol=1e-12. Labels and model fingerprints match. All 11 retained primary metric differences are 0.
The comparison covers physical Human/robot states, force/moment, robot torque, desired action, estimated state, measured wrench, allocation, reference progression, confidence traces and Safety Filter outputs.
The only excluded trace arrays are four host compute-time arrays. Host timing metrics remain saved and are not deterministic trajectory acceptance conditions.

| Metric | Historical rigid repeat 1 | New rigid |
|---|---:|---:|
| Task classification | COMPLETE | COMPLETE |
| Physical-force classification | STRICT_PASS | STRICT_PASS |
| Tracking RMSE (deg) | 0.1624167776334942 | 0.1624167776334942 |
| Endpoint error (deg) | 0.0005109435141079643 | 0.0005109435141079643 |
| Return error (deg) | 0.011742077948005303 | 0.011742077948005303 |
| Maximum tracking error (deg) | 0.41986350228396935 | 0.41986350228396935 |
| Physical force peak (N) | 117.45634792589532 | 117.45634792589532 |
| Physical moment peak (Nm) | 17.693916528637978 | 17.693916528637978 |
| Command force peak (N) | 121.09992355113886 | 121.09992355113886 |
| BRAKE entries | 0 | 0 |
| NO_SAFE_ACTION count | 0 | 0 |

Completion tolerance remains 0.06896926724078867 deg; endpoint and return both meet it.
Reference duration remains 14.106060606060604 s; simulation finished at 14.10699999999762 s on the historical time grid.
Physical force never exceeded 200 N: exceedance time, contiguous duration and excess impulse are zero. No MuJoCo warning, nonfinite trajectory, ROM event or unintended contact was observed. All 2823 model-lock assertions passed; Safety Filter left all 2822 commands unchanged.

Historical media note: `rigid_reproduction.png` was externalized during
repository closeout. Its archived path and SHA-256 remain in
[`EXTERNAL_RAW_ARCHIVE_SHA256SUMS`](../../summaries/phase3a_corrected_high_rom/EXTERNAL_RAW_ARCHIVE_SHA256SUMS).

## Required stop before compliant execution

The user now freezes all numerical settings to de23ea3. That baseline uses physics dt=1 ms, implicitfast, the original solver and five physics steps per 5 ms low-level update.
The sole Phase-2 registered soft candidate is Kt=500 N/m, Dt=35.63902676526988 Ns/m, Kr=20 Nm/rad, Dr=1 Nms/rad, qualified only at dt=0.25 ms. The donor report is identified and excerpted in phase2_timestep_evidence.txt.
Changing only the compliant arm to 0.25 ms would violate matching. Changing both arms to 0.25 ms would depart from the newly frozen historical numerical baseline. Using the soft candidate at 1 ms would exceed its retained numerical qualification and earlier explicit registration. None was done.
**This is a registration/qualification conflict, not a demonstrated instability of the soft interface at 1 ms, and not a rigid reproduction failure.** No soft trajectory or new qualification diagnostic was run. The interface was not ported into this baseline yet.

| Endpoint | Rigid | Soft |
|---|---|---|
| 40/40 | Reproduction gate COMPLETE / STRICT_PASS | NOT_RUN: timestep qualification conflict |
| 40/80 | NOT_RUN | NOT_RUN |
| 90/120 | NOT_RUN | NOT_RUN |

DIRECTLY OBSERVED: baseline rigid behavior and physical/control traces reproduced exactly.
SUPPORTED: this checkout and environment preserve the tested rigid contract.
UNRESOLVED: whether the registered compliant mechanics are numerically credible at frozen 1 ms in the suspended scenario.
NOT SUPPORTED: any compliant force benefit, deformation/tracking/proxy tradeoff, ROM enlargement, or A/B outcome. The original A-D soft-behavior alternatives cannot be adjudicated without a soft run.

## Scope and reproducibility

Scientific variables changed: none. Scenario, contact domain, reference timing, seeds, population prior, geometry, allocator, Human, robot, 140 mm adapter, MPC, executable-command path, Reference Manager, safety contracts, integrator, timestep, solver and gains are unchanged.
New files consist only of the two gate/report scripts and this new result directory. No historical source, config or result was edited. No simulator exception occurred; no recovery or parameter adjustment was needed.
The inherited run manifest contains the baseline runner generic command string. The actual invocation and environment are preserved in registration.json and below; the generic string is not the executed shell command.

Actual working directory:
`/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a`

Single authorized simulation command:
```sh
/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/run_stage4_phase3a_rigid_gate.py --output stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1
```

Read-only analysis of existing traces plus report/plot generation:
```sh
/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/summarize_stage4_phase3a_rigid_gate.py --input stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1
```

Checks: script compilation and seven synthetic gate-comparator checks passed before execution (identity, above-tolerance perturbation, missing field, nonfinite value, changed mode, changed shape, host-timer exclusion). Post-run validation checks source/config/model and historical artifact hashes, finite numeric NPZ arrays, monotonic physics time and both historical deterministic comparisons.
No full test suite or additional experiment was run. There is no admitted formal or compliant command for the user to run under the unresolved timestep contract.

## Exact added file inventory

- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/scripts/run_stage4_phase3a_rigid_gate.py`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/scripts/summarize_stage4_phase3a_rigid_gate.py`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/REPORT.md`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/SHA256SUMS`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/base_scan_spec.json`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/commissioning_spec_v2.json`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/gate_result.json`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/phase2_timestep_evidence.txt`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/registration.json`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/rigid_hip40_knee40/manifest.json`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/rigid_hip40_knee40/model_lock.json`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/rigid_hip40_knee40/model_lock_cycles.npz`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/rigid_hip40_knee40/raw_summary.json`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/rigid_hip40_knee40/trace.npz`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/rigid_reproduction.png`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/phase3a_rigid_gate_20260904_v1/validation.json`
