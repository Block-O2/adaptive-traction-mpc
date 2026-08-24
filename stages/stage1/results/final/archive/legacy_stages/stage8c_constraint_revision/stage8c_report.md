# Stage 8C Task / Constraint Definition Revision Report

## Scope
- Diagnosis only: checked whether the current alpha metric/constraint is too strict, poorly defined, or conflicting with fast target reaching.
- Mainline remains CEM + UKF-bias + filtered Windowed NLS.
- Dynamics, estimator/identifier implementations, baseline CEM behavior, Stage 7 methods, and UKF settings were not intentionally changed.
- Optional soft-alpha re-evaluation used existing alpha100/alpha200 settings only.
- No formal safety claims are made.

## Commands Run
- `python /Users/hankli/Desktop/coding/adaptive-traction-mpc/scripts/run_spring2d_stage8c_constraint_revision.py --config /Users/hankli/Desktop/coding/adaptive-traction-mpc/configs/spring2d_safety_aware_cem.yaml --output-root /Users/hankli/Desktop/coding/adaptive-traction-mpc/results/stage8c_constraint_revision`

## Diagnostic Overrides
- `default_task`: current target, max_time/max_steps, and alpha logging.
- `relaxed_time`: doubled `max_time` and `max_steps`; target and weights unchanged.
- `lower_terminal_urgency`: single explicit reduction to `w_theta=45`, `w_terminal_theta=180`.
- `alpha100_eval` / `alpha200_eval`: existing alpha-soft settings re-evaluated with Stage 8C metrics.

## Aggregate Metrics
| method | target successes | T_reach avg | alpha p95 | alpha p99 | alpha max | clipped max | duration | integrated | early max | late max | omega p95 | omega max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| default_task | 3/3 | 2.017 | 4.766 | 6.798 | 7.307 | 7.042 | 0.8 | 2.044 | 7.297 | 5.81 | 0.228 | 0.4398 |
| relaxed_time | 3/3 | 2.017 | 4.766 | 6.798 | 7.307 | 7.042 | 0.8 | 2.044 | 7.297 | 5.81 | 0.228 | 0.4398 |
| lower_terminal_urgency | 3/3 | 2.017 | 4.766 | 6.798 | 7.307 | 7.042 | 0.8 | 2.044 | 7.297 | 5.81 | 0.228 | 0.4398 |
| alpha100_eval | 3/3 | 1.933 | 5.289 | 8.192 | 8.338 | 8.255 | 0.6967 | 1.943 | 8.338 | 6.55 | 0.3284 | 0.4672 |
| alpha200_eval | 3/3 | 2.333 | 5.242 | 7.305 | 7.675 | 7.523 | 0.7133 | 2.059 | 7.675 | 6.917 | 0.2417 | 0.4667 |

## Required Answers
1. Is alpha max dominated by isolated one-step spikes?
- No/not primarily for default_task: alpha max avg=7.307, clipped max avg=7.042, one-step reduction ratio=0.03635.

2. Do p95/p99/duration/integrated violation tell a different story than max?
- Yes: default p95/p99/max/clipped=4.766/6.798/7.307/7.042, duration=0.8, integral=2.044.

3. Does increasing allowed time reduce alpha tail?
- No: relaxed_time alpha p95/max=4.766/7.307 vs default=4.766/7.307. Because the environment stops at target reach, relaxed time alone may not slow an already-reaching trajectory.

4. Does lowering target urgency reduce alpha tail while preserving task completion?
- No/mixed: lower_terminal_urgency target=3/3, alpha p95/max=4.766/7.307.

5. Is current alpha constraint better treated as hard safety, soft smoothness cost, or diagnostic metric?
- Based on this diagnostic, treat raw alpha max as a diagnostic/tail-risk metric rather than a hard safety guarantee. p95/p99/duration/integral should be reported alongside any soft smoothness or safety cost.

6. Should alpha evaluation use p95/p99/duration instead of raw max?
- Use p95/p99/duration/integrated violation in addition to raw max, not as a silent replacement. Raw max remains useful for tail spikes, but alone can overstate or mischaracterize one-step events.

7. Is the current task definition conflicting with the alpha requirement?
- Yes/likely from this single-link diagnosis. The evidence should be read with Stage 8B: target-reaching and low alpha tail were not jointly achieved by simple oracle/budget/smoothness/time/urgency checks.

8. Is it safe to move to linked rods after this, or should single-link task definition be revised first?
- Revise the single-link task/alpha evaluation first; this is simulation evidence only and not a formal safety claim.

## Notes
- Bad or ambiguous results are retained directly. No post-result tuning was applied.
