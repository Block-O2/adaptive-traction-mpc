# Phase-3A 90/120 and mechanism-audit provenance checkpoint

This checkpoint records the completed exploratory 90/120 rigid-versus-P1 pair and the read-only rigid 40/80 versus 90/120 return-mechanism audit. It does not change any controller, interface, model, safety, solver, timestep, seed, trajectory, force-limit, measurement-boundary, or completion-tolerance setting.

## Included evidence

- `docs/PROGRESSIVE_90_120_AB_SPEC.{json,md}`
- `scripts/run_progressive_90_120_ab.py`
- `scripts/summarize_progressive_90_120_ab.py`
- `tests/test_progressive_90_120_ab.py`
- `results/engineering_validation/progressive_90_120_ab_20260907_v1/`
- `scripts/audit_progressive_rigid_return_mechanism.py`
- `results/engineering_validation/rigid_return_mechanism_audit_20260907_v1/`

The 90/120 Spec is historically bound to checkpoint `5e3800ae6570c45b125e74ea678cdf2b72f48d69`. The saved registration, run configurations, initial-state files, model locks, raw traces, reports, metrics, plots, and SHA256 manifests preserve that provenance.

## Historical 40/80 HEAD lock

`PROGRESSIVE_40_80_AB_SPEC.json` remains bound to `99169491ea1336d6af74e3b63318afba18c1e881`. Its contract preflight intentionally rejects later HEADs. After the authorized provenance commits, tests that call this historical contract report a HEAD assertion mismatch. The old Spec is not edited or relabeled to make those tests pass.

This mismatch is provenance-only: the historical 40/80 evidence, its frozen source hashes, and its scientific result are unchanged. It is not evidence of a controller, model, parameter, or scientific regression.

## Validation at checkpoint preparation

- 90/120 test module: 14 passed.
- Combined 40/80 and 90/120 invocation: 16 passed and 12 setup errors; every setup error came from the expected historical 40/80 HEAD assertion.
- Mechanism audit reproduced byte-for-byte from saved evidence.
- Audit SHA256 manifest verified.
- `git diff --check` passed.

The next 120/120 exploratory Spec must be created independently and bound to the commit containing this provenance record.
