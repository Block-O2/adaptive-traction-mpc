"""Verify protection, actual budget, files, resources and owned process exit."""
from pathlib import Path
import json,os,sys,time,hashlib,shutil,subprocess,platform,importlib.metadata as metadata
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
FINAL=len(sys.argv)>1 and sys.argv[1]=='final'
READONLY_OUTPUT='--readonly-output' in sys.argv
def load(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
    return h.hexdigest()
def g(root,*args):return subprocess.check_output(['git','-C',str(root),*args],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
def git_current(root):
    return dict(root=str(root),branch=g(root,'branch','--show-current').decode(),HEAD=g(root,'rev-parse','HEAD').decode(),status=g(root,'status','--porcelain=v1').decode(),
                index_sha256=sha(root/'.git/index'),staged_diff_sha256=hashlib.sha256(g(root,'diff','--cached','--binary')).hexdigest(),
                unstaged_diff_sha256=hashlib.sha256(g(root,'diff','--binary')).hexdigest(),untracked_paths=g(root,'ls-files','--others','--exclude-standard','-z').decode().split('\0'))
def owned_processes():
    found=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid():continue
        try:
            cwd=Path(os.readlink(p/'cwd'));cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            package_cwd=cwd==S or S in cwd.parents
            known_launcher='launch_phase.py' in cmd and 'ihear_overnight_research_retrospective_v1' in cmd
            if package_cwd or known_launcher:found.append(dict(pid=int(p.name),cwd=str(cwd),cmdline=cmd))
        except (OSError,PermissionError):pass
    return found

def copied_source_checks(original,plan):
    old=Path(plan['original_sources']);physical=[];binaries=[];expected=set()
    for name,record in original.items():
        source=Path(name);rel=source.relative_to(old)
        if rel.parts[0] not in ('source','build','native','weights'):continue
        target=S/rel;expected.add(str(rel))
        same=False
        if target.is_file() and source.is_file():
            same=(source.read_text().replace(str(old),str(S))==target.read_text()) if rel.parts[0]=='source' and source.suffix=='.py' else sha(target)==record['sha256']
        (physical if rel.parts[0]=='source' else binaries).append(dict(path=str(rel),same=same))
    additions=[]
    for name in ('source','build','native','weights'):
        for p in (S/name).rglob('*'):
            if not p.is_file() or 'results' in p.parts or '__pycache__' in p.parts or p.suffix=='.pyc':continue
            if str(p.relative_to(S)) not in expected:additions.append(str(p.relative_to(S)))
    manifest=load(S/'CODE_MANIFEST.json');manifest_errors=[]
    for rel,expected_hash in manifest.items():
        p=S/rel
        if not p.is_file() or sha(p)!=expected_hash:manifest_errors.append(rel)
    return dict(source_checked=len(physical),source_changes=[r['path'] for r in physical if not r['same']],binary_checked=len(binaries),binary_changes=[r['path'] for r in binaries if not r['same']],unexpected_protected_files=additions,
                manifest_checked=len(manifest),manifest_changes=manifest_errors,scope='source allows only old-study absolute path relocation in Python; build/native/weights exact original bytes; manifest checks actual current files')

def gate_checks(final):
    names=['ZERO_EXTENSION_REPRODUCTION_GATE.json','PRIOR_REPRODUCTION_GATE.json','BEST_REPEAT_GATE.json','BEST_SELECTION_REPRODUCTION_GATE.json','INDEPENDENT_SELECTED_METRIC_CHECKS.json','ACTUATOR_CONTACT_EVIDENCE.json']
    rows={};errors=[];pending=[]
    selection=load(S/'FROZEN_SELECTION.json') if (S/'FROZEN_SELECTION.json').is_file() else None
    representative_ids=set([selection['best']['base_id'],selection['best']['id'],selection['diagnostic']['id']]) if selection else set()
    for name in names:
        p=S/name
        if not p.is_file():
            rows[name]=dict(status='PENDING_MISSING');pending.append(name)
            if final:errors.append('KEY_GATE_MISSING:'+name)
            continue
        value=load(p);status=value.get('status');rows[name]=dict(status=status,sha256=sha(p),branches=value.get('branches'),generated_unix=value.get('generated_unix'))
        if status!='PASS':errors.append('KEY_GATE_NOT_PASS:'+name)
        if final and name in ('INDEPENDENT_SELECTED_METRIC_CHECKS.json','ACTUATOR_CONTACT_EVIDENCE.json'):
            entries=value.get('checks' if name=='INDEPENDENT_SELECTED_METRIC_CHECKS.json' else 'rows',[])
            if not representative_ids or {r.get('id') for r in entries}!=representative_ids:errors.append('KEY_GATE_SELECTED_IDS_MISMATCH:'+name)
            if name=='INDEPENDENT_SELECTED_METRIC_CHECKS.json' and any(r.get('status')!='PASS' for r in entries):errors.append('SELECTED_METRIC_ROW_NOT_PASS')
            if name=='ACTUATOR_CONTACT_EVIDENCE.json' and (value.get('final') is not True or value.get('selection_scope')!='FROZEN'):errors.append('ACTUATOR_EVIDENCE_NOT_FINAL_FROZEN')
        if final and selection and name=='ZERO_EXTENSION_REPRODUCTION_GATE.json' and selection['best']['base_id'] not in value.get('branches',[]):errors.append('ZERO_GATE_CURRENT_BASE_NOT_BOUND')
        if final and selection and name=='BEST_SELECTION_REPRODUCTION_GATE.json' and selection['best']['id'] not in value.get('branches',[]):errors.append('REPEAT_GATE_CURRENT_BEST_NOT_BOUND')
    if final:
        p=S/'BASELINE_REPRODUCTION.json'
        baseline=load(p) if p.is_file() else {}
        baseline_ids=[r.get('id','') for r in baseline.get('runs',[])]
        rows['BASELINE_REPRODUCTION.json']=dict(status=baseline.get('status','MISSING'),run_ids=baseline_ids)
        if not selection or baseline.get('status')!='PASS' or selection['best']['base_id'] not in baseline_ids or not any(ident.endswith('_prior_best_18D') for ident in baseline_ids):errors.append('CURRENT_BASELINE_GATE_NOT_BOUND')
    return rows,errors,pending
def main():
    errors=[];plan=load(S/'RUN_PLAN.json');before=load(S/'preservation/GIT_BEFORE.json');gitrows=[]
    for old in before:
        current=git_current(Path(old['root']));same=current==old;gitrows.append(dict(root=old['root'],same=same,starting_branch=old['branch'],starting_HEAD=old['HEAD'],current=current))
        if not same:errors.append('INITIAL_GIT_STATE_CHANGED:'+old['root'])
    original=load(S/'preservation/REUSED_SOURCE_BEFORE.json');changed=[]
    for name,r in original.items():
        p=Path(name)
        if not p.is_file() or sha(p)!=r['sha256']:changed.append(name)
    if changed:errors.append('ORIGINAL_REUSED_SOURCE_CHANGED')
    copied=copied_source_checks(original,plan)
    if copied['source_changes'] or copied['binary_changes'] or copied['unexpected_protected_files']:errors.append('COPIED_PHYSICAL_ARTIFACT_CHANGED')
    if not copied['manifest_checked'] or copied['manifest_changes']:errors.append('CURRENT_CODE_MANIFEST_CHANGED')
    motion=S/'MOTION_ACCEPTANCE_PROTOCOL.json'
    motion_hash=sha(motion)
    if motion_hash!=plan['motion_protocol_sha256'] or motion_hash!=sha(Path(plan['original_sources'])/'MOTION_ACCEPTANCE_PROTOCOL.json'):errors.append('FROZEN_MOTION_PROTOCOL_CHANGED')
    late=load(S/'preservation/MAIN_CONTENT_LATE_BEFORE.json');late_changes=[]
    for rootrow in late['roots']:
        root=Path(rootrow['root'])
        for name,r in rootrow['files'].items():
            p=root/name
            same=(p.is_file() and not p.is_symlink() and sha(p)==r['sha256']) if r['kind']=='file' else (p.is_symlink() and os.readlink(p)==r['target']) if r['kind']=='symlink' else not p.exists()
            if not same:late_changes.append(str(p))
    if late_changes:errors.append('LATE_CAPTURE_MAIN_CONTENT_CHANGED')
    history=load(S/'preservation/HISTORICAL_REPORTS_LATE_BEFORE.json');history_changes=[name for name,h in history['hashes'].items() if not Path(name).is_file() or sha(Path(name))!=h]
    if history_changes:errors.append('HISTORICAL_REPORT_CHANGED')
    events=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END']
    unique=len({r['id'] for r in starts})==len(starts)
    terminal={r['id']:sum(e['id']==r['id'] for e in ends) for r in starts};open_ids=[ident for ident,n in terminal.items() if n==0]
    unmatched_ends=[r['id'] for r in ends if r['id'] not in terminal]
    if not unique or any(n>1 for n in terminal.values()) or unmatched_ends or len(starts)>plan['physics_budget']:errors.append('ATTEMPT_ACCOUNTING')
    late_starts=[r['id'] for r in starts if r['unix']>=plan['dispatch_cutoff_unix']]
    late_physical_ends=[r['id'] for r in ends if r['unix']>plan['physics_hard_stop_unix']]
    late_dev=[r['id'] for r in starts if r.get('mode','').startswith('development') and r['unix']>=plan['search_cutoff_unix']]
    reserve_breaches=[r['id'] for index,r in enumerate(starts) if r.get('mode','').startswith('development') and index>=plan['search_cap']]
    if late_starts or late_physical_ends or late_dev or reserve_breaches:errors.append('PHYSICS_TIME_OR_RESERVE_CONTRACT')
    end_before_start=[r['id'] for r in starts if any(e['id']==r['id'] and e['unix']<r['unix'] for e in ends)]
    if end_before_start:errors.append('END_BEFORE_START')
    gates,gate_errors,pending_gates=gate_checks(FINAL);errors.extend(gate_errors)
    now=time.time();disk=shutil.disk_usage('/mnt/d');size=sum(p.stat().st_size for p in S.rglob('*') if p.is_file())
    resources=[json.loads(x) for x in (S/'RESOURCE_SAMPLES.jsonl').read_text().splitlines()]
    if size>=8*2**30 or disk.free<40*2**30:errors.append('RESOURCE_CONTRACT')
    procs=owned_processes()
    names=['REPORT.md','DETAILED_RESEARCH_HISTORY.md','ARCHITECTURE_EVOLUTION.md','RESEARCH_TIMELINE.md','MILESTONES_AND_EVIDENCE.md','CURRENT_SYSTEM_EXPLAINED.md','OPEN_PROBLEMS_AND_DECISIONS.md','PROFESSOR_BRIEF.md','EXPLORATION_RESULTS.json','EVIDENCE_LEDGER.json','CURRENT_MODEL_AND_TASK.json']
    files={name:dict(exists=(S/name).is_file(),bytes=(S/name).stat().st_size if (S/name).is_file() else None,sha256=sha(S/name) if (S/name).is_file() else None) for name in names}
    figures=list((S/'FIGURES').glob('*.png'))
    if not all(r['exists'] for r in files.values()) or not 6<=len(figures)<=8:errors.append('REQUIRED_FILES')
    if FINAL:
        if open_ids or procs:errors.append('OWNED_WORK_NOT_EXITED')
        if now>=plan['hard_stop_unix']:errors.append('DELIVERY_DEADLINE_MISSED')
    versions={}
    for name in ['numpy','scipy','mujoco','matplotlib','cffi']:
        try:versions[name]=metadata.version(name)
        except metadata.PackageNotFoundError:versions[name]='NOT_AVAILABLE'
    output=dict(status='PASS' if FINAL and not errors else 'IN_PROGRESS' if not FINAL and not errors else 'FAIL',final=FINAL,generated_unix=now,errors=errors,
                absolute_deadline=plan['hard_stop_unix'],remaining_to_deadline_s=plan['hard_stop_unix']-now,t0_unix=plan['t0_unix'],t0_monotonic=plan['t0_monotonic'],
                source_protection=dict(initial_git_snapshots=gitrows,original_reused_file_count=len(original),original_changes=changed,
                                       late_main_capture_scope=late['scope'],late_capture_start=late['capture_start_unix'],late_main_content_changes=late_changes,
                                       historical_report_count=len(history['hashes']),historical_report_changes=history_changes,
                                       copied_physical_artifacts=copied,frozen_motion_protocol_sha256=motion_hash,
                                       scope_note='No claim of t0 hash for all main bytes; t0 Git state and reused side source are distinct from late tracked/untracked content capture.'),
                attempts=dict(started=len(starts),ended=len(ends),cap=plan['physics_budget'],reserve_before_search=plan['validation_reserved'],unique_START=unique,open_ids=open_ids,unmatched_END_ids=unmatched_ends,nonzero_returncodes=[r for r in ends if r.get('returncode',0)!=0],
                              last_physical_START_unix=max((r['unix'] for r in starts),default=None),last_physical_END_unix=max((r['unix'] for r in ends),default=None),late_START_ids=late_starts,late_END_ids=late_physical_ends,late_development_ids=late_dev,reserve_breach_ids=reserve_breaches,end_before_start_ids=end_before_start),
                key_gates=gates,pending_key_gates=pending_gates,
                resources=dict(study_bytes=size,study_GiB=size/2**30,target_GiB=5,target_met=size<=5*2**30,hard_GiB=8,D_free_bytes=disk.free,D_free_GiB=disk.free/2**30,
                               minimum_observed_available_memory_bytes=min((r['available_memory_bytes'] for r in resources),default=None),minimum_observed_D_free_bytes=min((r['D_free_bytes'] for r in resources),default=None)),
                owned_processes=procs,all_owned_physics_exited=not procs and not open_ids,files=files,figure_count=len(figures),
                environment=dict(python=sys.executable,python_version=sys.version,platform=platform.platform(),package_versions=versions,WSL='Ubuntu-Research-Verify',user='hank'),
                no_Git_mutation=True,no_system_configuration_change=True,no_old_data_deletion=True,no_training=True,no_online_adaptation=True,no_final_PPT_or_PDF=True,no_professor_submission=True,
                scientific_scope='LEVEL1 simulation research; no new formal native-B/host/hardware/clinical qualification',
                verification_not_scientific_success=True)
    target=W/'audit/PACKAGE_HARDENING_PRECHECK.json' if READONLY_OUTPUT else S/'PACKAGE_VERIFICATION.json'
    target.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(dict(status=output['status'],errors=errors,attempts=len(starts),study_GiB=size/2**30,owned_processes=len(procs)),ensure_ascii=False),flush=True)
    if FINAL:assert not errors,errors
if __name__=='__main__':main()
