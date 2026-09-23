# Architecture Recovery V2.1 Fresh Phase-2 Preregistration

Status: **DOMAIN, ARCHITECTURE, GATES, BUDGET, AND EXCLUSIONS FROZEN BEFORE HIDDEN SEEDS**

Recorded: 2026-09-22, Asia/Shanghai.

## Preserved prior result

The `ARV2-P2-V2` formal result remains `PHASE_2_FAIL`. It is not reclassified,
rerun, or used as fresh evidence. The demonstrated root cause and V2.1 repair
are recorded in `phase2_recovery/ROOT_CAUSE_AND_REPAIR_V1.md`.

## Frozen V2.1 architecture

The architecture is sealed by `phase2_recovery/FREEZE_MANIFEST_V2_1.json`,
SHA-256 `98c4e245270164e42cbb3999518eea299db0e029ed600e09b1ebf2e947e8da05`.
Relative to V2 it adds only the independently qualified causal task residual:
EWMA alpha `0.20`, component bound `+/-12 Nm`, with task recency window and
alternate smoothing explicitly disabled. No further architecture, estimator,
probe, reference, domain, gate, budget, or exclusion change is permitted after
fresh hidden seeds are sealed.

## Scientific question and design

Does frozen V2.1 adaptive MPC remain functionally effective across fresh hidden
continuous patient/setup/task variation and materially outperform fixed,
wrong-geometry, and no-adaptation controls without deployable hidden truth?

- evidence: formal held-out;
- exactly 24 paired cases;
- four profiles x standard/high ROM x three replicates;
- six arms per case, 144 rollouts total;
- arms: oracle, adaptive, fixed nominal, wrong-geometry adaptive dynamics,
  no dynamics adaptation, commissioning-only dynamics;
- no pilot, tuning, replacement, threshold revision, or case exclusion after
  hidden seed generation.

## Frozen continuous hidden domain

- height `[0.88,1.12]`, mass `[0.78,1.28]`;
- passive stiffness `[0.65,1.45]`, damping `[0.70,1.35]`;
- rest offsets from `[-4,-5]` to `[5,6] deg`;
- thigh COM `[0.88,1.12]`, shank COM `[0.86,1.14]`;
- hip x `[-0.12,0.12] m`, hip z `[0.045,0.16] m`;
- cuff fraction `[0.52,0.88]` of full shank;
- initial q from `[6,10]` to `[18,28] deg`;
- standard goal q from `[35,48]` to `[62,78] deg`;
- high-ROM goal q from `[66,82]` to `[75,95] deg`;
- standard duration `[9,12] s`, high-ROM `[12,15] s`;
- task profiles: coordinated, hip lead, bounded knee lead, and two rate;
- pose noise: `0.00015 m` and `0.03 deg`;
- twist assumption: ideal noiseless simulated derivative;
- bed height `0.012 m`, shank radius `0.045 m`.

Mechanics-conditioned generation retains minimum analytic reference clearance
`0.025 m`, static generation screen `150 N / 45 Nm`, and at most 5,000 setup
draws for each fixed task draw. Actual hidden clearance is evaluated at no more
than 0.005 s intervals. The conditional generation population, attempts, and
rejection causes must be reported.

## Frozen gates

Adaptive: completion at least 0.90; full-horizon median/p95 RMSE at most
`3/5 deg`; full-episode force/moment at most `200 N / 60 Nm`; zero reference,
probe, or task clearance/ROM violations; zero consistency aborts, settle
timeouts, solver failures, and safety aborts.

Oracle: completion exactly 1.0; the same zero-event and wrench gates; adaptive
minus oracle median RMSE at most 2.5 deg.

Adaptive comparison passes against fixed nominal, wrong geometry, and no
dynamics if completion advantage is at least 0.50 or median improvement is at
least 20%. It passes against commissioning-only if completion advantage is at
least 0.25 or median improvement is at least 20%. Every arm must contain all 24
unique paired keys and every adaptive/oracle row must have complete metrics.

V2.1 audit requirements, in addition to the unchanged gates: every adaptive
residual must be finite and within the frozen bound; cap hits, maximum step,
total variation, and sign reversals must be reported; residual enablement must
remain restricted to the adaptive and wrong-geometry adaptive-dynamics arms.
These are integrity requirements, not new post-hoc performance gates.

## Exclusions, truth firewall, and reporting

There are no post-generation exclusions or replacement cases. Generation
failure, missing metrics, abort, contact, ROM, solver, safety, or timeout remains
in the denominator. Hidden truth may enter only generation, plant, explicit
oracle, evaluation, and post-run diagnosis. It may not enter deployable state,
geometry/Jacobian, dynamics/residual update, candidate generation, prediction,
action selection, or promotion.

Report task-only and full-episode wrench separately, along with completion,
q/dq tracking and tails, cumulative exposure, clearance/contact, ROM,
solver/safety, runtime, convergence, residual trace, conditional generation,
profile/ROM failures, and the maximum validated physical envelope. These
results do not establish hardware readiness.

The study is `PHASE_2_PASS` only if every frozen gate passes. Any failure is
preserved and returns to development under a new future held-out namespace.

