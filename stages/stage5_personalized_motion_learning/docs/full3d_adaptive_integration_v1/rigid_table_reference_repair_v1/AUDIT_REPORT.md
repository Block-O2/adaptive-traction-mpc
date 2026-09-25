# Independent DEV-D audit — final strict candidate

An independent fresh-context read-only Auditor reviewed the user contract,
production source, tests and raw result artifacts. The Auditor did not edit
files, did not run a physical simulation, and could not independently execute
the focused pytest suite in its plain Python environment because `pytest` was
unavailable there. Builder subsequently ran the suite in the registered
`mpc_learn` environment. The audit therefore independently checks source and
numerical artifacts, not a second physical replication.

## Challenge and correction

The Auditor first found two real omissions in the initial DEV-D
`broad_development_v1` version: the scheduler could derive a negative
clearance floor from an infeasible registered endpoint, and recovery/task
quintics had only discrete reference-node checks. Builder preserved that
batch, then added a strictly DEV-D-only nonnegative floor and a 1201-node
derivative-root conservative intersample certificate to both fixed-duration
recovery and duration-searched task paths. Nine focused tests exercise the
new source, including fabricated negative-floor and hidden intersample
failure cases. Source re-audit confirmed both paths call the certificate and
the original default scheduler behavior remains unchanged. The scheduler's
reference nodes are 5 ms; a “20 ms” string in its acceleration semantics
does not mean the clearance sampling period is 20 ms. This correction to the
Auditor's preliminary wording is recorded here.

The Auditor independently confirmed that:

- the old middle-case requested shank becomes negative at 2.535 s, before
  actual shank geometry does at 2.540 s;
- in the old near-upper-r02 case, actual sleeve becomes negative at 0.030 s,
  before the old requested shank first becomes negative at 2.325 s;
- strict DEV-D uses deployable estimated q, measured cuff pose, calibrated
  table/tool constants and effective geometry, while hidden physical geometry
  and true q remain plant-construction/evaluation-only;
- the same `CombinedRigidTableClearanceV1` is passed to recovery and task;
  it enforces identical geometry, structural shank upper length and retained
  margin, and its strict continuous certificate is active only under DEV-D;
- the fixed 100 ms age contract, retained task/physical limits and DEV-C-off
  flag remain in force; the sleeve collider's physical contact pair remains
  disabled and must not be described as a measured contact force;
- the strict batch has 23 selected rows, 21 per-case summaries and 2
  preserved early abort records; 21 commissioned/fitted/recovered/entered
  task, 5 COMPLETE, 11 stale, 2 velocity, 3 no-feasible and 2 sleeve-abort;
- recomputing the 109 task latencies from per-case decisions yields median
  73.509500 ms, p95 106.217608 ms and maximum 124.615333 ms; 11 measured
  planner calls exceed 100 ms and correspond to 11 stale aborts;
- all 23 native thigh/shank contact summaries have zero detected intervals
  and zero normal peak force;
- raw strict traces reproduce **measured-cuff-pose** sleeve-gap minima
  +20.711977 mm and +14.534717 mm, and physical cuff-force peaks
  132.754 N and 119.274 N, for selected
  `balanced_middle_r01` and `balanced_ordinary_r01` runs;
- both measured sleeve-abort gaps recompute from raw saved cuff pose as
  −0.017875 mm at 0.035 s and −0.032834 mm at 5.955 s.

The aggregate script's earlier V2 output was found to overcount deadline
misses as 14 by folding in 3 timely infeasible decisions. Builder corrected
the derivation from `activation_rejected_reason` and preserved the erroneous
V2 artifact alongside the accurate V3 summary. This is a documentation/
aggregation correction, not an implementation change to planner behavior.

## Final opinion and limits

The Auditor supports `REFERENCE_REPAIR_PARTIAL`, **not**
`RIGID_TABLE_REFERENCE_VALIDATED`. The code-level hard-table path contract is
substantially better and the 21 complete traces show no reference/physical
shank or sleeve penetration at saved 5 ms boundaries, but two cases cross
the table at the measured sleeve and only 5/23 complete. Robot-link path
collision is not certified by the new deployable envelope; evaluation-side
contact/geometry checks are still required. The model-based continuous
reference certificate does not guarantee the physical CR12–cuff–Human
system follows its reference. The per-run manifest contains case hash,
flags/config and command, but not a cryptographic snapshot of dirty source
at the instant of execution. The later local 163-file dependency manifest
records the final source/model/config hashes and explicitly states that
clean-clone reproduction is not yet supported. No fresh qualification claim
is authorized by this development audit.
