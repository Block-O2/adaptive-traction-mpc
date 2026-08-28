# Stage-4 11-base dynamics trust-rule recommendation

## Scope

This is an offline diagnostic using the saved registered baseline-CEM and
ungated-hybrid traces. The production estimator, physical bounds, gates,
controller, trajectory, confidence pacing, and safety limits were not changed.

## Diagnosis

The current gate declares a bound hit when the constrained solution is within
`1e-7` in raw parameter units of a box face. That quantity is solver slack, not
evidence that the data require the physical constraint.

At the first dynamics attempt, both modes have full SVD/RRQR rank 11 and pass
the existing conditioning, residual, and positive-definite-mass checks:

| mode | wall/phase (s) | cond | residual (Nms) | unconstrained `bv2` | lower bound | violation/span | constrained slack | current result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline CEM | 6.50/3.25 | 25,937 | 0.00621 | 1.04572 | 2.5 | 29.09% | 5.02e-7 | accepted |
| ungated hybrid | 6.48/3.24 | 31,501 | 0.00560 | 1.72008 | 2.5 | 15.60% | 4.44e-8 | rejected |

Thus the opposite decisions are caused only by where the bounded solver stops.
The unconstrained optima in both cases materially prefer an infeasible `bv2`.

## Numerically robust definition of a materially required bound

Let the unconstrained regularized estimate be `beta_u`, parameter spans be
`s_i = upper_i - lower_i`, and define the dimensionless signed violation

`v_i = max((lower_i - beta_u_i)/s_i, (beta_u_i - upper_i)/s_i, 0)`.

Solver distance of the constrained estimate from a bound must not enter this
definition. To distinguish a real data-supported violation from estimation
noise, estimate a correlation-aware standard error `se_i` (block bootstrap or
sandwich covariance is needed because the integral windows overlap) and use a
pre-registered one-sided confidence level:

`material_i = v_i > z_(1-alpha) * se_i/s_i`.

Equivalently, the one-sided confidence interval for `beta_u_i` lies wholly
outside the feasible interval. `alpha` is a scientific false-classification
choice and must be registered independently of baseline/hybrid outcomes.

## Recommended two-status rule

An active physical bound should not automatically mean that the constrained
model is unusable. It means that full 11-parameter interior identification is
not supported by those data. Keep two distinct statuses:

1. **Interior parameter trust**: no statistically material bound requirement,
   existing rank/conditioning/residual checks pass, and the model is physically
   valid.
2. **Boundary-supported model trust**: a material active set is allowed only
   when the constrained KKT solution is valid, the free/tangent subspace is
   identifiable (`rank(YT) = dim(T)` with acceptable conditioning), the mass
   matrix remains positive definite on the registered operating domain, and a
   causal held-out prediction comparison establishes non-degradation against
   the retained model (for example, an upper confidence bound on the held-out
   loss difference is at most zero).

The active-set flag and one-sided uncertainty remain exposed as information or
parameter confidence even when model trust is granted. In-sample residual and
full rank alone are insufficient.

The saved registered-true trajectory provides an oracle diagnostic: all 52
hybrid candidates and 29 of 30 non-bound-gate-viable baseline boundary
candidates have lower generalized-torque RMSE than the population prior. This
shows why blanket rule A can discard useful predictive models. It does not
validate rule B online, because registered true parameters are unavailable and
the current production estimator has no causal held-out predictive gate.

## Effect on prior Stage-4 evidence

The raw tolerance sweep changes the outcome:

| raw `atol` | baseline accepted / first trust | hybrid accepted / first trust |
|---:|---|---|
| 1e-8 | 3 / 6.50 s | 1 / 6.48 s |
| 1e-7 (production) | 3 / 6.50 s | 0 / none |
| 1e-6 | 1 / 11.50 s | 0 / none |

Baseline trust at 6.50 s is therefore a numerical boundary-detection artifact.
The first baseline candidate with no unconstrained box violation and all other
current gates passing occurs at wall time 11.50 s, reference phase 7.24 s. No
hybrid candidate has zero unconstrained violation; its minimum maximum
violation is 15.60% of a parameter span.

Any earlier result whose behavior was switched specifically by the 6.50 s
trust event (notably trust-gated refinement timing and confidence pacing) is
not robust to a scientific trust rule and needs revalidation only after that
rule is approved and implemented. The saved predicted-versus-realized model
exploitation evidence and the structural cuff-allocation/Pareto conclusions do
not depend on the `isclose` decision itself.

## Freeze verdict

The validated 11-base integral representation, physical box, and estimator
formulation can remain unchanged. The complete estimator subsystem cannot yet
be frozen because its production trust gate is numerically non-robust. No
production change is made by this audit.
