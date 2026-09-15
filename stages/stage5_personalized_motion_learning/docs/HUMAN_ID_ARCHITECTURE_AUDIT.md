# Stage-5 Human-ID architecture audit

Status: architecture and shadow service prepared under a **fixed nominal
interface**. No Human model from this service is connected to Goal-MPC,
observation, execution, Safety Filter, BRAKE, or task decisions.

## Stage-4 reuse classification

| Stage-4 component | Stage-5 classification | Decision |
|---|---|---|
| accumulated integral inverse-dynamics regression | reusable with Stage-5 measurement adaptation | Retain the exact 11-beta regressor and acceleration-free integration. Feed it the deployed Stage-5 Human-side q/dq estimate and measured Human-site generalized input. |
| 11-parameter base-dynamic Human model | directly reusable mathematically | Stage-5 changes cuff placement, not the verified planar Human dynamics basis. Interpret beta as control-effective combinations, never as independently recovered anatomy. |
| accumulated cuff geometry/state reconstruction | inappropriate at the Stage-5 input boundary; frozen historical code | Stage 4 assumes measured attachment pose is the Human cuff pose. Stage 5 has a loaded finite interface, so the accepted fixed Stage-5 geometry and interface-aware deployable Human estimate are the authority. |
| L1 timestamp/measurement integrity | directly reusable in principle | Require finite, new, causal, strictly ordered measurements and explicit model version. The Stage-5 service implements the relevant subset on its already reconstructed Human-side input. |
| rank/RRQR/condition/correlation/bound diagnostics | directly reusable | Keep numerical rank distinct from practical identifiability and report the complete correlation structure. |
| single incumbent/challenger lifecycle | reusable with Stage-5 adaptation | Permit only one pending challenger; never let a training-window fit replace the retained model directly. |
| embargoed future validation and alpha spending | reusable structure, Stage-5 timing required | Preserve disjoint future blocks and the Stage-4 HAC/alpha-spending logic. Use a 0.20 s task-local window and 8/10/12 future-block looks instead of copying the longer Stage-4 timing. |
| bounded/smoothed publication | reusable only as shadow publication | Keep the Stage-4 bounded 10% update with a 3%-of-span step cap, but publish a versioned `shadow_only` incumbent. This is estimator stability logic, not a safety threshold. |
| prior-only versus trusted-adaptive control arms | reusable future experiment pattern | The current task is prior-only in control. A trusted-adaptive arm is not preregistered because shadow validation did not support H-A. |
| Stage-4 thresholds and geometry promotion history | frozen historical evidence | They are not edited, imported as Stage-5 acceptance claims, or tuned using the new outcomes. |

## Stage-5 service contract

`Stage5HumanIDMeasurement` contains only:

- sample and arrival timestamps;
- the current deployable Human q/dq estimate;
- measured Human-cuff force and moment in WORLD at the registered cuff
  reference point;
- the corresponding measured generalized Human input;
- task phase and the accepted fixed interface-model version.

The service rejects a wrong interface version, stale/duplicate/noncausal time,
nonfinite or malformed data, and disagreement between measured wrench and its
geometry-mapped generalized input. MuJoCo Human state and true beta do not
exist in the online input type.

The output exposes:

- retained beta/model, version, and publication time;
- the current challenger and minimum future-validation time;
- trust state (`PRIOR_ONLY`, `CHALLENGER_PENDING`, or
  `SHADOW_INCUMBENT_VALIDATED`);
- fit/update diagnostics, rank, condition, singular values, full parameter
  correlation, bound pressure, and future paired-prediction evidence;
- an immutable `shadow_only=true`, `applied_to_control=false` declaration.

## Stage-5 timing choice

Measurements arrive at 200 Hz. The diagnostic uses 0.20 s integral windows,
0.05 s fit-block stride, a minimum of 16 fit blocks, and attempts at 0.25 s
intervals. A challenger receives one complete-window embargo followed by
8/10/12 nonoverlapping future blocks. The earliest qualification is therefore
1.8 s after a fit, long enough to be genuinely future evidence while still
observable within the roughly five-second goal episode.

These values were declared before the four-case diagnostic. They are
task-local research settings, not hardware-derived confidence thresholds and
not motion or safety limits.
