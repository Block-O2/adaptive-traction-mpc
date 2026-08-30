# Stage 4: adaptive control, trust, and validation

Stage 4 contains the online effective-dynamics estimator, causal
incumbent/challenger trust logic, Human-space MPC, report baselines, and the
curated simulation evidence built on the Stage-3 coupled plant. It imports
`traction_mpc_stage3` explicitly and does not duplicate Stage-3 mechanics.

## Layout

```text
stage4_adaptive_control/
├── configs/                    frozen experiment contracts
├── docs/research/              current state, specs, and evidence maps
├── scripts/                    canonical runners, summaries, and renderers
├── src/traction_mpc_stage4/    estimator, trust, MPC, allocation, reporting
├── tests/                      current regression suite
└── results/
    ├── robustness/             A/B, mismatch, sensors, trajectories, crossed
    ├── controller_validation/  gains, baselines, generalization, source index
    ├── negative_evidence/      failed preregistered PD-v1 gain selection
    ├── summaries/              repository-level concise indexes
    └── media/                  tracked real MuJoCo README media
```

Large raw robustness traces that were not required by current claims,
regressions, or media were removed from the active tree. Their aggregate
summaries remain here, the frozen configs/scripts can regenerate them, and the
full historical snapshots remain under `stage4-robustness-final-v1` and
`stage4-report-validation-final-v1`.

## Install and test

From the repository root, install Stage 3 before Stage 4:

```bash
conda run -n mpc_learn python -m pip install -e "stages/stage3_full3d[dev]"
conda run -n mpc_learn python -m pip install -e "stages/stage4_adaptive_control[dev]"

PYTHONPATH=stages/stage4_adaptive_control/src:stages/stage3_full3d/src:stages/stage4_adaptive_control \
  conda run -n mpc_learn pytest -q stages/stage4_adaptive_control/tests
```

The full professor-delivery MP4s are stored outside Git. To regenerate them
from frozen traces without running a controller or simulation, use `mjpython`
from this directory. The generated output goes under ignored `results/local/`:

```bash
cd stages/stage4_adaptive_control
PYTHONPATH=src:../stage3_full3d/src \
  mjpython scripts/render_stage4_professor_videos.py \
  --visualization-source-manifest results/controller_validation/visualization_sources/visualization_source_manifest.json \
  --generalization-config configs/stage4_report_generalization_matrix.json \
  --output-dir results/local/professor_videos_replay
```

Formal experiment commands are recorded in the approved specs. They remain
reserved for manual user execution and must never target an existing canonical
result directory.

## Evidence entry points

- [Current research state](docs/research/CURRENT_STATE.md)
- [Stage-4 robustness evidence](docs/research/STAGE4_EVIDENCE_MAP.md)
- [Controller/report evidence](docs/research/STAGE4_REPORT_VALIDATION_EVIDENCE_MAP.md)
- [Repository migration record](docs/STAGE4_REPOSITORY_MIGRATION.md)

The simulation is not a clinical safety, comfort, efficacy, certification, or
hardware-readiness claim.
