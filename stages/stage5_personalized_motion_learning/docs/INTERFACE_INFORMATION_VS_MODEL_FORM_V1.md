# Stage-5 Interface Identification: Information vs Model Form v1

Status: **exploratory offline diagnostic; Interface Identification v1 remains
inactive and the frozen deterministic controller is unchanged**.

This checkpoint reuses the saved Interface Mismatch v1 traces and the existing
Interface Identification v1 fit/embargo/future-validation contract. It does
not run MuJoCo, publish an interface parameter, change Goal-MPC, or provide a
hardware/clinical identifiability claim.

## Question and evidence separation

Two evidence paths are kept separate:

1. **Estimator self-consistency.** The exact identification predictor generates
   raw robot-cuff pose/twist and cuff-wrench measurements. Those measurements
   pass through the normal truth-free `ShadowInterfaceIdentificationService`,
   so the identifier receives only deployable signals and a nominal-observer
   arrival prior. Generator truth is used only after fitting for error scoring.
2. **Plant-vs-predictor model form.** Saved MuJoCo traces are replayed through
   the predictor with the evaluation-only true interface scales and either the
   evaluation-only consistent window state or an initial state fitted on the
   fit window. The executed commands and sample timing are unchanged.

The exact predictor rollout is exposed as an offline diagnostic object so the
same transition equations—not a copied audit model—produce robot measurements,
Human response, interface state, and base-drive state.

## 1. In-model self-consistency

The split is 0.20 s fit, 0.05 s embargo, and 0.10 s future validation. The
oracle column uses generator parameters and generator initial state only for
evaluation; the estimator never receives either.

| synthetic case | truth `[alpha_t,alpha_r,alpha_d]` | fitted scales | parameter L2 error | validation normalized RMSE | oracle validation RMSE | fixed-truth scales with fitted arrival RMSE | singular values | condition | max correlation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| nominal | `[1,1,1]` | `[0.974,0.989,1.001]` | `0.0287` | `0.0129` | `4.6e-16` | `0.00954` | `[13.83,6.40,2.38]` | `5.82` | `0.897` |
| `Kt x0.7` | `[0.7,1,1]` | `[0.713,1.010,1.003]` | `0.0167` | `0.00554` | `5.5e-16` | `0.00527` | `[15.75,7.18,3.70]` | `4.25` | `0.891` |
| `Kr x1.3` | `[1,1.3,1]` | `[0.734,1.078,0.998]` | `0.346` | `0.1000` | `6.6e-16` | `0.0328` | `[14.64,6.35,2.43]` | `6.04` | `0.945` |
| `D x0.7` | `[1,1,0.7]` | `[0.994,0.998,0.704]` | `0.00765` | `0.00890` | `5.4e-16` | `0.00880` | `[14.50,10.68,3.37]` | `4.30` | `0.804` |

All oracle residuals are numerical roundoff, so the generator and estimator
equations are internally identical. Translational stiffness and common damping
are recovered accurately in these representative in-model cases. Rotation is
not: `alpha_t` and `alpha_r` compensate each other even without plant mismatch.
The projected parameter correlation is `0.945`, and only `29.2%` of the raw
`alpha_r` Jacobian-column norm remains after projecting out the 16-dimensional
arrival state.

All three parameter/latent multistarts converge to effectively the same result
(largest parameter span below `2.3e-6`), so this is not the tested local-start
choice. It is the regularized current-window optimum under the online-style
arrival prior. With the unavailable generator initial state, the true scales
again give a much lower residual (`0.0328`), proving that arrival-state error
and parameter correlation drive the compensation.

### Window length and latent-state dependence

