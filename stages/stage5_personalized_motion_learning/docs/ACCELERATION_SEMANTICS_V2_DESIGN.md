# Stage-5 Acceleration-Semantics V2 Design

## Frozen boundary

This is a new implementation branch. The historical Interface Robustness V1
campaign remains frozen as **`EXIT C — STOP THIS IMPLEMENTATION`**; no V1 row,
label, or conclusion is rewritten.

The registered physical envelope remains q1 = 300 deg/s² and q2 = 600 deg/s².
Velocity limits, 15/25 deg/s pacing, controller nominal interface parameters,
15-step horizon, 32 candidates, two CEM iterations, objective weights, loaded
execution, HOLD, Safety Filter/BRAKE, the 180 N planning ceiling, and the 200 N
engineering gate are unchanged.

## V2 first-action contract

For every proposed first total Human action, the controller-only prediction
propagates cumulative velocity change at 5, 10, 15, and 20 ms and requires

```text
abs((dq_hat(t + delta_t) - dq_hat(t)) / delta_t) <= registered_limit
```

for both joints and every prefix. A failed prefix makes the candidate
infeasible; CEM is otherwise unchanged. There is no startup exemption, added
margin, new state/mode, command-slew threshold, or truth input.

The implementation uses one fixed action for the 20 ms MPC interval, refreshes
the loaded executable command every 5 ms, and couples the existing nominal
Kelvin-Voigt recurrence and fixed Human model at every 0.25 ms interface
substep. Robot/cuff measurements, the deployable Human/interface estimate,
explicit predictor state, fixed Human model, and controller nominal interface
parameters are the only online inputs. The 5/10/15 ms states are not
interpolated from the 20 ms endpoint.

The pure threshold function is
`screen_cumulative_prefix_acceleration`; first-action outputs explicitly log
prefix state, acceleration, margin, feasibility, and executable-wrench
increment. The online causal acceleration monitor was not changed.

## Scope limitation exposed by validation

This change aligns the time intervals being screened, but it does not make the
nominal interface/execution predictor physically exact under plant mismatch.
The targeted validation found a large early-transient prediction error even
after 0.25 ms coupled propagation. Per the preregistered stop rule, no margin,
new limit, or further controller redesign was added.
