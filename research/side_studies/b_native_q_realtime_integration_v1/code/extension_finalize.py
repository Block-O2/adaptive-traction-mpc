"""Close and export a supplement without altering accepted first delivery."""
from extension_common import *
import os,re

def preservation():
    before=json.loads((EXT/'BEFORE.json').read_text());issues=[]
    for name,digest in before['accepted_files'].items():
        p=Path(name)
        if not p.is_file() or sha(p)!=digest:issues.append('FIRST_DELIVERY_CHANGED:'+name)
    if {str(p) for p in FIRST_DELIVERY.rglob('*') if p.is_file()}!=set(before['accepted_files']):issues.append('FIRST_DELIVERY_FILE_SET_CHANGED')
    source=json.loads((STUDY/'SOURCE.json').read_text())
    for label,key in [('OLD_PROTECTED','originals'),('FROZEN_CONTROL','frozen_files')]:
        for name,digest in source[key].items():
            p=Path(name)
            if not p.is_file() or sha(p)!=digest:issues.append(label+':'+name)
    git=lambda *args:subprocess.check_output(['git','-C',str(ROOT),*args],text=True)
    gb=json.loads((STUDY/'GIT_BEFORE.json').read_text());ga=dict(branch=git('branch','--show-current'),head=git('rev-parse','HEAD'),status=git('status','--short'),index_sha256=sha(ROOT/'.git/index'),cached_diff_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(ROOT),'diff','--cached','--binary'])).hexdigest())
    if ga!=gb:issues.append('WSL_PRIMARY_GIT_METADATA_CHANGED')
    if sha(STUDY/'weights/frozen_Q_v1/weights.npz')!=before['Q_sha256']:issues.append('Q_CHANGED')
    if sha(STUDY/'reports/CLOSEOUT_STATUS.json')!=before['original_closeout_sha256']:issues.append('ORIGINAL_CLOSEOUT_CHANGED')
    out=dict(status='PASS' if not issues else 'FAIL',issues=issues,first_delivery_files_checked=len(before['accepted_files']),old_protected_files_checked=len(source['originals']),frozen_control_sources_checked=len(source['frozen_files']),Q_unchanged=True,WSL_primary_git_snapshot_equal=ga==gb,original_closeout_unchanged=True,unix=time.time(),limit='WSL primary Git branch/HEAD/status/index/staged diff and protected copied source hashes only; no complete original unstaged byte attestation or Windows Git snapshot.')
    save(EXT/'PRESERVATION_AUDIT.json',out);assert not issues,issues

def retain_sources():
    references=[]
    for r in [json.loads(x) for x in (EXT/'TASK_LEDGER.jsonl').read_text().splitlines()]:
        if r['event']=='START':references.append(dict(path=r['script'],sha256=r['source_sha256'],role=r['id']))
    cfg=json.loads((EXT/'SINGLE_CAPTURE_CONFIG.json').read_text())
    references.extend(dict(path=p,sha256=h,role='ACTUAL_PHYSICS_CONFIG_DECLARED') for p,h in cfg['algorithm_sources'].items())
    for p in EXT.glob('*_IMPORTED_SOURCES.json'):
        references.extend(dict(row,role=p.name) for row in json.loads(p.read_text()))
    for name in ('extension_finalize.py','extension_figures.py','extension_resource_watch.py','extension_common.py','extension_build_report.py','extension_export.py','extension_validate.py'):
        p=STUDY/'code'/name;references.append(dict(path=str(p),sha256=sha(p),role='FINAL_REPORT_HELPER'))
    unique={};missing=[]
    for r in references:
        key=(r['path'],r['sha256'])
        if key in unique:continue
        p=Path(r['path']);candidates=[p]
        if p.parent==STUDY/'code':candidates+=list((STUDY/'code_history').glob('*/code/'+p.name))
        match=next((q for q in candidates if q.is_file() and sha(q)==r['sha256']),None)
        if match is None:missing.append(r);continue
        target=EXT/'retained_code'/r['sha256']/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(match,target);unique[key]=dict(r,retained_path=str(target))
    save(EXT/'SOURCE_RETENTION.json',dict(status='PASS' if not missing else 'FAIL',rows=list(unique.values()),missing=missing,unique_variants=len(unique),references=len(references),interpretation='Script-at-launch hashes, declared actual physics sources and imported file hashes at job completion are retained. This is not per-module import-time attestation.'))
    assert not missing