| case | fit window | fitted `[alpha_t,alpha_r,alpha_d]` | parameter absolute error | smallest singular value | max correlation |
|---|---:|---:|---:|---:|---:|
| `Kt x0.7` | 0.10 s | `[0.724,1.011,1.000]` | `[0.024,0.011,0.000]` | `3.19` | `0.771` |
| | 0.20 s | `[0.713,1.010,1.003]` | `[0.013,0.010,0.003]` | `3.70` | `0.891` |
| | 0.40 s | `[0.708,1.006,1.002]` | `[0.008,0.006,0.002]` | `6.54` | `0.872` |
| `Kr x1.3` | 0.10 s | `[0.721,1.046,0.986]` | `[0.279,0.254,0.014]` | `1.55` | `0.944` |
| | 0.20 s | `[0.734,1.078,0.998]` | `[0.266,0.222,0.002]` | `2.43` | `0.945` |
| | 0.40 s | `[0.846,1.199,1.004]` | `[0.154,0.101,0.004]` | `4.84` | `0.864` |

Longer windows increase sensitivity and improve recovery, but do not fully
separate translation from rotation. Numerical rank three is therefore not
evidence of practically independent physical directions.

## 2. MuJoCo plant versus predictor at true parameters

The table uses the evaluation-only true initial Human/interface state. Values
are held-out over the same future-validation interval. The `q` and `dq`
columns are joint-wise RMSE.

| saved case | normalized RMSE, true initial | normalized RMSE, fit-window initial | robot pose RMSE | robot rotation RMSE | force RMSE | moment RMSE | Human q RMSE | Human dq RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| nominal | `2.050` | `0.628` | `8.82 mm` | `1.73 deg` | `1.52 N` | `0.378 Nm` | `0.13/2.82 deg` | `3.75/13.20 deg/s` |
| `Kt x0.7` | `1.421` | `0.464` | `5.97 mm` | `1.32 deg` | `1.69 N` | `0.307 Nm` | `0.16/2.35 deg` | `2.24/10.08 deg/s` |
| `Kt x1.3` | `2.113` | `1.330` | `8.65 mm` | `1.77 deg` | `0.98 N` | `0.658 Nm` | `0.13/2.84 deg` | `4.12/15.64 deg/s` |
| `Kr x1.3` | `0.987` | `0.692` | `3.23 mm` | `1.12 deg` | `3.90 N` | `0.392 Nm` | `0.63/2.47 deg` | `1.44/13.05 deg/s` |
| `D x0.7` | `1.727` | `0.555` | `7.33 mm` | `1.58 deg` | `2.12 N` | `0.458 Nm` | `0.09/2.70 deg` | `1.26/11.48 deg/s` |
| `D x1.3` | `1.321` | `0.425` | `5.41 mm` | `1.33 deg` | `1.67 N` | `0.392 Nm` | `0.26/2.44 deg` | `0.87/11.02 deg/s` |

A fit-window initial state reduces robot-pose prediction error, but requires a
large 2.65--3.38 scaled-L2 shift from the evaluation truth and does not reduce
the physical-wrench residual. This is latent-state compensation, not physical
model closure. At true parameters the interface-state errors themselves are
small (typical translation components below `0.33 mm` and rotation below
`0.18 deg`), while q2/dq2 future errors reach `2.35--2.84 deg` and
`10.1--15.6 deg/s`. The dominant structural residual therefore enters the
coupled Human/execution evolution and then appears in robot pose, rather than
being explained by the Kelvin-Voigt algebra alone.

The current predictor advances a force-driven effective interface oscillator
from a base-drive state updated by executable-command increments. The MuJoCo
plant instead obtains deformation from coupled robot/Human relative kinematics,
including low-level loaded pose/velocity feedback. The control predictor can
be adequate for short-horizon screening without being a physically exact
identification model over a 0.35 s fit/embargo/validation interval.

## 3. Counterfactual parameter landscapes

Only three predeclared local one-dimensional grids are evaluated. Other scales
remain at their evaluation truth; this is not a new robustness sweep.

