# Stage-5 Interface Robustness final campaign v1

## Final classification

**EXIT C — STOP THIS IMPLEMENTATION.** The frozen core campaign produced
25/27 accepted episodes. Two predeclared core episodes exceeded the registered
q2 20 ms acceleration limit and aborted at 0.010 s. The failures were detected
online, so they were not silent and were not false completions, but physical
truth had already exceeded 600 deg/s2. Therefore the full preregistered box is
not validated. Defining a smaller continuous box after observing these results
would be a prohibited post-hoc narrowing, so EXIT B is not claimed.

The continuous 30-episode session was mechanically successful (30/30 accepted),
but wall-clock MPC runtime showed a material upward trend: the first-five mean
of per-episode solve means was 18.10 ms and the last-five value was 21.01 ms.
This reinforces that the final campaign does not satisfy every preregistered
criterion and does not support a hard-real-time claim.

The interface branch is **not ready for a clean checkpoint or Human-ID work**.
Per EXIT C, do not automatically restart interface MHE/EKF/predictor work or
add another filter. The result is a research/mechanical-interface decision
point.

## Frozen campaign fingerprint

- complete evidence attempt: `results/interface_robustness_final_campaign_v1`
- HEAD: `e6ea54b701e2a825cc8558c3e0cae214a1fac777`
- fingerprint SHA-256:
  `c94d8b308fdfc3e9df2955df8471660d4fdcec6ed2fc0f23d73769db09e73eb4`
- seeds: `20260824`, `20260825`, `20260826`
- Plant-v1 and controller nominal: Kt `[25000,25000,25000] N/m`,
  Dt `[346.19104557,377.33911767,343.90028453] Ns/m`, Kr `320 Nm/rad`,
  Dr `10.02820618 Nms/rad`; physics step `0.25 ms`
- CEM: 15 steps at 20 ms, 32 candidates, 6 elites, 2 iterations; only
  delta-u-motion is sampled around support
- robustness pacing: `[15,25] deg/s`; predicted physical-force ceiling `180 N`
- unchanged registered limits: velocity `[45,75] deg/s`, 20 ms acceleration
  `[300,600] deg/s2`, physical engineering gate `200 N`
- no interface ID/adaptation, Human adaptation, terminal value, RL, plant-truth
  online authority, full q trajectory, fixed coordination ratio, or path corridor

The fingerprint contains exact tracked and relevant-untracked Stage-5 patches,
config snapshots, and SHA-256 hashes of all Stage-5 source/config runtime inputs.
It was rechecked before every episode; the complete attempt did not drift after
its first episode.

The frozen repeatability JSON did not restate numeric values for its named
"moderately-soft" condition. Before execution, it was resolved by the only
matching preregistered condition shared by the uncertainty config and core
matrix: `low_low_low = (alpha_t,alpha_r,alpha_d)=(0.9,0.9,0.8)`. This resolution
is recorded in the fingerprint and was not changed after results were seen.

## Core campaign: 9 conditions x 3 seeds

`H/R/C` are HOLD, RETURN, and COMPLETE transition times in seconds. `A2` is
truth peak q2 20 ms acceleration. Runtime is mean/p95 in milliseconds. The
machine-readable record contains every task, state, wrench-prediction, safety,
interface, path, and runtime field.

