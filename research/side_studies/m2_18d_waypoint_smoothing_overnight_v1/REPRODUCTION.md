# Reproduction

Canonical package: `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1`. Runtime: `/home/hank/envs/adaptive-online-rl-v1/bin/python -B`; existing MuJoCo/NumPy/SciPy, single numerical thread. Windows mirror omits full raw/source; canonical raw remains under source/results with full native and receipt capture.

Do not rerun this stopped package in place or reset its attempts. Reproduce into a fresh versioned sibling after copying and rebasing the closure, preserving RUN_PLAN scientific criteria and a new explicit time budget. Prepare script is a historical bootstrap and must be adapted to a fresh path; its initial absolute-path-only rebase defect and repair are documented. No setup command here implicitly starts physics.

Completed physical commands: `python -B control/campaign.py` with default STUDY_GROUP=development1; if present, the second batch used STUDY_GROUP=development2. Each complete task arm is an os.fork of the full live parent, not a saved-state replay. The initial and follow-up executable plans and per-START manifest hashes are preserved.

Read-only calculation entries: control/analyze_batch.py, control/decompose_new.py, control/selection_review.py, control/accounting.py. They write only new-package diagnostics; the algebra script blocks mj_step/step1/step2. Original evaluation: code/analyze_matched.py. Safety contract tests: tests/test_certification.py (30 cases). Original runtime source and motion thresholds were preserved; all modifications and final hashes are in CODE_MANIFEST.

J_F uses original full TASK 5ms left quadrature with exact phase clipping. Native dq at0.25ms yields raw acceleration/jerk using original edge_order=2 gradients. Baseline archival trace gates, zero gates, current certificate reconstruction, native ownership and parent invariance have separate artifacts.
