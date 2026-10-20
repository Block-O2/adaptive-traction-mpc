# Coordination-space source audit

## Accurate residual semantics

The nominal B planner first selects a joint target. Relative to the registered phase origin and signed joint span, it forms normalized joint progress p, mean m, and differential d. The v2 adapter interpolates the proposed spatial residual graph at m. Except at the B-owned terminal target, it changes p by [delta,-delta], and converts that modified target back to joint radians. RETURN reverses both the origin and span, so the same delta sign has phase-relative meaning. This is a target proposal, not a continuously applied force or trajectory law.

Original B recomputes feasibility and a physical schedule for that target. The scheduler/governor owns q, dq, ddq, waits and duration. Modified progress outside [0,1] or a native feasibility rejection returns B. HOLD is skipped; phase endpoint residual is forced to zero. The historical_d_to_residual descriptor subtracts the current nominal differential from the requested historical graph; ordinary residual graphs are additive. These are different semantics.

## Four spaces

| Level | Expressible behavior | Restriction |
| --- | --- | --- |
| Raw existing v2 proposal | arbitrary finite PWL spatial graph, zero at 0/1, phase-specific graph | antisymmetric normalized progress, original requests only |
| Current K3 frontend | 30 bounded amplitudes: 2 phases × 5 issued slots × 3 knots | fixed knots .1/.4/.7 over remaining progress, zero after slot5 |
| Ordinary candidate pool | zero/carry/design/positive/negative/reversal with coherent seeded perturbations | budget6, sparse structured coverage, not exhaustive |
| Actual execution | accepted native target and certified schedule after guard/admission | reject, expiry, late carry, fallback, terminal ownership and actual command receipts |

K3 knots are at start_m+(1-start_m)*[.1,.4,.7], with residual zero at start_m and 1; an explicit zero at progress0 is prepended when needed. Native requests consume issued slots, including attempts that need not execute. This table is neither five equally spaced physical time windows nor a durable same-state intervention.

The ordinary generator uses ±.25 coherent tables, reversal [.35,-.25,.15], and sigma .08 Gaussian noise smoothed .7/.3 over slots, clipped to [-1,1]. Cross-phase reversal tables are appended but budget6 can truncate them. Local scores/certification evaluate current segments without integrating a hidden full physical task. The frozen linear Q has a state-independent relative preference on a fixed masked pool; feasibility, mask, carry and pool identity can still change.

Historical strong E searched a K2, 20-parameter phase/issued-slot table using bounded smoothed diagonal CEM (population8, elite3, up to14 generations, std .06/floor .006). It used full native physical tasks and original R2 timing gates, 92 search attempts and cold confirmation. Its confirmed force integral 1360.602793 N·s is retained only as a historical reference; its scientific clock and commissioning differ from the present host campaign.

## Unsearched versus absent freedoms

Amplitudes, phase allocations, local progress shapes, sparse issued-slot interventions and additional PWL knots are already representable at some existing-interface level. The present C campaign searches a small deterministic K3 slice; it does not exhaust these freedoms. Actual temporal smoothing cannot be commanded independently of the scheduler. Common-progress shifts or separate hip/knee target offsets are absent and would require a new native contract. There is no source basis for asserting that a smooth spatial graph necessarily produces smoother physical knee motion.

No Stage D native extension is authorized by a negative result on only this bounded slice. A missing common-progress freedom can be described conceptually as NOT_NATIVE_EXECUTABLE, without bypassing admission. Phase/shape failures remain research comparison results rather than native safety failures.

## Frozen prospective experiment

EXPERIMENT_PROTOCOL.json defines 12 deterministic tables plus matched zero/M2 baselines, full OUT/HOLD/RETURN tasks, fixed nominal Human, physical dt .00025 s, original 40ms bridge and100ms expiry. TableCoordinator supplies only an existing residual_spec through the same C13 immutable envelope. It does not modify B, native authority or a schedule. Every attempt, failed guard, native rejection and actually applied residual is retained.

Source hashes and exact file paths: COORDINATION_SPACE_AUDIT.json.
