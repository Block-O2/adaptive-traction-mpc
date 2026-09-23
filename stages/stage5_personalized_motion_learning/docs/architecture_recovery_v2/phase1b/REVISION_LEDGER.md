# Phase 1B Material Revision Ledger

Budget: **0/6 consumed at opening; now BLOCKED by an independently audited
conservative count of at least 7/6**.

The four-row table below preserves the Builder's proposed grouping. The
independent Auditor did not approve that grouping, so it is not the controlling
budget interpretation for phase progression.

## Revision 0 — retained baseline and discriminating audit

- Number: `0` (baseline/audit; not a material revision).
- Hypothesis: the retained adaptive architecture may already be
  control-sufficient, while the remaining demonstrated failure is concentrated
  in task-domain mechanics and the all-the-way-first `knee_lead` trajectory.
- Change: none.
- Evidence motivating it: Phase-1 bed-feasible v4 passed its six development
  cases, but excluded `knee_lead`; the old `knee_lead` definition sends one
  joint fully to goal while the other remains at the start and previously
  exhausted the mechanics-feasible setup generator.
- Development result: the Builder's proposal-level study evaluated 160
  standard and 160 high-ROM continuous proposals. The legacy `knee_lead` was
  mechanics-feasible in `0/320`; coordinated and each of four bounded-lead
  candidates were feasible in `268/320` (`83.75%`). All force/moment screens
  passed; rejection was entirely clearance-driven. The bounded candidates did
  not change the endpoint-limited minimum-clearance statistic, so the smallest
  tested nonzero lead (`hip=0.65`, `knee=0.72` normalized midpoint progress) is
  preferred on simplicity/velocity grounds.
- Auditor judgment: **GO for Phase-1B development; NO-GO for freeze or Phase
  2**. An independent 25-case-per-cell audit found legacy knee-led acceptance
  `0/25` in both standard and high-ROM strata, while coordinated accepted
  `22/25` and `20/25`. Auditor requires versioned task semantics, dynamic and
  substep mechanics diagnostics, conditional-domain reporting, explicit
  deployable mechanics provenance, oracle-first testing, a dynamics simplicity
  ablation, and a fresh combined development matrix before freeze.
- Disposition: baseline retained. Proceed to Revision 1 limited to
  mechanics-aware task/domain redesign; do not alter the adaptive
  representation without evidence from the staged diagnostics.

## Revision slots

| Revision | Hypothesis | Material change | Motivation | Development result | Auditor judgment | Disposition |
|---:|---|---|---|---|---|---|
| 1 | A bounded nonzero knee lead with sufficient simultaneous hip advance removes the structurally invalid shank-down excursion without changing the retained adaptive representation. | Added versioned `knee_led_clearance_constrained_v1`; made the mechanics domain explicit; raised the commissioning-compatible reference-clearance reserve from 10 to 25 mm; added dynamic-wrench, rejection-cause, 5 ms actual-clearance, and fail-closed reporting. | Legacy profile was feasible in 0/320 Builder and 0/50 Auditor proposals. Post-hoc 25 mm recertification retained 516/640 (80.6%) stored unconditioned proposals from the configured 10 mm characterization; the versioned four-profile audit had 81.25–88.75% cell acceptance and all accepted dynamic inverse-dynamics demands below 200 N/60 Nm. | Retained. A 96-case probe audit passed clearance/ROM but exposed one 205.3 deg/s fixed-time handoff, motivating Revision 2. | Initial scope approved; final freeze judgment: NO-GO. | Retained candidate evidence only |
| 2 | A fixed 8 s handoff is fragile; using deployable cuff twist to hold the intended interior pose until actual settling will remove handoff-speed failures without changing excitation or using truth. | Builder grouped event settle, measured-end target, lower damping, and restored-interior target as one revision. Rejected amplitude-only and nominal-support candidates were preserved. | Initial 32-case stress had 12 substep clearance failures below the 25 mm reserve. The 25 mm domain gave 96/96 clearance-safe probes but one 205.3 deg/s handoff. Higher settle damping created a discrete oscillation; the lower deployment-signal damping settled it. | Final 96-case regression: 96/96, zero clearance/ROM/consistency/timeout events, minimum actual clearance 3.95 mm, maximum handoff speed 1.40 deg/s, realized generation acceptance 84.2%. | Final freeze judgment: grouping not approved; v3-v6 are materially distinct policies. | Retained candidate evidence only |
| 3 | The dynamics identifier admits mathematically positive but control-pathological mass matrices because its old eigenvalue floor was 1e-6. | Added a 0.03 minimum mass-matrix eigenvalue validity floor; invalid updates retain the last-valid model. | Failed adaptive models had minimum eigenvalues 0.013–0.029 versus 0.085–0.118 for passing models. An independent 2000-proposal domain audit found true values 0.0337–0.0982, p01 0.0381, and 0/2000 below 0.03. | Removed solver failures and improved the eight-case adaptive regression from 5/8 to 6/8, but two tracking tails remained because rejecting an inertia-invalid joint fit also blocked valid non-inertia corrections. | Scientifically supported; phase freeze still NO-GO on budget. | Retained candidate evidence only |
| 4 | When only the inertia block violates the frozen mass margin, freezing those three coefficients and conditionally refitting the remaining eight coefficients preserves physical validity while retaining useful dynamics adaptation. | Extended the existing conditional active set: freeze the three inertia coefficients at last-valid values on a margin violation, then refit the remaining control-effective coefficients; the 0.03 floor is unchanged. | Revision 3 logs showed 22 margin rejections in each remaining failure while gravity/stiffness/damping residual evidence remained informative. | Same eight cases improved to 8/8, median/p95 1.145/2.889 deg. Fresh 16-case x 5-arm development then passed every frozen gate: adaptive/oracle 16/16; adaptive 0.992/2.293 deg median/p95 and 159.89 N/50.24 Nm full-episode peaks; fixed 0/16, wrong geometry 1/16, fixed dynamics 5/16; zero adaptive events. Exact-source runtime-fix rerun had no exceptions or source/config/Git-status drift. Exact-current simplicity diagnostic then gave adaptive 8/8, commissioning-only 6/8, and no-dynamics 1/8. | Scientifically supported; phase freeze still NO-GO on budget. | Retained candidate evidence only |
| 5 | Unused | Unused | Unused | Unused | Unused | Unused |
| 6 | Unused | Unused | Unused | Unused | Unused | Unused |

The ledger must be updated after every material revision. Rejected revisions
remain recorded and still consume their slot.

## Independent conservative recount

The freeze audit counted at least these seven material policies:

1. bounded knee-led task/domain and 25 mm reserve;
2. event-driven settle;
3. measured excitation-end settle target;
4. lower settle damping;
5. restoration of the original estimated interior target;
6. 0.03 mass-matrix floor;
7. mass-margin conditional active-set refit.

Because the immutable amendment permits six, Phase 1B cannot autonomously
freeze. This ledger does not choose which successful policy to discard after
seeing outcomes and does not retroactively merge rejected variants.
