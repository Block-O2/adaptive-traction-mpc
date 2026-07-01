# adaptive-traction-mpc

This repository studies safe online payload/contact identification and adaptive MPC for robotic traction tasks. The target use case is rehabilitation-oriented motion where a robot pulls or guides an elastic, spring-like, or limb-like object along a desired angular trajectory while limiting radial deformation.

## Current Status

- The MuJoCo elastic rod scene has been validated with a hardcoded known-trajectory controller.
- The formal algorithm integration is pending.
- Current simulation uses the UR5e model from `third_party/mujoco_menagerie`.
- `assets/robots/cr12_12_pending` contains pending CR12-12 lab robot assets only. It is not part of the current runnable simulation flow.
- Historical prototypes are archived under `legacy/`.

## Repository Layout

- `src/traction_mpc/`: formal package namespace for future environment, estimation, identification, safety, MPC, controller, experiment, evaluation, and visualization modules.
- `scripts/`: runnable utility scripts, including MuJoCo scene generation and validation.
- `assets/mujoco/`: generated MuJoCo scene XML used by the current validation flow.
- `assets/robots/cr12_12_pending/`: pending CR12-12 URDF and meshes for future lab integration.
- `third_party/mujoco_menagerie/`: external MuJoCo robot model assets.
- `legacy/`: archived stage 1 and stage 2 prototypes kept for reference.
- `results/`: logs, figures, videos, and debug outputs.
- `docs/`: project notes and archived documentation.
- `tests/`: future test suite.

## Setup

Install the Python dependencies in a virtual environment or conda environment:

```bash
pip install -r requirements.txt
pip install -e .
```

If the MuJoCo scene XML needs to be regenerated:

```bash
python scripts/make_mujoco_scene.py
```

## Scene Check

Run the validated hardcoded MuJoCo scene check:

```bash
python scripts/check_mujoco_scene.py
```

The script loads `assets/mujoco/scene_rod.xml`, drives the known contact trajectory, and writes debug CSV output under `results/debug/mujoco_scene_validation/`.

Useful target checks:

```bash
python scripts/check_mujoco_scene.py --target-deg 60
python scripts/check_mujoco_scene.py --target-deg 90
python scripts/check_mujoco_scene.py --target-deg 120
```

## TODO

- Connect the validated MuJoCo scene to the formal environment API.
- Port selected legacy MPC and estimation ideas into `src/traction_mpc/` only after the scene interface is stable.
- Add reproducible experiment configs and evaluation scripts.
- Add tests for sensor consistency, scene loading, and trajectory metrics.
- Keep CR12-12 integration separate until the URDF and lab workflow are stable.
