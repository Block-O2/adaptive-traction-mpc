# Single-Link Spring2D Research Closeout

## 1. Research question

This phase asked whether a compliant single-link traction task could be
completed by model-predictive control while online state and parameter
estimation supplied a sufficiently accurate model for adaptive control. The
work separated three questions that must not be conflated:

- can the modeled task be completed under known state and parameters;
- can state and physical parameters be inferred from the passive task
  trajectory;
- does the resulting adaptive closed loop retain the tested motion and
  constraint behavior?

All conclusions below are empirical simulation conclusions. They are not
formal safety, stability, robustness, or identifiability guarantees.

## 2. Spring2D system definition

The simulated state and action are

```text
x = [theta, omega, r, r_dot]
u = [F_tan, F_rad]
delta_r = r - L0
alpha_k = (omega[k+1] - omega[k]) / dt
```

The task crossing criterion is the true simulated
`theta >= theta_target`, with `theta_target = pi/2` in the main configuration.
Near-target tolerances are not counted as crossing.

The online physical-parameter path estimates `[m, k, b_r]`: link mass, radial
spring stiffness, and radial damping. Later audits use the inverse-mass affine
coordinates
`[lambda, kappa, beta] = [1/m, k/m, b_r/m]`. Gravity, nominal length,
angular damping, force transmission, and integration step remain fixed model
inputs; they were not silently adapted.

The compact fixed-MPC configuration uses the tested planning limits
`|F_tan| <= 35 N`, `|F_rad| <= 1 N`, `|delta_r| <= 0.06 m`,
`|omega| <= 1.2 rad/s`, and `|alpha| <= 3 rad/s^2`. The reviewed
planner/tracker line uses the same physical quantities, with alpha handled by
the long-horizon plan and an explicit tracker slack/violation diagnostic.
These are controller constraints and empirical checks, not proof that every
realized trajectory is safe. The broader simulator action and termination
limits in `configs/spring2d.yaml` are not substitutes for the MPC limits.

## 3. Final controller architecture

The final researched architecture is hierarchical:

1. A one-shot long-horizon crossing planner constructs a feasible reference.
2. A short-horizon multiple-shooting NMPC tracker follows the state/action
   reference and records constraint slack and solver diagnostics.
3. A bias-aware UKF estimates state from noisy observations.
4. A filtered Windowed NLS / affine identifier estimates `[m, k, b_r]`.

Planner and tracker model parameters are frozen within each optimization solve
and may change only between control steps. The oracle, state-error-only,
parameter-error-only, fixed-nominal, and full-adaptive modes are isolated in
the Stage 9J audit. Event-triggered replanning is not part of the retained
primary architecture.

## 4. What worked

- The checked-in Spring2D dynamics, environment, fixed MPC baseline, and core
  regression tests provide a reproducible single-link simulation base.
- Known-state/known-parameter scaled NMPC completes the tested nominal task.
- A long planning horizon followed by a short tracking horizon resolves the
  initial-angle-offset failure seen with the short-horizon controller alone.
  The oracle planner/tracker crossed in 3/3 initial-offset runs and in 3/3 runs
  for each retained Phase 2 condition, with no tracker failure in those
  aggregates.
- The full adaptive planner/tracker crossed in all 24 Stage 9J primary runs,
  while the matched fixed-nominal mode crossed in 0/24. This crossing result
  does not erase the adaptive mode's larger true-alpha tails.
- The exact simulator transition closes the saved replay exactly, and its
  local true-state Jacobian retains three numerical parameter directions under
  the registered audit.

## 5. What failed

- The short-horizon controller alone did not reliably produce the required
  initial-offset crossing.
- The filtered UKF-to-Windowed-NLS cascade did not establish reliable,
  separately calibrated physical-parameter estimates. Robust Huber and Cauchy
  losses did not pass their offline gate.
- Adaptive crossing did not imply superior constraint behavior. Parameter error
  dominated the measured adaptive-oracle true-alpha gap, and stronger noise
  produced large alpha tails.
- The tested fixed-weight online single- and multiple-shooting MHE routes did
  not pass their declared accuracy, failure-rate, timing, or alpha gates.
- Information gating and a stable passive reduced-parameter subspace were not
  supported by the retained audits.
- A fixed block-aware uncertainty correction worsened rather than repaired
  lambda truth coverage under its preregistered treatment.

Negative and mixed results are retained as scientific evidence; none was
removed or tuned away during closeout.

## 6. Root-cause evidence

The final evidence supports the following mechanism chain:

1. **Control feasibility is not the primary blocker.** Fixed/oracle MPC and the
   oracle planner/tracker complete the modeled task.
2. **Estimated-state EIV matters.** Stage 9K shows a large gap between
   UKF-input and true-state replay parameter error, and Stage 11C materially
   improves two-dimensional truth inclusion when true states replace estimated
   states.