def process_closeout():
    candidates={}
    for line in (EXT/'RESOURCE_LOG.jsonl').read_text().splitlines():
        for r in json.loads(line)['processes']:candidates[(r['pid'],r['cmd'])]=r
    live=[]
    for (pid,cmd),r in candidates.items():
        if pid==os.getpid():continue
        p=Path('/proc')/str(pid)
        try:
            actual=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace');state=(p/'stat').read_text().split(') ',1)[1].split()[0]
            if state!='Z' and actual==cmd:live.append(dict(pid=pid,cmd=cmd))
        except OSError:pass
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid():continue
        try:
            cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            if str(STUDY/'code/extension_') in cmd and ('extension_job_monitor.py' in cmd or 'extension_resource_watch.py' in cmd or 'extension_timer_service.py' in cmd or 'extension_capture_worker.py' in cmd or 'extension_single_capture.py' in cmd):live.append(dict(pid=int(p.name),cmd=cmd))
        except OSError:pass
    save(EXT/'PROCESS_CLOSEOUT.json',dict(status='RECORDED_EXTENSION_IDENTITIES_ABSENT' if not live else 'FAIL',recorded_pid_command_identities=len(candidates),unexpected_live=live,unix=time.time(),limit='Recorded PID+command identities and study-specific dispatch/worker command scan; historical samples lack kernel birth IDs, so this is bounded evidence. All job-owned children were explicitly joined; no unknown process was killed.'))
    assert not live,live

def resource_summary():
    rows=[json.loads(x) for x in (EXT/'RESOURCE_LOG.jsonl').read_text().splitlines()];rows.sort(key=lambda x:x['unix']);gaps=[b['unix']-a['unix'] for a,b in zip(rows,rows[1:])];windows=[r['windows'] for r in rows if 'error' not in r['windows']]
    out=dict(samples=len(rows),first_unix=rows[0]['unix'],last_unix=rows[-1]['unix'],max_gap_s=max(gaps,default=0),WSL_mem_available_min=min(r['mem_available'] for r in rows),owned_PSS_max=max(r['PSS'] for r in rows),owned_count_max=max(r['owned_count'] for r in rows),swap_used_min=min(r['swap_used'] for r in rows),swap_used_max=max(r['swap_used'] for r in rows),swap_in_delta=rows[-1]['swap_in']-rows[0]['swap_in'],swap_out_delta=rows[-1]['swap_out']-rows[0]['swap_out'],oom_delta=rows[-1]['oom_kill']-rows[0]['oom_kill'],Windows_commit_headroom_min=min(r['commit_headroom'] for r in windows),Windows_available_min=min(r['available'] for r in windows),disk_C_min=min(r['disk_c'] for r in windows),scope='Job monitor samples own verified descendants; report watcher samples itself during idle authoring. Gaps between initial separately monitored jobs/authoring are retained. The 12.5s physical diagnostic completed before its next 45s sample, so its peak memory is unobserved. No gap interpolation, settings changes, cache drops or unknown kills.')
    save(EXT/'RESOURCE_SUMMARY.json',out)