| condition | seed | result | H / R / C (s) | truth A2 | peak F / M | runtime | >20 ms | accepted |
|---|---:|---|---:|---:|---:|---:|---:|---|
| nominal | 20260824 | COMPLETE | 2.110 / 2.610 / 4.890 | 458.7 | 120.5 N / 16.50 Nm | 18.02 / 18.94 | 0 | yes |
| nominal | 20260825 | COMPLETE | 2.435 / 3.085 / 5.565 | 492.4 | 118.5 / 16.05 | 18.16 / 18.99 | 2 | yes |
| nominal | 20260826 | COMPLETE | 2.485 / 3.170 / 5.645 | 377.1 | 115.7 / 16.39 | 18.05 / 19.00 | 1 | yes |
| low_low_low | 20260824 | COMPLETE | 2.230 / 2.940 / 5.225 | 570.6 | 118.1 / 16.11 | 18.19 / 18.98 | 1 | yes |
| low_low_low | 20260825 | COMPLETE | 2.225 / 3.035 / 5.430 | 501.6 | 118.0 / 16.75 | 17.96 / 18.97 | 2 | yes |
| low_low_low | 20260826 | COMPLETE | 2.440 / 3.145 / 5.385 | 462.8 | 118.5 / 16.21 | 18.01 / 18.92 | 0 | yes |
| low_low_high | 20260824 | ABORT, acceleration | - | **633.7** | 91.2 / 14.65 | 17.28 / 17.28 | 0 | **no** |
| low_low_high | 20260825 | COMPLETE | 2.165 / 2.965 / 5.235 | 546.4 | 118.6 / 16.12 | 18.48 / 18.96 | 3 | yes |
| low_low_high | 20260826 | COMPLETE | 2.335 / 3.095 / 5.405 | 474.6 | 116.4 / 16.12 | 18.01 / 18.94 | 0 | yes |
| low_high_low | 20260824 | COMPLETE | 2.245 / 3.055 / 5.155 | 425.8 | 113.7 / 16.40 | 18.18 / 18.99 | 1 | yes |
| low_high_low | 20260825 | COMPLETE | 2.235 / 2.965 / 5.080 | 404.2 | 115.3 / 16.35 | 18.14 / 18.90 | 1 | yes |
| low_high_low | 20260826 | COMPLETE | 2.180 / 2.930 / 5.125 | 400.5 | 118.0 / 16.30 | 18.15 / 19.07 | 1 | yes |
| low_high_high | 20260824 | COMPLETE | 2.455 / 3.200 / 5.290 | 414.4 | 116.5 / 16.32 | 18.00 / 18.99 | 1 | yes |
| low_high_high | 20260825 | COMPLETE | 2.110 / 2.810 / 4.955 | 390.6 | 113.5 / 16.04 | 18.09 / 19.06 | 1 | yes |
| low_high_high | 20260826 | COMPLETE | 2.245 / 3.015 / 5.110 | 358.1 | 115.6 / 16.10 | 18.16 / 18.98 | 1 | yes |
| high_low_low | 20260824 | COMPLETE | 2.225 / 2.990 / 5.215 | 563.9 | 119.6 / 16.16 | 18.01 / 18.99 | 1 | yes |
| high_low_low | 20260825 | COMPLETE | 2.075 / 2.815 / 5.240 | 499.1 | 119.1 / 16.76 | 18.31 / 19.06 | 4 | yes |
| high_low_low | 20260826 | COMPLETE | 2.335 / 3.105 / 5.325 | 426.7 | 116.7 / 16.70 | 18.09 / 18.90 | 1 | yes |
| high_low_high | 20260824 | ABORT, acceleration | - | **642.8** | 91.5 / 14.65 | 16.98 / 16.98 | 0 | **no** |
| high_low_high | 20260825 | COMPLETE | 2.160 / 2.925 / 5.370 | 560.3 | 118.1 / 16.06 | 18.01 / 18.94 | 0 | yes |
| high_low_high | 20260826 | COMPLETE | 2.575 / 3.380 / 5.520 | 470.2 | 117.1 / 16.27 | 18.08 / 19.00 | 0 | yes |
| high_high_low | 20260824 | COMPLETE | 2.190 / 2.930 / 5.085 | 363.7 | 116.3 / 16.49 | 17.98 / 18.95 | 1 | yes |
| high_high_low | 20260825 | COMPLETE | 2.235 / 2.735 / 4.930 | 459.9 | 114.4 / 15.76 | 17.92 / 18.91 | 1 | yes |
| high_high_low | 20260826 | COMPLETE | 2.230 / 2.980 / 5.045 | 351.6 | 119.1 / 16.40 | 17.97 / 18.89 | 1 | yes |
| high_high_high | 20260824 | COMPLETE | 2.285 / 3.045 / 5.135 | 357.7 | 116.4 / 16.25 | 18.12 / 18.97 | 1 | yes |
| high_high_high | 20260825 | COMPLETE | 2.120 / 2.870 / 5.045 | 505.8 | 115.3 / 16.76 | 18.00 / 18.92 | 0 | yes |
| high_high_high | 20260826 | COMPLETE | 2.155 / 2.950 / 5.290 | 372.3 | 116.1 / 16.37 | 18.15 / 19.01 | 2 | yes |

