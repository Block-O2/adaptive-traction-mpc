# Scorer-v2 new-trajectory online/offline verification

**Status: `SCORER_V2_ONLINE_OFFLINE_CONFIRMED`.** One new `p03_rss` development trajectory was generated and preserved. The scorer-v2 post-run artifact and a separate offline process reading the same saved trajectory produced identical complete JSON. No second simulation was run.

## Frozen candidate and run

- Branch: `codex/full3d-cr12-waypoint-smoothness-v1`; starting HEAD: `1901d4f6806cf08016495cabace58626ce994181`. The pre-run source, config, scorer-v1 and scorer-v2 hashes in `SCORER_V2_NEW_RUN_FREEZE.json` match the post-run files exactly. Existing production dirty files were not edited in this turn.
- Command: `/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python /Users/hankli/Desktop/coding/adaptive-traction-mpc-waypoint-smoothness-v1/stages/stage5_personalized_motion_learning/scripts/high_rom_v1/run_dev_case.py --plant-mode high_rom --case /Users/hankli/Desktop/coding/adaptive-traction-mpc-waypoint-smoothness-v1/stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_nominal_sync_100_v1.json --output /Users/hankli/Desktop/coding/adaptive-traction-mpc-waypoint-smoothness-v1/stages/stage5_personalized_motion_learning/results/scorer_v2_endpoint_v1/p03_rss_development_01 --host-monitor-limit-s 300`. Runner: `COMPLETE`; host time 41.500 s. Native trajectory: `/Users/hankli/Desktop/coding/adaptive-traction-mpc-waypoint-smoothness-v1/stages/stage5_personalized_motion_learning/results/scorer_v2_endpoint_v1/p03_rss_development_01`.
- The scorer-v2 artifact was emitted **immediately after runner exit**, outside the control loop. It is a post-run evaluator artifact, not an in-control scorer. Its saved provenance maps the accepted physical COMPLETE commit to the exact last native physics node; no interpolation or favorable-sample search was used.

## Endpoint comparison

| Field | Scorer-v1 offline | Scorer-v2 post-run | Scorer-v2 independent offline |
|---|---:|---:|---:|
| Proposal/source sample (s) | 23.770000000022 | preserved | preserved |
| Physical COMPLETE commit / v2 sample (s) | — | 23.771750000022 | 23.771750000022 |
| True RETURN q (deg) | [4.957613602025322, 9.116041762909111] | [4.955468919323759, 9.119485754681914] | [4.955468919323759, 9.119485754681914] |
| True RETURN dq (deg/s) | [-1.2792471566681964, 1.9736939065650039] | [-1.1854192502482777, 1.9635463501587387] | [-1.1854192502482777, 1.9635463501587387] |
| RETURN / task result | True / True | True / True | True / True |

All required fields and the **entire scorer-v2 JSON** match exactly. Scorer-v1 remains reproducible with its original source-sample semantics. All non-RETURN conditions and metrics match v1 exactly; this new run is PASS under both v1 and v2. Original `p03_rss` and `p04_rss` scorer-v1 FAIL artifacts from the earlier audit remain unchanged.

## Task and safety context

The new run has continuous goal dwell 0.920 s, peak force 116.621 N, peak moment 16.049 Nm, minimum modeled session shank clearance 0.008494 m, and maximum plan activation age 53.661 ms. All frozen scorer conditions are PASS. The single-run control-miss rate is descriptive and was not used as this verification's gate. This does not establish a runtime gate, continuous-time safety or qualification.

## Checks, quota, and checkpoint

Four focused mapping tests passed; `py_compile` and `git diff --check` passed. An initial independent v1 invocation resolved an older module; it was discarded, and both v1/v2 were recomputed with explicit source paths inside this worktree. The recomputed scorer-v2 JSON is exactly equal to the post-run artifact.

Weekly quota `codex.primary`: 7% used at start and at latest valid read, 10080-minute window ending Unix 1791047434. One simulation was run, with no repeats. Raw native data is local and git-ignored; its SHA-256 and compact score artifacts are in `SCORER_V2_ONLINE_OFFLINE_FINGERPRINTS.json`. The local checkpoint commit contains scorer-v2, tests and compact validation evidence; its SHA is the branch HEAD immediately after checkpoint creation. No push, merge, reset, stash, clean or deletion was performed.
