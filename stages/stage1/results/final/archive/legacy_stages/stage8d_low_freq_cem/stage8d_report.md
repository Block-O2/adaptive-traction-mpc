# Stage 8D Low-Frequency / Delta-Knot CEM Report

## Scope
- Diagnosis only: tested whether alpha tail comes from high-frequency or rough CEM action sequences.
- Mainline estimator/identifier remains UKF-bias + filtered Windowed NLS.
- No governor, no gatekeeper, no action projection, and no alpha-soft penalty for low-frequency modes.
- Alpha100/alpha200 are reference runs using existing alpha-soft settings.
- Dynamics, UKF settings, identifier, baseline CEM standard mode, Stage 7 methods, and default configs were not intentionally changed.
- No formal safety claims are made.

## Commands Run
- `python /Users/hankli/Desktop/coding/adaptive-traction-mpc/scripts/run_spring2d_stage8d_low_freq_cem.py --config /Users/hankli/Desktop/coding/adaptive-traction-mpc/configs/spring2d_safety_aware_cem.yaml --output-root /Users/hankli/Desktop/coding/adaptive-traction-mpc/results/stage8d_low_freq_cem`

## Aggregate Metrics
| method | family | target | T_reach | alpha mean | alpha p95 | alpha p99 | alpha max | clipped max | duration | integral | omega p95 | omega max | action smoothness | runtime |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_standard | standard | 3/3 | 2.017 | 1.008 | 4.766 | 6.798 | 7.307 | 7.042 | 0.8 | 2.044 | 0.228 | 0.4398 | 0.2057 | 34.21 |
| alpha100_omega0 | alpha_soft_reference | 3/3 | 1.933 | 0.9997 | 5.289 | 8.192 | 8.338 | 8.255 | 0.6967 | 1.943 | 0.3284 | 0.4672 | 0.2088 | 32.76 |
| alpha200_omega0 | alpha_soft_reference | 3/3 | 2.333 | 0.9282 | 5.242 | 7.305 | 7.675 | 7.523 | 0.7133 | 2.059 | 0.2417 | 0.4667 | 0.1787 | 40.24 |
| u_knots_4 | u_knots | 1/3 | 6.12 | 0.4317 | 2.007 | 5.546 | 8.795 | 8.508 | 2.33 | 3.111 | 0 | 0 | 0.1989 | 124.7 |
| u_knots_6 | u_knots | 3/3 | 4.76 | 1.385 | 5.262 | 10.95 | 32.36 | 32.01 | 1.94 | 6.428 | 0.2872 | 0.7583 | 0.2195 | 81.53 |
| du_knots_4 | du_knots | 0/3 | nan | 6.307 | 19.25 | 27.8 | 40.91 | 40.67 | 6.157 | 50.58 | 0.7375 | 2.333 | 0.5274 | 55.84 |
| du_knots_6 | du_knots | 0/3 | nan | 6.048 | 19.08 | 22.93 | 26.79 | 26.26 | 6.083 | 48.51 | 0.4704 | 1.15 | 0.5951 | 80.26 |
| move_blocking_2 | move_blocking | 2/3 | 3.36 | 0.5725 | 3.876 | 7.152 | 10.24 | 9.933 | 1.087 | 2.523 | 0.1099 | 0.3721 | 0.1346 | 84.79 |
| move_blocking_3 | move_blocking | 2/3 | 4.735 | 0.6461 | 3.812 | 7.386 | 17.16 | 16.81 | 1.253 | 3.429 | 0.05393 | 0.2213 | 0.146 | 99.41 |
| lowpass_perturb | lowpass_perturb | 1/3 | 7.41 | 3.218 | 11.83 | 18.47 | 23.69 | 23.18 | 5.25 | 25.18 | 0.2424 | 0.5282 | 0.4488 | 119.6 |

## Required Answers
1. Does low-frequency action parameterization preserve target reaching?
- u_knots_6

2. Does it reduce alpha p95/p99/max/duration/integral vs baseline?
- No low-frequency mode improved all requested alpha metrics while preserving 3/3 target reaching.

3. Does it avoid worsening omega tail risk?
- No/mixed for the best low-frequency mode `u_knots_6`: omega p95/max=0.2872/0.7583 vs baseline=0.228/0.4398.

4. Which mode is best: u_knots, du_knots, move_blocking, or lowpass perturbation?
- Best aggregate low-frequency mode by target success, alpha p95/p99/max, and omega p95 is `u_knots_6` (u_knots).

5. Does this outperform alpha100/alpha200?
- No/mixed: best low-frequency `u_knots_6` alpha p95/max=5.262/32.36; best alpha-soft reference `alpha200_omega0` alpha p95/max=5.242/7.675.

6. Is the next step stress validation, SQP/RTI NMPC, or task/constraint revision?
- Recommended next step: task/constraint revision before stress validation; low-frequency parameterization alone is not decisive.

## Notes
- Bad or mixed results are reported directly. No post-result tuning was applied.
