# Stage 11A: Information Metric Validation

- Filtered reduced-NLS mean mass error: 0.0626013; true-state oracle: 0.102233.
- The strongest simple excitation rank relation is `force_excitation_mean` (Spearman=-0.4805), but task-relevant `I_alpha` is the better update-quality classifier (AUC=0.7408 for 10% mass error; Spearman=-0.4582).
- Gate thresholds use leave-one-condition-out training quantiles only.

## Conclusions

1. Information can predict lambda error moderately, but not alpha prediction quality robustly.
2. `I_alpha` is the most task-relevant candidate; generalized-force mean is a useful secondary proxy.
3. EIV is not the dominant cause here: true-state oracle error is not lower than filtered-state error.
4. Hard gating is not justified: held-out `I_alpha` gating improves mass error in several conditions but worsens alpha error broadly and can worsen mass error under mass mismatch. Soft scaling is likewise unsupported by these results.
5. Do not implement gated reduced NLS in Stage 11B. If further estimator work is authorized, test a reduced online parameter UKF first.
