# Lab-Relevant Human Adaptation Contrast v1

STATUS: READY_WAITING_FOR_RESOURCES. Prepared and stopped; primary 0/21, oracle 0/3, combined not started. No task outcomes fabricated.

Height is fixed 1.72m, thigh .43688m and shank .40076m. Same nominal robot/table/setup and inherited hip offset [0,.0001]m. Primary task remains 5/10→120/120deg full OUTBOUND/HOLD/RETURN. Same original four-Human qualification runtime, waypoint reference/controller, measurement, scorer and .5/.25 reference pacing for all arms. No SAC Gym/RL/CEM substitution.

Mass: 60/75/90kg synthetic scaling; segment masses and derived inertias scale consistently at fixed lengths. Passive stiffness: [7,7]/[10,10]/[13,13]Nm/rad, damping always [5,5], rest/soft-limit law unchanged. Cuff final rho: .60/.72/.77, selected prospectively from .60/.72/.85 before any dynamic results.

Prospective rho .85 produces -2.778mm initial full-sleeve/table gap despite center and axial placement remaining on shank. Sleeve collision is disabled in the plant, so empty contact lists alone would miss this failure; the unchanged full-cylinder table envelope rejects it. The predeclared descending .01 grid selects nearest feasible .77, with only +.0161mm initial sleeve gap. This is a numerical installation boundary, not a robust laboratory installation claim. rho .60 has only .076mm full-sleeve clearance to the distal-half midpoint; no manufacturing tolerance assumed. No safety threshold/placement change.

| condition | mass kg | K Nm/rad | rho | MuJoCo propagation | static setup |
|---|---|---|---|---|---|
| C0 nominal | 75 | [10.0, 10.0] | 0.72 | verified compiled arrays | NECESSARY_STATIC_PRECHECK_PASS |
| C1 mass_low | 60 | [10.0, 10.0] | 0.72 | verified compiled arrays | NECESSARY_STATIC_PRECHECK_PASS |
| C2 mass_high | 90 | [10.0, 10.0] | 0.72 | verified compiled arrays | NECESSARY_STATIC_PRECHECK_PASS |
| C3 stiffness_low | 75 | [7.0, 7.0] | 0.72 | verified compiled arrays | NECESSARY_STATIC_PRECHECK_PASS |
| C4 stiffness_high | 75 | [13.0, 13.0] | 0.72 | verified compiled arrays | NECESSARY_STATIC_PRECHECK_PASS |
| C5 cuff_proximal | 75 | [10.0, 10.0] | 0.60 | verified compiled arrays | NECESSARY_STATIC_PRECHECK_PASS |
| C6 cuff_distal | 75 | [10.0, 10.0] | 0.77 | verified compiled arrays | NECESSARY_STATIC_PRECHECK_PASS |

All seven full MuJoCo models compiled, hip/shank mass/COM/inertia, joint stiffness/damping/range/rest and sleeve site/geom positions were checked. All mass matrices positive over 0–125deg sampled knee range; geometry/identifier bounds contain all truths and unchanged .46m shank prior applies. Three distinct cuff geometries passed 129-point static IK; mass/stiffness cases reuse exactly identical geometric paths with separate full-model compilation. Analytic sleeve/bar/connector and limb envelopes checked over 1201 primary path configurations. Initial contacts have no penetration. Geometric screening is necessary only; actual commissioning, replanning, loads, HOLD and true RETURN remain untested.

Raw commissioning waypoints include a geometrically unsafe literal target even for the inherited nominal case; the existing DEV-D feedback projection is part of the validated path. It remains unchanged in all arms. A raw-target gap is recorded separately, not misclassified as commissioning failure before execution.

A fixes nominal geometry/beta/residual and does not fit commissioned observations. B performs individual causal commissioning and freezes the TASK model. C repeats the same commissioning protocol, keeps geometry frozen and allows the original legal beta/residual updates. Physical truth/probes/noise semantics identical within each triplet; no observations/checkpoints transferred across arms.

No strongest B−A/C−B effect, success rate, task force/moment/RMSE or prediction improvement can be reported. No dynamic model-consumption hashes exist. Prepared wrappers emit actual numerical model hashes/value and separate geometry hash from planner/mechanics/execution per PID; unobserved worker emissions remain gaps. TASK torque prediction evaluates the frozen commissioning model on new TASK samples, and continual predictions before sample update. It is finite-difference torque reconstruction, not future-state forecasting; no hidden state/parameters enter the predictor. Effective cuff distance is evaluated directly; full shank and cuff fraction are not separately identified. In the lab, cuff geometry may be directly measurable, so this tests automatic calibration rather than impossibility of manual measurement.

Source: all 140 files copied from prior independent verified snapshot and rehashed. No source taken from evolving SAC worktree. All actual project imports resolve within new snapshot. Prefix backend is the frozen source NumPy fallback, same for all arms; prior unmanifested compiled extension was not copied. No native-backend timing/realtime equivalence claimed. The harness/postprocessor passed import checks, and 9 offline regression checks passed. Dynamics/serialization/worker instrumentation/actual scorer data path remain untested because no rollout ran. One evaluation-wrapper field repair; error preserved; controller/identifier/parameters/thresholds untouched.

Resource gate: initial Windows available ~3.36GiB below reserve; later ~4.75GiB still cannot absorb even the known prior parent peak ~2.44GiB while retaining 4GiB. Prior peak omits planner children; planning 4GiB is unverified and is not a release. Current sample and refusal reasons saved. WSL swap growth observed 0. Static CPU one numerical thread, nice19, no render/GPU, no time integration; static interval/peak RSS saved. SAC state subsequently reported its own qualification-stop/reset-stress blocker; no causation claimed. No SAC actions, affinity/config/environment/branch/index/shared STOP changes or WSL restart. Static host contention is unquantified, not a clean benchmark.

Previous height study is now STATIC_PRECHECK_ONLY / SUPERSEDED_FOR_DYNAMIC_STUDY with old state preserved. No height dynamic budget continued. No primary run, oracle, combined case, noise repeat or RL/hardware launched. Compact local evidence only; no checkpoint/full trajectory exists. No history deleted or Git stage/commit/push.

Next recommended step: obtain justified aggregate peak/headroom and confirm SAC is outside formal benchmark, then execute the frozen 21-run matrix with one side owner at a time. Stop here; no automatic wakeup or task expansion.
