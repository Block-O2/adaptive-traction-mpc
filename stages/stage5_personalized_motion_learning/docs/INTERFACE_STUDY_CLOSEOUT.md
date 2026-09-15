# Stage-5 interface study closeout

Status: **closed as a limited negative result**. This document is the durable
index for the interface-model and interface-identification branch that followed
the deterministic checkpoint `e6ea54b701e2a825cc8558c3e0cae214a1fac777`.
It does not replace or soften the historical reports. The machine-readable
companion is `INTERFACE_STUDY_CLOSEOUT_MANIFEST.json`.

## Final supported conclusion

- The fixed low-order nominal interface model was adequate for the nominal
  matched episode and many of the discrete parameter-mismatch cases tested in
  simulation.
- Accurate physical recovery of `Kt`, `Kr`, `Dt`, or `Dr` was not established
  and is not retained as a Stage-5 control requirement.
- The preregistered Interface Robustness v1 box was **not** validated: the final
  core campaign accepted 25/27 episodes and retained
  `EXIT C — STOP THIS IMPLEMENTATION`.
- A first-action physical transient remains underpredicted in some mismatch
  cases. In the Acceleration-Semantics V2 targeted replay, predicted versus
  evaluation-truth q2 acceleration at 5 ms was `363.58` versus
  `633.71 deg/s2`; the episode aborted at 10 ms.
- The 30-episode session's approximately 16% runtime growth was not reproduced
  by the controlled fixed-snapshot audit. The runtime classification remains
  `B6 — unresolved`; no WCET or hard-real-time claim is supported.
- Further interface-predictor, MHE/EKF/UKF, and physical K/D recovery work is
  paused pending actual CR-12/cuff hardware evidence.

These statements are simulation and mechanical-engineering evidence only. They
are not hardware calibration, a continuous robustness proof, hardware or
clinical safety validation, or real-time certification.

## Causal evidence chain

1. **Deterministic matched baseline.** The frozen checkpoint established a
   path-free Goal-MPC episode with unified loaded execution and explicit
   interface prediction state under matched nominal Plant-v1 conditions.
2. **Interface Mismatch v1.** OFAT probes showed both useful completions and
   asymmetric inference errors: a Kt-low truth acceleration false negative, a
   Kt-high conservative abort, and a Kr-low settled-start reconstruction
   rejection.
3. **Uncertainty monitoring.** A finite deterministic hypothesis treatment made
   the mismatch sensitivity explicit, but it was not a continuous or guaranteed
   bound and was not retained as a general control solution.
4. **Physical interface identification v1.** A bounded shadow estimator did not
   recover the physical scales reliably. Candidate parameters often behaved as
   effective compensators for prediction-model error.
5. **Information/model-form audit and physical predictor v2.** In-model tests
   separated correlated excitation from plant/predictor bias. Relative-
   kinematics predictor v2 reduced true-parameter residuals by roughly 42--54%,
   but several held-out landscapes still preferred incorrect or boundary
   parameter values. Physical identification therefore remained unsupported.
6. **Simple Interface Robustness v1.** Conservative path-free pacing and a
   force-planning reserve improved the small development set without changing
   the physical limits or safety chain. This justified only a preregistered
   final test, not a robustness claim.
7. **Final 27 + 4 + 30 campaign.** The core accepted 25/27, all four boundary
   outcomes were explicitly classified, and the continuous nominal/mild-
   mismatch session accepted 30/30. Two core startup acceleration violations
   and the long-session runtime trend forced `EXIT C`.
8. **Root-cause audit.** The original production screen checked only the full
   20 ms interval while the causal monitor also checked startup prefixes. Seed-
   dependent first actions triggered the mismatch; a 20 ms-only semantics bug
   was confirmed, but short-prefix physical prediction error remained.
9. **Acceleration-Semantics V2.** Checking 5/10/15/20 ms prefixes did not rescue
   the first retained failure. The physical 5 ms q2 transient was substantially
   underpredicted, so the remaining failure cannot be relabeled as interval
   semantics alone.
10. **Runtime telemetry.** A controlled 7000-solve, 133.3 s benchmark showed
    only about 2% fresh-to-post slowdown, not the historical 16%. CPU frequency
    and thermal telemetry were unavailable, so the cause remains unresolved.

## Frozen boundary for the next research line

Human-identification work after this closeout must isolate the Human model by
using the nominal Plant-v1 interface and the unchanged nominal controller-side
interface model. Interface adaptation, parameter hypotheses in control, new
interface predictors, Human adaptation in control, terminal-value learning,
and RL are inactive until separately authorized.

Large raw traces remain ignored local evidence. The compact final-campaign
summary and this manifest are retained in Git; historical reports retain their
original status and unfavorable results.
