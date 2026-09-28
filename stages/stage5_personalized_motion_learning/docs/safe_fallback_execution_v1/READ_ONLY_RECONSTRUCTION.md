# Safe fallback architecture — read-only review, awaiting authorization recognition

This is a review draft, not an implementation freeze or a successful validation result.
Target workspace: `/Users/hankli/Desktop/coding/adaptive-traction-mpc-learning`.
No production, config, historical evidence or Git state was changed. No new dynamic rollout was started.
The attempted combined provenance-write/commit/branch command was rejected before execution.

## Verified provenance

- Branch: `codex/adaptive-traction-learning-baseline`.
- HEAD: `5d977ab321af72d4ddb8fef919449c37ad67a4f9`.
- 178-file source/config/scorer fingerprint: `920b030d191eed8286aad355304c114bfc459a58ae6972dbdd1666f1c935103b`.
- All 178 hashes matched their learning baseline manifest.
- Pre-existing untracked directory: `stages/stage5_personalized_motion_learning/docs/simulation_research_baseline_v1/`.
- Historical freeze: representative 8/8; development 35/36 executed, 13 unrun; NOT FROZEN. Must remain preserved.
- Account-wide weekly used percentage: 24% at start, latest 25%, same reset 1791047434. This is not task-attributed usage.
- Working scientific interpreter located and imports verified: `/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python`, Python 3.10.20, NumPy 2.2.6, MuJoCo 3.10.0.

## Failure reconstruction

Retained case: `high_rom_function_fresh_03_v1`, RETURN target (6,11) degrees.
Evidence: `results/simulation_research_baseline_v1/development49/high_rom_function_fresh_03_v1/{runtime_artifacts.json,summary.json}` beneath Stage 5.

The previous accepted request 17 planned `return_dq_07`. Its rolling composite activated at physics 23.09450000001926 s; the suffix first executed at 23.116000000019362 s. The suffix duration is 1.26 s. Reference progress is receipt governed; its completion must not be inferred solely from activation wall time.

The terminal reference of that segment was emitted at the 24.37000000002535 s observation:
q=(0.5126811263353718,0.6080889582920138) rad,
dq=(-0.20943951023931948,-0.3490658503988661) rad/s,
ddq approximately zero.

The runtime then created a 40 ms constant-velocity bridge and requested future planning while that bridge executed:

| Event | Physics/source time or monotonic timestamp |
| --- | --- |
| Request 18 source sample | 24.375000000025373 s |
| Source capture | 1289172900049208 ns |
| Request | 1289172904152500 ns (source +4.103292 ms) |
| Worker start | 1289172905410708 ns (source +5.361500 ms) |
| Bridge start physics | 24.37650000002538 s |
| Nominal bridge end from start+duration | 24.41650000002538 s |
| Bridge endpoint reference emitted, observation timestamp | 24.415000000025564 s |
| Last endpoint command actual apply | 1289172945293041 ns |
| Abort source timestamp | 24.42000000002559 s |
| Cancellation/disposition | source +47.485458/+47.488167 ms |
| Worker finish | 1289173096838750 ns (source +196.789542 ms) |
| Worker compute duration | 191.428042 ms |

Observed bridge reference sequence (source timestamps) included 24.385, 24.400, 24.405, 24.410 and 24.415 s. Its endpoint was q=(0.504303545925799,0.5941263242760592) rad with dq=(-12,-20) degrees/s and ddq approximately zero. The preceding 24.410 s reference was q=(0.5052983835994005,0.595784387065395) rad at the same velocity and near-zero acceleration.

The endpoint abort is explicit in `runtime.py`: completed pass-through bridge plus unfinished future produces `PASS_THROUGH_PREFETCH_NOT_READY_AT_ENDPOINT`. At disposition the request was only 47.488 ms old; this failure is not originally caused by the 100 ms expiry rule. The worker subsequently completed too late and cancellation could not stop the running process. It was never activated.

The active supervisor was TRACK; the six recorded lifecycle fallback intervals (44.5 ms physical time) were ordinary continued TRACK execution, not a certified stop. No contact or acceleration violation was reported at the final node. The final actual state remained far from RETURN target. The failure is functional and is not covered by the accepted activation-runtime-tail limitation.

## Design comparison before production changes

A. Precomputed safe-stop branch: suitable direction. Construct an escape suffix before permitting a pass-through segment to execute, certify it using the existing scheduler, geometry and mechanics screens, and retain it alongside the original primary. Enforce branch choice on reference progress, not an assumed wall-clock planner latency. This requires execution integration and proof that every accepted pass-through has an attached escape.

