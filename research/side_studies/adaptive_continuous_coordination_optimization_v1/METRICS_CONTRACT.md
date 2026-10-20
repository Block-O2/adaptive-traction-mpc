# Metrics contract — frozen before new candidate results

The original `MOTION_ACCEPTANCE_PROTOCOL.json` is copied byte for byte. Its 10% burden, 0.5 degree, phase/total duration, dose, tracking, moment and force gates remain binding. These are engineering comparison gates, with no clinical interpretation. Feasibility precedes force ranking. A failed/partial run has no ranked J_F.

## Signal and objective grids

Actual Human q/dq are native MuJoCo outputs at 0.00025 s, mapped against independently recorded evaluation-only Human state. Acceleration is `numpy.gradient(dq, native_time, edge_order=2)`; jerk applies the same derivative again. All native samples, including endpoints, are retained. Raw results are mandatory; no diagnostic filtering is applied here. The inherited evaluator additionally reports its unchanged SG5/SG21 sensitivities.

Archived cuff-force vectors are recorded on the original 0.005 s controller trace, including terminal boundary rows. Native-state records do **not** contain native cuff-force vectors. C_F uses the original left quadrature of the force norm, clipping intervals at phase/window boundaries; it must close to the unchanged full-task J_F within 1e-8 N s. A 0.25 ms force curve cannot be reconstructed from these archives. No interpolation is presented as a native force measurement. Moment uses the same frozen quadrature. Actual OUTBOUND/HOLD/RETURN transitions determine phase bounds.

## Motion definitions

All joint-space calculations use radians and equal hip/knee coordinate weights. Joint metrics are reported separately, together with Euclidean combined diagnostics:

- Speed: ||dq||; joint speed is |dq_j|.
- Speed variation: TV(||dq||) = sum |speed[i+1]-speed[i]|.
- Joint velocity TV: sum |dq_j[i+1]-dq_j[i]|. Combined velocity TV: sum ||dq[i+1]-dq[i]||. These are distinct from speed TV and from geometric curvature.
- Acceleration variation: sum |a_j[i+1]-a_j[i]|; combined versions use the Euclidean vector difference.
- Jerk: per-joint p95 absolute, RMS and maximum; combined RMS = sqrt(mean ||jerk||^2). Jerk energy = sum ||jerk[i]||^2 dt_i, with separate joint energies. Units: rad^2/s^5. Raw jerk energy is amplitude/duration dependent and is not a universal comfort score.

## Curvature

For q=(hip,knee), signed planar curvature is det(dq,ddq)/||dq||^3 in rad^-1. It is undefined at rest and changes if the joint coordinate weights change. Primary regularization:

`kappa_eps = det(dq,ddq) / (||dq||^2 + eps^2)^(3/2)`, eps=1e-3 rad/s.

Sensitivity eps=1e-4 and 1e-2 rad/s is mandatory. Unregularized curvature is additionally reported only where speed>eps; its TV sums adjacent valid pairs and never bridges invalid intervals. The valid sample fraction is saved. Regularized curvature TV is sum |delta kappa_eps|. Its derivative is the native time gradient; integral |dkappa/dt| and derivative TV are separately identified if reported. No epsilon is selected to improve correlation. Near-rest behavior can dominate this diagnostic; it has no clinical certification.

## Association and selection

Nonoverlapping 0.5 s and 1 s windows use exact force-integral clipping and native motion summaries. Full-window correlations include phase confounding; within-phase results and lags -1,-0.5,0,0.5,1 s are reported. Windows that cross phases are excluded from within-phase estimates. Positive lag means motion precedes force. No p-values or independent-sample confidence claims are made for autocorrelated deterministic traces. Phase-normalized comparisons and candidate contrasts are descriptive, not causality.

Density means internal reference points per selected existing suffix; it does not mean planner requests or physics samples. Legacy +0.02/+0.05 have three internal partition knots but only one perturbed knot. D1/D2/D3 have one/two/three independently set positional points. Endpoint q/dq/ddq and suffix total duration remain unchanged; every new reference gets its own full original certificate and current-state admission.

Timing probes preserve waypoint positions and total suffix duration while redistributing internal times. Their Hermite segments may change the continuous geometric path, so they are labeled S_PROXY and P+S_PROXY. They do not establish an isolated pure-speed causal effect. Exact nonlinear time warp is a separately diagnosed interface ceiling, not silently compressed into a quintic.

Adaptive placement uses the archived B product of local force accumulation and velocity TV, constrained to an existing certified suffix. This is an offline research prototype using evaluation evidence to design experiments; it is not an online controller consuming Human truth. Further local refinement requires complete task/safety/motion/receipt PASS, lower full J_F, and velocity TV no more than 1% above B; this extra research decision gate does not weaken the original acceptance contract.

All physical STARTs, including cold parents, repeats, forks, failures and partials, enter ATTEMPTS.jsonl. Only a new complete feasible result below 1400.697221 N s triggers frozen independent paired validation on at least two legal prefix conditions. Validation cannot reselect the primary.
