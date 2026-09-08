# Rigid vs P1 40/80 exploratory matched A/B

> [!IMPORTANT]
> **PRE-CORRECTION / RETIRED DIAGNOSTIC EVIDENCE**
>
> This report predates the corrected low-latency robot velocity-feedback
> measurement path and is retained only as diagnostic provenance. Current
> authoritative conclusions are in [CURRENT_STATE](../../../docs/research/CURRENT_STATE.md)
> and the [corrected High-ROM evidence](../../summaries/phase3a_corrected_high_rom/README.md).
> Commands and paths below are frozen historical provenance; they are retired,
> non-current, and must not be treated as executable reproduction instructions.



**Both arms executed their complete registered reference phase. Both retain formal SAFE_INCOMPLETE. Rigid entered BRAKE during return and did not physically return; P1 remained TRACK and completed the practical outbound/return, with precision outside the unchanged 0.0689692672 deg criterion.**

Exploratory diagnostic evidence only. The earlier strict numerical-qualification FAIL remains unchanged. No compliant numerical qualification or clinical safety claim.



## Frozen contract

Spec SHA256 `19c46e9ff15d2f812db5124f3b8f86337a400881c35ca4b7efe77bd6ddf55976`; MD SHA256 `209bf752dcd428992488d18966c1790f85af779aec011d4854c1fcf0d2a686e5`. Branch codex/interface-phase3a-de23ea3 at `99169491ea1336d6af74e3b63318afba18c1e881`; baseline `de23ea3cdf9f0fb078496ba5ba4abb6a205ad955`.

Exactly rigid 40/80 then registered P1 40/80, fresh processes. Both dt=0.25 ms and 20 physics substeps per unchanged 5 ms control tick. Same controller, suspended_high_rom, nominal Human/model lock, adapter, seed, quintic reference, allocator, measurement timing/noise, Reference Manager, Safety Filter, BRAKE and force contracts. No parameter/tolerance adjustment and no 90/120.

P1 coefficients are unchanged: K1=60000 N/m, K3=5e10 N/m^3, D=490.68422685624563 Ns/m; Kr1=1800 Nm/rad, Kr3=4e6 Nm/rad^3, Dr=12.447966320580795 Nms/rad.



## Direct comparison

| Metric | Rigid | P1 |
| --- | --- | --- |
| Formal classification | SAFE_INCOMPLETE | SAFE_INCOMPLETE |
| Termination | reference_completed | reference_completed |
| Practical completion | full reference phase executed; BRAKE-limited physical return | full reference executed; precision criterion not met |
| Outbound / return reference % | 100.0/100.0 | 100.0/100.0 |
| Final phase / physical time s | 19.055583569411002/20.865000000008614 | 19.055749999999975/19.055749999999975 |
| Tracking RMSE / max norm deg | 24.66185503228125/71.86877002951313 | 0.4474783158106737/1.0460786711247736 |
| Tracking max q1/q2 deg | [32.1568, 64.2791] | [0.504819, 0.922523] |
| Endpoint / return error deg | 0.01698495873645811/64.24116946897739 | 0.10893917135769016/0.7970020802046687 |
| Command force RMS / peak N | 107.5152223851548/199.9999999999517 | 101.67222344669219/127.04981853959326 |
| Physical force RMS / peak N | 105.49102356959054/197.49715692658623 | 101.58362833533772/123.20384078663761 |
| Force slew RMS / peak N/s | 2343.9929949573298/251692.00776539982 | 247.5208530574396/8711.5096970233 |
| Moment RMS / peak Nm | 8.747063156536965/38.35978242360643 | 10.52228993305071/19.119027085120916 |
| BRAKE entries / duration s | 1/8.93 | 0/0.0 |
| First BRAKE physical / phase s | 11.93499999999486/11.93498749999486 | — |
| BRAKE_INFEASIBLE / NO_SAFE_ACTION | 0/0 | 0/0 |
| Filter intervention count / peak | 1/43.40470922660014 | 0/0.0 |
| Minimum feasible / BRAKE-feasible candidates | 1/6 | 1/— |
| Human cuff acceleration RMS / peak | 2.5138683210402424/16.250550988730442 | 0.28804550579930593/9.03507534400489 |
| Peak acceleration time s | 11.9304 | 0.000125 |
| Human cuff jerk RMS / peak | 452.67825051000295/20516.675886107405 | 41.18954820730419/1934.7379150504494 |
| Proxy RMSE q1/q2 deg | [0.0989226, 0.16154] | [0.31483, 0.600321] |
| Proxy peak q1/q2 deg | [0.610308, 0.843543] | [0.549931, 1.04495] |
| Force >200 duration / excess impulse | 0.0/0.0 | 0.0/0.0 |
| Force contract | STRICT_PASS | STRICT_PASS |

