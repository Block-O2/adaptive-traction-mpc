# Project Overview

[Home](../README.md) · [Architecture](architecture.md) · [Roadmap](development-roadmap.md)

## Research Direction

Adaptive Traction MPC studies robot-assisted lower-limb motion in MuJoCo.
A robot interacts with a passive two-joint leg through a cuff, with a support
surface and explicit coupled mechanics. The development goal is to combine
tracking, interaction-load management and personalization under uncertain
human dynamics.

The project develops the simulation plant, measurement interfaces, estimation,
control, motion generation and evaluation tools together. Its scope is
simulation-based robotics research. It has not reached robot/human trials or
clinical validation.

## Development Stages

| Stage | Engineering question | Retained implementation |
| --- | --- | --- |
| [1](../stages/stage1/README.md) | How do estimation and uncertain dynamics affect traction MPC? | Single-link Spring2D, state/parameter estimation, planner/tracker studies |
| [2](../stages/stage2_linkage/README.md) | How can robot motion drive a two-joint leg through a cuff? | Planar Human V2, rigid cuff linkage, reconstructed wrench |
| [3](../stages/stage3_full3d/README.md) | How can the coupled task use a full-3D robot model? | Torque-actuated UR10e surrogate, frames, robot/Human/cuff plant |
| [4](../stages/stage4_adaptive_control/README.md) | When should an estimated effective-dynamics model enter MPC? | Causal estimation, incumbent/challenger trust, constrained MPC, saved simulation studies |
| [5, archived snapshot](https://github.com/Block-O2/adaptive-traction-mpc/tree/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/stages/stage5_personalized_motion_learning) | How should motion planning, personalization and learning connect to protected execution? | Human waypoint planning, scheduler/governor, execution lifecycle and isolated research variants |

The stages record successive development, not interchangeable controller
packages. Stage 4 imports Stage 3 explicitly. Stage 1 and Stage 2 both expose
historical `traction_mpc` packages and should use separate environments rather
than be installed together indiscriminately.

## Current Development Context

The default branch's source baseline is the 2026-09-08 Stage 1–4 checkpoint
(`2c2140deac8ef91aa69c57af886243f68df485ec`). The
[2026-10-28 archive branch](https://github.com/Block-O2/adaptive-traction-mpc/tree/archive/research-closure-20261028)
contains later Stage-5 source, side studies, selected learning artifacts and
portable reproduction tools. Links in these guides pin that reviewed snapshot
to `11af82a7ee35ae3c8e41e4b84d235a494b117d8d`.

The archive's title and older stage guides describe completed or paused
studies. Those local conclusions remain historical records. The overall
repository continues as a work-in-progress research platform; these new
guides do not promote all archived modules into an integrated default system.

Some labels used in the later research need context:

- **Controller B** is the protected traditional waypoint-MPC execution baseline
  within those snapshots. Its nominal learning value term is zero; online
  observation updates alone do not establish continual learning.
- **18D** denotes an isolated parameterization of motion intent for coordination
  studies. It is not an 18-joint robot or an approved replacement for B.
- **H150** is a historical timing/posture schedule variant with specific task
  and parent-state conditions. Its name is not a runtime qualification.
- **Learning** covers several value/Q, imitation and RL interfaces with
  different input/action contracts. Selected trained artifacts exist, but
  reliable additional benefit over strong traditional alternatives remains open.

See [research notes](research-notes/README.md) for the original definitions.

## Open Work and Limits

Motion coordination, transition smoothness, execution timing and learning
integration remain open. A smooth quintic reference does not by itself make
the measured human motion or cuff force smooth. Similarly, deterministic
scientific simulation does not establish host-clock execution readiness.

The UR10e is a simulation surrogate. Cuff surface-load proxies and registered
force gates are engineering quantities, not patient comfort, tissue stress or
clinical thresholds. Hardware geometry, sensing, calibration, emergency-stop
behavior and clinical suitability require independent work.

The [roadmap](development-roadmap.md) describes the next engineering questions.
Historical studies, failures and original hashes remain linked from the
[experiment index](experiments/README.md).
