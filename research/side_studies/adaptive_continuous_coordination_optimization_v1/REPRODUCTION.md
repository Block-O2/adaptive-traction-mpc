# Reproduction and preservation

Canonical full package: `/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1`. Windows folder is a light review/export copy; raw compressed physics remains canonical in WSL.

Python: `/home/hank/envs/adaptive-online-rl-v1/bin/python`; Python 3.10.21. Serial CPU MuJoCo scientific simulation; BLAS/OMP/MKL threads=1. No new dependency installation. Original B/18D/native evidence locations and hashes are in DIAGNOSTIC_RESULTS.json; they must remain available for archived comparisons.

This package is STOPPED. Do not delete PHYSICS_STOP.json or reset ATTEMPTS.jsonl. No default reproduction command dispatches physics. To authorize another campaign use a new output/version with fresh budgets and preserve this record.

Read-only evidence recomputation (writes analysis outputs only, no physics):

```bash
/home/hank/envs/adaptive-online-rl-v1/bin/python -B /home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1/control/diagnostics.py
/home/hank/envs/adaptive-online-rl-v1/bin/python -B /home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1/control/enrich_diagnostics.py
/home/hank/envs/adaptive-online-rl-v1/bin/python -B /home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1/control/postprocess.py
/home/hank/envs/adaptive-online-rl-v1/bin/python -B /home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1/control/protection_audit.py
```

For immutable verification copy the package first, since analysis regenerates timestamps/figures/JSON. Inherited fixture/certification tests use the read-only key_traces link to the previous package; that is an explicit archive dependency. Active `source/code/deps/weights` are new isolated copies with rebased paths, not links to production.

Physical command executed once after a pre-physics dependency-startup repair: `/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1/control/owner.py`, which owns campaign.py and joins its process. Every actual START includes code-manifest hash; all children inherit the same full process state at a legal boundary, keep normal current-state admission and native ownership, and never replay/set Human state. The pre-physics missing-contract failure is archived; it produced no physical START. Initial wrong-path unit imports were repaired before physics and all30+12tests rerun. Source rebase and startup repairs are documented under audit/.

Executed source is fixed by EXECUTION_CODE_MANIFEST.json. Postprocessing scripts may be added afterward; only control/diagnostics.py was enriched after the execution freeze, with curvature derivative diagnostic output, and this file is not imported by campaign/plant. No active physical code was edited during the campaign. `multisegment_reference.py` is the sole semantic delta in the copied plant/controller closure; safety/current certificate functions have identical ASTs. Source relocation is not counted as a controller change.

Evidence chain: MATHEMATICAL_TRAJECTORY coefficients → CERTIFIED_REFERENCE ID/path certificate → ACTIVATED_REFERENCE learning record → ISSUED_REFERENCE samples → APPLIED_COMMAND positive-step receipt/torque → ACTUAL_HUMAN_MOTION native q/dq. Every new multi receipt additionally archives full current path certificate content and reconstructs its ID. Native steps are uniquely joined to receipt intervals and exact torques; raw full-task/phase integrals close within1e-8.

Candidate IDs, parent hash, reference parameters/count/placement/node q/timing, reference/certificate hashes, issued/applied evidence, actual q/dq, forces/moments, task/motion/safety/tracking and wall durations are retained across CANDIDATE_RESULTS, output/*REFERENCE*, reports/*MEASURED and source/results/*/runtime_artifacts.json.gz. Force samples are5ms; Human derivatives are0.25ms. All failed/partial runs remainunranked in the denominator.

No stage/commit/push/merge/reset/stash/delete of unrelated material. Starting/final git state matches. No hardware, learning, production tuning or next package. Exact current stop markers and process ownership are recorded in PACKAGE_VERIFICATION.json.
