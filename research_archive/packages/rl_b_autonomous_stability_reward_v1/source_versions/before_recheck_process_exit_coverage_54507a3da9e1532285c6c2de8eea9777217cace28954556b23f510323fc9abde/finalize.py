"""Bounded safe closure, historical protection and artifact manifest."""
from pathlib import Path
import json,os,signal,subprocess,sys,time,traceback,fcntl
from research_common import ROOT,RUNTIME,HARD_STOP,STATE,atomic,read,sha,now,same_pid,pid_identity,ledger,decision
from build_reports import build
SERVICES=['CAMPAIGN_PROCESS.json','WATCHDOG_START.json','STATUS_MONITOR_START.json',
          'ANALYSIS_SERVICE_START.json','FAILSAFE_START.json']

def service_sources():
    return SERVICES+[str(p.relative_to(ROOT)) for folder in [ROOT/'audit/observers',ROOT/'followup_queues']
                     for p in sorted(folder.glob('*/START.json'))]

def close_services():
    observed=[]
    for name in service_sources():
        a=read(ROOT/name,{});identity=a.get('identity')
        if not same_pid(identity):continue
        pid=identity['pid']
        # All five services were launched in exclusive sessions. Never signal
        # a shared host process group if a future launcher changes that rule.
        try:group=os.getpgid(pid)==pid
        except ProcessLookupError:continue
        try:os.killpg(pid,signal.SIGTERM) if group else os.kill(pid,signal.SIGTERM)
        except ProcessLookupError:pass
        observed.append(dict(service=name,identity=identity,exclusive_process_group=group))
    for _ in range(20):
        if not any(same_pid(x['identity']) for x in observed):break
        time.sleep(.1)
    for x in observed:
        if same_pid(x['identity']):
            pid=x['identity']['pid']
            try:os.killpg(pid,signal.SIGKILL) if x['exclusive_process_group'] else os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
        x['exited']=not same_pid(x['identity'])
        # This is an external exit observation, not a fabricated normal result.
        if x['service'] in SERVICES:
            stem=x['service'].replace('_START.json','').replace('_PROCESS.json','')
            end=ROOT/(stem+'_END.json')
        else:end=(ROOT/x['service']).with_name('END.json')
        if not end.exists():atomic(end,dict(time_utc=now(),reason='FINALIZER_OWNED_SERVICE_SHUTDOWN',
             identity=x['identity'],externally_observed_exit=x['exited'],normal_completion_claimed=False))
    atomic(ROOT/'audit/FINAL_SERVICE_SHUTDOWN.json',observed)

