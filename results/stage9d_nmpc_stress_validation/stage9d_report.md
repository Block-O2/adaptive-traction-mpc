# Stage 9D NMPC Sanity Check and Stress Validation Report

## Scope
- Logging sanity check plus stress validation for the Stage 9C scaled multiple-shooting alpha-slack NMPC.
- Stage 9C omega p95/max columns were omega violation severity, not raw omega. Stage 9D logs raw omega and violation severity separately.
- Slack activity is reported at thresholds 1e-05, 0.0001, 0.001.
- Seeds: [101, 102, 103]. Three seeds are used because this stress matrix covers 10 conditions x 5 methods.
- No broad tuning and no formal safety claims.

## Commands Run
- `python /Users/hankli/Desktop/coding/adaptive-traction-mpc/scripts/run_spring2d_stage9d_nmpc_stress_validation.py --config /Users/hankli/Desktop/coding/adaptive-traction-mpc/configs/spring2d_safety_aware_cem.yaml --output-root /Users/hankli/Desktop/coding/adaptive-traction-mpc/results/stage9d_nmpc_stress_validation`

## Aggregate Metrics
| method | condition | target | fail rate | fallback | solve | alpha p95 | alpha p99 | alpha max | duration | integral | slack mean | slack max | slack >1e-5/>1e-4/>1e-3 | raw omega p95/max | omega viol p95/max | delta_r | force |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| alpha200_omega0 | clean | 3/3 | nan | nan | nan | 4.913 | 7.98 | 9.051 | 0.9433 | 2.316 | nan | nan | 0/0/0 | 1.512/1.653 | 0.3125/0.453 | 0 | 0 |
| alpha200_omega0 | initial_theta_offset | 2/3 | nan | nan | nan | 3.66 | 7.499 | 9.126 | 1.047 | 2.377 | nan | nan | 0/0/0 | 1.449/1.745 | 0.2487/0.5454 | 0 | 0 |
| alpha200_omega0 | larger_target_angle | 3/3 | nan | nan | nan | 5.353 | 9.978 | 13.28 | 1.643 | 4.766 | nan | nan | 0/0/0 | 1.293/1.638 | 0.1022/0.4377 | 0 | 0 |
| alpha200_omega0 | noise | 3/3 | nan | nan | nan | 4.745 | 8.072 | 8.82 | 1.06 | 2.374 | nan | nan | 0/0/0 | 1.542/1.699 | 0.3425/0.4991 | 0 | 0 |
| alpha200_omega0 | noise_bias | 3/3 | nan | nan | nan | 4.785 | 7.668 | 8.715 | 0.9733 | 2.17 | nan | nan | 0/0/0 | 1.513/1.662 | 0.3128/0.4615 | 0 | 0 |
| alpha200_omega0 | parameter_mismatch_high_k | 3/3 | nan | nan | nan | 5.333 | 8.062 | 8.553 | 0.85 | 2.084 | nan | nan | 0/0/0 | 1.543/1.674 | 0.343/0.4738 | 0 | 0 |
| alpha200_omega0 | parameter_mismatch_low_k | 3/3 | nan | nan | nan | 5.041 | 8.392 | 9.202 | 1.037 | 2.463 | nan | nan | 0/0/0 | 1.514/1.691 | 0.314/0.4908 | 0 | 0 |
| alpha200_omega0 | stronger_bias | 3/3 | nan | nan | nan | 5.277 | 7.31 | 8.422 | 0.9367 | 2.37 | nan | nan | 0/0/0 | 1.485/1.643 | 0.2852/0.4427 | 0 | 0 |
| alpha200_omega0 | stronger_noise | 3/3 | nan | nan | nan | 6.63 | 13.25 | 16.05 | 0.9033 | 2.76 | nan | nan | 0/0/0 | 1.55/1.669 | 0.3498/0.4694 | 0 | 0 |
| alpha200_omega0 | tighter_alpha_limit | 3/3 | nan | nan | nan | 6.236 | 9.504 | 10.04 | 1.193 | 3.187 | nan | nan | 0/0/0 | 1.587/1.717 | 0.3868/0.5172 | 0 | 0 |
| baseline_cem | clean | 3/3 | nan | nan | nan | 6.026 | 10.13 | 11.29 | 0.9233 | 2.459 | nan | nan | 0/0/0 | 1.471/1.623 | 0.2708/0.4233 | 0 | 0 |
| baseline_cem | initial_theta_offset | 3/3 | nan | nan | nan | 4.832 | 7.917 | 9.142 | 1.033 | 2.357 | nan | nan | 0/0/0 | 1.591/1.715 | 0.3909/0.5147 | 0 | 0 |
| baseline_cem | larger_target_angle | 3/3 | nan | nan | nan | 5.638 | 10.27 | 14.45 | 1.827 | 5.053 | nan | nan | 0/0/0 | 1.28/1.603 | 0.08019/0.4029 | 0 | 0 |
| baseline_cem | noise | 3/3 | nan | nan | nan | 4.993 | 11.02 | 22.91 | 1.17 | 3.436 | nan | nan | 0/0/0 | 1.421/1.638 | 0.2214/0.4376 | 0 | 0 |
| baseline_cem | noise_bias | 3/3 | nan | nan | nan | 4.723 | 7.153 | 8.963 | 0.9267 | 2.185 | nan | nan | 0/0/0 | 1.44/1.633 | 0.2402/0.4335 | 0 | 0 |
| baseline_cem | parameter_mismatch_high_k | 2/3 | nan | nan | nan | 4.315 | 7.05 | 8.878 | 0.9333 | 2.254 | nan | nan | 0/0/0 | 1.403/1.697 | 0.2844/0.4975 | 0 | 0 |
| baseline_cem | parameter_mismatch_low_k | 3/3 | nan | nan | nan | 5.424 | 7.545 | 8.396 | 0.99 | 2.33 | nan | nan | 0/0/0 | 1.486/1.628 | 0.2863/0.4275 | 0 | 0 |
| baseline_cem | stronger_bias | 3/3 | nan | nan | nan | 4.512 | 7.464 | 17.64 | 1.05 | 2.436 | nan | nan | 0/0/0 | 1.447/1.63 | 0.2472/0.4298 | 0 | 0 |
| baseline_cem | stronger_noise | 3/3 | nan | nan | nan | 6.373 | 25.41 | 28.01 | 1.013 | 3.766 | nan | nan | 0/0/0 | 1.564/1.988 | 0.3642/0.7878 | 0 | 0 |
| baseline_cem | tighter_alpha_limit | 3/3 | nan | nan | nan | 6.389 | 9.013 | 10.83 | 1.24 | 3.305 | nan | nan | 0/0/0 | 1.507/1.665 | 0.3071/0.4646 | 0 | 0 |
| nmpc_rho1000_scaled | clean | 3/3 | 0 | 0 | 0.06272 | 2.905 | 3.202 | 3.308 | 0.29 | 0.3942 | 1.601e-05 | 8.762e-05 | 648/0/0 | 1.185/1.188 | 0/0 | 0 | 0 |
| nmpc_rho1000_scaled | initial_theta_offset | 0/3 | 0 | 0 | 0.02783 | 0 | 2.674 | 3.138 | 0.36 | 0.3802 | 1.051e-05 | 8.665e-05 | 486/0/0 | 1.176/1.182 | 0/0 | 0 | 0 |
| nmpc_rho1000_scaled | larger_target_angle | 3/3 | 0 | 0 | 0.0633 | 1.021 | 3.129 | 3.308 | 0.2 | 0.3813 | 1.545e-05 | 8.361e-05 | 702/0/0 | 1.189/1.19 | 0/0 | 0 | 0 |
| nmpc_rho1000_scaled | noise | 3/3 | 0 | 0 | 0.06232 | 2.823 | 3.205 | 3.421 | 0.4033 | 0.4231 | 1.647e-05 | 9.021e-05 | 720/0/0 | 1.208/1.238 | 0.007556/0.03808 | 0 | 0 |
| nmpc_rho1000_scaled | noise_bias | 3/3 | 0 | 0 | 0.05982 | 2.861 | 3.539 | 3.776 | 0.4167 | 0.4406 | 1.581e-05 | 8.855e-05 | 630/0/0 | 1.215/1.245 | 0.01487/0.04536 | 0 | 0 |
| nmpc_rho1000_scaled | parameter_mismatch_high_k | 3/3 | 0 | 0 | 0.05843 | 2.839 | 3.116 | 3.277 | 0.28 | 0.3904 | 1.534e-05 | 8.346e-05 | 648/0/0 | 1.193/1.194 | 0/0 | 0 | 0 |
| nmpc_rho1000_scaled | parameter_mismatch_low_k | 3/3 | 0 | 0 | 0.0586 | 2.827 | 3.156 | 3.32 | 0.29 | 0.4042 | 1.615e-05 | 8.985e-05 | 702/0/0 | 1.183/1.185 | 0/0 | 0 | 0 |
| nmpc_rho1000_scaled | stronger_bias | 3/3 | 0 | 0 | 0.05682 | 2.915 | 3.886 | 4.128 | 0.46 | 0.4809 | 1.597e-05 | 9.208e-05 | 666/0/0 | 1.222/1.252 | 0.02219/0.05169 | 0 | 0 |
| nmpc_rho1000_scaled | stronger_noise | 3/3 | 0 | 0 | 0.06003 | 2.618 | 3.291 | 3.536 | 0.5767 | 0.5127 | 1.575e-05 | 9.618e-05 | 650/1/0 | 1.221/1.254 | 0.02123/0.05441 | 0 | 0 |
| nmpc_rho1000_scaled | tighter_alpha_limit | 3/3 | 0 | 0 | 0.06426 | 0.6172 | 4.933 | 5.085 | 0.54 | 0.6631 | 1.355e-05 | 8.051e-05 | 594/0/0 | 1.187/1.189 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled | clean | 3/3 | 0 | 0 | 0.07217 | 2.9 | 3.201 | 3.308 | 0.29 | 0.3937 | 0.0001618 | 0.0008189 | 3780/1113/0 | 1.185/1.188 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled | initial_theta_offset | 0/3 | 0 | 0 | 0.03048 | 0 | 2.674 | 3.138 | 0.3 | 0.3581 | 0.0001076 | 0.0008045 | 14415/1278/0 | 1.176/1.182 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled | larger_target_angle | 3/3 | 0 | 0 | 0.07316 | 1.118 | 3.129 | 3.308 | 0.2 | 0.3803 | 0.0001547 | 0.0008371 | 4212/1263/0 | 1.189/1.19 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled | noise | 3/3 | 0 | 0 | 0.07687 | 2.827 | 3.206 | 3.421 | 0.4 | 0.4224 | 0.0001724 | 0.000952 | 3798/1261/0 | 1.208/1.238 | 0.007678/0.03812 | 0 | 0 |
| nmpc_rho100_scaled | noise_bias | 3/3 | 0 | 0 | 0.07152 | 2.862 | 3.538 | 3.776 | 0.4033 | 0.436 | 0.0001656 | 0.000893 | 3816/1237/0 | 1.215/1.245 | 0.01496/0.04541 | 0 | 0 |
| nmpc_rho100_scaled | parameter_mismatch_high_k | 3/3 | 0 | 0 | 0.06999 | 2.832 | 3.116 | 3.277 | 0.27 | 0.3732 | 0.0001569 | 0.0008357 | 3780/1173/0 | 1.193/1.194 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled | parameter_mismatch_low_k | 3/3 | 0 | 0 | 0.06948 | 2.805 | 3.154 | 3.32 | 0.29 | 0.3821 | 0.0001654 | 0.0008994 | 3942/1287/0 | 1.183/1.185 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled | stronger_bias | 3/3 | 0 | 0 | 0.06974 | 2.913 | 3.885 | 4.128 | 0.4567 | 0.4727 | 0.0001629 | 0.000871 | 3778/1231/0 | 1.222/1.252 | 0.0222/0.05175 | 0 | 0 |
| nmpc_rho100_scaled | stronger_noise | 3/3 | 0 | 0 | 0.07064 | 2.616 | 3.291 | 3.536 | 0.5867 | 0.5334 | 0.0006981 | 0.5699 | 3852/1282/4 | 1.221/1.254 | 0.02125/0.0544 | 0 | 0 |
| nmpc_rho100_scaled | tighter_alpha_limit | 3/3 | 0 | 0 | 0.08389 | 0.6072 | 4.932 | 5.085 | 0.53 | 0.6577 | 0.0001972 | 0.0009888 | 4536/1935/0 | 1.187/1.189 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | clean | 3/3 | 0 | 0 | 0.072 | 2.9 | 3.201 | 3.308 | 0.29 | 0.3937 | 0.0001618 | 0.0008189 | 3780/1113/0 | 1.185/1.188 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | initial_theta_offset | 0/3 | 0 | 0 | 0.03072 | 0 | 2.674 | 3.138 | 0.3 | 0.3581 | 0.0001076 | 0.0008045 | 14415/1278/0 | 1.176/1.182 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | larger_target_angle | 3/3 | 0 | 0 | 0.07053 | 1.118 | 3.129 | 3.308 | 0.2 | 0.3803 | 0.0001547 | 0.0008371 | 4212/1263/0 | 1.189/1.19 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | noise | 3/3 | 0 | 0 | 0.08043 | 2.827 | 3.206 | 3.421 | 0.4 | 0.4224 | 0.0001724 | 0.000952 | 3798/1261/0 | 1.208/1.238 | 0.007678/0.03812 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | noise_bias | 3/3 | 0 | 0 | 0.06981 | 2.862 | 3.538 | 3.776 | 0.4033 | 0.436 | 0.0001656 | 0.000893 | 3816/1237/0 | 1.215/1.245 | 0.01496/0.04541 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | parameter_mismatch_high_k | 3/3 | 0 | 0 | 0.07472 | 2.832 | 3.116 | 3.277 | 0.27 | 0.3732 | 0.0001569 | 0.0008357 | 3780/1173/0 | 1.193/1.194 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | parameter_mismatch_low_k | 3/3 | 0 | 0 | 0.06977 | 2.805 | 3.154 | 3.32 | 0.29 | 0.3821 | 0.0001654 | 0.0008994 | 3942/1287/0 | 1.183/1.185 | 0/0 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | stronger_bias | 3/3 | 0 | 0 | 0.07021 | 2.913 | 3.885 | 4.128 | 0.4567 | 0.4727 | 0.0001629 | 0.000871 | 3778/1231/0 | 1.222/1.252 | 0.0222/0.05175 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | stronger_noise | 3/3 | 0 | 0 | 0.07277 | 2.616 | 3.291 | 3.536 | 0.5867 | 0.5334 | 0.0006981 | 0.5699 | 3852/1282/4 | 1.221/1.254 | 0.02125/0.0544 | 0 | 0 |
| nmpc_rho100_scaled_with_cem_fallback | tighter_alpha_limit | 3/3 | 0 | 0 | 0.08543 | 0.6072 | 4.932 | 5.085 | 0.53 | 0.6577 | 0.0001972 | 0.0009888 | 4536/1935/0 | 1.187/1.189 | 0/0 | 0 | 0 |

