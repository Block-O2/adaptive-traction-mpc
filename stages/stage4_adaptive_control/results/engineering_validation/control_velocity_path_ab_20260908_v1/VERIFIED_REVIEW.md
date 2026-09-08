# Phase-3A robot control velocity path A/B verified review

Evidence category: exploratory diagnostic only. Formal task and force classifications are preserved.

Spec SHA-256: `7a283c9b573f8149b21bd4d1abbec89ddeb27f2abeaefe3b8f93154b96cace69`  
Implementation commit: `ce72ddfc8867f6fc021bdcdf6bbc22aa8c6d5dd0`

## 40/40

| metric | OLD processed-history velocity | NEW joint/Jacobian velocity |
|---|---:|---:|
| Formal task | COMPLETE | COMPLETE |
| Actual outbound / return | 100% / 100% | 100% / 100% |
| Tracking RMSE (deg) | 0.157621 | 0.157137 |
| Endpoint / return error (deg) | 0.000533 / 0.012788 | 0.014173 / 0.022757 |
| Velocity-feedback force RMS / peak (N) | 1.668 / 6.449 | 0.392 / 1.366 |
| Position-feedback force RMS / peak (N) | 1.212 / 3.031 | 1.120 / 2.540 |
| Human-level allocator force RMS / peak (N) | 99.023 / 119.249 | 99.022 / 119.030 |
| Nominal executable force RMS / peak (N) | 99.154 / 121.049 | 99.108 / 119.423 |
| Final command force RMS / peak (N) | 99.158 / 121.049 | 99.112 / 119.423 |
| Physical force RMS / peak (N) | 98.991 / 117.448 | 98.970 / 117.086 |
| Physical force slew RMS / peak (N/s) | 917.873 / 251692.008 | 869.317 / 252000.697 |
| Physical moment peak (Nm) | 17.691 | 17.641 |
| SAFE_FILTERED / FILTER_INFEASIBLE | 0 / 0 | 0 / 0 |
| BRAKE cycles / transitions | 0 / 0 | 0 / 0 |
| NO_SAFE_ACTION / MuJoCo warning | 0 / 0 | 0 / 0 |
| Force contract | STRICT_PASS | STRICT_PASS |

The NEW path preserves the easy baseline. Its velocity-feedback RMS and peak are 76.5% and 78.8% lower, while tracking RMSE changes by -0.3%. Endpoint and return errors are slightly larger but remain well inside the unchanged 0.068969 deg formal tolerance.

## 40/80

| metric | OLD processed-history velocity | NEW joint/Jacobian velocity |
|---|---:|---:|
| Formal task | SAFE_INCOMPLETE | COMPLETE |
| Actual reference outbound / return | 100% / 100% | 100% / 100% |
| Human physically reached / returned | yes / no | yes / yes |
| Tracking RMSE (deg) | 24.661855 | 0.080024 |
| Endpoint / return error (deg) | 0.016985 / 64.241169 | 0.000636 / 0.009260 |
| Velocity-feedback force RMS / peak (N) | 13.433 / 83.137 | 0.412 / 1.393 |
| Position-feedback force RMS / peak (N) | 5.437 / 36.309 | 1.208 / 2.893 |
| Human-level allocator force RMS / peak (N) | 105.231 / 157.820 | 101.408 / 122.845 |
| Nominal executable force RMS / peak (N) | 108.865 / 213.383 | 101.504 / 123.982 |
| Final command force RMS / peak (N) | 107.515 / 200.000 | 101.508 / 123.982 |
| Physical force RMS / peak (N) | 105.491 / 197.497 | 101.424 / 121.576 |
| Physical force slew RMS / peak (N/s) | 2343.993 / 251692.008 | 768.007 / 252000.697 |
| Physical moment peak (Nm) | 38.360 | 17.355 |
| SAFE_FILTERED / FILTER_INFEASIBLE | 1 / 1 | 0 / 0 |
| BRAKE cycles / transitions | 1786 / 1 | 0 / 0 |
| NO_SAFE_ACTION / MuJoCo warning | 0 / 0 | 0 / 0 |
| Force contract | STRICT_PASS | STRICT_PASS |