The two failures occurred only for `alpha_r=0.9`, `alpha_d=1.2`, seed
`20260824`, at both translational-stiffness endpoints. Each selected one
`SAFE_ACTION`, then aborted at 0.010 s. Online q2 acceleration was 610.5 and
625.6 deg/s2; aligned truth was 633.7 and 642.8 deg/s2. The online monitor
therefore detected the problem, but not before the registered physical limit
had been crossed. There was no `NO_SAFE_ACTION`, false completion, hidden
truth-only violation, force gate, BRAKE, Safety Filter intervention, structural
event, or MuJoCo warning. The first failed quantity was the physical motion
envelope, not state-estimation or wrench-prediction acceptance.

Across the 25 accepted core episodes, the worst terminal truth angle/speed was
0.419 deg and 3.221 deg/s. Worst q RMSE/p95/max was 0.385/0.548/0.613 deg;
worst dq RMSE/p95/max was 0.771/1.702/5.224 deg/s. Truth peak velocity and
acceleration were 26.713 deg/s and 570.600 deg/s2. Force-vector RMSE/p95/max
were 2.821/4.636/14.243 N; moment-vector RMSE/p95/max were
0.262/0.487/1.133 Nm; peak-force underprediction was 5.061 N. Peak/cumulative
force and peak moment were 120.545 N, 535.858 Ns, and 16.763 Nm. Peak
interface translation/rotation were 5.226 mm and 3.200 deg. Path diagnostic
spread was 0.164--0.213, with no path authority added.

Core runtime had 5,556 solves and 27 samples over 20 ms (0.49%). Per-run means
were 16.98--18.48 ms, p95 values 16.98--19.07 ms, and the isolated maximum was
101.59 ms. Simulated 20 ms action-hold timing was unchanged by wall time.

## Boundary challenges

| case | online/truth | classification | peak force / moment | truth peak ddq q1/q2 | force RMSE/p95 | result |
|---|---|---|---:|---:|---:|---|
| Kt x0.7 | COMPLETE/COMPLETE | successful completion | 115.42 N / 16.25 Nm | 196.82 / 523.44 | 1.99 / 3.73 N | acceptable |
| Kt x1.3 | COMPLETE/COMPLETE | successful completion | 118.93 / 16.24 | 184.05 / 439.62 | 1.91 / 3.63 | acceptable |
| Kr x0.7 | ABORT at t=0 / truth settled | conservative pre-violation rejection | 79.30 / 12.61 at start | approximately 0 / 0 | N/A | acceptable boundary detection |
| progressive Kt | COMPLETE/COMPLETE | successful completion | 118.55 / 16.26 | 180.92 / 457.00 | 1.84 / 3.63 | acceptable |

For Kr x0.7, truth was settled at `[5,10] deg` and zero speed, while nominal
inversion reconstructed `[5.627,11.595] deg`; the controller rejected the
initial condition before executing an episode. All four boundaries had no
silent failure or false completion. The progressive plant used exactly
`F_s=K*x*(1+beta*(||x||/x_ref)^2)`, beta `1/30`, x_ref
`0.004760026073649988 m`, giving 10% higher radial tangent stiffness at x_ref.

## Thirty-episode continuous session

