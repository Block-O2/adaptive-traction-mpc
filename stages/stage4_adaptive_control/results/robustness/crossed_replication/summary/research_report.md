# Stage-4 crossed excitation replication final report

Evidence reviewed: `formal_user_run_unreviewed`. Scope is simulation/engineering only.

## Integrity verdict

The exact 18-pair/36-arm matrix is mechanically complete: 16 new pairs and two preregistered read-only bridges. All required JSON/NPZ/Markdown artifacts exist; JSON is strict, NPZ traces are readable and finite, factor/runtime/config/baseline provenance matches, no smoke marker is present, A/B pre-promotion isolation and prior-only population-beta invariants pass, and all embargo/non-overlap/single-challenger checks pass.

The two bridge pairs were not copied or rerun. Their ten preregistered JSON/NPZ SHA-256 values were reverified, together with source configuration/provenance and finite traces. Final artifacts cannot prove the entire historical absence of overwrite, but contain no evidence of overwrite, config drift, or warm-start leakage.

This completed audit makes the study eligible for promotion to authoritative formal evidence. Canonical per-run artifacts remain unchanged and retain their original `formal_user_run_unreviewed` labels; promotion is an evidence-review decision, not a rewrite of those files.

## Aggregate outcomes

- Control promotion occurred in 18/18 cases; 0 retained the prior.
- Both arms completed in 18/18 cases; 0 cases ended early.
- Tracking RMSE improved in 18/18 and torque-prediction RMSE improved in 18/18.
- 2 cases improved tracking RMSE while worsening maximum tracking error.
- First promotion among promoted cases ranged from 9.72 to 15.36 s (mean 11.14 s).

## Matched-slice findings

### Descriptive trajectory aggregates

| trajectory | cases | promotion time mean [min, max] s | remaining mean % | tracking benefit mean % | prediction benefit mean % |
|---|---:|---:|---:|---:|---:|
| `hip_dominant_low_knee_23s` | 6 | 10.86 [9.74, 15.36] | 76.4 | 7.18 | 12.15 |
| `registered_high_flexion_23s` | 6 | 9.86 [9.72, 10.02] | 78.6 | 7.58 | 15.15 |
| `two_cycle_moderate_23s` | 6 | 12.71 [11.98, 13.08] | 72.4 | 7.25 | 12.40 |

All three regressors are structurally rank 11, so practical conditioning and information strength—not rank alone—separate them:

| trajectory | rank | cond(Z) | cond(X) | information lambda min | information trace | leading weakest component |
|---|---:|---:|---:|---:|---:|---|
| `registered_high_flexion_23s` | 11 | 349.05 | 1217.07 | 0.0302562 | 55865.49 | `b_distal_inertia_combination` |
| `hip_dominant_low_knee_23s` | 11 | 108.64 | 6118.80 | 0.00118871 | 51334.29 | `b_distal_inertia_combination` |
| `two_cycle_moderate_23s` | 11 | 19638.87 | 95364.89 | 5.72748e-06 | 60076.00 | `b_distal_inertia_combination` |

Two-cycle has by far the poorest practical conditioning despite full rank. Hip-dominant is qualitatively different: its column-normalized condition is lower than anchor, but raw condition is worse and minimum information eigenvalue is about 25 times smaller, consistent with joint-specific imbalance rather than uniformly weak information.

### A. Fixed patient + seed: trajectory excitation

There are 9 preregistered matched trajectory contrasts. Anchor versus two-cycle promotion patterns were: registered_stage2_mild_anchor@54113=poorer_later, registered_moderate_anchor@64122=poorer_later, registered_formal_perturbed_anchor@44104=poorer_later.

Two-cycle was later and left less remaining trajectory than anchor in all three matched contrasts. Its prediction benefit was smaller in 3/3, while its tracking benefit was smaller in 2/3; timing is consistent, downstream benefit magnitude is not universally weaker.

