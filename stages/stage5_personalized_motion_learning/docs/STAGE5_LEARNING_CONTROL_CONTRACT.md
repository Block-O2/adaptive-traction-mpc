# Stage-5 Learning and Control Contract

## Frozen responsibility split

This contract is future-facing. It does not activate learning or change the
current Stage-4-derived controller. `Stage-5 Plant v1`, explicit hard
constraints, and the executable safety path remain authoritative.

### Human estimator: predicts what will happen

The Human estimator retains online, causal identification of a
control-effective Human dynamics model. Its responsibilities are to:

- estimate Human state/geometry and dynamic parameters from the allowed
  measurement boundary;
- publish a versioned model for short-horizon prediction;
- expose uncertainty, validity, trust/publication state, and diagnostics;
- predict state evolution and generalized input/wrench mappings used by MPC.

It does not learn long-term task value, choose the control action, infer
clinical/anatomical truth, change the task goal, or relax constraints.

### CEM-MPC: chooses the actual action

CEM-MPC is the sole optimizer selecting the proposed control action. It:

- samples and ranks sequences of the existing two-dimensional desired Human
  generalized cuff action;
- predicts short-horizon state evolution with one published Human-model
  version per solve;
- optimizes short-term goal/progress, force-component, time, effort, and
  smoothness costs;
- rejects candidates violating explicit predicted constraints;
- submits the selected first action to the unchanged executable-screening,
  Safety Filter, and BRAKE path;
- records the proposed, filtered, and executed actions distinctly.

MPC may consume a published terminal value, but remains responsible for the
actual action. A value prediction is never itself an action.

### Value learner: estimates remaining cost

The value learner estimates state value/remaining task cost beyond the MPC
horizon. It is not a separate actor. Its input must include enough context to
make the prediction Markov with respect to the declared task, including the
estimated state, active phase/goal, remaining budget, and relevant model
versions.

It may update within an episode and across repetitions. Candidate parameters
may train continuously in shadow mode, but MPC may use only an immutable,
validated, explicitly published value version. Publishing during an episode,
if ever allowed, requires a separately defined causal rule; otherwise the
episode pins one published version from reset to termination.

Online TD targets may bootstrap from the published/candidate value as defined
by a future spec. At episode end, full observed returns must be computed and
used to correct/calibrate the online TD estimates. Failed, timed-out, BRAKE,
and aborted episodes remain non-success outcomes and must never receive the
zero remaining cost reserved for true completion.

## Future objective composition

For a feasible candidate action sequence beginning at state `s_t`, the intended
concept is

`J = sum_{k=0}^{H-1} stage_cost(s_k,u_k,task) + V_pub(s_H,task,model_context)`.

The short-horizon stage cost may include goal/progress, elapsed time, cuff-force
components, cuff moment, action effort, and smoothness. `V_pub` estimates the
remaining cost after the horizon. All terms require versioned units,
normalization, weights, discount/undiscounted-return convention, and terminal
semantics in an approved Experiment Spec.

Constraint evaluation occurs separately from this scalar score. Infeasible
candidates are rejected; a favorable value cannot compensate for a constraint
violation.

## Safety and execution invariants

- Learning cannot change hard constraints, limits, task-completion semantics,
  or Plant-v1 mechanics.
- Neither estimator nor value learner may bypass first-action executable
  screening, Safety Filter, BRAKE, or structural termination.
- Only the filtered/approved command is executed and used in the executed-action
  field of the dataset.
- Proposed and filtered actions/wrenches remain logged for intervention audit.
- Nonfinite value output, unknown value version, out-of-distribution state, or
  invalid model context must fall back to the defined no-value incumbent, not
  to unconstrained control.
- A BRAKE or stop does not by itself prove safe holding; hold/recovery
  feasibility remains explicit.
- Failed or aborted episodes are retained and cannot be relabeled or assigned
  zero-cost success returns.

## Minimum future transition data contract

Every control transition must be append-only and identify its session,
repetition, episode, control cycle, and timestamps. At minimum it contains:

| Field | Required content |
|---|---|
| state | estimator-facing state vector, units, frame, measurement timestamp, validity, and uncertainty/diagnostics reference |
| Human model | published control-effective model parameters or artifact reference, immutable model version/fingerprint, publication/trust state |
| task | task-contract version, phase, start/goal/allowed-region identifiers, progress, remaining time/hold budget |
| action | CEM-proposed generalized action, Safety-Filter-adjusted action/wrench when applicable, final executed generalized action/robot command, and units |
| cuff interaction | measured physical wrench, wrench frame/reference point, total/axial/tangential/radial/transverse force components, moment components, and provenance |
| cost | instantaneous cost total and named components, integration interval, constraint margins, and whether value was excluded from stage cost |
| termination | nonterminal/terminal flag, exact status/reason, completion predicate state, BRAKE/filter status, and numerical warnings |
| value | candidate value version, published value version actually used by MPC, predicted terminal/remaining cost, bootstrap target, and publication/fallback status |

