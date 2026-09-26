# High-ROM Stage C runtime blocker: paired audit and retest

**Status: `RUNTIME_TARGET_NOT_MET`.** Candidate 07 passed the frozen eight-case representative task and safety check (8/8), but planning compute p95 was **31.034 ms** against **≤30 ms**. Activation p95 was 52.230 ms (≤55), control misses were 9.524% (below the frozen historical 11.818%), and stale activations were zero. This is offline MuJoCo development evidence. It is not fresh qualification, continuous safety, hardware readiness, or a real-time guarantee. No qualification, RL, model/plant change, or full 49-case candidate-07 regression was run.

## Freeze and scope

The starting High-ROM runtime branch was `codex/full3d-cr12-high-rom-runtime-v1` at `89798cb83af7c8da20e63963495ebbc068489e20`, with candidate-03 source/config frozen in `ROOT_CAUSE_FREEZE.json`. The confirmed High-ROM worktree and original repository were left untouched. Candidate 07 is uncommitted. `CANDIDATE07_FREEZE.json` and `ROOT_CAUSE_FINAL_FINGERPRINTS.json` contain 173/173 matching source/config hashes, the unchanged `BENCHMARK_SPEC.json` hash, all eight case hashes, scorer hashes, and raw-case result hashes. No file was staged, committed, pushed, merged, reset, stashed, cleaned, or deleted.

The frozen 8 cases cover low ROM ordinary/near-upper, 100/100, 110/110, 120/120 synchronous and hip-leading, and 120/120 from (6°,11°) and (8°,13°). The previous candidate-03 49/49 regression remains separate evidence for a different source version. The 125° High-ROM engineering assumption, task/arrival/dwell/RETURN criteria, physical limits, collision checks, candidate definitions, cost, and 100 ms plan expiration were not changed.

## Paired timing audit before repair

The same baseline and candidate-03 cases were run in ABBA order with a single process at a time. These are uninstrumented timing runs; `PAIRED_ROOT_CAUSE_TIMING.json` includes per-stage p95/max, queue/wait, native-step records, and reconstructed miss streaks. The order was high-120 baseline/candidate/candidate/baseline, then low-ROM baseline/candidate/candidate/baseline.

| Pair order | High-120 miss | Low-ROM miss |
| --- | ---: | ---: |
| Baseline 1 | 12.45% | 15.12% |
| Candidate 1 | 17.67% | 15.05% |
| Candidate 2 | 25.69% | 16.70% |
| Baseline 2 | 27.81% | 17.98% |

Both implementations worsen with order. The historical cross-day 11.82%→30.11% miss gap therefore cannot be assigned causally to the planner optimization. Host scheduling/thermal contention is plausible but was not measured directly. The TASK phase, rather than commissioning, carries most misses: in the paired high-120 sequence TASK misses rose 16.18%→39.75%, while the uninstrumented TASK poll-end-to-next-tick-start p95 was 8.13–9.26 ms on a 5 ms grid. The longest paired miss streak was 19 grids/95 ms. Worker queue p95 was roughly 1.0–1.8 ms and worker-to-main handoff p95 roughly 9–12 ms. Planning uses a spawned process, so it does not share the main Python GIL; CPU/OS scheduling competition remains possible. GC events during the active epoch were zero in all eight paired runs. Active I/O and lock wait were not instrumented and cannot be excluded.

A separate low-ROM diagnostic with in-memory stage wrappers (`CONTROL_STAGE_INSTRUMENTED.json`) measured TASK measurement p95 0.442 ms, low-level command p95 1.446 ms, supervisor/safety p95 0.014 ms, next-tick physics/wait p95 11.389 ms, and whole execute-with-next-tick p95 14.954 ms. Wrappers add overhead, so these are descriptive, not frozen gate values. The main-loop and native MuJoCo workload are substantial; no single verified contention source explains every miss.

## Second-scale tail

The retained slow deployable planner snapshot was replayed twice with an event trace. Its wall times were about 1.85 s and matched CPU time; the first unpickle took about 14 ms, the second about 0.1 ms, and GC events were too small to explain the tail. One rejected `outbound_dq_09` candidate tried **1,854** durations and drove most of **1,873** continuous certificate calls; certificate work alone consumed about 925–931 ms. This is a finite search/conservative-certificate computational tail, not evidence of physical collision. Candidate 07 reduced the same saved snapshot to **1,441 ms** with the same selected decision, but the second-scale tail remains. This diagnosis is specific to the saved event, not a proof that all online tails share this cause.

## Same-semantics repairs and checks