The single-process `low_low_low` session completed 30/30 truth episodes with
30/30 full-contract acceptance. There were no false completions, silent
motion-envelope violations, Safety Filter interventions, BRAKE events, 200 N
gate events, structural events, or MuJoCo warnings. Episode-local task and
warm-start state were reset; plant, estimator, nominal interface history,
supervisor, executed-command history, and one continuous CEM RNG stream were
preserved.

- episode 1/30 long-HOLD durations: 5.210/5.330 s
- final-2-second q peak-to-peak in both: `[0,0] deg`
- last-five minus first-five mean terminal-error drift:
  `[-0.0195,+0.0263] deg`, within `[1,1] deg`
- peak force range: 116.21--124.63 N; first-five to last-five mean change:
  `-1.96 N`
- interface translation range: 5.141--5.303 mm; mean change `-0.058 mm`
- interface rotation range: 3.120--3.259 deg; mean change `+0.0068 deg`
- q-error max-norm mean change: `+0.0006 deg`; dq-error max-norm mean change:
  `-1.039 deg/s`
- task-duration mean change: `+0.017 s`; long-HOLD episodes make the full
  duration range 4.975--9.755 s
- truth peak velocity/acceleration: `[13.46,26.65] deg/s` and
  `[207.12,570.60] deg/s2`
- peak/cumulative force and peak moment: 124.63 N, 962.98 Ns, 17.00 Nm
- path diagnostic spread: 0.174--0.213; no trajectory/ratio/corridor authority

The mechanical, estimation, prediction, task, and settling trends show no
material degradation. Runtime does: the first-five/last-five mean solver time
was 18.10/21.01 ms, a `+2.91 ms` (`+16.1%`) change, with a fitted slope of
`+0.171 ms/episode`. Episodes 20--23 missed nearly every 20 ms deadline. The
session total was 2,289 misses in 6,738 solves (34.0%), per-episode mean solve
time averaged 19.63 ms, and the maximum was 61.54 ms. This wall-clock behavior
did not alter simulated/action-hold time, but it violates the requested
no-material-runtime-degradation check and prevents any real-time/WCET claim.

## Exact supported evidence scope and limitation

No continuous interface operating box is validated. The exact retained
simulation evidence is limited to:

- nominal: 3/3 independent seeds accepted;
- six core corners other than the two `alpha_r=0.9, alpha_d=1.2` corners:
  3/3 seeds accepted at each discrete point;
- `low_low_low`: additionally 30/30 consecutive episodes accepted;
- the two `alpha_r=0.9, alpha_d=1.2` corners: only 2/3 accepted and therefore
  explicitly outside any validated claim;
- Kt x0.7, Kt x1.3, and the preregistered progressive law: one boundary seed
  accepted each; these isolated probes are not robustness ranges;
- Kr x0.7: only conservative settled-start rejection is supported.

This is simulation and mechanical-engineering evidence only. It is not a
continuous robustness proof, hardware calibration, hardware or clinical safety
validation, or hard-real-time/WCET certification.

## Tooling attempts and preserved evidence

Three incomplete attempts remain local and are not included in any scientific
count:

1. attempt 01 stopped before repeatability episode 2 because the reused causal
   acceleration monitor was called twice at the unchanged boundary timestamp;
2. attempt 02 stopped at the same place after the entry call was fixed but the
   first control-loop read still assumed absolute time zero;
3. attempt 03 passed 15 repeatability episodes and stopped before episode 16
   when a floating-point sensor scheduler boundary returned the already
   published measurement timestamp.

All interruptions occurred before the affected episode executed a command or
plant step. The minimal tooling correction made duplicate causal measurement
reads idempotent by reusing the already-published acceleration record; it did
not create a new sample or alter controller parameters/decisions. Every new
attempt received a new pre-episode fingerprint and restarted the complete
matrix. The two core failures reproduced identically in all four attempts.

Compact authoritative local records are:

- `results/interface_robustness_final_campaign_v1/campaign_results.json`
- `results/interface_robustness_final_campaign_v1/campaign_fingerprint/`

Large traces and plots, plus all incomplete attempts, remain ignored local
evidence and were neither deleted nor promoted.