Both force reports are STRICT_PASS: zero >200 N duration and zero excess impulse. Rigid has one SAFE_FILTERED and one FILTER_INFEASIBLE cycle; its filter intervention coordinate norm peaks at 43.4047. P1 has 3812 SAFE_UNCHANGED cycles and zero intervention. Neither arm has BRAKE_INFEASIBLE or NO_SAFE_ACTION.



## Explicit progress and state

Both references reach 100% outbound and 100% return. `reference_completed` is a phase/timing result; it does not mean the physical Human followed the return. Both formal labels are preserved as SAFE_INCOMPLETE.



| Event | Rigid q_true deg | Rigid q_proxy deg | P1 q_true deg | P1 q_proxy deg |
| --- | --- | --- | --- | --- |
| target_arrival | [40.0926, 79.9528] | [40.0449, 79.9052] | [39.9107, 79.851] | [40.0169, 79.9736] |
| return_end | [37.1559, 74.2161] | [37.1524, 74.2148] | [4.56781, 9.16488] | [5.00827, 10.0328] |
| reference_end | [37.1507, 74.2412] | [37.122, 74.206] | [4.60756, 9.203] | [5.08879, 10.1213] |

Rigid reaches the target at reference time near [40.093,79.953] deg. Its BRAKE starts at physical t=11.935 s / phase=11.93499 s, 21.31% into the registered return leg. At return-end phase it remains [37.156,74.216] deg and finishes [37.151,74.241] deg. This is full reference phase executed with a controller-boundary-limited physical return.

P1 reaches the target at [39.911,79.851] deg, reaches return-end at [4.568,9.165] deg, and finishes [4.608,9.203] deg. This is full reference executed; precision criterion not met.



## P1 interface and energy

| Metric | P1 |
| --- | --- |
| Translation peak / RMS mm | 1.0601073933296485 / 0.9552467157196891 |
| Rotation peak / RMS deg | 0.5097473862657227 / 0.2987707575728594 |
| Relative velocity peak m/s | 0.066659 |
| Relative angular velocity peak rad/s | 0.564738 |
| Target / return translation mm | 0.964781621013061 / 0.8833818479777653 |
| Spring energy peak J | 0.116241 |
| Damping loss J | 0.13895 |
| Max absolute / running-normalized residual | 0.0023433721047023404 J / 1.152066718289806% |
| Final residual / trailing slope | -0.002244832404853264 J / -0.00011909773552767834 J/s |
| Sustained-growth triggers / windows | 0 / 381 |

The small rigid-column relative-pose trace in the aligned plot is the weld/geometry consistency diagnostic; it is not compliant-interface deformation.

No registered persistent energy/amplitude-growth watchdog fires. The residual is diagnostic and nonzero; this does not overturn the strict qualification failure.



## Temporal alignment

Rigid peak Human-cuff acceleration occurs at 11.930375 s. Physical force peaks 0.125 ms earlier, command force peaks 0.375 ms earlier, the nearest deformation radial reversal is 2.125 ms earlier, and BRAKE/FILTER_INFEASIBLE occurs 4.625 ms later at the next 5 ms controller boundary. The proxy-error norm peaks 110.375 ms earlier. This cluster occurs during return, 1.652 s after return start, rather than at an analytic reference segment transition.

P1 global acceleration peak is the same startup transient observed in 40/40: 9.0351 m/s² at 0.000125 s. Its largest post-start (t>=0.1 s) acceleration is 1.00337 m/s² at 9.027625 s, 0.249625 s after target arrival; it is not aligned with BRAKE/Safety Filter events because none occur. See detailed_metrics.json for nearest reversal, command, force and proxy times.

These are time associations from saved traces. They do not identify causality. Simulator truth is used only in this offline analysis.



Historical media note: `aligned_40_80_diagnostics.png` was externalized during
repository closeout. Its archived path and SHA-256 remain in
[`EXTERNAL_RAW_ARCHIVE_SHA256SUMS`](../../summaries/phase3a_corrected_high_rom/EXTERNAL_RAW_ARCHIVE_SHA256SUMS).