For delayed or filtered sensing, sample time and controller arrival/use time
must both be recorded. God-view simulator state may be logged in a clearly
separate evaluation namespace but must never enter estimator, MPC, value, or
safety inputs.

At episode close, store the complete return, return convention, terminal cost,
success/failure class, and links to every transition. The dataset must preserve
proposed-versus-executed differences so the value learner is not trained as if
rejected commands were executed.

## Current interface audit

### Reusable without behavior change

- `BaseParameterHumanModel.step_dynamics(...)` already provides a versionable
  short-horizon Human predictor over state `[q1,q2,dq1,dq2]` and the existing
  two-dimensional generalized action.
- `HumanSpaceMPC` already supplies CEM sampling, warm start, deterministic RNG,
  batched/scalar rollout, and feasible-first candidate selection.
- The cuff allocator maps generalized action to a physical world-frame wrench
  while preserving generalized torque and already exposes sagittal/cylindrical
  diagnostics.
- The first-action preview, executable force filter, and `TrackBrakeSupervisor`
  already form an execution boundary that can remain authoritative.
- The measurement boundary already separates robot/cuff measurements from
  MuJoCo Human truth.
- Existing traces already contain estimated state, Human-model estimates,
  desired action, allocated wrench, measured/physical wrench, filter status,
  executed robot command, tracking/evaluation data, and termination summaries.

### Prescribed-trajectory couplings that must change in Stage 5

1. `HumanSpaceMPC.solve(...)` requires `reference_fn(time)` and constructs
   horizon arrays of `q_ref`, `dq_ref`, and `ddq_ref`.
2. The CEM seed uses inverse-dynamics tracking of those reference arrays.
3. Candidate cost is dominated by time-indexed joint position/velocity tracking.
4. The runtime turns the same full reference into cuff pose/twist targets for
   low-level command preview and Safety Filter/BRAKE evaluation.
5. Completion is based on requested duration/reference phase, not outbound,
   goal hold, return, and return-hold predicates.

### Current constraint and logging gaps

- MPC horizon rejection currently covers predicted Human ROM and allocated
  translational force, plus finite-state checks. It does not yet apply the full
  Stage-5 velocity, acceleration, moment/component-force, interface-deformation,
  progress/path, or collision contract.
- Robot torque/command feasibility and the Safety Filter are applied to the
  first action, not predicted as a full robot/collision horizon.
- Goal-MPC v1.1 now propagates an independent nominal Kelvin--Voigt interface
  across the first 20 ms action hold. It screens predicted physical force and
  uses the predicted mean transmitted Human generalized input for the first
  Human-state step. The remaining horizon is still the existing Human-only
  predictor; robot collision and interface uncertainty are not horizon models.
- Current replay traces lack a first-class task phase/goal contract,
  instantaneous task-cost breakdown, explicit proposed-versus-filtered
  generalized action, published value version, and session/repetition identity.
- The Stage-5 sanity replay deliberately uses a fixed registered estimator; it
  is not the future online-identification runtime.

## Stage-5-only interface migration status

No Stage-3/4 edit is required. The minimal next implementation should add only
Stage-5 modules/adapters:

1. `task.py`: immutable `GoalTaskSpec`, `TaskPhase`, `GoalTaskState`, progress
   and terminal-predicate functions, with no controller logic. This interface
   is implemented and the engineering runtime, rather than MPC, owns its phase
   transitions and completion decision.
2. `goal_mpc.py`: candidate evaluation returns named goal-cost components and
   a separate constraint margin; no prescribed time reference enters this
   evaluation.
3. `goal_mpc.py`: a Stage-5 CEM-MPC adapter/subclass that reuses current
   action sampling, Human rollout, allocator, and first-action preview, while
   replacing `_reference_arrays`, the tracking seed, and tracking cost with
   goal/task inputs. Terminal value is fixed to zero in the first version.
   This adapter is now implemented. v1.1 adds only a first-step nominal
   transmitted-input map; horizon/candidates and all registered weights remain
   unchanged.
4. `controller_interface.py` owns a controller-deployable interface observer
   and nominal action-hold predictor. Its immutable config is independent from
   `mechanics.py`; only the plant/evaluation receives plant-truth K/D and
   interface state. Matched initialization of the two records does not merge
   their runtime ownership.
5. `local_command_reference(...)` in `goal_mpc.py` builds only the current
   one-step cuff pose/twist structure required by the existing low-level
   preview/Safety Filter/BRAKE. It anchors q/dq to the current deployable
   estimate because the Human-only predictor lacks Plant-v1 cuff deformation;
   the selected generalized wrench is the motion authority. It never creates
   an episode-long trajectory.
6. `goal_mpc_smoke.py` is the engineering-only episode runtime. It owns phase
   transitions and state-based completion while delegating every proposed
   command to the unchanged safety stack.
