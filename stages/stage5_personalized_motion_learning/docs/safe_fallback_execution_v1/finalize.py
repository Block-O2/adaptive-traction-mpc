"""Seal retained evidence after dispatch stops. Does not launch experiments or Git."""
import json,hashlib,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[4];DOC=Path(__file__).resolve().parent;STAGE=ROOT/'stages/stage5_personalized_motion_learning'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
f=read(DOC/'FREEZE_v1.json');state=read(DOC/'STATE.json');rows=[]
for r in f['rows']:
    paths=[DOC/('v1_'+r['run_id']+'_CORRECTED_REVIEW.json'),DOC/('v1_'+r['run_id']+'_RESULT.json')]
    found=next((p for p in paths if p.exists()),None)
    if found:rows.append(read(found))
    else:
        result=STAGE/'results/safe_fallback_execution_v1/v1'/r['run_id']/'HIGH_ROM_CASE_RESULT.json'
        if result.exists():
            x=read(result);rows.append(dict(r,run_status=x['status'],pass_all=False,abort_reason=x.get('abort_reason'),scoring_pending=True))
assert all(sha(ROOT/p)==h for p,h in f['source_map'].items()),'source drift'
status='SAFE_FALLBACK_TARGETED_VALIDATION_FAIL' if any(not r['pass_all'] for r in rows) else 'PAUSED_QUOTA_OR_TIME'
quota_end=int(sys.argv[1]);started=read(DOC/'STARTUP.json')
state.update(status=status,phase='closed_targeted_validation',current_run=None,dynamic_runs=len(rows),targeted_passed=sum(r['pass_all'] for r in rows),targeted_denominator=8,account_wide_latest=quota_end,optional_8_run=False,optional_8_allowed=False,
    representative_ready=False,production_source_fingerprint=f['source_fingerprint'],updated_utc=datetime.now(timezone.utc).isoformat(),
    remaining=[r['run_id'] for r in f['rows'] if r['run_id'] not in {x['run_id'] for x in rows}],
    next_action='Only after separate quota authorization, run the original optional eight-case representative freeze once on the unchanged candidate; do not start49/repeats/RL.',
    stop_reason='No optional8 allowed at quota>=28; targeted milestone closed. No further dispatch.' if status=='PAUSED_QUOTA_OR_TIME' else 'Targeted validation failed; preserve all evidence and stop, no further repair.')
save(DOC/'STATE.json',state)
metrics=[]
for r in rows:
    score=r.get('scorer_v2',{});events=r.get('fallback_events',[]);smooth=r.get('smoothness',{})
    metrics.append(dict(run=r['run_id'],status=r['run_status'],pass_all=r['pass_all'],fallback_count=sum(x['event']=='FALLBACK_COMMITTED' for x in events),
        reference_near_stop_s=smooth.get('non_task_reference_near_stop_longest_s'),stale_activated=r.get('stale_activated'),
        force_peak_n=score.get('peak_force_n'),moment_peak_nm=score.get('peak_moment_nm'),clearance_min_m=score.get('minimum_session_shank_clearance_m'),dwell_s=score.get('true_goal_continuous_dwell_s'),abort=r.get('abort_reason')))
save(DOC/'TARGETED_SUMMARY.json',dict(status=status,source_fingerprint=f['source_fingerprint'],rows=metrics,optional8=False,account_wide_start=24,account_wide_resume=26,account_wide_end=quota_end))
manifest=[]
for r in rows:
    p=DOC/('v1_'+r['run_id']+'_RAW_MANIFEST.json')
    if p.exists():manifest.extend(read(p))
save(DOC/'RAW_DATA_MANIFEST.json',dict(files=manifest,file_count=len(manifest),bytes=sum(x['bytes'] for x in manifest),git_ignored=True))
for p in DOC.glob('*.log'):
    (DOC/(p.stem+'_CONSOLE.txt')).write_bytes(p.read_bytes())
commands=[]
python='/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python'
for r in rows:
    commands.append([python,str(DOC/'run_case.py'),'--delay-ms',str(r['delay_ms']),'--plant-mode',r['plant'],'--case',str(ROOT/r['case']),'--output',str(STAGE/'results/safe_fallback_execution_v1/v1'/r['run_id']),'--host-monitor-limit-s','300'])
save(DOC/'COMMANDS.json',dict(environment={'PYTHONDONTWRITEBYTECODE':'1','MPLCONFIGDIR':'/private/tmp/fallback-mpl','OPENBLAS_NUM_THREADS':'1'},dynamic_commands=commands,
    tests=[python,'-m','pytest','-q','-p','no:cacheprovider',str(STAGE/'tests/safe_fallback_execution_v1/test_safe_fallback.py'),str(STAGE/'tests/high_rom_v1/test_score_return_endpoint_v2.py')],tests_extra_environment={'PYTHONPATH':str(STAGE/'scripts/high_rom_v1')},analysis=[python,str(DOC/'check_retained_escape.py')]))
lines=[f'# Safe fallback execution result\n\nFinal status: **{status}**.\n',
    f'Targeted: {state["targeted_passed"]}/{len(rows)} executed PASS; fixed targeted denominator 8. Optional original eight-case representative freeze NOT run because account-wide usage reached {quota_end}%. This is not FALLBACK_EXECUTION_REPRESENTATIVE_READY and does not authorize a 49-case freeze.\n',
    '| Run | Task | Gate | Fallbacks | Ref near-stop s | Stale activations | Force N | Moment Nm |',
    '|---|---|---|---:|---:|---:|---:|---:|']
