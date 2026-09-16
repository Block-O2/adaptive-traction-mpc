# Stage-5 current-model trust persistence v1

## Scope and frozen boundaries

This checkpoint changes exactly one behavioral semantic: valid causal support
already earned by the Human model currently used by Goal-MPC survives later
neutral or inconclusive challenger evidence for that same model version.  The
reduced three-scale Human ID, fitting, validation thresholds, acceleration
monitor and limits, gamma settings, Goal-MPC, interface model, task, Safety
Filter and BRAKE are unchanged.  Shadow Human parameters remain shadow-only.

The preceding acceleration/trust authority audit was frozen separately in Git
commit `8021fae` (`stage5: checkpoint acceleration and trust audit`).  Its
acceleration conclusion remains **A-MONITOR-UNRESOLVED**; this work does not
replace or reinterpret that monitor.

## Old and new trust semantics

The old adapter was stateless.  On every callback it scanned the current
challenger list from newest to oldest and returned:

- high only if the newest resolved rejection reported a challenger
  statistically worse than at least one reference;
- low for an inconclusive rejection or a validated shadow publication;
- otherwise it skipped pending attempts or returned low when no resolved
  comparison was available.

Consequently, a later inconclusive rejection replaced an earlier valid
current-model support result with `False`, although the control-model version
had not changed.

The new `Stage5CurrentModelTrust` owns a binary `SUPPORTED`/`UNSUPPORTED` state
for one explicit `current_model_version`.  It records the supporting or
revoking evidence version and timestamp.  It is not a score:

| Future-validation outcome | Current-model trust effect |
|---|---|
| Challenger is statistically worse than the current population-prior/control-model reference | `SUPPORT`; set `SUPPORTED` |
| Validated challenger is statistically better than that explicit current-model reference | `NEGATIVE`; revoke to `UNSUPPORTED` |
| pending, unavailable, training-only, insufficient future evidence, or statistically inconclusive | `NEUTRAL`; preserve the existing state |
| Shadow fit/publication about a different model version | Does not raise current-model trust |
| Control-model version changes | Start the new version as `UNSUPPORTED`; do not transfer old support |

Information rank/conditioning and challenger quality remain logged authorities
but do not mutate current-model trust.  The existing confidence filter (0.75 s),
hysteresis (0.75/0.25), gamma targets (0.5/1.0) and rates (0.25/s recovery,
1.0/s slowdown) are unchanged downstream.

## Saved-trace causal replay

The replay used only already-saved nominal, stiffness +15%, and damping +20%
measurement/evidence sequences from
`human_id_confidence_pacing_v1_attempt_01`.  Each service snapshot was
reconstructed only from attempts and validation looks available at that
timestamp; no future samples were used.

| Case | Old replay vs saved gamma max abs. error | Old vs new before first support | First current-model support | Final new trust / gamma |
|---|---:|---:|---:|---:|
| nominal | 0 | 0 | 8.245 s | SUPPORTED / 0.5 |
| stiffness +15% | 0 | 0 | none | UNSUPPORTED / 0.5 |
| damping +20% | 0 | 0 | none | UNSUPPORTED / 0.5 |

At nominal 8.245 s, the rejected challenger supplied valid support for the
fixed nominal control model; the new pending challenger at the same timestamp
did not erase it.  The episode ended at 8.300 s, before the unchanged filter
and hysteresis could raise gamma.  Stiffness/damping shadow publications did
not create nominal-model support or gamma recovery.

Local compact replay output is kept under
`results/current_model_trust_replay_v1_attempt_01/` and is not proposed for
commit.

## Minimal nominal two-repetition A/B

Both arms used the fixed nominal Human in Goal-MPC, fixed nominal interface,
the same seed and controller settings, and the unchanged acceleration monitor.
Human-ID and trust lifecycle persisted across repetitions; physical state was
reset with the existing 0.25 s session-time gap, and regression windows did not
cross the artificial reset.

| Arm / repetition | Result | Duration | Support start -> end | Filter / hysteresis final | gamma max / final |
|---|---|---:|---|---|---:|
| historical stateless / 1 | COMPLETE | 8.300 s | no -> yes at 8.245 s | 0.076884 / low | 0.5 / 0.5 |
| historical stateless / 2 | COMPLETE | 7.870 s | yes -> no at 11.150 s | 0.000864 / low | 1.0 / 0.5 |
| persistent versioned / 1 | COMPLETE | 8.300 s | no -> yes at 8.245 s | 0.076884 / low | 0.5 / 0.5 |
| persistent versioned / 2 | COMPLETE | 6.285 s | yes -> yes | 0.999848 / high | 1.0 / 1.0 |

The causal timeline shared by both arms through the relevant point was:

- 8.245 s: first valid support for `stage5_fixed_registered_human_v1`;
- 8.550 s: Rep 2 starts with the same current model and persisted lifecycle;
- 9.280 s: filtered confidence crosses 0.75 and gamma target becomes 1.0;
- 9.285 s: actual gamma first leaves 0.5;
- approximately 11.280 s: gamma reaches 1.0 under the unchanged 0.25/s ramp.

At 11.150 s the next challenger result was inconclusive.  The old adapter set
raw trust low; its filter crossed the 0.25 exit threshold at 12.170 s and gamma
returned to 0.5 at approximately 12.670 s.  The persistent adapter classified
the same result as neutral, kept the same model `SUPPORTED`, and ended Rep 2 at
gamma 1.0.  No future evidence entered either path.

The planning ceilings therefore remained `[7.5, 12.5] deg/s` in Rep 1 and
causally ranged from `[7.5, 12.5]` to `[15, 25] deg/s` in Rep 2.  No identified
or published shadow Human model entered control.

## Safety observations and limitations

All four episodes had zero 200 N gate events, zero BRAKE events, only
`SAFE_UNCHANGED` Safety Filter statuses, and no MuJoCo warnings.  Peak
deployable/truth accelerations remained below the unchanged `[300, 600]
deg/s^2` limits.  The persistent Rep 2 peak force/moment were 117.148 N and
14.495 Nm; its cumulative force was 586.500 N s.

The local machine reported approximately 77--79 ms mean and 93--94 ms p95 MPC
solve time in this run, with all solves above the 20 ms nominal replanning
period.  The A/B arms had comparable timing and simulated/action-hold semantics
were unchanged, so this does not explain the trust difference; it is also not a
hard real-time or WCET claim.  It is an unfavorable runtime observation that
must not be hidden.

This experiment demonstrates neither personalized Human control nor
closed-loop use of identified parameters, hardware safety, acceleration-monitor
correctness, nor 3--5 repetition personalization.

## Decision

**T-A — TRUST PERSISTENCE FIX VALIDATED.**  Unit tests enforce version
isolation and evidence authority; replay is causal and exactly reproduces the
historical pre-support behavior; nominal Rep 2 retains already-earned support
through neutral evidence and gamma changes only through the unchanged
filter/hysteresis/ramp chain.  No other control or safety semantic was changed.