- `fast_physics_monitor.py` and the evaluation-only import in `runtime.py` remove temporary arrays/contact sets from each native-step physical monitor observation. The same clearance, contact, ROM, load, and count definitions remain. An in-memory 2,000-state synthetic old/new record comparison was exact. The monitor never supplies control inputs.
- `monotonic_clearance.py` caches exact binary64 interval trig bounds and endpoint-proof bounds using keys containing every read input. Cached objects are immutable bound tuples; a new interval is constructed for callers. This preserves outward-rounding operations while avoiding repeated common-start proof work.
- `rigid_table_reference.py` now computes sampled knee height only on the existing fallback branch. If the existing structural proof succeeds, that array was unused.

The retained 120° outbound/HOLD/RETURN fixed snapshots match candidate 03's full decisions exactly; the historical slow snapshot's selected decision and full serialized decision also match. These are finite equivalence checks, not a formal proof over every possible state. The prior candidate-03 vectorized scheduler, grid cache, and terminal-reference reuse remain part of this source. No candidate count, search interval, score, controller policy, physical model, task, safety, or stale rule changed.

## Frozen eight-case gate and function evidence

| Measure | Historical functional baseline | Candidate 03 | Candidate 06 | Candidate 07 | Gate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Planning compute p95 | 41.849 ms | 33.372 ms | 30.762 ms | **31.034 ms** | ≤30 ms |
| Sample→activation p95 | 63.992 ms | 55.609 ms | 53.991 ms | **52.230 ms** | ≤55 ms |
| Control miss ratio | 11.818% | 30.114% | 9.467% | **9.524%** | <11.818% |
| Longest miss streak | 19 grids | 19 | 19 | **18 grids/90 ms** | Descriptive |
| Stale activated | 0 | 0 | 0 | **0** | 0 |

Candidate 07 had 139/139 requests activated, no dropped or stale requests, compute max 31.965 ms, and activation max 55.846 ms. Candidate 07's 8/8 runs were `COMPLETE`, with native arrival, continuous valid dwell ≥0.5 s, actual RETURN, registered task quality and original safety limits confirmed. Minimum native dwell was **0.520 s**, minimum native shank/table clearance **8.247 mm**, maximum native interface force **114.103 N**, and maximum moment **16.116 Nm**. Native contact, ROM, phase-limit, and stale-activation counts were zero. Physical q/dq nodes are recorded every 0.25 ms; load/clearance extrema are monitor cumulative values, while sleeve/kinematic samples are about 5 ms. No between-step continuous-safety claim follows.

The first two new scoring outputs used an incorrect relative case path, then the helper's 120° default for 100/110° and low-ROM sampled scoring. Both erroneous JSONs are retained as `CANDIDATE07_FUNCTION_INITIAL_SCORER_ERROR.json` and `CANDIDATE07_FUNCTION_SECOND_SCORER_ERROR.json`. `score_runtime_gate.py` now uses each registered case path and goal and independently combines sampled and native checks. Only evaluation code changed; the same eight raw rollouts were rescored, never rerun for the scorer correction.

The independent read-only Auditor accepted the 8/8 representative function scoring, 173/173 source/config fingerprint match, and limited same-semantics/truth-firewall evidence. The Auditor rejected the runtime gate because compute p95 exceeds 30 ms and explicitly warned that the ABBA drift prevents a causal claim that the control-miss root cause was fully fixed. No source/config drift, truth injection, or hidden scientific-threshold change was found in the checked path.

## Budget, commands, and stopping point

The actual Codex weekly bucket was **18% used at start and 20% at closeout**, in the same 10,080-minute window resetting at Unix `1790917420`. This is +2 percentage points, the stop-expanding-diagnosis line; +3 is wrap, +4 the maximum authorization, and 45% the outer project stop. The budget was not inferred from hours or tokens. In-flight worker interruption remains unverified; each development run had a 300 s host monitor and campaign STOP check. No paid API, model upgrade, hardware action, or long unattended campaign was used.

The 29 unique new diagnostic/development rollouts took about **1,322 s summed host time**; the final eight candidate-07 gate runs took **391.885 s**. Each raw `HIGH_ROM_CASE_RESULT.json` records its exact `run_dev_case.py --case ... --output ... --plant-mode ... --host-monitor-limit-s 300` command. Aggregation commands were `runtime_benchmark.py --mode candidate --candidate-root results/high_rom_runtime_v1/candidate07_gate --output docs/high_rom_runtime_v1/CANDIDATE07_BENCHMARK.json` and `score_runtime_gate.py --candidate 07`, both under `scripts/high_rom_v1/`. Original raw outputs and earlier failures remain under `results/high_rom_runtime_v1/`; the paired, tail, stage, gate, and fingerprint JSONs are under this documentation directory.

**Next step:** if Stage C continues later, optimize the measured certificate hot path under a newly frozen same-semantics candidate, then run one prespecified development runtime gate. Do not enter qualification or RL from candidate 07.