for m in metrics:lines.append(f'| {m["run"]} | {m["status"]} | {m["pass_all"]} | {m["fallback_count"]} | {m["reference_near_stop_s"]} | {m["stale_activated"]} | {m["force_peak_n"]} | {m["moment_peak_nm"]} |')
lines += ['''
## Required answers

1. The historical 191.428 ms compute failure occurred because a 40 ms bridge ended at nonzero dq while the future was unfinished. It aborted at source age 47.488 ms, before expiry. Historical failure and matrix are unchanged; see READ_ONLY_RECONSTRUCTION.md and the provenance checkpoint.
2. The selected primary carries a prevalidated original bridge and stop before activation. Fork = latest certified 5 ms bridge grid node strictly before endpoint (0.035 s in tested cases). Receipt reference progress is capped at the fork; primary not activated/validated before reaching it commits braking irrevocably. This is a reference-progress deadline, not a wall-clock/WCET guarantee.
3. Constructing/validating the stop occurs in the isolated worker before primary admission. Commit and stop sampling do not call or await the future planner. The existing per-command safety supervisor still runs. Delayed/cancelled producer output cannot preempt braking. The scope is current deployable model and tested simulation, not universal physical invariance.
4. Original-case 200 ms availability delay passed stop→hold→fresh replan→resume→COMPLETE. Result became visible at source age 239.214 ms and was dropped; fresh resume age was 62.397 ms. Natural run independently reproduced a 191.053 ms compute tail and recovered.
5. Natural and 0 ms runs each included a natural fallback; do NOT claim zero-fallback normal execution for them. Both retained whole-trace near-stop=0.150 s, below the frozen original-case cap .350 s. Separate no-fallback representative evidence is in the table. All original primary q/dq/ddq polynomials are unchanged by the preparation adapter. Intentional fallback occurrences are explicitly reported.
6. All executed-run stale activations are in the table. Deterministic tests reject exactly 100 and 200 ms. The previous >100 comparison was tightened to >=100; timestamp origins were not renewed. Scorer-v2 source and thresholds are unchanged.
7. Optional original eight-case representative freeze was NOT run. The targeted denominator is a different eight-run development protocol and must not be conflated with representative readiness.
''',f'8. Production source/config/scorer fingerprint (179 files including the new module): `{f["source_fingerprint"]}`. Freeze v1 matched after execution.\n',
    f'9. Provenance-only checkpoint: `{(DOC/"PROVENANCE_CHECKPOINT.txt").read_text().strip()}`. Final candidate checkpoint is recorded separately in CHECKPOINT_SHA.txt after commit; no promotion implied.\n',
    f'10. ACCOUNT-WIDE usage: original task start24%, authorized resume26%, last{quota_end}%, reset window1791047434. Shared-account delta, not measured task-only consumption. No quota reset.\n',
    '''11. Do not start49-case. The one next step, only with renewed quota authorization, is the original optional eight-case representative freeze on the unchanged candidate; if it fails, preserve and stop under the exhausted repair budget.

## Validation and integrity

15 deterministic/scorer tests passed. 69/69 retained moving endpoints passed the pre-implementation model feasibility check, not a new dynamic campaign. AST and git diff --check passed. Tests initially failed collection due to missing scorer PYTHONPATH; the failing invocation remains. One evidence-wrapper Boolean bookkeeping correction is charged conservatively as the single repair. Old false summaries and separately recomputed corrected reviews remain; no natural/0ms rerun and no production repair occurred. See SCORING_BOOKKEEPING_CORRECTION.md. No acceptance threshold or scorer-v2 semantics changed.

Files: three existing production modules changed (runtime.py, online_planning.py, activation_validation.py); safe_fallback.py added; one test module added; new docs/protocol/results/manifests under docs/safe_fallback_execution_v1. No scientific cost/search/task/force/moment/clearance/ROM/noise/plant/solver/rollout-duration changes. New execution assumption is explicit admission of a certified escape; no new sensor or hidden truth. Source of escape inputs is deployable belief/reference/registered limits. No hardware actuation. No subagent or independent Auditor was dispatched.

Commands and environment: COMMANDS.json. Raw traces remain ignored; RAW_DATA_MANIFEST.json gives hashes. All attempted dynamic runs retained and none retried for a random PASS. No49-case/30-repeat/value/RL/fresh qualification. Local individual staging/commits only; no push/merge/reset/stash/clean/delete/worktree creation. Canonical checkout source was not edited.

## Future async value contract

The architecture supports a droppable producer: execution owns the selected primary plus escape independently. A future value interface must fix value/model/trajectory versions, enforce its ranking deadline, drop late outputs, and use baseline ranking when missing. It must not delay execution or bypass activation validation. No value/RL implementation or training was performed.
''']
(DOC/'FINAL_REPORT.md').write_text('\n'.join(lines))
save(DOC/'FINAL_FINGERPRINTS.json',dict(source_fingerprint=f['source_fingerprint'],source_map=f['source_map'],scoring_wrapper_sha256=sha(DOC/'evidence_tools.py'),harness_sha256=sha(DOC/'run_case.py'),new_tests_sha256=sha(STAGE/'tests/safe_fallback_execution_v1/test_safe_fallback.py')))
print(json.dumps({'status':status,'executed':len(rows),'passed':state['targeted_passed'],'raw_files':len(manifest)}))
