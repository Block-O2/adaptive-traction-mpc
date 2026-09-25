# FULL-3D Adaptive Integration V1 Failure Ledger

All failed runs remain under
`results/full3d_adaptive_integration_v1/`; none was overwritten or promoted as
formal evidence.

| Run | Observed result | Cause / lesson | Repair classification |
|---|---|---|---|
| `baseline_existing_cr12_v1` | aborted at `0.32 s`, `TASK_ACCELERATION_LIMIT`; all 20 ms planner deadlines missed | strongest existing CR12 path was physically connected but its old execution/controller timing was not task-qualified | baseline evidence only |
| `nominal_attempt_01` | commissioning handoff failed | the residual estimator needed a prior aligned history sample | implementation defect; added causal warm-up |
| `nominal_attempt_02` | physical task completed, CLI serialization failed | result existed, but terminal presentation was broken | output defect only |
| `nominal_attempt_03/04` | completed motion but q-reference jump at HOLD (`~0.12--0.14 deg`) | actual arrival could switch phase before the emitted quintic endpoint was consumed | defer phase switch until the active q/dq/ddq endpoint boundary |
| `nominal_attempt_05` | final closeout had no mechanics-feasible candidate | shortest reference-feasible duration was not necessarily wrench-feasible | opt-in bounded longer-duration search, same force/motion limits |
| `nominal_attempt_06` | timeout with repeated replanning | the endpoint schedule was replaced on its exact terminal node before emission | endpoint consumption ordered before transition/replan |
| `nominal_timing_aware_attempt_07` | completed, later audit found trace defects | terminal node omitted; command channel lagged; learning cost included planning wait; last transition duration could be negative; belief request/execution labels were ambiguous | logging/provenance correction; no controller retuning |
| `no_task_actuation_diagnostic_01` | expected task failure, but inherited logging defects | causal idea valid, artifact contract incomplete | rerun after logging repair |
| `nominal_timing_aware_attempt_08` | completed after terminal/learning repair | still preceded all-contact, realized-limit, qdd-reference, and applied-command fixes | superseded development evidence |
| `nominal_timing_aware_attempt_09` | completed and supported the first independent audit | post-run source audit found missing terminal `next_adaptive_state` plus unexercised global-timeout and low-level-exception trace defects | preserved; superseded by the post-audit final rerun |
| `no_task_actuation_diagnostic_02` | correctly showed zero task actuation and an early acceleration abort | inherited the same terminal next-state omission | preserved; superseded by the post-audit final diagnostic |
| `nominal_timing_aware_attempt_10` | completed after terminal-state and exception-path repairs | preceded the required per-boundary acceleration/contact/clearance trace channels | preserved; superseded logging evidence |
| `nominal_timing_aware_attempt_11` | task completed, but 61 deployable session-clearance samples were negative; minimum `-3.303649 mm` | reference-only nonpenetration allowed a `+0.173960 mm` near-bed return schedule whose realized tracking crossed the conservative set | preserved failed acceptance artifact; added task-endpoint clearance floor plus fail-closed realized monitor before one frozen rerun |
| `nominal_timing_aware_attempt_12` | clearance-policy rerun aborted at `4.010 s` with `STALE_PLAN_MAXIMUM_AGE` | a return replanning attempt exceeded the unchanged 100 ms age cap; the rejected solve was not retained in the timing list | preserved timing failure; logging repaired so any repeated stale solve is visible, with no deadline/solver/controller tuning |
| `nominal_timing_aware_attempt_13` | repeated the same return abort at `4.010 s`; rejected solve took `2093.990 ms` and proposed `return_dq_08` | the safe-return mechanics-duration search is consistently incompatible with the frozen 100 ms plan-age contract in this state | final constraint/timing evidence; stop rather than relax the deadline or stack another search heuristic |
| `no_task_actuation_diagnostic_03` | expected zero-actuation abort with complete terminal belief | preceded final per-boundary constraint channels | preserved; superseded logging evidence |
| `phase2_v22_corrected_time_replication_v1` | 168 rows and 46/46 checks true | 14 aborted comparator rows omitted the final boundary, so generic N/N+1 coverage was incomplete | preserved corrected-replication draft; evaluator repaired without controller tuning |
| `phase2_v22_corrected_time_replication_v1_1` | 168 rows, 46/46 checks true, and all rows have N+1 boundaries for N intervals | independent audit found that the run manifest omitted the imported `time_contract.py` dependency | preserved; repeated as V1.2 with provenance-only manifest repair |
| first media render | CoreGraphics connection error | native MuJoCo raster renderer unavailable in the headless shell | replaced by numeric-state x-z projection replay; videos are inspection only |

The post-audit final nominal artifact is `nominal_timing_aware_attempt_14`; the
paired causal diagnostic is `no_task_actuation_diagnostic_06`. The failure
history supports the narrow final implementation but does not constitute
repeatable timing or target-domain robustness evidence.
