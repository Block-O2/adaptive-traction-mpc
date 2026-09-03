# Coarse ROM capability engineering audit

## Commissioning setup finding — do not promote this as a verified envelope

Only 40/40 was executed. Its observed task status is SAFE_INCOMPLETE and its
force status is STRICT_PASS. The reference finished at 14.107 s, but target
error was 1.681794 deg and return error was 0.612729 deg. No further grid run
was executed and no controller or threshold was retuned.

Post-run read-only diagnosis also found that the full-model-freeze requirement
was not met: dynamic beta stayed exactly at its population prior, but the
existing geometry estimator remained active in `estimator.model`. During the
target hold, knee state estimation was low by 1.755077 deg on average. This
is a plausible proximal explanation for the endpoint discrepancy, not a
causally isolated conclusion. See `commissioning_diagnosis.json` for evidence.

The maps are commissioning diagnostics only. They do not establish a verified
ROM region. The three unverified continuous IK paths (120/40, 120/60, 120/80)
are separately recorded in `prechecks.json`; no claim of global structural
impossibility is made. Other cells remain NOT_RUN.

The separately recorded dynamic-beta check must not be read as proof of a
fully frozen geometry-plus-dynamics model. The original run artifacts are
retained without rewriting the observed unfavorable result.

MPC mean/p95/max latency was 10.717/10.936/12.898 ms (zero 20 ms misses).
High-level fast-path mean/p95/max was 12.399/12.650/14.624 ms (zero 20 ms misses).
Existing 200 Hz filter/BRAKE plus Reference Manager path had one 5 ms deadline
miss (maximum 22.793 ms). Its timing excludes the separately recorded physical
force supervisor, whose per-sample p95/max was 0.020917/2.157791 ms. These are
desktop measurements, not a hard-realtime guarantee.

No speed-boundary recommendations are justified until commissioning wiring is
reviewed. Changing the geometry-freeze boundary or rerunning commissioning
requires the next explicit instruction.

Scan spec SHA: `02114e3217eb0f993531951e51e946c5ca1087a37661f6aa68f36ba75adeec79`

Executed 1 / 27. Verified sampled endpoints: []. No unsampled region is implied.
Tracking is reported continuously; no nominal/degraded-quality band was invented.

Commissioning did not complete cleanly. Remaining grid was not executed, as required.
No ROM-region, hip-versus-knee limitation, or envelope-expansion conclusion is supported.
No 3–6 speed-boundary trajectories are recommended from a failed commissioning gate; diagnose setup first.

| Hip/knee | Task | Force | End error deg | RMSE deg | Physical peak N |
|---|---|---|---:|---:|---:|
| [40, 40] | SAFE_INCOMPLETE | STRICT_PASS | 1.6817939615472 | 0.8068906429687372 | 122.9612622231222 |
| [40, 60] | NOT_RUN | — | None | None | None |
| [40, 80] | NOT_RUN | — | None | None | None |
| [40, 100] | NOT_RUN | — | None | None | None |
| [40, 120] | NOT_RUN | — | None | None | None |
| [60, 40] | NOT_RUN | — | None | None | None |
| [60, 60] | NOT_RUN | — | None | None | None |
| [60, 80] | NOT_RUN | — | None | None | None |
| [60, 100] | NOT_RUN | — | None | None | None |
| [60, 120] | NOT_RUN | — | None | None | None |
| [80, 40] | NOT_RUN | — | None | None | None |
| [80, 60] | NOT_RUN | — | None | None | None |
| [80, 80] | NOT_RUN | — | None | None | None |
| [80, 100] | NOT_RUN | — | None | None | None |
| [80, 120] | NOT_RUN | — | None | None | None |
| [100, 40] | NOT_RUN | — | None | None | None |
| [100, 60] | NOT_RUN | — | None | None | None |
| [100, 80] | NOT_RUN | — | None | None | None |
| [100, 100] | NOT_RUN | — | None | None | None |
| [100, 120] | NOT_RUN | — | None | None | None |
| [120, 40] | NOT_RUN | — | None | None | None |
| [120, 60] | NOT_RUN | — | None | None | None |
| [120, 80] | NOT_RUN | — | None | None | None |
| [120, 100] | NOT_RUN | — | None | None | None |
| [120, 120] | NOT_RUN | — | None | None | None |
| [75, 90] | NOT_RUN | — | None | None | None |
| [90, 120] | NOT_RUN | — | None | None | None |
