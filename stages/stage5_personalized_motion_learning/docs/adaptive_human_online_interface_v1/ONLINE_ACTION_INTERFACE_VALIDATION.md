# Online action qualification

QUALIFIED_IN_TESTED_SCIENTIFIC_SIMULATION_DOMAIN. Seven kinematic/ownership unit tests; 16/16 complete blocker criteria; 44 adversarial probes; 48 deterministic reference streams; 9 successful full physical online runs. Two earlier integration aborts remain in the data. Two subsequent Gym smoke runs also pass the inherited physical/scientific evaluator.

| command period ms | first changed receipt task s | reference effect ms | physical difference ms | physical pass |
| --- | --- | --- | --- | --- |
| 5 | 0.505 | 5.000 | 10.000 | PASS |
| 10 | 0.505 | 5.000 | 10.000 | PASS |
| 20 | 0.505 | 5.000 | 10.000 | PASS |
| 50 | 0.505 | 5.000 | 10.000 | PASS |


Actual first local-switch reference differences use the recorded six-dimensional q/dq/ddq against the same-interface constant-target run, threshold 1e-8; physical differences use evaluation-only Human q, threshold 1e-7 rad. This is a controlled first-command difference measurement, not per-command plant settling latency or host inference delay. The remaining stream may supersede accepted commands before their individually predicted effects.

Reference-only stream changed-command effects range 5.0–60.0 ms. Some small forward adversarial changes share a saturated prefix for about 410–460 ms, still preceding the former endpoint. Far-endpoint physical switch inputs were superseded before visible change; their successful completion does not demonstrate action freedom. The separate local-switch tests supply that evidence.

Short-stream host realization median 3.173 ms, maximum 9.884 ms. Full physical changed-command host profile: median 7.061 ms, maximum 87.470 ms. Full-horizon clearance and mechanics certification is retained at every accepted update and on model-signature changes. Timing excludes separately attributed identical-command revalidation; complete per-run wall duration remains recorded. Scientific physics freezes while computing. No hardware realtime claim, no silent lookahead bypass.

Raw scorer wall-age outputs are retained; physical/scientific PASS comes from the unchanged evaluate_execution_mode.py plus explicit new online continuity/chronology/certificate checks. The original 100 ms wall-age rule has not been relaxed or promoted to a realtime PASS.
