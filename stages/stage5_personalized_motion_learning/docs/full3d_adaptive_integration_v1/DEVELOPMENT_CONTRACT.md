# Full-3D Adaptive Integration V1 Development Contract

Status: frozen before the first new development execution run.

This contract governs integration development only. It is not a formal
held-out acceptance contract and it does not change any historical Stage-5 or
architecture-recovery result.

## Evidence boundary

- Required plant: MuJoCo CR12 six-axis torque-actuated robot, provisional
  Stage-5 flange/adapter/cuff, explicit spring-damper cuff-to-Human interface,
  Human V2, bed plane and enabled contact mechanics.
- Human task coordinates remain `(q1,q2)` but the execution plant is 3-D.
- Direct Human torque/wrench task actuation, scripted state changes and static
  synthetic belief handoff are forbidden in accepted integration runs.
- Hardware evidence remains absent. The cuff/adapter and F/T frame are
  provisional simulation assets, not OnRobot HEX evidence.
- Value/RL hook is fixed to exactly zero; no value, RL or imitation training.

## Pre-development motion and execution table

| Item | Frozen development value | Enforcement/source |
|---|---|---|
| Human hard ROM | q1 `0..80 deg`, q2 `0..100 deg` | Human V2 MuJoCo joints and task state monitor |
| Human soft-limit margin | `5 deg` inside hard ROM | Human V2 passive soft-limit torque |
| Task velocity limits | q1 `45 deg/s`, q2 `75 deg/s` | actual reconstructed motion monitor |
| Task acceleration limits | q1 `300 deg/s^2`, q2 `600 deg/s^2` | causal 20 ms actual-motion window; reference checks do not replace it |
| Completion tolerance | `1 deg` each joint and `2 deg/s` each joint | actual estimated arrival/settling |
| HOLD dwell | `0.5 s` continuous validity | event state machine; invalid sample resets dwell |
| Phase timeout | `10 s` per active phase | no-progress protection, never an arrival trigger |
| Cuff force limit | `200 N` Euclidean world force norm | planning screen plus realized-wrench monitor |
| Cuff moment limit | `60 Nm` Euclidean world moment norm | planning screen plus realized-wrench monitor |
| CR12 torque limits | `[436,436,194,102,66,66] Nm` | MuJoCo actuator ctrl/force ranges and command receipt |
| CR12 velocity limits | `[120,120,180,234,240,240] deg/s` | actual CR12 joint-velocity monitor |
| Physics step | `0.00025 s` nominal | MuJoCo plant |
| High-level decision cadence | `0.020 s` target | timestamped planner lifecycle |
| Reference execution cadence | physics step with continuous quintic sample | low-level Cartesian/joint-torque realization |
| Contact rules | Human-bed and enabled CR12/adapter collision geoms remain active | MuJoCo contact model; no contact disabled for performance |

The Stage-5 `2 deg/s` completion rule is authoritative. The reduced Phase-2
`5 deg/s` terminal rule is not imported into this integration.

## Contact inclusion and exclusion

Active collision classes include the bed plane, Human thigh/shank capsules,
CR12 group-3 collision geoms and the provisional adapter cylinder. The visual
cuff bar has `contype=0, conaffinity=0` and is therefore not collision-active.
The cuff-to-Human load is the explicit spring-damper site interface; the old
six-row weld is disabled.

The inherited CR12 XML excludes these body pairs, copied from the supplied
SRDF and therefore not covered by collision claims:

- base-link1, base-link3;
- link1-link2, link1-link3;
- link2-link3, link2-link4;
- link3-link4, link3-link5, link3-link6;
- link4-link5, link4-link6;
- link5-link6.

All other enabled pairs remain subject to MuJoCo collision filtering. Accepted
results must log active contacts and must not claim protection for excluded
pairs.

## Observation and truth firewall

Deployable inputs may use simulated robot encoders, robot cuff pose/orientation
and Jacobian-derived twist, and reconstructed physical interface wrench at the
Human sleeve reference point. Hidden Human joint state, hidden session
geometry/dynamics and evaluation clearance are restricted to plant
construction and evaluation channels. Every sample carries measurement,
planning-completion and activation timestamps and measurement age.

## Timing contract

- State and reference metrics compare values with equal timestamps.
- `N` integration intervals have `N+1` boundary states.
- Commands and force costs are interval records `[t_k,t_{k+1})`.
- The final interval ends exactly at requested duration; a short final interval
  is allowed when duration is not divisible by nominal `dt`.
- No extra integration step is taken merely to record the endpoint.
- Force/moment exposure uses each interval's actual duration.

## Development promotion boundary

Nominal completion is only an intermediate milestone. Formal held-out work may
start only after the actual chain, session-geometry consistency, timing,
actuation-disable causal check, planning latency semantics and trace contract
have independent audit approval and a separately frozen preregistration.

## Post-freeze source-audit corrections (2026-09-23)

These are documentation corrections, not retroactive changes to the frozen
limits or plant. Source inspection established two mismatches in the table
above:

- High-level waypoint decisions are **event-driven**, at task start, phase
  changes, or completion plus settling of the active waypoint segment. The
  `0.020 s` period is the continual-adaptation cadence, not a planner cadence.
  `development_v1_1.json` records the corrected label.
- MuJoCo collision masks are not all-to-all. CR12 and adapter collision geoms
  use `contype=1, conaffinity=1`; Human geoms use `2/4`; the bed uses `4/2`;
  the visual cuff bar uses `0/0`. Consequently Human-bed contact is active,
  CR12 self-contact remains active except the listed exclusions, but direct
  CR12-Human and CR12-bed contacts are filtered out. The physical Human load
  path is the explicit Kelvin-Voigt site interface, not geom contact. Accepted
  evidence must not claim robot-Human or robot-bed collision protection.
- The continuous quintic is sampled by the execution loop every `0.005 s`;
  that command is held while MuJoCo takes twenty `0.00025 s` physics substeps.
  The pre-development phrase "physics step with continuous quintic sample" in
  the table describes the mathematical reference, not the implemented command
  update rate.

## Post-audit clearance correction freeze (2026-09-23)

The first run with per-boundary constraint channels (`attempt_11`) exposed 61
estimated-state violations of the deployable conservative session-clearance
set, despite no hidden-truth MuJoCo shank contact. That run is preserved and is
not accepted. Before the next development rerun, the following single
clearance-policy revision is frozen:

- every reference schedule must retain at least the smaller deployable
  clearance of the registered task start/return target and the active phase
  goal; this task-derived floor prevents an unnecessary near-bed intermediate
  detour without introducing a fitted numerical margin;
- the execution loop independently fails closed when the estimated-state
  `SessionClearanceContract` becomes negative at a 5 ms boundary;
- this monitor detects a sampled violation; it is not a forward-invariance or
  between-substep collision guarantee.

The plant, task endpoints, ROM, motion limits, wrench limits, controller gains,
candidate set, adaptation, and all other parameters remain unchanged. A
passing rerun is development evidence only and cannot establish varied-domain
robust clearance.
