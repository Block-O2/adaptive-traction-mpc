# Stage-5 Human-ID shadow v1 diagnostic

## Decision

**H-B — REPARAMETERIZE / REDUCE.** The path-free Stage-5 task contains useful
Human dynamics information, but the complete 11-beta representation is
practically too correlated for closed-loop publication. No Human adaptation is
activated, and no closed-loop A/B is preregistered.

This is a four-case diagnostic under the fixed nominal Plant-v1 interface and
the fixed controller interface model. Goal-MPC kept the nominal Human model in
all cases. The interface bank, interface adaptation, terminal value, and RL
were inactive. The conservative Simple Interface Robustness v1 planning values
were retained: 180 N predicted-force ceiling and path-free `[15,25] deg/s`
planning pace. The current acceleration-screen implementation was not rolled
back or retuned.

## Task and identification result

| Human case | online result | phases / duration | ID attempts | shadow decisions | first trusted time | beta11 condition / max correlation | scale3 condition / max correlation |
|---|---|---|---:|---|---:|---:|---:|
| nominal | COMPLETE | H 2.110, R 2.610, C 4.935 s | 2 | 1 future reject, 1 pending | none | 994.1 / 0.999919 | 1.333 / 0.279 |
| mass +8% | ABORT, acceleration | OUTBOUND only, 0.270 s | 0 | no complete fit window | none | no information | no information |
| stiffness +15%, rest `[-2,+2] deg` | COMPLETE | H 2.450, R 3.145, C 5.080 s | 3 | 2 shadow publications, 1 pending | 3.045 s | 1228.2 / 0.999814 | 1.337 / 0.283 |
| damping +20% | COMPLETE | H 2.310, R 2.810, C 5.060 s | 2 | 1 future reject, 1 pending | none | 1325.4 / 0.999960 | 1.353 / 0.293 |

Across all seven attempted fits, none hit a parameter bound. There were two
future-qualified shadow publications, two future rejections, and three
challengers still pending when their episodes ended. Numerical beta11 rank was
11/11 in each complete episode, but the smallest normalized singular values
were about `0.00145--0.00193`; numerical full rank does not overcome the nearly
unit parameter correlations.

The three-scale Stage-4 control-effective projection (common effective mass,
passive stiffness, and damping) was 3/3 rank in all three complete episodes,
with much milder conditioning. This is diagnostic evidence for the H-B next
step, not validation of a reduced identifier or permission to use it in
control.

## Causal future prediction

The nominal case's first candidate reduced fit-window integrated-torque RMSE
from `0.01324` to `0.00335 Nms`, but failed all 8/10/12 future looks and was
rejected at 3.845 s. The damping candidate similarly reduced training RMSE
from `0.05105` to `0.00258 Nms` yet failed future validation. Those outcomes
are evidence that training-fit improvement alone can be compensation or
overfit.

The stiffness/rest case passed its first eight-block future look at 3.045 s
and a second challenger passed at 4.845 s. Its final shadow beta reduced
whole-phase integrated-torque RMSE by `18.78%` in OUTBOUND, `18.81%` in HOLD,
and `17.91%` in RETURN. Evaluation-only beta distance also decreased modestly
from `0.5343` to `0.4899` in prior-normalized L2 coordinates. However, the
11-beta maximum correlation remained above `0.9998`; this supports a useful
control-effective direction, not independent physical/anatomical recovery.

HOLD contains fewer independent 0.20 s blocks (2--3) and, in nominal/damping,
very small residuals. Most excitation and discriminating future evidence comes
from OUTBOUND and RETURN. The mass +8% case terminated on the unchanged task
acceleration limit before one complete identifier fit block was available; the
failure is preserved and was not tuned around.

## Safety and isolation

The three complete episodes recorded 219/216/225 `SAFE_ACTION` decisions and
no `NO_SAFE_ACTION`. The mass case recorded 14 `SAFE_ACTION` decisions before
the detected task-acceleration abort. Across all cases there was no Safety
Filter intervention, BRAKE, 200 N gate event, or MuJoCo warning.

All truth beta comparisons were appended offline after service execution.
Truth was not an input to the shadow service, and the service never changed the
controller model, observer, task decision, or command.

## Next research step

Implement and validate a Stage-5 shadow identifier in the already defined
three-scale control-effective subspace before any closed-loop Human adaptation.
It must repeat the same causal embargoed validation and show stable prediction
benefit across representative mismatches. The mass-case early safety abort
must be treated as missing identification opportunity, not as a successful
adaptation result.

Because the result is H-B rather than H-A, no fixed-versus-trusted closed-loop
A/B experiment is preregistered or run here, and no 3--5 repetition
personalization claim is made.

Compact evidence is in `HUMAN_ID_SHADOW_V1_SUMMARY.json`. Raw episode traces
and two incomplete tooling attempts remain ignored local diagnostic artifacts.
