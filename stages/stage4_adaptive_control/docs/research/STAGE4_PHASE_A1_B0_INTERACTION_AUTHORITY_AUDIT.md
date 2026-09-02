# Stage 4 Phase A.1 / B.0 Interaction Authority Audit

## Scope and evidence status

This is engineering evidence, not formal or authoritative scientific evidence.
Phase A was checkpointed first at commit `542909c` (`diagnose high-rom
interaction force`). The A.1 and B.0 files listed below remain uncommitted.

No controller, cost, constraint, force margin, Reference Manager setting,
trajectory parameter, physical parameter, optimizer setting, or solver setting
was changed. Adaptive MPC, task relaxation gamma, and new recovery logic were
not introduced. The independent 200 N executable-command and physical-force
gates remain separate.

## A.1 suspended 90/120 engineering pilot

Exactly one complete pilot command was run for Fixed MPC, nominal High-ROM
Human V2, seed 44104, and the 90/120 trajectory. The only scientific variable
changed from the preserved lying-bed run was the engineering scenario: all
Human-bed collisions were disabled during model construction, before t=0.

| Metric | Existing lying bed | New suspended history |
|---|---:|---:|
| Completion | no, 16.046 s | no, 16.055 s |
| Termination | `physical_cuff_force_gate` | `BRAKE_INFEASIBLE` |
| Executable command force peak | 200.000 N | 200.000 N |
| Physical cuff force peak | 218.441 N | 197.839 N |
| Physical cuff moment peak | 53.568 Nm | 40.991 Nm |
| Maximum positive physical-norm minus held-command-norm residual | 26.101 N | 22.969 N |
| Acceleration combined RMS | 147.022 deg/s2 | 139.080 deg/s2 |
| Jerk combined RMS | 6379.619 deg/s3 | 5675.254 deg/s3 |
| Safety Filter status counts | 3204 unchanged, 6 filtered, 0 infeasible | 3209 unchanged, 1 filtered, 1 infeasible |
| Peak absolute filtered lambda | 50.065 | 22.536 |
| Reference Manager alpha | 0.5 throughout | 0.5 throughout |
| Bed-force nonzero samples | 397 (peak 840.228 N) | 0 (peak 0 N) |
| Bed-contact samples | not stored separately in preserved trace | 0 |

The same >200 N physical-force event did not remain under a completely
bed-contact-free trajectory history. This resolves the Phase-A full-history
confound for reproduction of the 218.441 N gate crossing: preceding bed
interaction materially changes the later closed-loop state. It does **not**
show that the suspended system is acceptable. The suspended run still retained
a positive command-to-physical norm residual (up to 22.969 N) and terminated
through the existing `BRAKE_INFEASIBLE` path at 16.055 s. No tuning or rerun was
performed.

## B.0 exact-state local authority

Every channel used the exact saved 16.045 s MuJoCo integration state. Responses
were recorded at 1--5 ms. The original executable force was exactly at the
200 N boundary, so the common comparison center was obtained by a 1 N radial
reduction to 199 N. This creates symmetric diagnostic headroom only; it is not
a selected controller margin. All plus/minus commands remained below 200 N.

The table reports the central 5 ms sensitivity of physical force norm and the
observed lower-force member of each symmetric pair. Raw sensitivities for force
vector, moment, Human generalized torque, cuff pose error, Human/robot
acceleration, and executable force are retained in `authority_audit.json`.

| Channel and perturbation coordinate | d|Fphys|/du at 5 ms | Tested reduction | Cuff displacement | Human / robot acceleration change |
|---|---:|---:|---:|---:|
| A1 allocator force magnitude, 0.25 N | 0.442 N/N | 0.114 N | 1.890 um | 0.0477 / 0.0367 rad/s2 |
| A2 allocator force direction, 0.25 N | -0.016 N/N | 0.008 N | 0.204 um | 0.0352 / 0.0657 rad/s2 |
| B null-space lambda, 0.25 force-normalized N | -0.592 N/N | 0.150 N | 0.412 um | 0.0108 / 0.0257 rad/s2 |
| C commanded cuff moment, 0.10 Nm | 8.087 N/Nm | 1.445 N | 2.327 um | 0.8104 / 0.6225 rad/s2 |
| D velocity-reference compliance, 0.001 m/s | 56.718 N/(m/s) | 0.066 N | 2.232 um | 0.0163 / 0.0365 rad/s2 |
| E pose-reference compliance, 0.00005 m | 1268.889 N/m | 0.070 N | 2.235 um | 0.0184 / 0.0379 rad/s2 |
| F existing Cartesian P/D scale, 0.001 | 53.182 N/fraction | 0.054 N | 2.309 um | 0.0278 / 0.0421 rad/s2 |

Commanded cuff moment has the strongest physical-force authority for the tested
step: -0.10 Nm reduced 5 ms physical force by 1.445 N without changing
executable translational force. That response is not task-neutral: the Human
generalized torque changed by approximately [-0.831, -0.045] Nm and the Human
acceleration norm changed by 0.810 rad/s2.

Null-space lambda provides the best low-disturbance tradeoff in this audit. A
+0.25 lambda step reduced physical force by 0.150 N and physical moment by
0.080 Nm, with 0.412 um cuff displacement and much smaller acceleration
changes. The static mapping residual was exactly zero in double precision,
`norm(B(q)n(q)) = 0`, while the 5 ms dynamic Human constraint torque still
changed slightly as the coupled state evolved.

## Dynamic null-space finding

The event is associated with an abrupt redundancy transition:

- lambda changed from -9.597 to -50.065 in one 5 ms cycle
  (`delta lambda = -40.468`);
- allocator force and moment slew reached 7992.975 N/s and 2934.816 Nm/s;
- total executable force and moment slew around the event reached 8615.559 N/s
  and 3423.685 Nm/s;
- the next 1 ms physical force and moment rates reached 44476.285 N/s and
  16841.940 Nm/s.

Thus the current memoryless filter can produce a dynamically aggressive wrench
transition even though the selected wrench increment is in the instantaneous
torque null space. The same-state continuity-direction test (+0.25 toward the
previous lambda) reduced 5 ms physical force by 0.150 N with small disturbance.
This is local evidence for continuity authority, not a validated slew limit.

A standalone lambda rate limiter is not justified: slowing the null-space move
can conflict with the independent 200 N executable-command gate. Continuity
must be handled jointly with command feasibility and measured interaction, with
the hard command gate retained.

## Architecture decision (recommendation only)

Recommend **A: interaction-aware wrench/allocator control** as the primary next
direction. The evidence places the largest local authority in commanded cuff
moment and the cleanest low-disturbance authority in allocator null-space
lambda. Velocity/pose compliance and existing P/D scaling had weaker reduction
for comparable small force changes and directly disturb task-space tracking.

The future interaction controller should treat measured physical cuff force
and moment as feedback and jointly coordinate allocator translational force,
cuff moment, and lambda while retaining the independent executable 200 N gate.
Lambda and total wrench continuity/slew regularization should be part of that
same optimization or control layer, but it must be feasibility-aware rather
than an independent post-filter limiter.

This task does not justify implementing a final allocator, admittance law,
impedance change, measured-force QP/CBF, new force margin, task relaxation,
BRAKE recovery, Reference Manager change, new MPC objective, trajectory-specific
tuning, Adaptive MPC, or additional seeds.

## Artifacts

- `results/engineering_validation/phase_a1_suspended_90_120_20260902/`
  contains the raw summary, trace, metrics, and frozen comparison.
- `results/engineering_validation/phase_b0_interaction_authority_audit_20260902/`
  contains the full A--F sensitivity record and pickle-free response NPZ.
