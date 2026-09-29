# Rep14 clearance forensic plan (frozen)

Question: why did Rep14 OUTBOUND lose incremental clearance after Rep1–13 passed in one zero-value session? The original V2 FAIL remains unchanged.

Hypotheses are fixed before analysis: **A** Human model/adaptation drift; **B** persistent causal-history or estimator implementation defect; **C** waypoint/candidate low-clearance selection; **D** accumulated physical-state drift; **E** valid safety rejection of real geometry; **F** other or insufficient evidence.

First verify raw and checkpoint hashes, source/config/seed and production fingerprint. Audit Rep10–14 model, estimator, geometry, waypoint, start/end states and timing. Locate the last legal and first invalid native/control states. Restore the exact formal Rep13 checkpoint twice in separate replay directories, with identical control logic. Compare failure time and scientific states. Only use offline counterfactuals for causal separation. Nondeterministic replay takes precedence over algorithmic attribution.

A production fix is permitted only if a timestamp/history alignment, checkpoint serialization, persistence/reset, or deterministic bookkeeping defect is demonstrated. Limit to one minimal fix, regression test, and exact checkpoint replay. Do not alter controller mathematics, planner cost, Human dynamics, scientific scheduler, safety threshold, or clearance requirement. Do not run a new 30-repetition campaign.
