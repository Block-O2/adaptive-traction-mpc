# Frozen 1 ms compliant qualification: preregistration preflight

Branch: `codex/interface-phase3a-de23ea3`; current commit: `99169491ea1336d6af74e3b63318afba18c1e881`.
No new simulation, source port, controller edit, parameter change, timestep change, or commit was made for this request. This file records the evidence gap before selecting an acceptance rule or viewing new outcomes.

## Qualification status

NOT EVALUATED. A numerical PASS or FAIL cannot be established from the available matched-reference evidence. This is not a simulated failure and not evidence of 1 ms instability.

## Reference mismatch

| Contract | Retained Phase-2 reference | Requested new run |
|---|---|---|
| Motion | 1 mm world-x robot target ramp over 0.1 s | Human 40/40 outbound, hold, return |
| Reference duration | 0.3 s diagnostic | 14.106060606060604 s phase duration |
| Scenario | Human-bed contact retained | suspended_high_rom |
| Controller | Small robot Cartesian PD diagnostic; no Human-space MPC | Frozen de23ea3 MPC, executable command, Safety Filter, BRAKE, Unified Reference Manager |
| Numerical comparison available | Same diagnostic at 1, 0.5 and 0.25 ms | No compliant 40/40 reference at 0.25 ms in the registered evidence |

The shared candidate Kt=500 N/m, Dt=35.63902676526988 Ns/m, Kr=20 Nm/rad, Dr=1 Nms/rad does not make these different driven systems timestep-comparable. Interpolating, truncating or time-normalizing unmatched trajectories would confound numerical error with different loads, motion, controller and contact behavior.

## Existing short-diagnostic evidence only (not a new 40/40 result)

| Quantity | Retained 1 ms | Retained 0.25 ms |
|---|---:|---:|
| Physical force peak (N) | 16.6762976 | 16.4725301 |
| Human-side moment peak (Nm) | 1.43129582 | 1.40364444 |
| Translation deformation peak (mm) | 9.86892021 | 9.80013105 |
| Stored energy peak (J) | 0.0496342666 | 0.0495929235 |
| Cumulative damping dissipation (J) | 0.128471021 | 0.126164815 |
| Normalized max energy residual (%) | 0.586925873 | 0.146966039 |

Both retained short diagnostics finished with finite samples and no MuJoCo warnings per the Phase-2 report. This does not certify the requested suspended MPC trajectory.

| Diagnostic waveform | 1 ms vs 0.25 ms relative Linf (%) |
|---|---:|
| force | 7.423841 |
| torque | 7.023642 |
| displacement | 2.164194 |
| velocity | 9.671318 |
| spring_energy | 1.971260 |
| dissipated_energy | 2.232904 |

## Missing preregistered decision rules

The Phase-2 registration explicitly defines descriptive engineering stabilization, with no automatic scientific PASS/FAIL classifier. It provides comparison formulas but no accepted bounds for waveform errors, scalar convergence, discrete energy residuals, or full-trajectory deformation. Its observed 2.25% scale is not a preregistered acceptance threshold.
The existing deterministic tolerance rtol=0, atol=1e-12 can be retained for two identical 1 ms repeats. It cannot serve as the convergence tolerance between different timesteps. Deterministic repeatability also requires at least two compliant 40/40 executions (the same trajectory, no other endpoint).

## Scope decision needed before execution

A valid convergence gate needs a matched compliant 40/40 numerical reference at 0.25 ms with the same de23ea3 contract apart from the expressly declared refinement timestep, or an already existing artifact proving that exact contract. Generating that reference requires an explicit exception to the current instruction to run only at frozen 1 ms; none was inferred.
Before new outcomes are observed, a qualification spec must also freeze the waveform/scalar error limits, energy-residual tolerance and the meaning of bounded deformation (numerical boundedness versus a physical allowable-deformation limit). No physical or clinical deformation threshold should be invented.
Until those points are approved, new compliant 40/40 executions are NOT_RUN; task/force classification, full-trajectory stability and numerical qualification remain unavailable. No 40/80, 90/120, tuning, or rigid-vs-soft campaign is admitted by this preflight.

## Checks and file changes

Read-only commands: git status --short; git branch --show-current; git rev-parse HEAD; targeted rg/cat/head reads; Python CSV extraction. No simulator or unit tests were run. The initial branch was clean. The sole added file is this report; it is intentionally uncommitted.

## Evidence files and hashes

- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-spring-damper-interface-v1/stages/stage3_full3d/configs/interface_qualification_phase2_v1.json`
  SHA256: `7624b9fc56cbe429e1592881e962ffc3e1c4545ca8681bfb66510ccd7c143284`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-spring-damper-interface-v1/stages/stage3_full3d/configs/interface_mechanics_smoke_v1.json`
  SHA256: `eaa1006f41049e1779ad43aab3aa9f8d286a3bb5ef9a0158f269025968a36470`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-spring-damper-interface-v1/stages/stage3_full3d/docs/INTERFACE_PHASE2_REPORT.md`
  SHA256: `bbfa4a2616f0aad4fedcf197353b13880c3ba8d0dcb8086e036abce4f64c7446`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-spring-damper-interface-v1/stages/stage3_full3d/docs/interface_phase2_evidence/all_cases.csv`
  SHA256: `fdffa27fdafc60ef77b8d17cf9db5da8622e4a955df30d52f36925d010f2695b`
- `/Users/hankli/Desktop/coding/adaptive-traction-mpc-spring-damper-interface-v1/stages/stage3_full3d/docs/interface_phase2_evidence/waveform_and_scalar_convergence.csv`
  SHA256: `4302393c73cd153145deab0e61258b4d93592e42d3983d2064e6270209d0a2f3`
