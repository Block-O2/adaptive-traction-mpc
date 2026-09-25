# Qualification Attempt 2 preregistration

Status: F0 preregistered under generation protocol `qualification_attempt2_generation_v2`; zero Attempt 2 proposals or simulations executed. The first pre-generation draft is preserved in `audits/qualification_attempt2_v1/superseded_pregen_v1/`. This v2 stream amendment is controlling for Attempt 2.

- Candidate: frozen Round19 round19_full23_confirmation_v1. Source manifest SHA-256 2880c67d0844ce551ff068474642a4b6ff9bc1fa2d7c81dfcd6914dd32c1ab99; config SHA-256 d11bb72950f9f74e451548f57ff509e89f92e10aa18f8c62f78bd7a4b7f4c6bb.
- Contract: FRESH_QUALIFICATION_V1.md, 48 slots = four replicates × four task families × three range cells. The presealed Batch 2 root is 7433081872978425150. Attempt 1 is an exposed failed 48-slot attempt and remains excluded.
- Generator: unchanged frozen draw ranges, mechanical screen, v1→v2 assembly repair, 30 proposals per slot, and slot execution order. This versioned qualification adapter routes the first four uniform draws of each proposal to a separate per-slot task PCG64 stream and the remaining physical setup draws to a separate per-slot setup PCG64 stream. Both are SHA-256 derivations from the presealed slot seed; stream states continue across rejected proposals. This changes random coupling only, before observing Attempt 2 outcomes. All proposals and rejections are logged.
- Exclude all 48 Attempt 1 slot seeds and case contents plus all development case contents. Any exact duplicate is invalid; never replace a case after exposure. Failed or precheck-rejected slots remain in the 48 denominator.
- Simulation chain: CR12 → compliant cuff → Human V2 → deployable observations → frozen Round19 controller and real simulated feedback. No oracle online input.
- Frozen task/safety: original phase, task and session timeout; physical arrival, continuous 0.500000 s dwell and actual RETURN; force/moment, velocity/acceleration, sleeve/shank/table clearance; 100 ms stale-plan activation rule. The hashed source/config and FRESH_QUALIFICATION_V1.md govern exact values.
- Frozen gate: at least 46/48 true complete; at least one completion in each of 12 cells; at least 36/48 adaptation-active cases; no unexplained concentrated failure; both original and actual-receipt ZOH quality (median q RMSE ≤2°, pooled q p95 ≤5°, median dq RMSE ≤5°/s); zero registered native-node safety violations and zero stale activation; complete evidence/provenance. Normal case failures do not stop the batch.
- Evidence: all 48 task/arrival/dwell/RETURN/COMPLETE and failure categories, dual quality, timing, requests and ages, native 0.25 ms sampled-node safety. Sampled-node evidence does not prove mathematical continuous-time safety or hardware readiness.
- Exactly one Attempt 2; no production modification, controller repair, outcome-based exclusion, rerun or Attempt 3. One independent read-only Auditor checks F0 and final evidence.

The compatibility gate and candidate seal in audits/qualification_attempt2_v1 bind frozen Round19 development evidence into the existing qualification lifecycle validator. They are evidence adapters, not new development experiments.

The versioned case-generation amendment is [QUALIFICATION_ATTEMPT2_STREAM_AMENDMENT_V2.md](QUALIFICATION_ATTEMPT2_STREAM_AMENDMENT_V2.md). The internal v1 lifecycle identifier remains only for the unmodified bundle validator.
