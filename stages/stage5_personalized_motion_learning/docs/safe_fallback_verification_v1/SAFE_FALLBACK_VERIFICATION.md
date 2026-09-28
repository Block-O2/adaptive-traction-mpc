# Safe Fallback verification v1

Status: **FALLBACK_EXECUTION_REPRESENTATIVE_READY** (intermediate checkpoint; 49-case freeze pending).

- Branch: `codex/learning-safe-fallback-v1`; source HEAD before this stage: `0cb898b61497b51b5d2a645b3941d03dd3f3f74b`.
- Frozen 179-file production/config/scorer fingerprint: `5a4b1d15f0711c349926cba2ed604906853215edd7cfdee6d188a7bac1c72ae7`. No production source, scientific parameters, scorer thresholds, task, plant or safety limits changed.
- Prechecks: 15/15 fallback/scorer-v2 deterministic tests; XML nq=nv=6; runtime import; case hashes and harness hash; `git diff --check` PASS. A first import command omitted Stage-4 PYTHONPATH and failed; a corrected import check passed.
- Targeted: **8/8 PASS**. The final variable-start case ran once and completed, scorer-v2 PASS, C2 PASS, reference near-stop 0.150 s, stale activation 0, fallback count 0. The earlier seven runs were retained. Original-natural and delay-0 have preserved evidence-only corrected reviews, because original Boolean bookkeeping marked their intentional natural fallback near-stop incorrectly; raw runs were not repeated.
- Representative: **8/8 PASS**, all eight rerun once under the Safe Fallback fingerprint in the original frozen order. Fallback commits 0; stale activations 0; minimum goal dwell 0.580 s; peak force 117.000 N; peak moment 15.966 Nm; minimum session clearance 0.004022 m. All scorer-v2 conditions, C2 switch checks and frozen near-stop caps passed. The highest activation p95 was 58.750 ms.
- Targeted runs contained 5 committed fallbacks; all corresponding cases completed. The retained natural case reproduced a 191.053 ms planner compute tail and recovered. This representative matrix did not happen to trigger fallback; the controlled targeted cases establish its observed recovery behavior.
- Historical `RSS_RUNTIME_QUALIFICATION_NOT_MET`, 55 ms activation-tail failure, previous 49-case functional failure and scorer-v1 failures remain unchanged. Activation timing is characterization, not a hardware or hard-realtime qualification.
- Raw traces remain Git-ignored. `RAW_DATA_MANIFEST.json` hashes the new representative runs and new targeted case; the prior seven targeted runs are linked through the retained earlier manifest. No failed output was removed or overwritten.

Next stage: a fresh same-version 49-case preregistration and one run per case. This intermediate status does not authorize 30-repeat, value learning, RL or hardware use.