Historical media note: `rigid_boundary_event_alignment.png` was externalized
during repository closeout. Its archived path and SHA-256 remain in
[`EXTERNAL_RAW_ARCHIVE_SHA256SUMS`](../../summaries/phase3a_corrected_high_rom/EXTERNAL_RAW_ARCHIVE_SHA256SUMS).



## Interpretation

### DIRECTLY OBSERVED

- Rigid: full phase, SAFE_INCOMPLETE, first BRAKE at 11.935 s / phase 11.93499 s, final BRAKE mode, no physical return, peak 197.50 N.

- P1: full phase, SAFE_INCOMPLETE, TRACK throughout, practical physical return with 0.7970 deg strict return error, peak 123.20 N, deformation bounded to 1.060 mm / 0.510 deg.

- P1 lowers physical peak force 37.62%, RMS force 3.70%, moment peak 50.16%, force-slew peak 96.54%, cuff-acceleration peak 44.40%, and acceleration RMS 88.54% versus rigid in this 40/80 pair.

- P1 increases proxy RMSE and leaves a precision offset; q2 proxy error at return-end is 0.868 deg.



### SUPPORTED BY CURRENT EVIDENCE

Dominant interpretation **B**: P1 changes the observed 40/80 feasibility/BRAKE boundary mechanism. Rigid triggers FILTER_INFEASIBLE then BRAKE during return; P1 has no filter intervention or BRAKE and completes the practical return. Interpretation A also applies to force-transient smoothing, with a large slew reduction. P1 therefore changes more than waveform smoothness at this tested point.



### UNRESOLVED

The causal pathway between compliance, proxy bias, acceleration and filter feasibility is unresolved. P1 is not numerically qualified, and one matched point cannot establish repeatability or a general boundary shift. The host-runtime difference is instrumentation/runtime cost, not hard real-time evidence.



### NOT SUPPORTED

No clinical safety claim, qualified compliance-physics claim, formal capability-envelope expansion, or claim that P1 consistently lowers force across all trajectories. In 40/40 P1 reduced slew but slightly increased force peak/RMS and worsened tracking. Interpretation C is not dominant at 40/80 because P1 avoids the rigid boundary failure, although its proxy/precision offsets are a real cost. Interpretation D is not dominant because both traces are finite, bounded, complete in reference phase, and free of growth-watchdog events; numerical qualification nevertheless remains failed.



## Relation to 40/40 and next test

At 40/40, rigid COMPLETE and P1 precision-limited SAFE_INCOMPLETE; P1 reduced slew without reducing force peak/RMS. At 40/80, both formal labels are SAFE_INCOMPLETE, but their mechanisms differ: rigid is BRAKE/return-limited, P1 is precision-limited after a practical full return and has much lower peak force.

90/120 is scientifically justified as a separately reviewed exploratory boundary probe because 40/80 shows a mechanism change with bounded P1 deformation and no pathology. It is not authorized or executed here. A future Spec should preserve this exact stack and report whether that trend survives the more extreme point.



## Reproducibility

Run directories: `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/progressive_40_80_ab_20260907_v1/hip40_knee80_rigid_dt0250us` and `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/progressive_40_80_ab_20260907_v1/hip40_knee80_P1_dt0250us`. Fourteen preflight tests passed. Postprocessing verified 273 arrays, 375 frozen hashes, exact paired initial state/config and matching control-model fingerprints. git diff --check passes; tracked diff is empty. Everything remains uncommitted.

Added only the new 40/80 Spec, runner, test, report script, and result directory. Scientific variable: interface rigid vs registered P1. Explicitly unchanged: controller, estimator, model lock, Human/robot, geometry, adapter, trajectory/timing, seed, force limits/contracts, Reference Manager, Safety Filter, BRAKE, solver and gains. Both arms use the same requested 0.25 ms.

Commands:

```text

PYTHONDONTWRITEBYTECODE=1 <python> -m pytest -q -p no:cacheprovider stages/stage4_adaptive_control/tests/test_progressive_40_80_ab.py

PYTHONDONTWRITEBYTECODE=1 <python> stages/stage4_adaptive_control/scripts/run_progressive_40_80_ab.py --freeze

PYTHONDONTWRITEBYTECODE=1 <python> stages/stage4_adaptive_control/scripts/run_progressive_40_80_ab.py --run-next  # exactly two fresh processes

PYTHONDONTWRITEBYTECODE=1 <python> stages/stage4_adaptive_control/scripts/summarize_progressive_40_80_ab.py

git diff --check

git status --short

```

No formal command is admitted. No 90/120 run until review.
