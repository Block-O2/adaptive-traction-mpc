# V2.1 Independent Fragility Audit

Status: **PASS/FREEZE WITH EXPLICIT TRANSFER CAVEATS**

| Layer | Purpose | Deployable input/output | Observable failure | Simpler alternative and decision |
|---|---|---|---|---|
| commissioning probe | excite geometry/dynamics before task | cuff pose/twist and commanded wrench to history | consistency abort, settle timeout, unsafe motion | no-probe fixed model fails broadly; retain |
| effective geometry | recover control-sufficient hip, thigh, knee-to-cuff tuple | pose/orientation to q/Jacobian | rejected fit, ROM/clearance abort | full anatomical L2/f is unidentifiable here; effective tuple is simpler and sufficient |
| bounded beta fit | capture global effective dynamics | estimated q/dq/ddq and previous generalized torque to beta | rejected update, active/frozen set, mass margin | commissioning-only loses tail/completion; retain continual fit |
| task residual | correct task-local model mismatch | same causal estimated history to bounded torque bias | finite/bound/cap/step/variation/sign logs | recency windows did not resolve the root cause; residual gives the smallest demonstrated repair |
| active-set/refit | preserve feasible physical mass and bounded coefficients | regressor history to accepted/rejected beta | explicit frozen parameters and diagnostics | unconstrained fit is less safe; retain |
| state estimate | map cuff pose/twist through estimated geometry | cuff pose/twist to q/dq | nonfinite/ROM supervisor | no oracle geometry; retain, but noisy hardware twist remains unvalidated |
| mechanics feasibility | keep registered reference/execution clear of bed and ROM | estimated state/reference plus structural bed model | clearance and ROM events | cannot be removed without losing the scientific task family boundary |
| reference generator | produce multiple smooth outbound/return profiles | task goal and estimated start to q/dq reference | exact-reference clearance audit and tracking gates | fixed single trajectory is inadequate; retain registered profiles |

The Auditor independently verified that the residual uses no hidden plant
truth, does not mutate physical beta, is disabled for nonadaptive comparison
arms, and is invariant to changes in evaluation-only truth diagnostics. It
also verified all current source hashes and reran the 27 focused tests.

The principal unresolved transfer fragility is ideal noiseless simulated twist
and finite-difference acceleration. Reduced-plant success does not validate
sensor noise, delay, detailed robot/interface dynamics, or the physical sensor
moment frame. The simulated cuff-reference-point moment must not be interpreted
as an OnRobot HEX hardware suitability result.