| saved case / varied scale | tested scales | held-out minimum with true initial state | held-out minimum after fit-window initial-state fit | true scale |
|---|---:|---:|---:|---:|
| `Kt x0.7 / alpha_t` | `[0.5,0.7,0.9]` | `0.5` | `0.9` | `0.7` |
| `Kr x1.3 / alpha_r` | `[1.1,1.3,1.5]` | `1.3` | `1.1` | `1.3` |
| `D x0.7 / alpha_d` | `[0.5,0.7,0.9]` | `0.9` | `0.9` | `0.7` |

`alpha_t` and `alpha_d` do not minimize the evaluation objective at truth even
when the window starts from evaluation truth. `alpha_r` does only with that
unavailable truth state; allowing the fit-window latent state to move changes
its preferred value to `1.1`. Multiple scales also yield close force errors:
the wrong scale is acting as an effective compensation parameter rather than a
recovered physical constant.

## 4. Per-parameter diagnosis

| direction | in-model evidence | plant evidence | diagnosis under current task/predictor |
|---|---|---|---|
| `alpha_t` | `Kt x0.7` recovered within `0.013`; retained information `48%` but high correlation | local held-out minimum moves away from truth and depends on latent-state treatment | **model-form biased**, with additional translation/rotation correlation |
| `alpha_r` | `Kr x1.3` has `0.222` error at 0.20 s, `0.945` correlation, and only `29%` retained information; 0.40 s helps but does not close | minimum is truth only with unavailable truth initialization and shifts with fitted latent state | **weakly/practically unidentifiable and latent-state biased**; physical direction remains unresolved |
| `alpha_d` | `D x0.7` recovered within `0.004` per scale component; retained information `86%` for damping | both true-state and refitted-state grids prefer `0.9` over true `0.7` | **model-form biased** for plant data despite good in-model observability |

Overall classification: **Causal factors A and B both occur**, but B must be
addressed first. New excitation cannot make a structurally biased objective
recover physical parameters reliably.

## 5. Architectural decision

**Decision B — correct the identification predictor before designing a loaded
excitation experiment.**

The smallest justified correction is identification-side only:

- retain raw measured robot-cuff pose/twist as the robot state authority;
- propagate Human cuff pose/twist with the fixed Human model;
- derive interface displacement/velocity from the predicted robot-versus-Human
  relative kinematics at every step;
- compute Kelvin-Voigt wrench algebraically from that relative state;
- drive the robot side through the already defined loaded execution/feedback
  semantics, rather than treating executable-wrench increments as a complete
  force drive for an independent effective interface oscillator.

This correction should first pass the same in-model and saved-trace true-
parameter closure tests. Only after the held-out landscape minimum is near the
true scale and the remaining Jacobian correlations are quantified should a
limited loaded-interface excitation be specified. No correction is implemented
here, and no lower-dimensional physical parameterization is promoted from the
current biased evidence.

Follow-up: `INTERFACE_IDENTIFICATION_PHYSICAL_PREDICTOR_V2.md` implements the
first identification-only relative-kinematics correction. It materially
reduces true-parameter residuals, but its constant diagonal robot response
still produces incorrect held-out parameter minima. That report supersedes the
next-step wording above with a narrower robot-side propagation correction.

## Evidence limitations

- Saved Mismatch-v1 traces predate direct raw robot pose/twist retention. The
  audit reconstructs evaluation-only sensor-equivalent robot kinematics from
  saved plant Human/interface truth; future traces already log raw deployable
  quantities, but no new run was made here.
- Interface velocity truth is an offline finite derivative because the exact
  MuJoCo interface velocity was not saved.
- The OFAT traces and three-point local landscapes do not prove global or
  continuous identifiability.
- The result does not invalidate the frozen predictor as a short-horizon control
  surrogate; it rejects treating it as a physically exact K/D identification
  model without further correction and validation.

Compact machine-readable evidence remains local at
`results/interface_model_form_v1_offline/audit.json`.