def close():
    guard();assert (EXT/'RESOURCE_WATCH_STOP.json').exists()
    process_closeout();preservation();retain_sources();resource_summary()
    from accounting import rows
    events=rows();starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];assert len(starts)==len(ends)==160 and {r['id'] for r in starts}=={r['id'] for r in ends}
    jobs=[json.loads(x) for x in (EXT/'TASK_LEDGER.jsonl').read_text().splitlines()];js={r['id'] for r in jobs if r['event']=='START'};je={r['id'] for r in jobs if r['event']=='END'};assert js==je and all(r['child_joined'] and r['returncode']==0 for r in jobs if r['event']=='END')
    raw=json.loads((EXT/'BACKLOG_AND_RAW_AUDIT.json').read_text());out=dict(status='STOPPED_AND_RECONCILED',unix=time.time(),deadline_unix=DEADLINE,elapsed_package_h=(time.time()-START)/3600,extension_elapsed_minutes=(time.time()-json.loads((EXT/'BEFORE.json').read_text())['start_unix'])/60,attempts=160,ended=160,active_physics=[],new_physics_attempts=1,remaining_physics_attempts=0,new_public_B_repairs=0,public_B_repairs_total=2,new_optimization_promoted=False,actual_host_qualification='NOT_QUALIFIED',actual_nonzero_learning_execution=0,adaptation='NOT_RUN',Q_updates=0,authoritative_native_steps=raw['authoritative_total_native_steps'],jobs_started=len(js),jobs_ended=len(je),auto_resume=False,resource_watcher_join_required=True,first_delivery_preserved=True,stop_reason='Original 160-attempt hard cap reached; finite authorized offline follow-up and reporting complete before extended time ceiling. No minimum wait to noon was requested.')
    save(EXT/'CLOSEOUT_STATUS.json',out);plan=json.loads((EXT/'RUN_PLAN.json').read_text());plan.update(status='CLOSED',phase='CLOSED',closed_unix=out['unix'],auto_resume=False,physics_dispatch_disabled=True);save(EXT/'RUN_PLAN.json',plan)
    (EXT/'RESUME.md').write_text('CLOSED / STOP\nCumulative physical attempts 160/160; two public-B repairs used. No automatic resume and no pending dispatch. Original STOP_DISPATCH remains. First accepted delivery is immutable; this extension is the authoritative supplement for attempt 160 and the updated time ceiling. Any future physical work requires a new explicit attempt budget and scope. No Q updates or adaptation occurred.\n')
    main_plan=json.loads((STUDY/'RUN_PLAN.json').read_text());main_plan.update(phase='CLOSED',status='STOPPED_AND_RECONCILED',deadline_unix=DEADLINE,dispatch_cutoff_unix=DEADLINE-2700,dispatch_disabled=True,auto_resume=False,latest_supplement=str(EXT/'CLOSEOUT_STATUS.json'),cumulative_attempts=160);save(STUDY/'RUN_PLAN.json',main_plan)
    checkpoint=json.loads((STUDY/'CHECKPOINT.json').read_text());checkpoint.update(status='STOPPED_AND_RECONCILED',auto_resume=False,dispatch_disabled=True,active=[],attempts=160,ended=160,elapsed_h=out['elapsed_package_h'],hard_deadline_unix=DEADLINE,dispatch_cutoff_unix=DEADLINE-2700,remaining_physics_attempts=0,latest_supplement=str(EXT/'CLOSEOUT_STATUS.json'))
    new=raw['new_diagnostic'];result=json.loads((STUDY/'output'/(new['id']+'_RESULT.json')).read_text());rr=new['raw_provenance']
    checkpoint['results'].append(dict(id=new['id'],status=result['status'],valid=False,J_F=None,error=result['error'],scientific_version=result['inputs']['scientific_version'],timing_version=result['inputs']['timing_version'],execution_mode=result['inputs']['execution_mode'],wall_seconds=result['wall_seconds'],physics_seconds=rr['native_step_count']*.00025,physics_steps=rr['native_step_count'],raw_verified=True,attempt_count=1,classification=new['classification'],input_hash=sha(EXT/'SINGLE_CAPTURE_CONFIG.json'),result_sha256=sha(STUDY/'output'/(new['id']+'_RESULT.json'))))
    save(STUDY/'CHECKPOINT.json',checkpoint)
    ledger=json.loads((STUDY/'TASK_LEDGER.json').read_text());ledger[new['id']]=dict(status='COMPLETE',worker_status='FAILED',returncode=0,config=result['inputs'],input_sha256=sha(EXT/'SINGLE_CAPTURE_CONFIG.json'),result_sha256=new['result_sha256'],explicit_extension_owner=True);save(STUDY/'TASK_LEDGER.json',ledger)
    shutil.copy2(EXT/'RESUME.md',STUDY/'RESUME.md');(STUDY/'PROGRESS.md').write_text('CLOSED: original package plus user-authorized noon extension.\n160/160 physical attempts ended; no active dispatch; no auto resume.\nActual host qualification NOT_QUALIFIED; Q updates=0; adaptation NOT_RUN.\nLatest evidence/report: extension_to_noon/. First accepted delivery remains immutable.\n')
    print(json.dumps(out))

def main():
    if sys.argv[1]=='close':close()
    elif sys.argv[1]=='stop_watch':(EXT/'STOP_EXTENSION_RESOURCE').write_text('Report closeout; no dispatch; stop resource-only watcher.\n')
    elif sys.argv[1]=='figure_qa':
        f=json.loads((EXT/'FIGURE_MANIFEST.json').read_text());expected='4133c0d1002d237aad689e47b085b31eef3536e9e28b064a33d91b5c7e6c1f40';assert len(f['figures'])==1 and f['figures'][0]['sha256']==expected and sha(Path(f['figures'][0]['path']))==expected
        f.update(status='VISUALLY_VERIFIED',reviewed_unix=time.time(),approved_sha256=expected);save(EXT/'FIGURE_MANIFEST.json',f)
    else:raise ValueError('Use close; delivery helpers are separate.')

if __name__=='__main__':main()
