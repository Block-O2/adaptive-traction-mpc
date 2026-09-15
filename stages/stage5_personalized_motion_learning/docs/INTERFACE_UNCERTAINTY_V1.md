# Stage-5 Interface Uncertainty v1 closeout

## Scope

This closes Interface Mismatch v1 and evaluates the smallest deterministic
interface-uncertainty layer justified before Human identification. It starts
from checkpoint `e6ea54b701e2a825cc8558c3e0cae214a1fac777` plus the retained
Mismatch v1 evidence. No old mismatch cell was rerun. No controller parameter,
cost, CEM setting, motion limit, Plant-v1 value, HOLD gain, Safety Filter,
BRAKE, or 200 N gate was changed. No Human adaptation, interface residual
learner, value learner, or RL is active.

## Mismatch v1 reclassification

Evaluation-truth task completion replays the original GoalTaskSpec state
machine using truth q/dq while separately disabling motion-envelope aborts, so
task achievement and envelope compliance are not conflated. For traces that
ended early, truth completion is reported as not demonstrated rather than
assumed impossible.

| unique cell | online task | truth task | online envelope | truth envelope | false negative | false positive | settled-start failure | normal success |
|---|---|---|---|---|---|---|---|---|
| `Kt×0.7` | COMPLETE | COMPLETE | compliant | **q2 acceleration violation** | **yes** | no | no | no |
| nominal | COMPLETE | COMPLETE | compliant | compliant | no | no | no | **yes** |
| `Kt×1.3` | ABORT `TASK_ACCELERATION_LIMIT`, 0.385 s | not demonstrated before truncation | **violation** | compliant up to abort | no | **yes** | no | no |
| `Kr×0.7` | ABORT at t=0 | not started | compliant at t=0 | compliant at t=0 | no | no | **yes** | no |
| `Kr×1.3` | COMPLETE | COMPLETE | compliant | compliant | no | no | no | **yes** |
| `D×0.7` | COMPLETE | COMPLETE | compliant | compliant | no | no | no | **yes** |
| `D×1.3` | COMPLETE | COMPLETE | compliant | compliant | no | no | no | **yes** |

The three defining Mismatch v1 defects are therefore distinct:

- `Kt×0.7`: online false negative. Truth q2 20 ms acceleration reached
  `656.34 deg/s2`, while the nominal online peak was `490.33 deg/s2`.
- `Kt×1.3`: online false positive. The nominal online q2 estimate reached
  `734.07 deg/s2` and aborted, while truth remained at `504.37 deg/s2` through
  the retained trace.
- `Kr×0.7`: state-reconstruction/start-set failure. Nominal-estimator q error
  was `[0.627, 1.595] deg`; q2 exceeded the immutable 1 deg settled-start
  tolerance before MPC began.

## Provisional limited operating set

The predeclared controller-side engineering set is:

- `Kt / Kt_nominal in [0.9, 1.1]`;
- `Kr / Kr_nominal in [0.9, 1.1]`;
- common `(Dt, Dr) / (Dt_nominal, Dr_nominal) in [0.8, 1.2]`.

This is a proposed post-installation verification range, not a hardware-
calibrated confidence interval and not a continuous robustness guarantee. It
was fixed before uncertainty replay and was not narrowed after seeing the
result.

The engineering basis is the observed nominal working deformation: about
5.1 mm translation and 3.4 deg rotation. A ±10% stiffness band keeps the
single-step inverse-deformation sensitivity at roughly sub-millimetre and
sub-degree scale, still material relative to the task tolerance. Rotational
stiffness directly changes orientation and therefore both reconstructed q
coordinates. Translational stiffness primarily shifts reconstructed position
and q. Damping does not change the static loaded equilibrium, but it strongly
changes inferred interface velocity, dq, and transient acceleration; its
provisional range is wider at ±20%. These choices describe a deliberately
narrow research operating band, not expected cuff manufacturing variability.

The earlier ±30% cells remain out-of-set stress evidence. They were not used
as a hardware uncertainty bound.

## Deployable uncertainty method

`InterfaceUncertaintyMonitor` propagates nine deterministic interpretations:
the unchanged nominal record plus all eight corners of the three-dimensional
`Kt/Kr/D` box. Every interpretation consumes the same deployable robot/cuff
pose, twist, measured cuff wrench, timestamps, and nominal Human model. It
maintains its own causal interface history and produces:

