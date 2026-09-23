# Phase 2 V1 Preregistration

Status: frozen before any Phase-2 result is generated or viewed.

## Scientific question

Does the deployable effective-geometry plus online 11-base-dynamics adaptive
MPC generalize across fresh continuous hidden Human dynamics, geometry,
placement, cuff attachment, initial condition, and multiple task profiles,
while remaining within registered ROM/wrench/solver gates and materially
outperforming wrong/fixed nominal control?

## Frozen design

- Config: `phase2_formal_unknown_setup_task_v1.json`.
- Evidence: formal held-out simulation; no physical hardware or human test.
- Environment: suspended planar Human-V2/cuff control-sufficiency benchmark.
  It contains no bed/table contact or robot reach/torque plant; those are not
  silently counted as zero events and remain separate Phase-3 feasibility
  constraints.
- Budget: 24 fresh setup seeds x 5 arms = 120 closed-loop runs.
- Cases: 16 standard-ROM and 8 high-ROM; setup and task use independently
  permuted seed namespaces. Task profiles are explicitly stratified at six
  cases each, including two high-ROM cases per profile, without viewing any
  outcome.
- Arms: oracle, recovered adaptive, fixed nominal, wrong geometry plus adaptive
  dynamics, and adaptive geometry plus fixed dynamics.
- Exclusions/replacements: none. Every failure remains in the denominator.
- Hidden truth: case generation, explicit oracle, and post-run evaluation only.
- Commissioning supervision: a causal q-hat consistency envelope, not an exact
  ROM guarantee. The target envelope is `[10,2]..[38,59] deg`; a frozen 15 deg
  margin comprises the declared maximum 8 deg initial q1 anchor discrepancy,
  the 5 deg structural soft-limit layer, and a 2 deg pose/IK reserve. A causal
  envelope abort or any evaluation-only hidden ROM breach fails the gate.

The strongest historical Stage-4 adaptive result remains the reproduced
historical anchor. It is not inserted as a sixth case-wise arm because it
requires exact initial q and its registered single setup/task does not implement
this unknown-setup/unknown-task contract. The recovered arm retains its
11-base-dynamics lineage while replacing that unavailable startup assumption.

## Preregistered gates

The recovered adaptive arm must satisfy every check:

1. completion rate >= 0.90;
   the paired matrix must contain exactly 24 rows for every one of the five
   arms and all 24 adaptive rows must expose tracking metrics;
2. median q-tracking RMSE <= 3.0 deg;
3. q-tracking RMSE p95 <= 5.0 deg;
4. peak force <= 200 N and peak moment <= 60 Nm;
5. zero registered-ROM violations, solver failures, and safety aborts;
6. versus adaptive geometry with fixed dynamics: at least 20% full-horizon
   median-RMSE improvement with all 24 full-horizon metrics present, or at
   least 0.50 absolute completion-rate advantage;
7. versus fixed nominal: at least 20% median-RMSE improvement or at least 0.50
   absolute completion-rate advantage;
8. adaptive median-RMSE gap to oracle <= 2.5 deg.

The oracle must complete 24/24 with complete tracking metrics, zero probe/task
ROM violations, zero solver/safety aborts, and the same full-episode wrench
limits. An oracle failure therefore classifies the sampled task/domain as
infeasible under this controller contract rather than being silently excluded.
Full-episode force/moment are `max(commissioning probe, task)`. Percentiles use
NumPy's linear method. Adaptive/oracle tracking gates use full-horizon rows and
require all 24. Baseline medians also use full-horizon rows; a baseline with
missing/aborted rows can only satisfy the comparison through the preregistered
0.50 completion-rate disadvantage, never by silently omitting its failures.
Aborted runs are never dropped from completion/event denominators.

The tracking thresholds bound ordinary and tail performance while allowing the
observed development-to-development variation. The wrench/ROM/solver checks
are hard safety/validity gates, not statistical targets. The comparison gates
test that both effective geometry and dynamics adaptation contribute instead of
letting beta absorb wrong geometry.

## Sensor and mechanics assumptions

Cuff position and orientation have the frozen bounded measurement noise in the
config. Cuff twist is an ideal, noiseless simulated derivative: this is an
explicit idealized sensor assumption and a hardware-transfer limitation, not a
claim about a physical sensor. The registered Human-V2 hard ROM is q1 <= 80 deg,
q2 <= 100 deg with a 5 deg soft-limit layer. Consequently 120--130 deg is
outside this verified plant and cannot be tested by silently changing its
dynamics/constraints; the maximum in-contract high-ROM goals are q1 66--75 deg
and q2 82--95 deg.

## Post-result discipline

No source, config, gate, seed, or domain change is allowed during the run.
Before/after source/config hashes and full Git-status inventories are recorded;
all local Stage-3, Stage-4, and V2 Python package sources are hashed and copied
into the result. A formal failure is preserved; any repair returns to
development and requires a new versioned preregistration with fresh held-out
seeds.
