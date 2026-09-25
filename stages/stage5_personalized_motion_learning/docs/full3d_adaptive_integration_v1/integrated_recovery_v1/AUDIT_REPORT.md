# Final independent audit — integrated recovery v1

Date: 2026-09-24. Independent Auditor review of the final report, architecture,
metrics, commands, file inventory, status and underlying development artifacts.

**Audit disposition: the bounded diagnosis and terminal classification are
supported. No integrated-controller or fresh-qualification success is approved.**
Campaign terminal status: `BLOCKED_MECHANICS_OR_DEPLOYMENT_INFORMATION`.

## Terminal decision and causal scope

The blocker follows the current integrated contract's physical-credibility
requirement, not DEV-C's superseded Human-action-only scope. The proximal thigh
sphere is fixed at the hip; bed height and radius are fixed; registered downward
hip translations necessarily produce overlap which joint control cannot remove.
The evidence does not uniquely specify a correction restoring documented intended
mechanics. Choosing a new support relationship, moving the hip, changing contact
geometry/compliance or excluding negative placements would introduce a substantive
assumption or reduce the registered domain. Stopping before estimator/controller
tuning or fresh qualification is therefore justified under the amendment.

This is a physical interpretation and setup-information blocker. It does not
prove all tasks mathematically impossible or identify contact as the cause of
every historical failure. The report correctly retains other estimator,
reference/allocation, execution and lifecycle issues as unresolved. DEV-B's
local causal action-switch evidence and DEV-C's local improvements are preserved
without being promoted to full-session recovery evidence.

## Findings checked against evidence

| Claim | Independent check and disposition |
|---|---|
| 33.35 kN is a simulated bed-thigh normal reaction | Confirmed by independent `mj_contactForce`, frame transpose, equal/opposite `mj_applyFT`, and agreement with Human `qfrc_constraint`. It is neither a cuff-force claim nor a validated real-human load. |
| Fixed proximal penetration | Confirmed analytically and from initial/checkpoint geometry. Strongest penetration 4.819128 mm equals downward hip shift. Normal inverse effective mass 4.778115e-33 1/kg and disabled equality were checked in the raw artifact. |
| Sustained loading before model activation | Strongest raw trace has 28,100 contiguous 0.25 ms intervals from t=0 through 7.025 s. Independent peak/integral recomputation gives 33,353.295159 N and 234,306.898494 N s. |
| Force timestamp and impulse | Wrapper samples the executed `mj_step2` solve before next-boundary refresh. Integral weights that force by actual interval duration. It is a numerical discrete impulse, not experimental evidence. |
| Contrasts | Ordinary has no thigh contact but has shank loading. Nominal has roundoff-scale detected thigh penetration and nonzero force: 195.002635 N peak, 8.172986 N s impulse. Neither contrast is whole-leg contact-free. |
| Nominal duration | Detected thigh contact lasts 0.829 s; force greater than the analysis numerical tolerance of 1e-8 N lasts 0.1305 s. These are distinct metrics. The published contact-duration definition is correct. |
| Replay integrity | All three final `mjSTATE_INTEGRATION` vectors were independently confirmed exactly equal to original DEV-B checkpoints. Selected strongest-case derived fields, models and reference/control context also match. This is not a per-interval full-state or entire-pickle equality claim. |
| Old-24 association | Independently joined raw initial geometry to historical DEV-A rows: negative group 11 cases / 4 task entries / 0 completes; nonnegative group 13 / 11 / 2. This is association, with all cases retained, not a controlled causal effect estimate. |
| Historical clearance | Original screen/monitor explicitly measure shank clearance/contact. New proximal diagnostics add coverage; they do not retroactively redefine old fields or silently change old gates. |
| No new controller / fresh campaign | Source and manifest review support zero controller revisions and zero fresh formal episodes. Three commissioning prefixes do not establish full-task recovery or adaptation benefit. |
| Source and evidence integrity | All 607 baseline dependency hashes and baseline archive hash independently matched. Final experiment manifest's new-source and recorded input/output hashes also matched. |
| Plot revision | Parsed `review_v1/ANALYSIS.json` and `review_v2/ANALYSIS.json` are exactly equal. Review-v2 scaling improves display without changing numerical analysis. |

The architecture keeps contact/truth diagnostics on the evaluation branch. No
new controller truth input or production data-flow mutation was found. This
bounded source audit is not a proof of the entire historical stack's formal
noninterference or real-hardware deployability.

## Reporting corrections and limits

One editorial correction was requested from the Builder: replace “published
SHA” in `CHANGED_FILES.md` with “recorded starting HEAD”. This audit did not
verify remote publication. That wording does not affect the mechanics findings.
The Auditor also recommended explicitly mentioning nominal positive-force
duration (0.1305 s) alongside the detected-contact duration (0.829 s); the
existing table is already correct under its stated detected-contact definition.

The Builder reports 20 focused software tests passed. The Auditor inspected
the documented test command but did not rerun that suite; those checks are
software regression evidence, not full-session, physical, fresh-domain or
real-time qualification. The Auditor independently checked raw numerical
artifacts and source integrity as detailed above and in `INITIAL_AUDIT.md`.

Historical planning delays are deliberately replayed. Instrumented wall time
is not fresh planner latency evidence. No high-ROM, physical robot, clinical,
RL, or patient-safety claim is approved. Dirty/untracked dependencies and local
heavy checkpoints remain necessary; no clean-clone reproduction claim is made.

## Ownership and next step

The Auditor's only files changed during this campaign are `INITIAL_AUDIT.md`
and this `AUDIT_REPORT.md`; the final review changed only this file. Auditor
commands were read-only source/artifact inspection and lightweight independent
recalculation. No production/config/physical parameter change, new rollout,
scientific assumption change, staging, commit, push, reset, stash, branch switch
or deletion was performed by the Auditor.

Exactly one recommended next step: specify and document the intended fixed-hip,
proximal-thigh and bed support/contact relationship for the entire registered
placement domain, then implement only the justified versioned mechanics change
and resume integrated controller development from the preserved baseline.
