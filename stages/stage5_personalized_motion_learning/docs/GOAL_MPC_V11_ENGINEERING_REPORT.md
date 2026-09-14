# Goal-MPC v1.1 interface-model engineering report

Evidence category: **engineering smoke only**. This is not formal evidence and
is not a scientific PASS/FAIL decision. Stage 3, Stage 4, Plant v1, the Human
model, MPC horizon/candidates/weights, Safety Filter, BRAKE, and the 200 N
simulation engineering gate were unchanged. No learning was enabled.

## Exact v1.1 changes

- The controller now estimates the Human-side cuff pose/twist from causal
  robot-side pose/twist and measured cuff wrench by inverting an independently
  configured nominal Kelvin--Voigt interface. MuJoCo Human truth is evaluation
  only.
- Plant truth remains `mechanics.py`/`Stage5SensorBoundaryPlant`; controller
  nominal K/D is loaded only from
  `configs/stage5_controller_nominal_interface_v1.json`. The controller module
  does not import the plant parameter singleton or access plant interface
  state.
- First-action executable screening is batched. It propagates nominal
  translation/rotation spring-damper state at 0.25 ms across the 20 ms selected
  action hold, rejects a candidate whose predicted physical force crosses the
  unchanged 200 N gate, and uses mean predicted transmitted wrench for only
  the first Human prediction step.
- The redundant second full-horizon rollout formerly used only to populate
  selected-cost diagnostics was removed. No horizon/candidate reduction was
  made.

The nominal observer uses measured wrench plus finite differences of its own
previous interface estimate. The force predictor uses the provisional
effective mass/inertia values already recorded by the Stage-5 engineering
calibration. Both remain non-hardware-calibrated models.

## Matched-model result

Primary retained output:
`results/goal_mpc_v11/matched_03/`.

The episode reached `OUTBOUND -> HOLD` at 1.945 s, then ended at 11.95 s with
`TIMEOUT_HOLD`. It did **not** reach RETURN or COMPLETE. No physical-force gate,
BRAKE, structural event, Safety-Filter intervention, MPC failure, nonfinite
state, or MuJoCo warning occurred.

| Quantity | Observed value |
|---|---:|
| Peak / cumulative physical cuff force | 167.081 N / 1269.409 N s |
| Peak physical cuff moment | 24.693 Nm |
| q estimation RMSE | 0.0097 deg / 0.0197 deg |
| dq estimation RMSE | 0.4851 deg/s / 0.8110 deg/s |
| physical-force vector prediction RMSE / p95 / max | 6.759 / 14.881 / 36.991 N |
| physical-force norm prediction RMSE / p95 / max | 5.469 / 12.753 / 30.698 N |
| MPC solve mean / p95 / max | 16.958 / 19.950 / 39.033 ms |
| MPC solves / returned SAFE_ACTION | 599 / 599 |
| maximum diagnostic q1/q2 normalized-progress difference | 0.244 |

The path-freedom contract remains genuine: no full q(t), coordination ratio,
or corridor is present, and the observed normalized q1/q2 progress differs.

## Remaining deterministic blocker

The timeout is not an observer/state-machine artifact: controller and
evaluation truth produce the same at-goal predicate. During HOLD, both angle
and velocity tolerances were simultaneously satisfied for only 2.60% of
samples; the longest continuous interval was 0.035 s, versus the required
0.5 s. Angle-only and velocity-only satisfaction were 22.19% and 13.24%.

Measured physical wrench mapped back to Human generalized input still differs
from the requested action during HOLD: RMSE 4.505/2.835 Nm and correlation
0.800/0.515 for q1/q2. First-step interface prediction reduces the abstraction
gap, but the unchanged objective has only terminal velocity cost. Receding
horizon operation can therefore defer settling and does not maintain the true
HOLD predicate. Correcting this requires an explicit, separately approved
minimal HOLD/stage-state objective or constraint treatment; changing a weight
silently would violate the research contract.

## Mismatch decision and learning boundary

The requested sequencing says mismatch checks begin only after matched-model
completion works. Because matched completion was not obtained, plant K/D
mismatch runs were not started. Therefore this task does not establish whether
interface uncertainty is manageable under mismatch.

The matched observer errors show that a simple nominal interface model is
adequate for Human-state reconstruction in the current ideal-sensor setup.
Force prediction is useful for gate avoidance but has non-negligible tail
error. That is evidence for later validating an extended deterministic
interface model, not evidence that a residual learner is currently necessary.
Learning remains blocked until matched deterministic HOLD behavior is fixed
and mismatch evidence exists.

## Reproduction

```bash
MPLCONFIGDIR=/tmp/mpl-stage5 \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/run_stage5_goal_mpc_smoke.py \
  --output-dir stages/stage5_personalized_motion_learning/results/goal_mpc_v11/matched_03 \
  --maximum-duration-s 30.5
```

The output directory is immutable-by-convention: the runtime refuses to
overwrite a nonempty directory.
