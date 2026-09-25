# DEV-A lifecycle design decisions (development, not formal qualification)

## Frozen comparison boundary

The prior formal result stays `FULL3D_FRESH_FAILED_WITH_EVIDENCE`. Its 24
adaptive cases are consumed development cases. DEV-A keeps the accepted
effective-geometry fit, eleven-dimensional beta, bounds, smoothing, 3%-span
step cap, 20 ms estimator cadence, residual learner, task HWMPC, task goals,
ROM, velocity/acceleration and cuff wrench limits, bed model, 100 ms stale-plan
rule and zero value hook. It adds pre-task execution semantics and recovery;
it does not credit model adaptation for lifecycle improvement.

## Observed failure → hypothesis → change → validation

1. Three varied cases failed *before physics* after finite six-axis IK because
   `initial_support` was checked for OUTBOUND task progress. Hypothesis:
   non-task physical support should obey task bounds and mechanics, but not
   directional task progress. Change: explicit `WaypointExecutionContext`;
   `TASK` retains the old progress predicate, while `STARTUP_SUPPORT`,
   `COMMISSIONING` and `ACTIVE_RECOVERY` omit only that predicate. The three
   former pre-step cases each entered 7.02 s/28,080 MuJoCo physical steps in
   `startup_context_only/`; they still failed the *old* fixed handoff, as
   expected.
2. DGN measured early physical tracking error and 17 handoff failures, with
   only a small fitted-state jump. Hypothesis: an event-driven physical
   recovery can bring a displaced state back to task start without changing
   the model. Change: after unchanged physical commissioning and fit/replay,
   `ACTIVE_RECOVERY` plans from the continuous *emitted* q/dq/ddq reference,
   uses fresh deployable qhat/dqhat for the correction target, executes every
   5 ms through the existing supervised CR12 torque path and compliant cuff,
   then applies the original `at_goal` predicate for a retained 20 ms
   persistence interval before calling unchanged `start_episode`.
3. The first prototype made the recovery reference target equal to lagging
   qhat. In `balanced_ordinary_r01`, that candidate had lower deployable
   clearance than the unchanged task endpoint floor; it was rejected before
   physical recovery. Hypothesis: tracking error requires a correction
   reference on the *other* side of task start, not a reference that chases
   lag. Change: symmetric correction `q_corr = q_start + λ(q_start - qhat)`;
   use λ=1 first, then 0.5, 0.25, 0.125, 0 only if the exact existing
   scheduler, clearance and mechanics checks reject prior candidates. Every
   attempted target and rejection is logged. This is a recovery-only
   feedback reference; the task candidate set, task cost and task progress
   checks are unchanged. It is not a fixed-r production trajectory.
4. The nominal-to-fitted geometry maps the same registered start q to robot
   cuff desired poses separated by 16.97 mm in `balanced_ordinary_r01`.
   Hypothesis: immediate model activation can create a desired-pose step.
   Change: during planning, keep prior support/model; at first recovery
   segment activation, a C2 quintic SE(3) bridge goes from the old commanded
   robot cuff pose to the new fitted-model segment endpoint. Human q/dq/ddq
   reference remains continuous. Robot pose and twist bridge endpoint jumps
   are measured. This does **not** automatically prove torque or generalized
   action continuity; those are separately traced and audited.
5. The first 24-case DEV regression V1 exposed a redundant second 1.5 s
   zero-displacement segment when the first fitted-model bridge already ended
   at the registered start. Change: after CAPTURE completion, if the emitted
   reference is exactly at start, immediately enter measured-state settling;
   if the measured state is not settled, plan another correction. This does
   not change the settle predicate or timeout. Also distinguish exhaustion
   of the remaining registered phase time from geometric infeasibility.
   Preserve V1 results; run a new V2 development regression on the same
   already-consumed cases for the final DEV-A implementation.

## Failure policy and provenance

All recoveries use the registered 10 s phase timeout and inherit the 1.5 s
commissioning segment time as a minimum recovery transition duration. During
a measured planning delay, physics advances under the previous reference.
A plan older than 100 ms aborts without activation. A negative session
clearance or any existing physical limit violation aborts. Infeasible
schedule, mechanics rejection, deadline miss, plant safety abort and task
failure are distinct. True Human q/dq and bed contact are evaluation-only.
There is no Human-state assignment, reset, time rewind or hidden-truth origin.

The exact post-commissioning *eligibility* counterfactual is reconstructible
from the same physical state: the old path called `start_episode` immediately;
the new path evaluates the identical fitted observer state and then performs
recovery before calling `start_episode`. No separate cloned MuJoCo/control/RNG
branch was implemented. Thus old-vs-new reruns support a lifecycle comparison
but not a fully matched physical trajectory counterfactual after time 7.02 s.

## Open scientific/engineering boundary

The conservative session-clearance floor can reject recovery or later task
waypoints even when the evaluation-only true geometry is nonpenetrating.
That is *not* repaired by lowering the margin or using hidden geometry.
Likewise, the fitted-model activation may still produce a generalized-action,
allocated-wrench or torque transient despite the pose/reference bridge. V2
measured as much as 49.582 N / 9.730 Nm allocated-wrench and 34.780 Nm
six-axis torque-command L2 change across one 5 ms model-activation boundary.
This is not labeled bumpless or repaired by a silent rate limiter.
