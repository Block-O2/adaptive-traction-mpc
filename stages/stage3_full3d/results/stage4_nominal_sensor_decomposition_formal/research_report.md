# Stage-4 Nominal Sensor-Mechanism Decomposition Report

Status: completed `formal_user_run_unreviewed` engineering evidence. All six requested 32 s rollouts completed mechanically; no 23 s reference completed within the wall-time window. No controller, estimator, trust, pacing, MPC, allocator, trajectory, safety, or patient parameter was changed.

## Aggregate results

| sensor regime | first qualification / promotion s | promotions / rejections | max active bounds / max violation spans | tracking RMSE prior -> adaptive deg | clean-oracle RMSE prior -> adaptive Nm | mean speed / final phase s | reference complete |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ideal_200hz` | none / none | 0 / 3 | 4 / 1.485 | 0.053076 -> 0.053076 | 0.000000 -> 0.000000 | 0.5000 / 16.00 | no |
| `noise_200hz` | none / none | 0 / 2 | 5 / 6.424 | 0.410351 -> 0.410351 | 0.000000 -> 0.000000 | 0.5000 / 16.00 | no |
| `noise_bias_drift_200hz` | 17.74 / 17.74 | 1 / 2 | 6 / 10.504 | 0.433063 -> 0.424941 | 0.000000 -> 0.071029 | 0.6913 / 22.12 | no |

The prior/adaptive pacing traces are identical within each regime. Ideal and noise-only never qualify, remain at speed scale 0.5 for the full 32 s, and accumulate 16.00 s (69.57%) of reference. The bias+drift pair qualifies at 17.74 s, spends 18.76 s at minimum speed and 11.24 s at nominal speed, and reaches 22.12 s (96.17%). Its extra progress is a shared qualification/pacing effect, not an effect of applying the adaptive model.

No arm recorded a force-gate, ROM, unintended-contact, torque-saturation, joint-limit, MPC-solver, or MuJoCo-warning event.

## Causal mechanism

### Ideal sensing

Ideal wrench measurement error is exactly zero, while the existing state/geometry reconstruction still has small nonzero error (hip/knee state RMSE 0.0325/0.0615 deg; acceleration RMSE 0.2613/0.5574 rad/s2). The identifier creates candidates, but the three completed decisions are rejected: none establishes the registered held-out advantage over the exact prior. Therefore no model qualifies, the control beta remains the exact prior, and clean-oracle control-model error remains 0 Nm in both arms.

### Zero-mean noise plus frozen preprocessing/reconstruction

Noise-only increases force/moment measurement-channel RMS error to 1.1619 N / 0.2040 Nm and state RMSE to 0.2040/0.5104 deg. It also creates stronger bounded candidates (up to five active bounds and 6.424 spans maximum unconstrained violation), but both completed challengers are rejected. The most favorable completed look has candidate-minus-prior measured MSE mean -0.001921 Nms2 with upper bound +0.001486 Nms2, so ordinary zero-mean noise plus this frozen preprocessing/reconstruction path is not sufficient for trusted promotion in this seed and observation window.

### Added bias and drift

Bias+drift increases force error to 1.9833 N and produces the strongest bound pressure (six active bounds; 10.504 spans maximum unconstrained violation). Challenger 0 is rejected. Challenger 1 reduces training residual from 0.3853 to 0.0621 Nms and, at the first eight-block look, has candidate-minus-prior held-out measured MSE mean -0.01910 Nms2 with registered HAC bounds [-0.02677, -0.01142]. Both reference upper bounds are below zero, so it qualifies and is promoted at 17.74 s exactly under the frozen rule.

The same promoted candidate worsens post-decision clean-oracle prediction from 0.0000 to 0.1098 Nm. Once applied, full-rollout control-model oracle RMSE changes from 0 to 0.0710 Nm. Tracking RMSE changes from 0.433063 to 0.424941 deg (-1.88%), while maximum error is unchanged. Thus the model is better for the measured trust target and slightly better for tracking, but worse as a clean physical dynamics model.

## Interpretation

The exact nominal prior is essentially untouched under ideal sensing. Zero-mean noise plus the existing preprocessing path creates large compensating candidates and bound pressure but no trusted promotion here. Adding systematic bias/drift is the condition that turns measured-domain compensation into statistically trusted promotion, and it also yields the strongest pressure and oracle degradation.

This supports the phrase **control-effective compensation model** over **physical patient identification model** for the current estimator. It does not show a trust-lifecycle bug: the ideal and noise-only proposals are rejected when their registered upper bounds do not establish improvement, and the biased candidate is promoted only when held-out measured evidence does. Oracle error never enters that decision.

The conclusion is limited to one seed and cumulative existing sensor regimes. It cannot separate noise from preprocessing, bias from drift, or estimate promotion frequency. No threshold or parameter change is supported by this experiment.

## Next scientific question

Keep the frozen controller/trust lifecycle and preregister a multi-seed repeat of this same three-regime decomposition if the next goal is to distinguish a reproducible systematic nuisance effect from seed-specific trust variability. A later bias-only versus drift-only split would require new sensor configurations and therefore a separate preregistration; it is not implied by this result.
