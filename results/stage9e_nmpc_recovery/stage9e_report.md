# Stage 9E NMPC Recovery / Progress Refinement Report

## Scope
- Focused diagnosis and recovery variants for the Stage 9D `initial_theta_offset` failure.
- Dynamics, estimator, identifier, scaled multiple-shooting structure, force bounds, delta_r treatment, and alpha slack formulation are unchanged.
- rho_L1 remains 100 for all NMPC variants.
- Variants are one-setting only: terminal theta multiplier=3, progress penalty weight=250, longer horizon N=30.
- No broad tuning and no formal safety claims.

## Commands Run
- `python scripts/run_spring2d_stage9e_nmpc_recovery.py`

## Aggregate Metrics
| method | condition | target | fail rate | solve | final err | err reduction | pred progress | pred final err | alpha p95 | alpha max | raw omega max | slack max | delta_r | force |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_cem | initial_theta_offset | 3/3 | nan | nan | 0.1085 | 88.75 | nan | nan | 4.832 | 9.142 | 1.715 | nan | 0 | 0 |
| nmpc_base | initial_theta_offset | 0/3 | 0 | 0.03186 | 0.05275 | 88.8 | 6.998 | 10.05 | 0 | 3.138 | 1.182 | 0.0008045 | 0 | 0 |
| nmpc_longer_horizon | initial_theta_offset | 0/3 | 0 | 0.0362 | 0.04972 | 88.8 | 10.58 | 4.352 | 0 | 6.351 | 1.182 | 7.618 | 0 | 0 |
| nmpc_progress_stage_cost | initial_theta_offset | 0/3 | 0.7378 | 0.244 | 0.09344 | 88.76 | 7.027 | 10.06 | 0 | 3.138 | 1.182 | 0.001506 | 0 | 0 |
| nmpc_terminal_progress | initial_theta_offset | 0/3 | 0 | 0.03017 | 0.05146 | 88.8 | 6.599 | 7.219 | 0 | 7.049 | 1.18 | 8.33 | 0 | 0 |

## Phase 2
- Phase 2 skipped: no recovery variant reached >=2/3 target success on initial_theta_offset

## Variant Definitions
- `nmpc_base`: Stage 9D rho100 scaled NMPC.
- `nmpc_terminal_progress`: same formulation, terminal theta-error cost multiplied by 3.
- `nmpc_progress_stage_cost`: adds a small per-horizon penalty for negative/no target-error progress, weight 250.
- `nmpc_longer_horizon`: same weights, horizon increased from 18 to 30.

## Required Answers
1. Why does original NMPC fail to reach the target under initial_theta_offset?
- Near-target underreach, not gross stalling: base target=0/3, final error=0.05275 deg, theta-error reduction=88.8 deg, predicted progress=6.998 deg. The environment requires theta >= theta_target; base ends just below the crossing threshold.

2. Is the cause weak progress incentive, short horizon, or alpha conservatism?
- Evidence points to near-target crossing/settling logic plus alpha/action conservatism, not a simple horizon-only fix: winner=none. Terminal-progress and longer-horizon variants did not restore target crossing; progress-stage-cost caused high solver failure. The initial reverse omega does not send the controller in the wrong direction, but the conservative solution avoids the final crossing margin.

3. Which minimal variant restores recovery?
- No mandatory variant restored recovery to >=2/3 target success.

4. Does recovery improvement preserve alpha-tail gains?
- No/mixed: initial_theta_offset winner alpha max=nan, baseline CEM alpha max=9.142.

5. Is a dedicated recovery mode necessary?
- Yes, likely necessary: the mandatory variants did not recover target reaching.

6. Is the controller ready for linked-rods preparation after this?
- No, not yet: dedicated recovery mode or task/progress redesign before linked-rods preparation.
- Recommended next step: dedicated recovery mode or task/progress redesign before linked-rods preparation.