## Stress Overrides
- `clean`: default clean condition
- `noise`: default noise condition
- `noise_bias`: default noise_bias condition
- `stronger_noise`: observation noise std doubled vs default noise
- `stronger_bias`: observation bias doubled vs default noise_bias
- `parameter_mismatch_low_k`: initial/model k set to 270; true dynamics unchanged
- `parameter_mismatch_high_k`: initial/model k set to 600; true dynamics unchanged
- `initial_theta_offset`: theta_init=0.02 rad and omega_init=-0.15 rad/s explicit run override
- `larger_target_angle`: theta_target=105 deg explicit run override
- `tighter_alpha_limit`: alpha_max constraint/evaluation set to 2.0 rad/s^2

## Required Answers
1. Was omega logging in Stage 9C raw omega or omega violation?
- Stage 9C reported omega violation severity. Stage 9D distinguishes `omega_abs_*` raw absolute omega from `omega_violation_*` severity.

2. Is alpha slack genuinely active, or mostly numerical boundary contact?
- Use the threshold split. Across available rho100 conditions, slack active counts are >1e-5/>1e-4/>1e-3 = 49909/13060/4. If the count collapses at 1e-4 or 1e-3, most activity is numerical boundary contact rather than meaningful slack.

3. Does NMPC preserve target reaching under stress?
- No/mixed: rho100 target success is at least baseline in 9/10 available conditions.

4. Does NMPC reduce alpha p95/p99/max/duration/integral vs baseline under stress?
- Yes: rho100 improves all tracked alpha aggregate metrics vs baseline in 10/10 available conditions.

5. Does NMPC avoid worsening raw omega, delta_r, and force safety?
- Raw omega max is not worse than baseline in 10/10 conditions; delta_r count not worse in 10/10; force count not worse in 10/10.

6. Is rho100 enough, or does rho1000 improve robustness?
- rho1000 beats rho100 on alpha max without target loss in 0/10 available conditions. Treat rho100 as sufficient unless this count is broad and material.

7. Does fallback materially improve robustness?
- No material effect observed: fallback has nonzero use or target improvement in 0/10 available conditions.

8. Which stress condition breaks NMPC first, if any?
- initial_theta_offset.

9. Is solve time acceptable for this small system?
- Yes for offline/small-system validation: clean rho100 mean solve time=0.07217 s.

10. Should the next step be NMPC refinement, alpha/task redesign, linked rods preparation, or paper/report consolidation?
- Recommended next step: alpha/task redesign before linked rods preparation.
