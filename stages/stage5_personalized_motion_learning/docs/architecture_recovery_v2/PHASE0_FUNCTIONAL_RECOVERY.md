# Phase 0 — Functional Historical Recovery

Status: **PASS — reproduction complete and independently audited.**

## Historical correction

The repository does not contain a multi-link adaptive-MPC capability across
Stages 1--3. The actual lineage is:

1. **Stage 1** — adaptive single-link Spring2D. A one-shot crossing planner and
   short-horizon NMPC tracker use UKF state estimates and online estimates of
   `[m,k,b_r]`. The retained Stage-9J evidence reports 24/24 adaptive crossings
   versus 0/24 fixed, but adaptive true-acceleration tails are worse and
   reliable individual-parameter recovery is not established.
2. **Stage 2** — fixed nominal planar Human-V2 inverse dynamics and rigid-cuff
   tracking. No adaptive estimator/controller is present.
3. **Stage 3** — fixed-model coupled Human-V2/UR10e-surrogate simulation and
   execution foundation. Its README explicitly assigns adaptation to Stage 4.
4. **Stage 4** — first and strongest multi-link Human/robot adaptive MPC:
   control-effective cuff geometry, 11-base Human dynamics, single-challenger
   causal trust, and Human-space feasible-first CEM MPC.
5. **Stage 5** — deterministic fixed-model goal MPC and later shadow/session
   personalization work. The baseline froze/bypassed the Stage-4 geometry and
   online dynamics authority while adding a narrow fixed task and current
   Human-waypoint prototypes.

The strongest historical recovery target is therefore the Stage-4 registered
Human A/B. Stage 1 is reproduced separately as a bounded predecessor, not
misrepresented as the same plant or controller.

## Reproduction evidence

### Stage 4 original source

The registered runner was executed from a temporary `git archive` of
`stage4-baseline-v1` (`ef1fe90e61c5981df8e934585780ce188d104ea4`) without
switching the campaign branch. The key functional metrics reproduce:

- both arms completed at 28.87 s;
- first trusted-adaptive promotion at 9.72 s;
- exact pre-promotion A/B equality for the audited signals;
- tracking RMSE `0.765477 deg -> 0.713056 deg`;
- post-promotion tracking RMSE `0.858633 deg -> 0.787659 deg`.

The regenerated JSON is not byte-identical because runtime timings and
environment provenance are serialized. The scientific metrics above match the
canonical evidence.

### Stage 4 current-HEAD derivative

The same named runner on V2 HEAD is deliberately classified as a derivative
regression, because later commits corrected the robot translational
velocity-feedback measurement path. Both arms still completed and adaptive
control still improved tracking (`0.798719 deg -> 0.763823 deg`), but this is a
4.37% benefit rather than the canonical 6.85%. It is not used to rewrite the
historical claim.

### Stage 1

The original Stage-9J config and current-source runner completed 144 isolated
runs (eight conditions, three seeds, six methods) in a new V2 result directory.
The mode/data-source audit passed. The reproduced functional boundary is:

- full adaptive planner/tracker crossed in `24/24` primary cases;
- fixed nominal planner/tracker crossed in `0/24`;
- oracle planner/tracker crossed in `24/24`;
- the adaptive true-alpha tail remained poor (per-run maximum up to `47.42`),
  so crossing recovery is not evidence of safe/low-acceleration control;
- the report's cross-condition gap decomposition assigns the largest average
  absolute true-alpha-max contribution to parameter error (`8.202`) rather
  than state error (`0.156`) or the diagnostic interaction residual (`0.668`).

Historical generating revisions are unavailable for some Stage-9 artifacts,
so this is a current-source reproduction of an honestly bounded historical
contract, not a byte-exact regeneration. The preserved report explicitly does
not claim formal safety/stability.

## Capability matrix

