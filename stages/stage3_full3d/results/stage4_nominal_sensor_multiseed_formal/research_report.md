# Stage-4 Nominal Sensor Multi-Seed Report

Status: completed `formal_user_run_unreviewed` engineering evidence. The preregistered matrix contains five measurement seeds, three existing sensor regimes, and two frozen A/B arms: 15 valid pairs and 30 completed 32 s rollouts.

## Promotion frequency

| regime | A no promotion | B measured improvement / oracle degradation | C measured + oracle improvement | any promotion | first-promotion times s |
|---|---:|---:|---:|---:|---|
| `ideal_200hz` | 5/5 | 0/5 | 0/5 | 0/5 (0%) | none |
| `noise_200hz` | 3/5 | 2/5 | 0/5 | 2/5 (40%) | 54113:9.74, 64122:18.30 |
| `noise_bias_drift_200hz` | 0/5 | 5/5 | 0/5 | 5/5 (100%) | 44104:17.74, 54113:9.74, 64122:9.78, 74131:9.38, 84140:9.50 |

Ideal sensing protected the exact prior in all five repeats. The five ideal traces were byte-identical across measurement seeds, confirming that the unused ideal-case RNG seed did not leak into MPC or execution.

Noise-only promoted in 2/5 seeds (40%): 54113 at 9.74 s and 64122 at 18.30 s. Thus zero-mean noise plus the frozen preprocessing/reconstruction path can produce trusted nominal compensation, but the outcome is seed-variable rather than dominant.

Noise+bias+drift promoted in 5/5 seeds (100%). First promotion times were 17.74, 9.74, 9.78, 9.38, and 9.50 s (median 9.74 s; range 9.38–17.74 s). Four seeds promoted near 9.4–9.8 s; the original 44104 anchor remained the late 17.74 s case. The regime accumulated 10 total promotions across five seeds, versus two for noise-only.

## Measured-domain versus clean-oracle prediction

Every promotion satisfied the frozen held-out measured-loss rule, including negative registered upper bounds against both references. The first-promotion candidate-minus-prior measured MSE means were:

- noise-only: 54113:-0.07477, 64122:-0.00919 Nms2;
- noise+bias+drift: 44104:-0.01910, 54113:-0.15631, 64122:-0.01787, 74131:-0.01614, 84140:-0.17313 Nms2.

All seven promoted seed/regime pairs were category B: measured-domain improvement with clean-oracle degradation. Category C occurred 0/15. Applied-model clean-oracle RMSE changes by seed were:

- noise-only: 44104:0.0000, 54113:0.2132, 64122:0.0925, 74131:0.0000, 84140:0.0000 Nm;
- noise+bias+drift: 44104:0.0710, 54113:0.4462, 64122:0.3120, 74131:0.2078, 84140:0.4711 Nm.

This is direct evidence that trust is validating future measured integral-target prediction, not recovery of the physical nominal dynamics. Oracle diagnostics remained offline and did not influence any decision.

## Tracking, pacing, and completion

Maximum tracking-error A/B deltas were exactly zero in all 15 pairs. Tracking-RMSE deltas were zero without promotion and small after promotion:

- noise-only: 44104:0.000000, 54113:-0.001363, 64122:-0.000516, 74131:0.000000, 84140:0.000000 deg;
- noise+bias+drift: 44104:-0.008123, 54113:-0.002423, 64122:-0.005737, 74131:0.001544, 84140:-0.003309 deg.

Noise-only improved tracking RMSE slightly in both promoted seeds. Bias+drift improved it in four seeds and worsened it slightly in seed 74131. Therefore measured prediction improvement did not guarantee tracking improvement, and the tracking consequences were much smaller than the oracle-model degradation.

Pacing and reference progress were exactly identical between A/B arms within every pair. Reference completion occurred in 0/5 ideal seeds, 1/5 noise-only seeds, and 4/5 bias+drift seeds. This reflects shared qualification timing and confidence pacing, not adaptive-model application. Every arm completed its requested 32 s wall duration.

## Bound pressure and safety

Maximum active-bound counts across seeds were ideal [4,4,4,4,4], noise-only [5,7,4,3,5], and bias+drift [6,6,3,5,5]. Median maximum unconstrained violations were respectively 1.485, 3.157, and 2.776 estimator spans; the largest single value was 10.504 under the original biased seed. The noise and biased distributions overlap: bound pressure is a general reconstruction/identification feature, not by itself an explanation of the 40% versus 100% promotion split.

All 30 arms were free of force-gate, ROM, unintended-contact, torque-saturation, joint-limit, MPC-solver, and MuJoCo-warning events.

## Interpretation

Within this fixed five-seed set, bias/drift compensation appears systematic rather than an artifact of seed 44104: the cumulative bias+drift regime promoted in every seed and much more often than noise-only. However, noise-only promotion in 2/5 seeds shows that finite-sample sensor/preprocessing variability is also a real pathway to nominal compensation.

The evidence strengthens the description of the identified beta as a control-effective measured-channel compensation model, not physical patient truth. It does not identify a trust-lifecycle error and does not justify changing thresholds or bounds.

A further separately preregistered component decomposition is now scientifically justified: ideal versus noise-only remains confounded by preprocessing, while the cumulative biased regime cannot distinguish fixed bias from drift. Such a study should isolate preprocessing, zero-mean noise, fixed bias, and drift without tuning the frozen controller. No such new regime is added here.

These five deterministic seeds provide descriptive 20-point frequency resolution only; they are not a precise Monte Carlo estimate or a clinical/population claim.
