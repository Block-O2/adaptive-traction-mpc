# Human Size Contrast v1

STATUS: READY_WAITING_FOR_RESOURCES. Static preparation complete; dynamic 0/9, diagnostics 0/3. Resource waiting is not experiment failure.

Heights 1.60/1.72/2.00m; nominal mass 75kg and all independent parameters fixed. Primary task 5/10 → 120/120 deg, full OUTBOUND/HOLD/RETURN planned. All arms reuse the same old four-Human runtime, reference, controller, measurement, pacing options and scorer. No Gym/SAC interface substitution.

140-file ~11.5MB snapshot: verified Stage5 manifest plus Git objects at 41cdddef117caa4b191a52129c4ff83e481fd5a8. All 105 actual project import paths resolve inside snapshot; CPU numerical threads 1; existing adaptive-online-v1 environment used read-only with bytecode disabled. No results/archive/training data copied. Snapshot assets are Git objects. Provenance and environment are retained.

All heights: 129/129 sampled 120-degree IK feasible, no initial penetrating contacts, positive sampled Human mass matrices. MuJoCo shank length/COM/inertia and cuff site change with height, not labels alone. These checks are necessary only, not dynamic safety certification. Parameter bounds contain all three truths.

2.00m has shank .466m, outside structural .460m upper bound by 6mm. A lower existing 20/35-degree task also passes sampled geometry but cannot repair the same prior-domain violation. No common supported pilot frozen. 2.00m three rows remain NOT_RUN_UNSUPPORTED_TEST_DOMAIN; 1.60/1.72 six rows await resources. No commissioning/task failures or successes fabricated.

No B−A or C−B contrasts, executed model-consumption hashes, or prediction-quality results exist. Static dataflow confirms A never fits commissioning observations; B freezes TASK model; C uses existing legal beta/residual updates with commissioning-frozen geometry. Geometry and dynamic adaptation effects are not separated. Prior qualification results are not reused as this study's outcomes.

SAC owns priority. Initial Windows available 4.07GiB, after static screen 2.30GiB; WSL available 6.99→5.76GiB; observed swap growth 0. Prior parent peak ~2.44GiB lacks planner-child aggregate peak. No dynamic launch authorized by these observations. Static-only peak and sparse process records in RESOURCE_OVERLAP_LOG; exact parallel interval is bounded, not a benchmark. No SAC signals, repository/index/environment/config/STOP mutations, WSL restart, RL or hardware. No resource changes or automatic wakeups.

Preparation errors: two missing snapshot dependencies, resolved only by verified manifest/Git extraction. No harness/science/controller fixes. No staging/commit/push. All outputs local to side-study. Retention keeps compact evidence and frozen source only; no checkpoints or trajectories exist because no dynamic run occurred.

Next step: recheck aggregate resource evidence and headroom; resolve 2.00m supported-domain question as a separately versioned decision. Do not silently enlarge the prior in v1. Pending integration candidates are the study contract, parameter audit, source/import provenance, comparison/resource/model evidence and preparation scripts; none written to the main repository.

Runner `human_qualification.py --check` passed hash verification for all 140 snapshot files, isolated imports and frozen physical/mode scorer imports. `--execute` is gated by an absent RESOURCE_RELEASE.json containing verified aggregate peak evidence, fresh resource samples, individual prior eligibility and total-time/budget caps; no release was fabricated. Resource callback raises a side-only stop exception and uses only SIDE_STOP in this directory. Dynamic runner/serialization/postprocessing are untested because no rollout is authorized by present resources.

Effective reference pacing in inherited options is velocity fraction .5 and acceleration fraction .25; online reference defaults from the prior report are not substituted. Lower-ROM geometry screen used the same synthetic physical parameterization and was necessary geometry only. No smaller-goal result was relabeled as the primary task. Static CPU overlap may affect SAC host timing; its impact is unquantified.
