# B Multi-Rate Real-Time Architecture v1 — frozen contract

Start: 2026-10-07, Asia/Shanghai. RUN_PLAN.json carries authoritative wall timestamps, 8-hour hard cap and 45-minute reserved closeout. Only local MuJoCo simulation is dispatched. One physical plant owner at a time. No Q/G/learning training or inference in B gates. No Git mutations.

Source authority: isolated copy of prior integration frozen B runtime, original Human physics, native scheduler, PlanLifecycle, receipt_reference_governor, activation_validation and original R2/strict evaluator. SOURCE_MANIFEST.json and source relocation records identify bytes. Historical artifacts are protected by a full file/hash inventory. Windows authoring folder is an evidence workspace rather than the WSL primary Git repository.

## Time semantics (unchanged)

- Native physics: 0.25 ms. Sensor and service cadence: 5 ms.
- Physical handoff bridge: 8 × 5 ms = 40 ms (safe_fallback.prepare_decision).
- Strict qualification activation age: less than 55 ms, measured from original source_capture_ns to conservative actual activation. This is retained from the prior host/learning execution qualification and the user's current contract. The native execution-mode evaluator reports its separate configured strict_age_limit_ms=100; native generic activation is not evidence of meeting <55 ms. Both evaluators must pass and neither threshold is edited.
- Generic lifecycle expiry: age >=100 ms. Wall command write retains original >100 ms pre/post-write comparison. These boundaries are separate.
- Original fixed-grid source acquisition time and actual host materialization time are logged separately. No source timestamp rewriting, fake age, retroactive activation, missed callback fabrication, or physics pause while planner computes in host mode.

## Ownership

FAST owner: plant, sensor capture, causal observer/monitor, original low-level controller and safety filter, current legal reference/command, receipt application, mandatory current-state admission, fallback and native physics integration. It may never wait for a planning future in host mode. Absence of a fresh proposal retains the original legal carry/fallback; original phase/HOLD and task deadlines govern.

SLOW owner: a prewarmed spawn process, original B planner mathematics, scheduler/mechanics preparation and proposal construction on immutable serialized deployable inputs. No runtime/plant may be sent. Native lifecycle has one outstanding task request and bounded worker lifecycle; original pending/cancel/expiry rules remain authoritative.

Proposal admission: original source age, current belief sequence/model, phase, schedule identity/reference compatibility, current mechanics, clearance, ROM, motion, original goal/remaining phase time and final command safety/receipt checks. Earlier worker validation cannot substitute for current mandatory checks. A revalidation failure is a failed proposal/attempt, never a reason to loosen thresholds.

Commissioning target selection and model estimation are initially synchronous in frozen source. Later revisions may move them to a distinct execution owner. Candidate model updates must be built privately, validated, and published atomically with a monotonic version. The estimator equations and ordered measurements remain unchanged.

## Gates and preregistered comparisons

Every substantive revision: nominal B and frozen legal deviation full scientific regression, then timing smoke, then host ladder. Deviation is the prior legal prefix OUTBOUND [[.2,.1,-.1],[.05,.15,.25]], followed by original B, with no Q. Identical baseline/candidate seeds 2026100621 and 2026100623. All native step arrays/contact, 5 ms trace, reference q/dq/ddq, actuator commands, selected native decisions, safety, fallback, OUT/HOLD/RETURN and original J_F/force/moment/tracking/clearance must match. Prefer exact physical signatures; absolute tolerance 1e-10 is frozen before results. Host diagnostic timestamps and measured computation runtimes are excluded from scientific comparisons. No tolerance changes after inspection. These deterministic regressions are not held-out scientific robustness evidence.

Level 1 records real fast-service idle and active windows; timer-only isolation can provide auxiliary evidence only. Level 2 real B proposal transport and admission. Level 3 fresh nontrivial plans physically execute (HOLD/no-op excluded). Level 4 complete physical task plus original R2/safety. Level 5 four cold and four consecutive/session runs; new plant per consecutive run must be explicitly distinguished from continuous plant repetitions.

Qualification requires all requested conditions and unchanged independent realtime evaluator, not just mean planner <55 ms. Report all deadline/service misses, ages and censoring, p50/p90/p95/p99/max. At most three architecture revisions. Frozen M2 smoke is forbidden before B_HOST_QUALIFIED and requires >=1.5 hours remaining; maximum 8 runs, existing six candidates and exact frozen Q SHA only. No adaptation.

Resource samples every 45 seconds while jobs run: WSL MemAvailable/swap-in/out/owned PSS/process count, Windows commit headroom, CPU load. Short dispatch resource pressure pauses new work while owned jobs release; no WSL restart, unknown-process kill, RAM/swap change or cache drop.

R1: native process planner plus immutable version/identity auditing and complete service instrumentation. Existing process support is reused and is not claimed as a newly invented speedup. Remaining blocking commissioning and admission work is measured explicitly.

R2: separate prewarmed commissioning target process. While it computes, the sole plant owner services the last legal native reference through the unchanged controller/safety/receipt chain. A new causal observation and measured sleeve gap are acquired on return for command admission; the original request timestamp remains unchanged. Scientific mode alone waits without advancing physical ticks, preserving deterministic regression semantics. In real host mode, target estimation never owns the physical clock.

R3: additionally fit/replay commissioning measurements privately in the slow process, validate and atomically return a complete belief/updater version. Task arm remains original commissioning_only, hence no new continual task estimator updates are enabled. Prepare original mechanics certificates in the planner process with an exact hash of every screen/belief/candidate/schedule input; FAST verifies the current complete input hash and otherwise invokes native recomputation. All current-state/age/phase/goal/clearance/motion/final command checks stay native. Original evaluation-only native-node aggregation is deferred using the previously preserved formula wrapper; raw samples, safety/observer/controller and physics are untouched. This is off-critical dataflow, not a controller math change.

Instrumentation corrections preserve their previous source bytes. Earlier R1 scientific sensor-capture cadence is auxiliary host diagnostic data only; corrected host instrumentation measures actual feedback services, while sensor-only captures and extra services within a period are separately identified. No scientific-simulation cadence is treated as real host qualification.
