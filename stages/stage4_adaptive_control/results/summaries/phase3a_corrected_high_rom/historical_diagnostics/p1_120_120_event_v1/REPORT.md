# P1 120/120 physical-force event mechanism audit

Checkpoint `5452d09c6ab7d2c17dda78dadb65c7e28c381c95`. This is a read-only audit of saved exploratory evidence. No simulation or replay was run, no parameter or threshold changed, and the strict numerical-qualification FAIL is preserved.

## Compact critical-window comparison

| Saved P1 run | Peak N | Spring at peak N | Damping at peak N | Translation mm | Relative speed m/s | Command N | Safety Filter | Moment Nm | Cuff accel m/s2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 40/80 | 123.204 | 123.087 | 0.345 | 1.0597 | 0.00070 | 126.888 | SAFE_UNCHANGED | 7.241 | 0.378 |
| 90/120 | 130.228 | 129.894 | 4.454 | 1.0889 | 0.00908 | 126.057 | SAFE_UNCHANGED | 51.926 | 1.117 |
| 120/120 | 222.216 | 201.160 | 22.709 | 1.3414 | 0.04628 | 200.000 | SAFE_FILTERED | 44.011 | 33.513 |

At the 120/120 terminal sample, physical force is `[-201.01866395777947, 70.62422178085916, -63.11708048397312]` N and command force is `[-175.95299034738107, -2.8638701944828107, 95.03864180008136]` N. Reconstructed spring and damping vectors are `[-185.15190548540082, 60.02885552540144, -50.800502322275]` N and `[-15.86675847237866, 10.595366255457726, -12.316578161698121]` N. Reconstruction error is below `5.204e-14` N across the trace.

## Spring versus damping

The event is spring/deformation dominated. Spring force is 201.160 N and projects 200.997 N onto the physical-force direction. Damping is 22.709 N and contributes 21.219 N in that direction. The 1.3414 mm deformation raises the isotropic radial stiffness to 149965 N/m through P1's cubic term; the 0.04628 m/s relative speed supplies the additional damping load.

For 40/80 and 90/120, deformation at their peaks is only 1.0597 and 1.0889 mm, effective stiffness is 116151 and 119287 N/m, and command is approximately 127 and 126 N. Their spring contributions remain 123.09 and 129.89 N and damping remains 0.34 and 4.45 N. The 120/120 event combines a higher command episode, larger cubic-regime deformation, and much larger relative velocity.

## Duration and impulse

The final >200 N segment starts at 11.140993003 s and is observed for at least 1.257 ms, with at least 0.014044 N s excess impulse. The >220 N portion is observed for at least 0.128 ms, with at least 0.000142 N s excess impulse. Both segments are open at the trace boundary because the 220 N absolute ceiling stops the run. Their closure and final duration are therefore `NUMERICALLY_UNRESOLVED`; the evidence shows a rapid rising transient prefix, not a demonstrated sustained plateau. A separate earlier >200 N event was closed after 2.502 ms at 200.989 N.

## Controller and Safety Filter alignment

The hard-stop peak is 2.250 ms after the 11.140 s controller update. The nominal executable command is 239.558 N and the Safety Filter produces a feasible 200.000 N action (`SAFE_FILTERED`, lambda -85.045, one feasible candidate). Physical force crosses 200 N 0.993 ms after that update. There is no BRAKE, FILTER_INFEASIBLE, or NO_SAFE_ACTION. The event coincides with controller/Safety Filter switching but occurs while the command side remains executable; the saved evidence does not prove the counterfactual that the update alone caused it.

## Rotation and energy

At peak, rotation is 0.7947 deg and physical moment is 44.011 Nm. Rotational spring/damping contributions are 35.637/9.283 Nm. Stored energy is 0.304575 J, damping dissipation is 7.973726 W, cumulative damping loss is 0.986837 J, and residual is -0.017453 J (-1.3334%). The complete saved trace has zero warnings, nonnegative damping, zero growth-watchdog triggers, maximum positive residual 0.000120 J, and final 100 ms residual slope -0.040466 W. No saved evidence indicates numerical runaway or artificial-energy growth.

## Evidence classification

### DIRECTLY OBSERVED

- The 222.216 N sample is reconstructed exactly by the registered P1 spring and damping law.
- Spring is the dominant contribution; damping materially increases the peak.
- The filtered command remains feasible at 200 N while physical load exceeds 220 N.
- The trace ends while both threshold exceedances remain open.

### SUPPORTED BY CURRENT EVIDENCE

- The event is a coupled high-command/interface-state transient: cubic elastic loading dominates and relative-velocity damping adds in nearly the same force direction.
- Lower 40/80 and 90/120 peaks correspond to materially smaller command, deformation, effective stiffness, and relative velocity.
- There is no indication of numerical or energy runaway in the recorded prefix.

### UNRESOLVED

- Exact >200 N and >220 N duration and impulse after the hard stop.
- Whether the force would have decayed immediately or developed into a sustained oscillation without the registered stop.
- A causal counterfactual separating the new controller action from the accumulated interface state.

### NOT SUPPORTED

- Retrospective numerical qualification of P1.
- A claim that damping alone caused the event.
- Clinical safety or validated tissue mechanics.

## Closeout decision

The soft-interface exploratory branch has enough saved evidence to close out its current scientific question: P1 has trajectory-dependent benefits, smooths some transients, and can shift the limiting mechanism, but it does not provide consistent peak-force or task-completion improvement and remains numerically unqualified. No additional ROM point is justified by this audit. If work on this model family resumes, the one specifically justified follow-up is a separately preregistered event-closure/numerical study that preserves the 120/120 initial history while recording beyond the force-policy stop under an explicit non-authoritative diagnostic protocol; it should not be treated as another capability rollout.