3. **EIV is incomplete.** In Stage 11C, true-state one-dimensional lambda truth
   inclusion is still only 0.494, practical identifiability is not established,
   and some metrics do not improve monotonically.
4. **Simple dependent-residual calibration is insufficient.** Stage 11E changes
   overall lambda coverage from 0.494 to 0.266 (gain -0.228); zero of eight
   conditions gains at least 0.10, while the WLS point estimate remains fixed.
5. **The affine construction has structured point bias.** Stage 11D observes
   structured true-parameter residuals and truth-score projection. Stage 11F
   then obtains exact-discrete weighted residual RMS and exact/affine residual
   ratio equal to zero in every one of 710 windows, supporting the reviewed
   finite-difference/continuous-regression formulation-bias interpretation.
6. **Exact-discrete local information does not collapse.** The reviewed Stage
   11G matrix has 24 runs and 710 windows, exact rank-3 fraction 1.0, overall
   median exact/affine conditional-lambda-information ratio 689.197, all eight
   conditions above the retained-information criterion, and mechanically
   stable central differences.
7. **Recovery is still unknown.** The exact-discrete result is evaluated at
   true states and true parameters. No exact-discrete optimizer or estimator
   was fitted.

The value 689.197 is an information ratio, not a predicted multiplier for
parameter accuracy.

## 7. Final scientific conclusions

- The single-link control architecture is feasible in the tested simulator
  when state and parameters are accurate.
- The present adaptive identifier is the limiting component of the tested
  adaptive pipeline; crossing success alone is not enough to claim improved
  closed-loop quality.
- Estimated-state EIV contributes to the identification problem, but does not
  fully explain it.
- The retained affine finite-difference regression introduces formulation bias
  on this replay.
- The simulator's exact discrete mapping is internally consistent with the
  replay and retains local true-state parameter information.
- No evidence in this repository demonstrates that an exact-discrete
  identifier can actually recover parameters, remain calibrated under noise,
  or improve the adaptive closed loop.

## 8. Limitations

- Simulation-only, single-link evidence.
- Passive rehabilitation-like trajectories rather than designed active
  excitation.
- A single model family and saved Stage 9J replay dominate the later diagnosis.
- True-state audits are oracle diagnostics, not deployable estimators.
- Local rank and information do not prove global or practical identifiability.
- The exact transition's replay closure partly reflects use of the same
  transition implementation that generated the replay.
- No formal safety/stability proof, hardware validation, linkage dynamics, robot
  SDK integration, or human-interaction validation.
- Historical generating revisions are unavailable for some early reviewed
  Stage 9 artifacts.

## 9. Reproducibility, source paths, and final file inventory

Core paths:

- Dynamics and integration:
  [`src/traction_mpc/models/spring2d_dynamics.py`](../../src/traction_mpc/models/spring2d_dynamics.py)
- Environment:
  [`src/traction_mpc/envs/spring2d_env.py`](../../src/traction_mpc/envs/spring2d_env.py)
- Fixed/adaptive MPC:
  [`src/traction_mpc/mpc/`](../../src/traction_mpc/mpc/)
- UKF-bias state estimation:
  [`src/traction_mpc/estimation/ukf.py`](../../src/traction_mpc/estimation/ukf.py)
- Windowed identifier:
  [`src/traction_mpc/identification/windowed_ls_identifier.py`](../../src/traction_mpc/identification/windowed_ls_identifier.py)
- Planner/tracker and mode audit:
  [`scripts/run_spring2d_stage9h_planner_tracker.py`](../../scripts/run_spring2d_stage9h_planner_tracker.py)
  and
  [`scripts/run_spring2d_stage9j_gap_decomposition.py`](../../scripts/run_spring2d_stage9j_gap_decomposition.py)
- Main configurations:
  [`configs/spring2d.yaml`](../../configs/spring2d.yaml),
  [`configs/spring2d_fixed_mpc.yaml`](../../configs/spring2d_fixed_mpc.yaml), and
  [`configs/spring2d_safety_aware_cem.yaml`](../../configs/spring2d_safety_aware_cem.yaml)
- Tests: [`tests/`](../../tests/)

The canonical fixed-MPC demo was executed once during closeout as a
non-scientific interface check. It exited normally at `max_time` after 802
steps, with final angle 89.97 degrees, maximum radial deformation 0.012 m,
maximum tangential/radial force 8.77/0.76 N, and maximum true alpha
42.175 rad/s². Because it did not satisfy the strict 90-degree crossing and its
true alpha exceeded 3 rad/s², it is not counted as controller-success evidence.
No parameter or configuration was changed in response.

Curated final evidence:

