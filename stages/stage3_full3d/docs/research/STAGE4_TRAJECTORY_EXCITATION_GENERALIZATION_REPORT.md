# Stage-4 trajectory-excitation generalization formal report

Evidence category: `formal_user_run_unreviewed`.

Scope: one registered perturbed Human, one registered sensor/noise realization, and the frozen Stage-4 controller in simulation. This is engineering evidence, not a clinical, population, or safety claim.

## Integrity verdict

All 6 preregistered trajectories and 12 arms are present. Config hash, controller fingerprint, patient, sensor, seeds, runtime mapping, finite traces, causal validation isolation, and pre-promotion A/B equality all passed. The anchor traces exactly match the earlier registered perturbed-Human traces byte-for-byte. Final artifacts cannot prove the entire historical absence of overwrite, but contain no evidence of config drift, case substitution, smoke contamination, or warm start.

## Main comparison

Positive benefit percentages mean lower error under trusted adaptation. `cond(Z)` and `lambda_min(I)` are frozen offline descriptors.

| trajectory | cond(Z) | lambda_min(I) | first promotion s | remaining % | tracking RMSE P/A deg | benefit % | max error P/A deg | torque RMSE P/A Nm | benefit % | promo/rej | max bound #/span | progress P/A | event |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `registered_high_flexion_23s` | 349 | 0.0303 | 9.72 | 78.9 | 0.7655/0.7131 | 6.85 | 1.820/1.561 | 4.4244/3.9687 | 10.30 | 4/0 | 4/3.13 | 1.000/1.000 | none |
| `moderate_rom_23s` | 709 | 0.00873 | 9.88 | 78.5 | 0.7953/0.6330 | 20.41 | 2.054/2.092 | 4.6463/3.9457 | 15.08 | 4/0 | 4/1.42 | 1.000/1.000 | none |
| `slow_high_flexion_34p5s` | 345 | 0.0106 | 11.14 | 83.9 | 0.7882/0.6034 | 23.45 | 1.691/2.046 | 4.3962/3.4513 | 21.49 | 6/0 | 7/7.29 | 1.000/1.000 | none |
| `hip_dominant_low_knee_23s` | 109 | 0.00119 | 9.72 | 78.9 | 1.0515/0.8861 | 15.73 | 2.603/2.169 | 4.4231/3.8236 | 13.55 | 3/1 | 5/7.97 | 1.000/1.000 | none |
| `knee_dominant_low_hip_23s` | 881 | 0.00931 | none | none | 1.6036/1.6036 | 0.00 | 9.899/9.899 | 4.7458/4.7458 | 0.00 | 0/0 | 0/0.00 | 0.243/0.243 | shared force gate |
| `two_cycle_moderate_23s` | 1.96e+04 | 5.73e-06 | 12.94 | 71.9 | 1.0193/0.9481 | 6.98 | 3.810/3.810 | 4.4992/4.0604 | 9.75 | 4/0 | 6/20.67 | 1.000/1.000 | none |

## Causal-chain findings

Every trajectory remained structurally rank 11, but practical conditioning varied by orders of magnitude. 5/6 produced at least one valid promotion; the remaining case retained the prior. Promotion timing and downstream benefit varied materially, so rank alone did not predict usefulness.

Tracking RMSE improved in 5/6 cases and clean-oracle torque-prediction RMSE improved in 5/6, while maximum tracking error strictly improved in only 2/6. Five cases completed in both arms. The knee-dominant case stopped identically in both arms at 24.3% progress on the commanded cuff-force gate before any challenger fit; this is a shared controller/safety event, not an adaptation-induced event and not evidence that weak excitation itself is unsafe.

The aggregate JSON retains the complete singular spectra, three weakest parameter directions, candidate-by-candidate active-bound pressure, promotion timelines, prediction/tracking windows, progress, safety, and descriptive force/moment/surface-proxy metrics.

## Trajectory-by-trajectory findings

- **Anchor:** promotion at 9.72 s with 78.9% reference remaining; tracking/prediction RMSE improved 6.85%/10.30%. The traces exactly reproduce the earlier registered result.
- **Moderate ROM:** despite weaker offline information than the anchor, promotion was only 0.16 s later and RMSE benefits were larger (20.41% tracking, 15.08% prediction). Maximum tracking error worsened 1.82%, so the result is mixed rather than uniformly better.
- **Slow high-flexion:** full geometric ROM preserved `cond(Z)` near the anchor, but lower acceleration reduced absolute weakest-direction strength. Promotion occurred at 11.14 s yet left 83.9% of the slower reference; RMSE benefits were the largest (23.45%/21.49%), while maximum error worsened 21.04%.
- **Hip-dominant/low-knee:** its apparently favorable `cond(Z)=109` masked weak absolute information (`cond(X)=6119`, `lambda_min(I)=1.19e-03`). It still promoted at 9.72 s and improved tracking/prediction RMSE 15.73%/13.55%, but recorded one later challenger rejection and substantial bound pressure.
- **Knee-dominant/low-hip:** both arms hit the same commanded cuff-force gate at reference phase 5.58 s, before any challenger was created. Trust retained the prior and A/B outputs remained identical. Because the causal chain was interrupted by shared early termination, no-promotion cannot be attributed solely to offline conditioning.
- **Two-cycle moderate:** the preregistered practically ill-conditioned case (`cond(Z)=1.96e+04`, `lambda_min(I)=5.73e-06`) fit later (8.42 s), promoted latest (12.94 s), left the least reference among promoted cases (71.9%), and showed the largest bound pressure (6 active bounds, 20.67 spans maximum unconstrained violation). It still improved tracking/prediction RMSE 6.98%/9.75%, so poor conditioning delayed and constrained usefulness rather than preventing it outright.

## Excitation versus adaptation

Across only six fixed trajectories, log10(lambda_min(I)) versus first promotion had Pearson r=-0.824 and Spearman rho=-0.462; prediction benefit versus tracking benefit had Pearson r=0.923 and Spearman rho=0.886. These are descriptive associations, not inferential evidence or a calibrated excitation threshold.

This supports the timing portion of the causal chain: among the five promoted cases, poorer conditioning was associated with later promotion and less remaining trajectory. It does **not** support a simple monotonic excitation-to-benefit rule: `lambda_min(I)` had near-zero descriptive association with tracking or prediction benefit across all six cases, and moderate/slow/hip-dominant trajectories are counterexamples to such a ranking.

Force, moment, and cylindrical surface-proxy changes were small and not consistently signed in the five completed pairs. The knee-dominant pair had identical, larger peak interaction values because both arms shared the same early force-gate termination. These quantities remain descriptive and are not pressure, comfort, tissue-loading, or safety benefit evidence.

## Scientific conclusion

The hypothesis that natural rehabilitation excitation is sufficient for useful one-shot adaptation is **conditionally supported but limited**. Natural task motion was sufficient for valid promotion in five of six trajectories in this one patient/seed suite, while one normal task retained the prior. Practical conditioning was associated with when trust could act, but did not alone determine how much prediction/tracking benefit followed. Full rank was not sufficient evidence of timely or useful adaptation, and excitation quality alone did not determine benefit magnitude. The shared force-gate/no-promotion result, maximum-error degradations, late promotion, rejection, and bound pressure are valid negative/mixed evidence and were not tuned away.

## Recommended next step

Pre-register replication across a small fixed set of patient mismatches and measurement seeds using these unchanged six trajectories. Treat promotion probability/timing and benefit variability as outcomes; do not add active excitation, retune weak trajectories, or change the trust/controller contract within this evidence set.