7. The smoke trace/summary records the fixed model version, observation age,
   phase, action, physical cuff wrench, solver/safety status, and termination.
   A production `transition_log.py` satisfying the complete future data
   contract, including explicit proposed-versus-filtered action and
   `value_model_version="none"`, remains future work.

The first implementation milestone is therefore a deterministic,
goal-directed, **model-based-only** episode with fixed Human model and zero
terminal value. It should reproduce action/constraint/safety invariants in unit
and smoke tests before online identification or value learning is enabled.

The v1.1 matched engineering smoke removes the original physical-force-gate
abort and reaches `HOLD`, but the unchanged receding-horizon objective does not
sustain the angle/velocity predicate for 0.5 s and terminates at
`TIMEOUT_HOLD`. This is now the blocking deterministic controller-design issue.
No plant mismatch check or learned terminal value may start until a separately
approved minimal HOLD treatment is specified.

Goal-MPC v1.2 implements that minimal phase-aware treatment: OUTBOUND and
RETURN retain the existing goal-directed cost, while HOLD adds normalized
running position and velocity costs across all 15 horizon states. The retained
provisional weights are `wq_hold=4.0` and `wv_hold=0.25`; q uses the inherited
2 deg scale and dq the inherited 8 deg/s scale. `wq_hold=4.0` is the smallest
tolerance-based correction tested after `wq_hold=1.0` traded too much position
error for reduced velocity. The matched smoke still times out in HOLD, so this
objective is not a completed baseline and mismatch/learning remain blocked.

Goal-MPC v1.3 replaces that tracking-style HOLD treatment with the immutable
`GoalTaskSpec` completion set and extends the independently configured nominal
translation/rotation interface state and transmitted physical cuff wrench
through all 15 horizon steps. The candidate dimension remains vectorized. The
200 N physical-transmission and allocated-request force checks are both
preserved. If a sampled, plant/task-safe sequence can remain in the HOLD set,
only such sequences are admitted; if stored interface energy makes that set
temporarily unreachable, plant/task safety stays hard and the normalized set
violation selects a recovery sequence. This fallback cannot advance the
continuous timer; `GoalTaskState` remains the sole completion authority.

The retained matched smoke still terminates at `TIMEOUT_HOLD`, with only
0.005 s of continuous set membership. A targeted synchronized check shows the
fixed Human model accurately predicts the next state when driven by the
measured mean generalized cuff input, while the simple nominal interface drive
surrogate has a 4.98/1.94 Nm HOLD input RMSE. Therefore the remaining blocker
is deterministic future executable-command/robot-feedback semantics, not a
reason to tune HOLD weights or start learning. Interface mismatch testing and
terminal-value learning remain blocked.

The subsequent Stage-5 loaded-HOLD checkpoint separates motion planning from
loaded support without changing the contract above. OUTBOUND remains the
reference-free Goal-MPC. At HOLD entry, a deterministic computed-torque local
controller regulates the deployable Human-state estimate around a statically
consistent nonzero cuff-wrench/interface-strain equilibrium. A single 0.10 s
quintic pose-authority transfer makes the first local executable wrench equal
to the preceding MPC executable wrench before converging to the equilibrium
robot cuff pose. In the matched 20/35 deg engineering smoke this controller
recovers the actual Goal-MPC arrival, maintains the `GoalTaskSpec` completion
set continuously for 0.5 s, and allows the task state to enter RETURN. RETURN
and full episode completion have not yet been revalidated; interface mismatch
and learning remain deferred.

The next matched engineering checkpoint reconnects unchanged path-free RETURN
Goal-MPC through a generic 0.10 s executable-reference transfer. The first
RETURN target wrench is frozen and CEM is held during this short transfer so
prediction and partial-blend execution cannot diverge. The controller then
resumes unchanged RETURN Goal-MPC and reaches `COMPLETE`; no return terminal
stabilizer is required. This closes the first deterministic non-learning
episode. It authorizes only a small interface-mismatch engineering checkpoint,
not adaptation, value learning, RL, or a robustness claim.

## Unresolved design choices requiring an Experiment Spec

- exact `Q_start`, `Q_goal`, `Q_allowed`, tolerances, and hold durations;
- progress coordinate/path corridor and allowed reversals;
- episode/phase time budgets and joint velocity/acceleration/action-rate limits;
- force-component, moment, deformation, and collision/contact constraints;
- objective form, units/normalizations, weights, and time/force tradeoff;
- prediction treatment for robot collision, cuff compliance, and uncertainty;
- Human-model trust/publication cadence in a 30-repetition session;
- value state/context features, return/discount convention, terminal penalties,
  TD method, candidate validation, publication cadence, rollback, and
  out-of-distribution fallback;
- matched episode population and evidence criteria for “personalized within
  3--5 repetitions” and “stable exploitation”.