| Evidence | Retained compact files |
|---|---|
| Stage 11C paired state source | report, state-source summary, command, resolved config, manifest, mechanical status |
| Stage 11D residual/coverage | report, condition summary, command, resolved config, manifest, mechanical status |
| Stage 11E block calibration | report, condition summary, command, manifest, mechanical status |
| Stage 11F exact closure | report, condition summary, command, manifest, mechanical status |
| Stage 11G exact information | report, condition summary, command, manifest, mechanical status |

No new GIF is retained: the closeout conclusions depend on aggregate metrics,
not a visually selected trajectory.

The omitted full window/profile tables remain locally under the ignored
`results/local/archive/single_link_closeout/` tree. Their closeout SHA-256
values are:

| Local archived artifact | SHA-256 |
|---|---|
| `stage11c_state_source_audit/paired_profile_summary.csv` | `d3eb915f8143d5115c79db6aaec5446fa6c486600903edd2ec3102b67ad1e83d` |
| `stage11c_state_source_audit/paired_window_metrics.csv` | `a3983cac469a1a1530dd61e4040561ce09e54575d3cd57dd22d3b818917b4855` |
| `stage11d_residual_coverage_audit/window_residual_diagnostics.csv` | `d8e17700cbee6a2288ffe54f18ff95e04e344f9538a22f33b030676870c2890b` |
| `stage11e_block_coverage_calibration/window_calibration_metrics.csv` | `5dd6acd051cdec04cce17cab6a5ec0f4f12e8a3005d6288b7ce812a09545169f` |
| `stage11f_discrete_closure_audit/window_discrete_closure_metrics.csv` | `0c77a3308e38f5ffbef1ec2e8b334c1b97d373e89e211cfd36e09b5c1d8455c3` |
| `stage11g_discrete_information_audit/window_discrete_information_metrics.csv` | `8cfb51572a349b36a40719dc3d899720bc3b86832e3b627a05e7de934e0b260b` |

These local paths are not part of a clone. The retained scripts, replay,
specifications, commands, summaries, and manifests provide the sequential
reproduction route.

Final active-file disposition:

- **KEEP — active/final:** core Spring2D dynamics and environment; fixed and
  adaptive MPC components; planner/tracker implementation; UKF and Windowed NLS
  implementation; main configurations; tests; the fixed-MPC minimal demo; the
  replay; closeout documentation; curated reports and summaries.
- **KEEP — historical research:** Stage experiment runners, MHE
  implementations, estimator ablations, diagnostic utilities, `legacy/`, and
  negative-result reports. They remain because they are the only direct
  implementation/evidence trail for reviewed failures or because no verified
  exact replacement exists.
- **REMOVED:** the unfinished `professor_progress_update/` HTML and generated
  assets (presentation-only); five local Stage 11C–11G smoke directories
  (disposable mechanical checks superseded by full formal artifacts); Python,
  pytest, and editor caches (recomputable). No tracked scientific source or
  reviewed result was deleted.
- **RELOCATED, NOT REMOVED:** complete untracked Stage 11C–11G formal
  directories were preserved in the ignored local closeout archive before the
  compact subsets were restored at their standard result paths.

## 10. Closed branches

- Short-horizon-only crossing for the initial-offset case.
- Event-triggered replanning as a primary architecture.
- Robust-loss Windowed NLS ablations.
- Fixed-weight online MHE.
- Hard/soft information gating from the tested passive metrics.
- A stable passive reduced-parameter subspace.
- Fixed block-aware lambda coverage calibration.
- Continuous affine finite-difference identification as an unbiased recovery
  route on this replay.

Stage 11H is cancelled by phase decision; it is not a failed experiment.

## 11. Explicitly untested questions

- Exact-discrete offline parameter recovery with true states.
- Exact-discrete recovery with estimated states or noisy observations.
- Calibration, bias, convergence, and computation time of such an estimator.
- Online exact-discrete identification and closed-loop adaptive planner/tracker
  behavior.
- Benefits of deliberate active excitation.
- Robust/safe adaptive MPC based on defensible uncertainty bounds.
- Multi-link, contact-rich, hardware, and human-interaction behavior.

## 12. Reason for stopping this phase

The professor reviewed the direction and closed the single-link phase. The
repository therefore stops at a bounded mechanism diagnosis rather than
implementing Stage 11H. This decision is a scope decision, not a claim that
exact-discrete parameter recovery has been solved or disproved.

## 13. Next-phase handoff

The next phase should be maintained separately and begin from the
professor-supplied MATLAB linkage reference program. The first work should be a
dynamics, state/action, parameter, constraint, integration, and controller
audit against that reference. Only after the reference behavior is understood
should it be connected to a new simulator/controller stack and extended toward
end-effector grasping and upper/lower-limb rehabilitation.

The MATLAB program has not been imported, and no linkage implementation belongs
to this closeout. A suitable empty repository name is
`adaptive-linkage-rehabilitation-mpc`.

## Post-closeout organizational note

A later organizational decision keeps the linkage phase under `linkage/` in
this repository.
