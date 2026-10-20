# Reproduction — archive-only, zero new physics

Canonical package: `/home/hank/coding/adaptive-traction-mpc-side-studies/force_motion_coupling_diagnosis_v2`. Windows review: `C:\Users\HankL\Desktop\Coding\adaptive_traction_mpc\force_motion_coupling_diagnosis_v2`.

Python `/home/hank/envs/adaptive-online-rl-v1/bin/python` and existing NumPy/SciPy/Matplotlib are reused. No dependency installation. `SOURCE_MANIFEST.json` lists every consumed archive path/size/SHA256, including complete 5ms trace, summary/config, 0.25ms native-derived arrays and full compressed native/receipt archive. These archives remain in original Side Study packages. `provenance/` holds copied original contracts/results, all candidate configs/measured qualification, frozen18D parameters and complete positive-step receipts for five core cases. `series/` stores all20 force/cumulative/native motion arrays. This is an explicit archive-dependent package; it does not claim all historical physical source/model closures were duplicated.

For a fresh, separately named output (never overwrite this stopped package):

```bash
PY=/home/hank/envs/adaptive-online-rl-v1/bin/python
SRC=/home/hank/coding/adaptive-traction-mpc-side-studies/force_motion_coupling_diagnosis_v2
OUT=/home/hank/coding/adaptive-traction-mpc-side-studies/force_motion_coupling_diagnosis_v2_recompute_001
export IHEAR_DIAG_OUTPUT="$OUT"
"$PY" -B "$SRC/control/analyze.py"
"$PY" -B "$SRC/control/enrich.py"
"$PY" -B "$SRC/control/focus_and_plot.py"
```

OUT must not exist. These commands import no controller/plant and never step physics. They regenerate read-only analyses into OUT. No inherited campaign/owner script should be run. Full native checks may take roughly a minute depending on storage. The `--resume-engineering` and `--verify-only` flags are guarded recovery modes used for the two recorded analysis failures; default reproduction requires a fresh output and does not use them.

The finalized script uses explicit archived Human joint addresses [0,1], verifies every native task q/dq against archived series, and checks native command ownership/counts across all116320 native rows/5817positive-step receipts in each of B/18D/+0.02/+0.05/repeat. For other15cases it verifies every5ms q/dq node and derivatives of stored native series, retaining the earlier full evaluator evidence separately. Last TASK trace row has no future command and NaN torque-component decomposition; only that final row is excluded from component checks, while force/trajectory completion and all integration intervals stay present.

J_F is original5ms boundary-left quadrature, not trapezoidal and not a fabricated0.25ms force stream. Phase costs clip original intervals at actual transition times. Motion TV and numerical derivatives retain native rate. Correlation uses independently aggregated phase-local equal bins, positive lag=motion leadsforce, ±1s, >=8pairs. Full tails remain in cost accounting. Raw/SG21/SG101, level/detrend/first-difference, force-rise and matched-difference analyses are separate; cumulative J is never an independent correlated signal. All trends/lag maxima remain exploratory, without independent participant replication.

All qualification is inherited at its original PHYSICAL_LEVEL1/scientific-mode scope. No new qualification, new physical candidate, host qualification, cross-state validation or training. Main git state/metadata and hashes of consumed archives are compared before/after; this is not a new full-byte hash of every unrelated historical package. Exact scope is in FINAL_PROTECTION. Engineering failures and their repairs are preserved in EXECUTION. STOP.