B. Reuse existing BRAKE or HOLD wholesale: not sufficient. Stage-4 TrackBrakeSupervisor searches rates and validates the next action during execution; it is not a prevalidated full finite stop branch and can return BRAKE_INFEASIBLE. HOLD assumes a stationary boundary. Terminal goal selection is bound to the task terminal set, not arbitrary intermediate safe stops. These cannot simply replace the moving bridge endpoint.

C. Clamp the endpoint, wait longer, or plan after endpoint: reject. The endpoint has nonzero velocity, so a constant pose/zero-velocity hold breaks continuity. Extending a bridge or waiting a fixed number of milliseconds reintroduces a timing assumption.

Provisional minimal choice: A, reusing the existing fixed-duration quintic scheduler and validation primitives. No production implementation has been attempted.

## Candidate braking derivation and evidence

At a constant-velocity bridge point with a=0, let u=t/T:

- q(t)=q0+v0*T*(u-u^3+u^4/2)
- dq(t)=v0*(1-3u^2+2u^3)
- ddq(t)=v0/T*(-6u+6u^2)

Thus terminal dq=ddq=0, the start is C2, peak |ddq_j|=1.5*|v0_j|/T, displacement=v0*T/2, and dq does not reverse. Choose T by rounding max_j(1.5*|v0_j|/a_limit_j) upward to the registered 5 ms grid. This does not use the observed 191 ms compute tail.

For retained request 18, the unchanged reference acceleration fractions give (75,150) degrees/s². T=0.240 s. A provisional reference-grid branch point is bridge progress 0.035 s, the last grid point strictly preceding its 0.040 s endpoint. This is NOT yet a proven runtime deadline: a governor must prevent advancing past the branch point without an atomic primary-or-fallback choice, and certification must cover the full route before activation. A fixed timer alone is insufficient.

Read-only check using retained deployable belief sequence 1012 and fixed session effective geometry:

- Brake start q=(28.9544647750,34.1409308786) degrees.
- Start dq=(-12,-20) degrees/s, ddq=0.
- Stop q=(27.5144647750,31.7409308786) degrees.
- End dq/ddq within 2.5e-15 rad-based units of zero.
- Peak reference acceleration=(75,125) degrees/s².
- Existing scheduler q/ROM, reference motion and continuous reference clearance checks passed.
- Nominal and source-observed-position-offset model clearance lower bound=0.0001 m.
- Existing 21-sample mechanics screen: peak force 86.251339338 N, peak moment 17.165320041 Nm, feasible=true; limits unchanged (200 N,60 Nm).

This is retained-case model analysis, not dynamic validation, invariant physical safety proof, or evidence of eventual task completion. The first analysis script failed because JSON geometry lists needed NumPy array reconstruction; the read-only diagnostic script was corrected. No production repair budget was consumed.

## Required unresolved integration checks

1. Attach certified escape before each pass-through activation, including original accepted suffixes rather than only bridges created later.
2. Reference governor must cap advancement at the branch point and handle control-cycle overruns without skipping it.
3. Primary readiness includes original validation and actual activation-age checks, not just future.done(). A rejected/expired candidate must leave the prevalidated branch available.
4. Once braking commits, the pending primary cannot interrupt it. Harvest/discard it without using its output; submit a fresh observation request only after safe hold and worker availability.
5. Keep fallback execution state separate from task HOLD so no artificial task dwell is credited.
6. Resume from the accepted zero-velocity, zero-acceleration reference using fresh deployable observations and original validation.
7. Preserve immutable source age, original task/phase deadlines and all current physics/safety/scorer inputs.
8. The baseline uses `>100 ms` expiry checks (and `<=100 ms` validation), whereas this request explicitly says `>=100 ms` must not activate. Exact equality must be addressed explicitly and tested without widening the age limit; it must not be silently assumed already compliant.

## Validation still required

No requested deterministic execution-state tests or new MuJoCo runs have been performed. Natural failure case, 0/100/200 ms availability-delay tests, targeted regression and optional representative 8-case remain unrun. Source remains baseline. No success status is assigned.

Future asynchronous value/planner results need immutable source/model/trajectory versions, a branch deadline, unconditional late-result dropping and baseline ranking when value is unavailable. That compatibility cannot be claimed implemented until execution holds a validated fallback independently of the producer.

## Authorization blockage and exact next step

The automatic approval reviewer rejected the combined provenance-write/local-commit/branch action because it did not recognize attachment-based authorization as trusted user authorization. The action did not execute. A direct chat confirmation was requested. No alternative Git mutation or target-repository write has been used to bypass that rejection.

Next action after confirmation: save this reconstruction and startup record in the learning repo; individually stage/review only pre-existing freeze docs/results/manifests for a provenance checkpoint; create the single authorized development branch, then finish the architecture gate before any production implementation or simulation.
