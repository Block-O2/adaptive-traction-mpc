# Phase 1B Candidate Freeze V1

Status: **NOT FROZEN — AUDITOR NO-GO / BLOCKED_CONTRACT_CHANGE_REQUIRED**.

The evidence below remains a Builder candidate record. Independent audit found
the architecture credible but declined freeze because conservative material-
revision accounting is at least `7/6`. It also required exact post-probe
constructed-reference clearance instrumentation; that evaluation-only repair
has been added, but no further campaign was run after the contract stop.

## Candidate evidence

The authoritative candidate development result is:

`results/architecture_recovery_v2/phase1b/combined_development_v1_runtime_fix_rerun/result.json`

- Result SHA-256: `d4032ba854c70c37e12298c68a2feddcb2187c39cfce2500087eebb1dcd2e978`
- Config SHA-256: `6331c776878d32a9a0a42a6c4ce78d54cebdb99513f833fd17fb1d6a98eb6bee`
- `functional_benchmark.py`: `8f07df1a26e1bcfee92d3cf1b67e0f90a690ff113248f169d5153110e5cc72c3`
- `effective_model.py`: `41a4730ef071fa84fa84d73c3a4bfa98a1230848c6e08bb42018f47643c6987c`
- `run_functional_campaign.py`: `34ac0e3791773e8a98a8afbb6d7fc0c3d7aa8c1e6a5464543547985b33c160c2`
- Branch/HEAD: `codex/stage5-architecture-recovery` /
  `4caea258ec1450f082bb7cb8097cc1441bdf589f`
- Source/config changed during run: false.
- Git status changed during run: false.
- Runner exceptions: zero.
- Frozen development gates: all passed.

## Candidate architecture and domain

- Causal effective geometry: `(hip_x, hip_z, thigh_length,
  knee_to_cuff_distance)` from cuff pose history; full shank length and cuff
  fraction remain individually unreconstructed.
- Dynamics: causal bounded 11-beta control-effective identifier, continual
  updates retained because commissioning-only completed 3/8 and fixed dynamics
  completed 1/8 in the simplicity regression versus full adaptive 5/8 before
  the final mass repairs.
- Validity: minimum predicted mass-matrix eigenvalue `0.03`; an invalid inertia
  proposal freezes the three inertia coefficients at last-valid values and
  conditionally refits the remaining coefficients.
- Probe: original one-sided excitation at 100 Hz, followed by an event-driven
  hold at the intended interior pose until 20 consecutive estimated-velocity
  samples are below 5 deg/s; 4 s hard settle timeout.
- Task profiles: coordinated, hip-led, two-rate, and versioned bounded knee-led
  (`0.65/0.72` normalized hip/knee progress at 52% outbound, exact reverse).
- Mechanics: flat bed plus analytical shank capsule; 12 mm bed height, 45 mm
  shank radius, 25 mm minimum certified reference clearance, 150 N/45 Nm
  generation static-wrench screens, and actual hidden clearance evaluated at
  every <=5 ms integration substep.
- Domain remains conditional: tasks are fixed while hidden setups are
  rejection-sampled. Post-hoc recertification of the 640 stored unconditioned
  proposals from the 10 mm characterization retained 516/640 (80.6%) at a
  25 mm reserve; this was not the configured 10 mm acceptance result. The
  final combined matrix realized 80.0% under its configured 25 mm reserve.

## Explicit limitations

The result is simulation development evidence, not held-out or hardware
evidence. The clearance model covers a shank capsule and flat bed only; it does
not cover contact dynamics, thigh/body/cuff collision, pressure, tissue safety,
robot reach, robot torque, or physical sensing/calibration. Ideal noiseless cuff
twist remains a frozen simulation assumption. The current verified Human-V2
ROM remains q1 <= 80 deg and q2 <= 100 deg, so simultaneous 120–130 deg claims
are outside this plant. Reference-clearance cases between 10 and 25 mm remain
physically feasible but are explicitly outside the retained commissioning
domain because the unmodified excitation was not mechanically reliable there.

No Phase-2 seed, config, or outcome has been generated or viewed by the Builder
at this candidate-freeze checkpoint.
