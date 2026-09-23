# Phase 1B-F Freeze Candidate V1

Status: **PHASE 1B-F PASS — ARCHITECTURE FROZEN**

Builder and independent Auditor agree to freeze the declared conditional planar
Human-V2 simulation architecture. No further architecture tuning is permitted
before fresh Phase 2.

## Exact candidate

- Control-effective geometry `(hip_x, hip_z, thigh_length,
  knee_to_cuff_distance)` estimated causally from cuff pose history.
- Bounded 11-beta continual adaptive dynamics.
- 0.03 predicted mass-matrix eigenvalue floor.
- Conditional active set freezes invalid/bound-limited components and refits
  remaining coefficients.
- 100 Hz bounded probe followed by event-driven estimated-velocity settling at
  the estimated interior pose.
- Four mechanics-aware task profiles, including versioned bounded knee-led
  motion.
- 25 mm pre-probe proposal reserve, exact post-probe reference audit, and <=5 ms
  actual simulated clearance evaluation.

## Builder gate outcome

- Combined qualification V2: PASS, adaptive/oracle 16/16.
- Adaptive RMSE median/p95: 0.9921/2.2927 deg.
- Adaptive full-episode peaks: 159.89 N/50.24 Nm.
- Fixed nominal 0/16; wrong geometry 1/16; no dynamics 5/16.
- Exact-current continual ablation V3: PASS, 8/8 versus commissioning-only 6/8
  and no dynamics 1/8.
- Post-probe exact references: all adaptive/oracle rows evaluated, zero
  violations, minimum 50.585 mm.
- No adaptive probe/task clearance, ROM, settle-timeout, consistency, solver or
  safety events.
- Per-update audit: beta finite/in-bounds, mass floor/residual/step cap pass.
- Truth-firewall regression: evaluation-only clearance cannot change adaptive
  behavior.
- Source/config and Git status did not change during authoritative V2/V3 runs.

## Freeze scope

Freeze is limited to the declared conditional, planar, contact-free Human-V2
simulation family. It does not freeze or validate a hardware sensor model,
robot/interface predictor, contact/tissue model, or 120–130 deg ROM.

No Phase-2 seeds/configurations/outcomes were generated or viewed before this
freeze. Architecture tuning is now stopped.