The OLD arm enters BRAKE at `t=11.935 s`; the reference later reaches 100% return progress, but the Human remains 64.241 deg from the initial posture. The NEW arm remains in TRACK for all 3812 control cycles and physically completes the round trip.

## OLD 40/80 boundary event

| quantity at t=11.935 s | value |
|---|---:|
| OLD Human q (deg) | [36.7197, 76.0063] |
| OLD Human dq (deg/s) | [-14.6394, -11.5911] |
| Target cuff velocity WORLD (m/s) | [0.032075, 0.000002, -0.003995] |
| Processed-history cuff velocity WORLD (m/s) | [-0.124572, 0.000094, -0.576794] |
| Joint/Jacobian cuff velocity WORLD (m/s) | [0.056207, 0.001221, -0.104468] |
| OLD velocity-feedback vector (N) | [21.9305, -0.0129, 80.1919], norm 83.1365 |
| Position-feedback vector (N) | [6.9599, 0.0277, 25.7952], norm 26.7176 |
| Rejected Human-level allocator force (N) | norm 143.2310 |
| Rejected nominal executable force (N) | [-81.5569, -0.0354, 197.1820], norm 213.3829 |
| OLD-minus-NEW velocity term (N) | [25.3090, 0.1578, 66.1257], norm 70.8038 |
| OLD-minus-NEW term projected on rejected-force direction (N) | 51.4318 |
| Same-state/action replace-only counterfactual (N) | [-106.8660, -0.1932, 131.0563], norm 169.1039 |
| Actual NEW nominal force at matched time (N) | 100.8495, SAFE_UNCHANGED |

The 169.104 N value is an offline algebraic counterfactual, not a new closed-loop outcome. It shows that changing only the velocity measurement at the OLD boundary state/action is sufficient to move the nominal executable force below the registered 200 N engineering target. The actual NEW rollout additionally follows a different, better-tracked state history by that time.

## Evidence checks

- All four runs used the same initial-state artifact SHA-256: `5d0521f8e01225b76bd209d8461c4bd50cf3d04bdae205af92a6cad538b78871`.
- All four per-cycle frozen model-lock assertions passed.
- All numeric trace arrays are finite; MuJoCo warning count, unintended contact count, robot joint-limit count, Human ROM event count, and NO_SAFE_ACTION count are zero.
- Both 40/40 and both 40/80 arms have complete saved control, mode, physics, command, model-lock, and summary evidence.
- The shared force-slew peak near 252 kN/s occurs at the common startup transient and is therefore not evidence that NEW worsens the return-boundary mechanism. The full-trajectory force-slew RMS falls 67.2% in NEW 40/80.
- `REPORT.md` has a presentation-only field-name bug in its BRAKE-entry column: OLD 40/80 should read one transition and 1786 BRAKE cycles. Raw `result.json` and `modes.npz` are correct and were used here.

## Interpretation

DIRECTLY OBSERVED: NEW preserves 40/40 COMPLETE behavior and removes the 40/80 FILTER_INFEASIBLE/BRAKE transition in this matched exploratory rollout. NEW 40/80 completes the physical return with much smaller tracking error, velocity-feedback force, executable/physical force peak, force-slew RMS, and moment peak.

SUPPORTED BY CURRENT EVIDENCE: the history-derived measured velocity is the dominant avoidable execution term at the OLD 40/80 boundary. The same-state/action replacement calculation reduces the rejected nominal force from 213.383 N to 169.104 N, and the matched NEW closed loop remains feasible.

UNRESOLVED: generalization to 90/120 and 120/120, sensitivity to real encoder noise/latency, and hardware behavior. This exploratory A/B is not clinical safety evidence or numerical qualification.

Recommendation: the correction passes the registered 40/40 non-degradation gate and produces a meaningful 40/80 mechanism change. A separately preregistered extension to rigid 90/120 and 120/120 is scientifically justified; keep the 140 Ns/m gain and all other frozen settings unchanged.