| Dimension | Historical assumption | Historical method/evidence | Reproduced? | Current Stage-5 status | Lost/bypassed? | V2 recovery path |
|---|---|---|---|---|---|---|
| Patient dynamics | Representable Human-V2 mismatch | Stage-4 causal 11-beta integral identification plus trust | Original registered A/B reproduced | Narrow opt-in beta/session updates; baseline fixed | Baseline authority bypassed | 11-beta control-effective model with independent geometry ablations |
| Leg geometry | Effective hip-plane translation, `L1`, knee-to-cuff vector; exact initial-q prior | Stage-4 accumulated cuff-pose fit | Geometry process exists in reproduced run but not isolated by A/B | Global `STAGE5_GEOMETRY/STAGE5_HUMAN` | Yes | Fit observable `(hip,L1,sc)` without exact initial q; retain bounded full-`L2` uncertainty for clearance |
| Leg placement | Anchored from first cuff pose plus known initial q | Stage-4 world-frame geometry initialization | Only under exact-q startup assumption | Fixed `T_WH` | Yes | Continuous hidden placement and pose-history fit in a calibrated gravity/world frame |
| Cuff attachment | Effective knee-to-cuff vector; finite small variants | Stage-4 geometry estimator | Conditional/shared across A/B | Fixed fraction `f=0.72` | Yes | Recover effective `sc`/offset; never require separate `L2,f` for cuff mapping |
| Initial state | Simulator reset/reference q supplied to estimator | Exact `initial_q_prior_rad` | Reproduced as historical assumption, not deployment capability | Same exact start target pattern | Yes | Causal pose-history geometry/state inference; no exact hidden q input |
| Reference trajectory | q/dq/ddq reference supplied | Six handcrafted Stage-4 trajectories; formal anchor to 75/90 deg | Original A/B anchor reproduced | Narrow 5/10 to 20/35 goal plus finite waypoint families | Materially narrowed | Multiple smooth coordinated, hip-lead, knee-lead and two-rate profiles |
| Reference velocity/profile | Slow registered profiles | Finite Stage-4 timing variants | Bounded, not broad | Quintic/fixed matched-pacing studies | Partly | Continuous duration/profile variation and event-driven completion |
| ROM/high-ROM | Formal adaptive anchor to 75/90 deg; later fixed-model engineering studies beyond nominal ROM | Corrected 40/80, 90/120, 120/120 are not adaptive hidden-setup proof | Only original 75/90 adaptive anchor reproduced | Default plant ROM remains 80/100 deg | Desired 120--130 not admitted by nominal plant | Validate within 80/100 and report separate suspended-high-ROM engineering evidence without conflation |
| Contact/table | Fixed bed/table and exact full geometry | Nominal contact model; no hidden table family | Historical assumption only | Hard clearance uses fixed `L2` and placement | Yes | Calibrated table plus conservative full-`L2`/ankle envelope |
| Interface | Mainly rigid; P1 exploratory | Fixed registered interface per study | Reproduced rigid A/B | Provisional fixed/identified interface studies | Not generalized | Keep interface provenance explicit; no tissue-fidelity claim |

## Control-critical provenance and unresolved assumptions

| Quantity | Historical source | V2 required classification |
|---|---|---|
| Cuff pose/twist | robot FK / interface measurement | MEASURED |
| Cuff wrench | reconstructed measurement | MEASURED/RECONSTRUCTED |
| Sagittal plane normal and gravity vertical | initial-pose alignment in Stage 4 | CALIBRATED; V2 may not use hidden simulator orientation |
| Initial Human q | exact reference/reset value | HIDDEN_ORACLE in the target contract; must be removed or replaced by an explicit setup procedure |
| `hip,L1,sc,cuff offset` | Stage-4 effective pose fit | ONLINE_ESTIMATED control-effective geometry |
| Full `L2` and cuff fraction `f` | nominal anatomy/fixed Stage-5 config | not separately identifiable from cuff kinematics; bounded prior/calibration only for ankle clearance |
| 11-base beta | population prior then online identification/trust | ONLINE_ESTIMATED control-effective dynamics |
| Table plane | fixed simulator world | CALIBRATED environment geometry |
| ROM and soft limits | Human-V2 model contract | STRUCTURAL_PRIOR for this simulation family, not clinical truth |
| Robot reach/torque limits | UR10e surrogate model | STRUCTURAL_PRIOR/SURROGATE, not CR12 evidence |

## Phase-1 mandatory ablations

To prevent dynamics beta from concealing bad geometry, Phase 1/2 comparisons
must include wrong fixed geometry plus adaptive beta, adaptive geometry plus
fixed beta, joint geometry/beta adaptation, oracle, and wrong/fixed nominal.
The development and held-out domains must vary geometry, placement, cuff,
initial state, dynamics and task continuously rather than choose a lookup
table. Exact initial q is forbidden from the deployable path.

## V1 disposition

V1 remains valid individual-physical-parameter identifiability negative
evidence. `sc=fL2` is sufficient for cuff pose, Jacobian and generalized wrench
mapping. Full `L2` matters for ankle/table clearance and is handled separately
by calibration or conservative uncertainty; no evidence yet establishes
incompatible controls for observationally equivalent setups.

## Independent audit outcome

The independent Auditor approved Phase 0 after checking the historical-source
reproduction, the separately labelled current-HEAD derivative, the Stage-1
boundary claim, and the capability/scope-loss matrix. The approval does not
promote Stage-1 crossing into a safety claim and does not treat Stage-4's exact
initial-state assumption as deployable.