- the unchanged nominal q/dq and acceleration point estimate used by MPC;
- empirical min/max q/dq across interface hypotheses;
- causal model-based 20 ms acceleration for every hypothesis;
- once a full 20 ms history exists, a causal dq-difference acceleration for
  every hypothesis as an independent measurement-history check.

The finite range is explicitly empirical. Interior extrema or unrepresented
physics are not proven bounded by its corner values. MuJoCo Human truth is
absent from the online API and is used only by the saved-trace audit.

Decision semantics are conservative without changing physical limits:

- settled start: all hypotheses must satisfy the original start q/dq set;
- phase/HOLD/episode completion: all hypotheses must satisfy the existing
  controller-tightened GoalTaskSpec set;
- velocity: every hypothesis must remain within `[45,75] deg/s`;
- acceleration: every hypothesis model estimate and every available full-
  window causal derivative must remain within `[300,600] deg/s2`.

The GoalTaskSpec remains the phase authority. The uncertainty layer can delay
completion or abort on an empirical range crossing, but cannot loosen a task
tolerance or motion limit. The MPC still uses the nominal state and unchanged
controller model; v1 does not adapt, select, or publish a hypothesis.

## Saved-trace validation

The nominal measurement reconstruction used for counterfactual replay matches
the stored nominal state to at most approximately `3e-8 rad` in q and
`2.8e-6 rad/s` in dq. No plant truth is needed for this reconstruction.

| trace | uncertainty start | first uncertainty decision | evidence |
|---|---|---|---|
| `Kt×0.7` | accepted | abort at 2.955 s | q2 empirical acceleration 719.22 deg/s2; known truth violation is no longer silently compliant |
| nominal | accepted | **abort at 0.060 s** | empirical q2 604.79 deg/s2 from low-K/low-D model corner; causal derivative 489.37 deg/s2 and truth peak 481.89 deg/s2 |
| `Kt×1.3` | accepted | abort at 0.060 s | model-corner q2 633.78 deg/s2; causal derivative 461.50 and truth 504.37 deg/s2; original false positive remains |
| `Kr×0.7` | rejected by existing nominal start check | no MPC | rotational reconstruction failure is explicit |
| `Kr×1.3` | rejected by uncertainty settled-start check | no counterfactual execution | stiffness-induced start-state ambiguity is explicit rather than hidden |
| `D×0.7` | accepted | abort at 0.125 s | causal hypothesis q2 618.61 deg/s2 although truth peak was 482.75 deg/s2 |
| `D×1.3` | accepted | abort at 0.055 s | model-corner q2 649.77 deg/s2 although truth peak was 487.73 deg/s2 |

The method closes the known `Kt×0.7` false-negative path, but it does so by
introducing false positives. Most importantly, even the nominal matched trace
would abort after 60 ms. This violates the required nominal usability
criterion. The failure is not caused by CEM, force gating, or a widened
physical limit; it is the overlap between interface-induced q/dq uncertainty
and the existing narrow acceleration envelope.

No new nominal episode and no predeclared low/high-corner holdout plants were
run after this stopping condition. Running them could not restore the already
failed nominal counterfactual criterion, and narrowing the range until nominal
passes would be result-driven tuning.

## Endpoint: B

**B. Fixed nominal plus conservative finite-range monitoring is not useful for
the stated limited operating set. The next justified module is low-dimensional
online interface identification before Human identification.**

The identification target should remain the three low-dimensional scales used
here (`Kt`, `Kr`, and common `D`), retain a frozen nominal fallback, and publish
parameters only after causal consistency checks. Its purpose is to shrink the
empirical state/acceleration ambiguity enough for useful completion and
envelope decisions. It must not learn a black-box residual, change registered
limits, or begin Human/value learning at the same time.

This task does not implement that identifier. Interface mismatch is therefore
not ready to close under endpoint A; the remaining blocker is parameter
observability and trustworthy online set contraction.

## Evidence

The final read-only aggregate is
`results/interface_uncertainty_v1_audit02/saved_trace_audit.json`. It records
zero new plant runs. The preliminary audit output remains local and ignored;
neither file is intended as formal or hardware evidence.