def finalize(reason='AGENT_FINALIZATION'):
    # No new attempts can pass admission after this marker.
    (ROOT/'STOP_REQUESTED').write_text(reason+'\n')
    decision('FINAL_REVIEW_START',dict(reason=reason,budget=read(ROOT/'LEDGER.json')),
             'Stop owned physical work, close evidence and verify protected artifacts')
    stopped=[]
    for p in (ROOT/'owned').glob('*.json'):
        a=read(p)
        if a.get('ended') or not same_pid(a.get('worker')):continue
        os.killpg(a['pgid'],signal.SIGTERM);stopped.append(a)
    limit=min(time.time()+20,HARD_STOP-5)
    while time.time()<limit and any(same_pid(a['worker']) for a in stopped):time.sleep(.5)
    for a in stopped:
        if same_pid(a['worker']):os.killpg(a['pgid'],signal.SIGKILL)
    # Allow supervisors to settle crash reservations and close jobs.
    for _ in range(20):
        active=[read(p) for p in (ROOT/'owned').glob('*.json') if read(p).get('worker') and same_pid(read(p)['worker'])]
        if not active:break
        time.sleep(.5)
    with ledger() as value:
        for a in value['attempts']:
            if not a['settled']:
                a.update(settled=True,native_steps=a['reserved_native_steps'],
                    native_counting='FINAL_CONSERVATIVE_RESERVATION',outcome='INTERRUPTED_FINAL_CLOSE',end_utc=now())
                value['native_steps']+=a['reserved_native_steps']
    atomic(ROOT/'END.json',dict(event='END',time_utc=now(),unix=time.time(),reason=reason,
           status='PHYSICS_STOPPED_FINAL_AUDIT',t0_utc=STATE['t0_utc']))
    # The two service monitors observe END and exit without being killed.
    for _ in range(35):
        live=[]
        for name in service_sources():
            a=read(ROOT/name,{})
            if same_pid(a.get('identity')):live.append(a['identity'])
        if not live:break
        time.sleep(.5)
    close_services()
    # All evaluation-only analyses are deterministic saved-data operations.
    py=ROOT.parent/'rl_b_matched_recovery_stability_v1/cpu-env/bin/python'
    analyses=[]
    for line in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines() if (ROOT/'ALL_ATTEMPTS.jsonl').exists() else []:
        a=json.loads(line)
        if a['mode']=='evaluation' and not (Path(a['run'])/'COMMON_MOTION_METRICS.json').exists():
            if time.time()>HARD_STOP-90:break
            p=subprocess.run([str(py),str(ROOT/'scripts/motion_metrics.py'),a['run']],capture_output=True,text=True,timeout=min(60,max(1,HARD_STOP-time.time()-60)),env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
            analyses.append(dict(run=a['run'],returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
    atomic(ROOT/'audit/FINAL_MOTION_ANALYSIS.json',analyses)
    # Recompute every frozen native/receipt/terminal/dose/motion result in a
    # separate CPU-only process after all physical owners and writers close.
    recheck_process=dict(start_utc=now(),attempted=False,returncode=None,error=None)
    if time.time()<HARD_STOP-180:
        recheck_process['attempted']=True
        try:
            proc=subprocess.run([str(py),str(ROOT/'scripts/recheck_frozen_evidence.py'),'--all','--final'],
                capture_output=True,text=True,timeout=min(600,max(1,HARD_STOP-time.time()-150)),
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
            recheck_process.update(returncode=proc.returncode,stdout=proc.stdout[-4000:],stderr=proc.stderr[-4000:])
        except subprocess.TimeoutExpired as exc:
            recheck_process['error']='SAVED_EVIDENCE_RECHECK_TIMEOUT:'+str(exc.timeout)
    else:recheck_process['error']='INSUFFICIENT_HARD_DEADLINE_RESERVE'
    recheck_process['end_utc']=now()
    atomic(ROOT/'audit/FINAL_FROZEN_RECHECK_PROCESS.json',recheck_process)
    recheck_result=read(ROOT/'audit/FINAL_FROZEN_PHYSICS_RECHECK.json',{})
    recheck_pass=(recheck_process['returncode']==0 and recheck_result.get('all_pass') is True
        and recheck_result.get('expected_frozen')==read(ROOT/'LEDGER.json')['evaluation_attempts']
        and recheck_result.get('rechecked')==recheck_result.get('expected_frozen')
        and recheck_result.get('ledger_unchanged_during_recheck') is True)
    from audit_accounting import audit as accounting_audit
    accounting=accounting_audit(final=True)
    from audit_source_versions import audit as source_audit
    source_identity=source_audit()
    if time.time()<HARD_STOP-180 and (ROOT/'ALL_ATTEMPTS.jsonl').exists():
        for script,timeout in [('checkpoint_diagnosis.py',90),('saved_action_execution.py',45),('reward_reflection_evidence.py',45),('phase_dose_attribution.py',45),('plot_results.py',60)]:
            if time.time()>=HARD_STOP-150:break
            try:
                p=subprocess.run([str(py),str(ROOT/'scripts'/script)],capture_output=True,text=True,
                      timeout=timeout,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
                record=dict(returncode=p.returncode,stdout=p.stdout[-2000:],stderr=p.stderr[-4000:])
            except subprocess.TimeoutExpired as exc:
                record=dict(returncode=None,error='OFFLINE_ANALYSIS_TIMEOUT',timeout_s=exc.timeout,pass_=False)
            atomic(ROOT/'audit'/('FINAL_'+script.replace('.py','.json')),record)
    protected=read(ROOT/'audit/HISTORICAL_PROTECTION_START.json')['files'];mismatches=[];checked=0
    for item in protected:
        if time.time()>HARD_STOP-45:break
        p=Path(item['path']);actual=sha(p) if p.exists() else None
        checked+=1
        if actual!=item['sha256']:mismatches.append(dict(path=str(p),expected=item['sha256'],actual=actual))
    verification=dict(time_utc=now(),files_expected=len(protected),files_verified=checked,
          mismatches=mismatches,pass_=checked==len(protected) and not mismatches,
          incomplete_reason='HARD_STOP_TIME_GUARD' if checked<len(protected) else None)
    atomic(ROOT/'audit/HISTORICAL_PROTECTION_END.json',verification)
    frozen=read(RUNTIME/'FROZEN_CONTRACT_MANIFEST.json')['files']
    runtime_bad=[rel for rel,h in frozen.items() if sha(RUNTIME/rel)!=h]
    github=ROOT.parent/'rl_b_matched_recovery_stability_v1/github'
    identity={}
    for key,args in [('HEAD',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--short'])]:
        p=subprocess.run(['git','-C',str(github),*args],capture_output=True,text=True,timeout=30,
             env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'});identity[key]=p.stdout;identity[key+'_rc']=p.returncode
    atomic(ROOT/'audit/GITHUB_END_IDENTITY.json',identity)
    owned=[]
    for p in (ROOT/'owned').glob('*.json'):
        a=read(p)
        if a.get('worker'):owned.append(dict(job=a.get('job'),identity=a['worker'],alive=same_pid(a['worker']),end=a.get('ended')))
    services=[]
    for name in service_sources():
        a=read(ROOT/name,{})
        services.append(dict(name=name,identity=a.get('identity'),alive=same_pid(a.get('identity'))))
    atomic(ROOT/'PROCESS_EXIT_AUDIT.json',dict(time_utc=now(),workers=owned,services=services,
           all_owned_workers_exited=all(not x['alive'] for x in owned),all_services_exited=all(not x['alive'] for x in services),
           active_finalizer='This bounded finalizer exits immediately after writing its closing artifacts.'))
    decision('STOP',dict(reason=reason,counts=read(ROOT/'LEDGER.json'),protection_pass=verification['pass_']),
             'No next package or final Campaign automatically started')
    atomic(ROOT/'STOP.json',dict(time_utc=now(),reason=reason,status='STOP',formal_campaign_started=False))
    atomic(ROOT/'RESEARCH_STATE.json',dict(read(ROOT/'RESEARCH_STATE.json'),status='STOP',time_utc=now(),next='Human review only; no automatic next research package'))
    atomic(ROOT/'END.json',dict(event='END',time_utc=now(),unix=time.time(),reason=reason,status='STOP',t0_utc=STATE['t0_utc']))
    from enrich_decisions import enrich
    enrich()
    # Read the final STOP END clock when constructing the final report.
    result=build(final=True)
    # Closeout stdout may be a file inside ROOT. Flush its final message before
    # hashing; no normal stdout/stderr writes are permitted after sealing.
    print(json.dumps(dict(event='SEALING_MANIFEST',elapsed_h=result['elapsed_h'],attempt_rows=result['rows'])),flush=True)
    entries=[]
    exclude={'OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json'}
    files=[p for p in sorted(ROOT.rglob('*')) if p.is_file()
         and str(p.relative_to(ROOT)) not in exclude]
    for p in files:
        if time.time()>HARD_STOP-10:break
        entries.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)))
    atomic(ROOT/'OUTPUT_MANIFEST.json',dict(time_utc=now(),files=entries,excludes=list(exclude),
        evidence_scope='All new package files apart from self-referential manifest/verification',
        expected_file_count=len(files),manifest_complete=len(entries)==len(files),
        hard_stop_reached=time.time()>=HARD_STOP-10))
    required=['REPORT.md','RESEARCH_DECISION_LOG.jsonl','AUTONOMOUS_EXPERIMENT_PLAN.md','H1_STABILITY_RESULTS.json',
       'PPO_OPTIMIZATION_DIAGNOSIS.md','REWARD_CANDIDATES.md','REWARD_VERSION_MANIFEST.json','REWARD_SEARCH_RESULTS.json',
       'CHECKPOINT_COMPARISON.json','FROZEN_EVALUATION_RESULTS.json','TASK_FORCE_MOTION_COMPARISON.md','GENERALIZATION_AUDIT.md',
       'RESOURCE_USAGE.json','ATTEMPT_ACCOUNTING.json','SOURCE_RETURN_PLAN.md','FINAL_CAMPAIGN_READINESS.md','NEXT_RESEARCH_DECISION.md',
       'SCIENTIFIC_REVIEW.md','SCIENTIFIC_REVIEW_STATUS.json']
    missing=[name for name in required if not (ROOT/name).exists()]
    atomic(ROOT/'PACKAGE_VERIFICATION.json',dict(time_utc=now(),historical_protection=verification,
       runtime_447_unchanged=not runtime_bad,runtime_mismatches=runtime_bad,
       attempt_native_Adam_accounting_pass=accounting['pass_'],
       frozen_saved_physics_recomputed_pass=recheck_pass,
       frozen_saved_physics_rechecked=recheck_result.get('rechecked',0),
       frozen_saved_physics_expected=read(ROOT/'LEDGER.json')['evaluation_attempts'],
       frozen_saved_physics_evidence='audit/FINAL_FROZEN_PHYSICS_RECHECK.json',
       used_source_bundles_and_checkpoint_provenance_pass=source_identity['pass_'],
       github_fixed_commit_unchanged=identity['HEAD'].strip()=='1adb1de177d6f5f32de6d01c4e629cbfae9ce121',
       github_status=identity['status'],owned_workers_exited=all(not x['alive'] for x in owned),
       services_exited=all(not x['alive'] for x in services),required_missing=missing,
       scientific_review_status=read(ROOT/'SCIENTIFIC_REVIEW_STATUS.json',{}).get('status','MISSING'),
       scientific_review_sha256=sha(ROOT/'SCIENTIFIC_REVIEW.md') if (ROOT/'SCIENTIFIC_REVIEW.md').exists() else None,
       completion_requirements_status=read(ROOT/'COMPLETION_REQUIREMENTS.json',{}).get('overall_status','MISSING'),
       manifest_expected_files=len(files),manifest_complete=len(entries)==len(files),
       manifest_entries=len(entries),manifest_sha256=sha(ROOT/'OUTPUT_MANIFEST.json'),
       hard_stop_utc=STATE['hard_stop_utc'],finalizer_completed_before_deadline=time.time()<HARD_STOP,
       no_git_writes=True,no_formal_campaign=True))
    return result
if __name__=='__main__':
    closing_lock=(ROOT/'.finalize.lock').open('a')
    try:fcntl.flock(closing_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit(0)
    try:
        atomic(ROOT/'FINALIZER_IDENTITY.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),
               exclusive_closeout_lock=True))
        def deadline(signum,frame):raise TimeoutError('FINALIZER_HARD_DEADLINE')
        signal.signal(signal.SIGALRM,deadline)
        signal.setitimer(signal.ITIMER_REAL,max(.1,HARD_STOP-time.time()-5))
        x=finalize(sys.argv[1] if len(sys.argv)>1 else 'AGENT_FINALIZATION')
        signal.setitimer(signal.ITIMER_REAL,0)
    except BaseException as exc:
        atomic(ROOT/'FINALIZATION_FAILURE.json',dict(time_utc=now(),error=repr(exc),traceback=traceback.format_exc()))
        raise