Hip-dominant was later than anchor once and tied twice; two-cycle was later than hip-dominant in all three comparisons. It is timing-intermediate/equal in these slices, but qualitatively seed-sensitive, is the only trajectory family with rejections (five total), and accounts for both cases where RMSE improved while maximum error worsened; it is not a simple scalar midpoint.

### B. Fixed trajectory + seed: patient mismatch

Across 9 matched patient contrasts, the stronger configured mismatch had larger tracking benefit in 6 and larger prediction benefit in 9. Stronger mismatch therefore does not consistently yield larger benefit; the selected patients are composite mechanisms rather than a scalar dose.

### C. Fixed patient + trajectory: measurement seed

Promotion status changed in 0/9 seed contrasts. For cells where both seeds promoted, the mean absolute timing change was 0.84 s and the maximum was 5.54 s. Tracking-benefit sign changed in 0 cells and prediction-benefit sign changed in 0 cells.

The incomplete balanced design does not repeat the same two-trajectory contrast under two seeds within one patient. It can show seed sensitivity and whether matched trajectory patterns span all three seeds, but cannot separately identify a seed-caused reversal of trajectory ordering or an unrestricted three-way interaction.

## Prediction versus tracking

Prediction benefit versus tracking benefit had descriptive Pearson r=0.176 and Spearman rho=0.284, with matching signs in 18/18 cases. This is association within a small fixed simulation matrix, not a threshold, population estimate, or guarantee that prediction improvement produces tracking improvement.

## Negative and mixed evidence

No-promotion cases: none.

Early-termination cases: none.

Tracking-RMSE improvement with worse maximum error: registered_stage2_mild_anchor__hip_dominant_low_knee_23s__seed64122, registered_formal_perturbed_anchor__hip_dominant_low_knee_23s__seed54113.

No promotion means trust retained the prior; it is not automatically a controller failure. Shared early termination is reported separately and is not attributed to excitation alone. Interaction force, moment and cylindrical surface proxy remain descriptive and support no safety, comfort, pressure or tissue-load claim.

## Preregistered hypothesis verdicts

| hypothesis | verdict | basis |
|---|---|---|
| H1 poorer practical excitation tends to delay qualification/promotion | **supported** | the poorer trajectory was later in 7/9 matched contrasts, tied in 2, and earlier in 0; two-cycle was later than anchor in 3/3 |
| H2 stronger mismatch does not necessarily imply larger adaptive benefit | **supported** | stronger mismatch had larger tracking benefit in 6/9 matched patient contrasts and larger prediction benefit in 9/9; benefit is not consistently ordered |
| H3 prediction improvement generally associates with tracking improvement | **conditionally supported** | descriptive Pearson r=0.176, Spearman rho=0.284; association is not a casewise guarantee |
| H4 seed may change timing/status but should not systematically reverse the excitation pattern | **conditionally supported** | promotion status changed in 0/9 fixed patient/trajectory seed contrasts, while promotion time changed by up to 5.54 s; the fractional matrix does not repeat one trajectory contrast at two seeds within the same patient, so seed-caused ordering reversal is not separately identifiable |
| H5 poor excitation may reduce remaining adaptation time without preventing promotion | **supported** | two-cycle promoted in all six cases and was later than anchor in 3/3 matched contrasts, leaving 6.09, 6.09, and 7.00 percentage points less trajectory |

## Conclusion and next step

Natural rehabilitation excitation remains a conditional source of one-shot adaptive information. Practical conditioning affects when useful control adaptation becomes available, but patient mismatch and measurement realization materially modify the chain, and neither structural rank nor mismatch magnitude alone predicts benefit. Identified beta remains a measured-channel/control-effective model, not recovered physical patient truth.

The next justified study is a separately preregistered model-inadequacy replication using the same small matched-slice discipline and frozen controller, varying one unsupported mechanism at a time. Do not add active excitation or retune weak trajectories merely to force promotion.
