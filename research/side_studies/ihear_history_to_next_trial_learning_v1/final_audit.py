"""Offline evidence audit and protected-history closeout. Never dispatches physics."""
from pathlib import Path
import json,time,hashlib,sys,os,collections,subprocess
import numpy as np
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):
    h=hashlib.sha256()
    with Path(f).open('rb') as s:
        for b in iter(lambda:s.read(4*2**20),b''):h.update(b)
    return h.hexdigest()
def protected():
    from bootstrap import git_snapshot
    old=read('audit/HISTORY_BEFORE.json');errors=[];after={};started=time.time()
    roots=[Path('/home/hank/coding/adaptive-traction-mpc-learning'),P.parent]
    current={str(f) for root in roots for f in root.rglob('*') if f.is_file() and not f.is_relative_to(P) and '.git' not in f.parts}
    additions=sorted(current-set(old));errors.extend(dict(path=f,reason='NEW_FILE_IN_PROTECTED_TREE') for f in additions)
    for i,(name,before) in enumerate(old.items()):
        f=Path(name)
        if not f.is_file():errors.append(dict(path=name,reason='MISSING'));continue
        st=f.stat();now=dict(size=st.st_size,mtime_ns=st.st_mtime_ns,sha256=sha(f));after[name]=now
        if now!=before:errors.append(dict(path=name,before=before,after=now))
        if i%20000==0:print('PROTECTED_HASH',i,len(old),flush=True)
    beforegit=read('audit/GIT_BEFORE.json');git=git_snapshot();put('audit/GIT_AFTER.json',git)
    put('audit/HISTORY_AFTER.json',after)
    out=dict(status='PASS' if not errors and git==beforegit else 'FAIL',files=len(old),bytes=sum(v['size'] for v in old.values()),
        differences=errors,git_identical=git==beforegit,git_fields_identical={k:v==git.get(k) for k,v in beforegit.items()},
        started_unix=started,finished_unix=time.time(),all_sha256_recomputed=True)
    put('audit/PROTECTED_CLOSEOUT.json',out);assert out['status']=='PASS';print('PROTECTED_CLOSEOUT_PASS',flush=True)
def evidence():
    interim='--interim' in sys.argv
    import history_features as hf
    from learning_models import select
    acc=read('ATTEMPT_ACCOUNTING.json');results=read('LEARNING_RESULTS.json');cont=read('CONTINUOUS_REPETITION_RESULTS.json')
    closed_ids={a['id'] for a in acc['attempts']}
    assert acc['starts']==acc['ends']<=80 and not acc['open_starts'] and not acc['unmatched_ends']
    assert not acc['independent_recompute_failures']
    assert acc['total_recomputed_complete_tasks']==acc['complete_task_results']
    native_complete=0;native_other=0
    for a in acc['attempts']:
        if a['complete_task']:
            independent=read('derived/'+a['id']+'_INDEPENDENT.json')
            assert independent['native_rows']==a['actual_new_native_steps'],(a['id'],'NATIVE_BUDGET_MISMATCH')
            native_complete+=independent['native_rows']
        else:native_other+=a['actual_new_native_steps'] or 0
    assert native_complete+native_other==acc['total_new_native_steps']
    source_hash_checks=0
    for f in (P/'reports').glob('*_MEASURED.json'):
        if interim and f.name[:-len('_MEASURED.json')] not in closed_ids:continue
        for name,h in json.loads(f.read_text())['sources'].items():
            assert sha(name)==h,'RAW_CHANGED_AFTER_RECOMPUTATION:'+name;source_hash_checks+=1
    events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts={e['id']:e for e in events if e['event']=='START'}
    if interim:starts={k:v for k,v in starts.items() if k in closed_ids}
    revisions=[]
    manifests=[P/'EXECUTION_CODE_MANIFEST.json',*(P/'versions').glob('*/EXECUTION_CODE_MANIFEST.json')]
    for identity in sorted({e['controller_version'] for e in starts.values()}):
        manifest=next(f for f in manifests if sha(f)==identity);count=0
        for rel,h in json.loads(manifest.read_text())['files'].items():
            source=manifest.parent/rel
            if not source.exists():source=P/rel
            assert sha(source)==h,'EXECUTED_SOURCE_CHANGED:'+str(source);count+=1
        revisions.append(dict(manifest=str(manifest.relative_to(P)),sha256=identity,files=count,status='PASS'))
    assert all(e['unix']<read('RUN_PLAN.json')['dispatch_cutoff_unix'] for e in starts.values())
    histories=[];decisions=[];ownership=[];boundaries=[];termination=[]
    allowed={'phase','physical_s','phase_elapsed_s','estimated_q_dq','reference_q_dq','reference_ddq','reference_progress','force_world_N','moment_world_Nm',
        'source_sample_time_s','source_age_s','proposed_slot','truth_used','terminal_boundary'}
    for f in sorted((P/'learning').glob('*_RAW_HISTORY.json')):
        if interim and f.name[:-len('_RAW_HISTORY.json')] not in closed_ids:continue
        raw=json.loads(f.read_text());ident=raw['metadata']['trial_id']
        assert all(set(r)<=allowed and r['truth_used'] is False and r['source_age_s']>=-1e-8 for r in raw['rows'])
        if not raw['metadata']['complete_task_observed']:
            histories.append(dict(id=ident,status='PARTIAL_PRESERVED_NOT_TRAINING_SAMPLE',samples=len(raw['rows'])));continue
        compact=read('learning/'+ident+'_HISTORY.json')
        recomputed=hf.summarize(raw['rows'],raw['metadata']);assert recomputed==compact
        assert not compact['truth_used'] and not compact['policy_can_use_native_derivatives']
        with np.load(P/'source/results'/ident/'trace.npz') as z:
            m=z['stage']=='TASK';t=z['time_s'][m];rt=np.array([r['physical_s'] for r in raw['rows']]);assert len(t)==len(rt) and np.max(abs(t-rt))<1e-8
            for key,tracekey in [('estimated_q_dq','estimated_human_state_rad_rad_s'),('force_world_N','physical_cuff_force_world_n'),('moment_world_Nm','physical_cuff_moment_world_nm')]:
                assert np.max(abs(np.asarray([r[key] for r in raw['rows']])-z[tracekey][m]))<1e-8,(ident,key)
        histories.append(dict(id=ident,status='PASS',samples=compact['sample_count'],history_sha256=compact['raw_history_sha256'],full_feature_recomputed=True,causal_fields_match_saved_trace=True))
    freeze=read('models/METHOD_FREEZE.json')
    for name,h in freeze['model_files'].items():assert sha(P/name)==h
    for g in results['groups']:
        if g['status']!='EXECUTED':continue
        group='P00R' if g['patient_id']=='P00' else g['patient_id'];h=read('learning/'+group+'_T1_HISTORY.json')
        frozen=read('learning/'+group+'_T2_DECISIONS_FROZEN.json')
        ds=frozen['decisions'] if isinstance(frozen,dict) else frozen
        first_start=min(e['unix'] for e in starts.values() if e.get('run_group')==group and e.get('trial_number')==2)
        if g['split']!='development':assert freeze['frozen_unix']<starts[group+'_T1']['unix']
        for d in ds:
            assert d['frozen_unix']<first_start and d['future_trial_outcomes_consumed'] is False
            method=d['method'];replay=None
            if method=='ILC':replay=hf.ilc(h)
            elif method=='ILC_DISABLED':replay=hf.ilc(read('models/POPULATION_HISTORY.json'))
            elif method in ['BO','VALUE','BO_DISABLED','VALUE_DISABLED']:
                enabled=not method.endswith('_DISABLED');replay=select(P,method.split('_')[0],h if enabled else None,enabled)
            if replay:assert replay['action']==d['action'],(group,method,'DECISION_NOT_REPRODUCIBLE')
            decisions.append(dict(group=group,method=method,status='PASS',frozen_before_all_T2=True,recomputed=replay is not None,
                current_history_withheld=method.endswith('_DISABLED'),action_hash=d['action']['action_hash']))
        gr=read(group+'_RESULTS.json');assert all(c['unchanged'] and c['before']==c['after'] for c in gr['parent_checks'])
        if (P/(group+'_T3_RESULTS.json')).exists():
            tr=read(group+'_T3_RESULTS.json');d3=read('learning/'+group+'_T3_DECISIONS_FROZEN.json')
            prior=next(r['decision']['action'] for r in gr['rows'] if r['method']=='ILC')
            actual=next(d['action'] for d in d3['decisions'] if d['method']=='ILC')
            assert hf.ilc(read('learning/'+group+'_T2_ILC_HISTORY.json'),previous=prior)['action']==actual
            assert all(d3['frozen_unix']<e['unix'] for e in starts.values() if e.get('run_group')==group and e.get('trial_number')==3)
    for c in cont['continuity']:
        assert c['plant_unchanged'] and c['updater_unchanged'] and not c['human_state_written']
        assert c['fork']['before']==c['fork']['restored']
        assert c['after']['physical_time_s']>c['before']['physical_time_s']
    for ident,s in starts.items():
        if 'BOUNDARY' in s.get('kind',''):
            b=read('output/'+ident+'_NATIVE.json');rows=b['rows'];r=b['held_command_receipt']
            assert rows and b['before']['plant_identity']==b['after']['plant_identity']
            assert all(x['control']==rows[0]['control'] and x['inherited_receipt_index']==r['receipt_index'] for x in rows)
            assert all(abs(a['end_s']-b['start_s'])<1e-9 for a,b in zip(rows,rows[1:]))
            assert abs(rows[0]['start_s']-b['before']['physical_time_s'])<1e-8 and abs(rows[-1]['end_s']-b['after']['physical_time_s'])<1e-8
            boundaries.append(dict(id=ident,status='PASS',steps=len(rows),duration_s=rows[-1]['end_s']-rows[0]['start_s'],inherited_command_receipt=r['receipt_index']))
        if ident.endswith('_H150') and (P/'source/results'/ident/'summary.json').exists():
            su=read('source/results/'+ident+'/summary.json')
            if su.get('status')!='COMPLETE':
                ownership.append(dict(id=ident,status='PARTIAL_NO_FULL_H150_EXECUTION_CLAIM',reason=su.get('abort_reason')));continue
            line=read('reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json');owners={r['decision_index']:r for r in line['rows']};pieces=[]
            for r in su.get('learning_records',[]):
                for k,v in r.get('selected_plan',{}).get('execution_screen',{}).items():
                    if k in ['terminal_duration_intervention','second_round_posture','early_return_duration','terminal_hip_timing']:
                        n=owners.get(r['decision_index'],{}).get('actual_native_steps',0)
                        assert v['status']=='ACCEPTED' and r['selected_plan_activated'] and n>0
                        pieces.append(dict(kind=k,decision=r['decision_index'],native_steps=n))
            ownership.append(dict(id=ident,status='PASS',pieces=pieces))
        if (P/'motion_series'/(ident+'.npz')).exists():
            with np.load(P/'motion_series'/(ident+'.npz')) as z:
                q=np.rad2deg(z['true_q_rad']);ret=z['phase']=='RETURN'
                extra=read('reports/'+ident+'_EVALUATION.json')['motion_extra']
                with np.load(P/'source/results'/ident/'trace.npz') as trace:
                    issued=np.rad2deg(trace['reference_q_rad'][trace['stage']=='TASK'][-1])
                minimum=np.min(q[ret],axis=0);undershoot=np.maximum(issued-minimum,0.)
                assert np.max(abs(issued-np.asarray(extra['final_issued_return_reference_deg'])))<1e-8
                assert np.max(abs(undershoot-np.asarray(extra['return_undershoot_deg'])))<1e-8
                assert np.max(abs(q[-1]-issued-np.asarray(extra['return_terminal_error_from_issued_reference_deg'])))<1e-8
                termination.append(dict(id=ident,status='PASS',return_min_deg=minimum.tolist(),return_max_deg=np.max(q[ret],axis=0).tolist(),terminal_deg=q[-1].tolist(),
                    final_issued_reference_deg=issued.tolist(),return_undershoot_deg=undershoot.tolist(),terminal_error_deg=(q[-1]-issued).tolist()))
    training=read('models/TRAINING_DATA.json');assert {r['patient'] for r in training['rows']}=={'P00','P05','P08'}
    assert all(r['patient'] in freeze['training_patients'] for r in training['execution_labels'])
    label_checks=[]
    for row in training['rows']:
        group='P00R' if row['patient']=='P00' else row['patient'];actual=next(r for r in read(group+'_RESULTS.json')['rows'] if r['id']==row['id'])
        h=read('learning/'+group+'_T1_HISTORY.json');ind=read('derived/'+row['id']+'_INDEPENDENT.json')
        assert abs(row['JF']-ind['J_F_N_s'])<1e-8 and abs(row['first_JF']-h['JF_N_s'])<1e-8
        assert abs(row['y_cost']-(row['JF']-row['first_JF']))<1e-8
        assert row['a']==hf.encode_action(actual['decision']['action']).tolist()
        assert row['h']==[h['features'][i] for i in [2,3,4,5]] and row['qualified']==actual['complete_qualified']
        assert row['execution_success']==float(actual['absolute_task_execution_qualified'])
        label_checks.append(dict(id=row['id'],status='PASS',labels_joined_to_complete_physics=True))
    owners=[json.loads(f.read_text()) for f in (P/'audit').glob('*_OWNER_EXIT.json')]
    assert all(r['joined'] for r in owners)
    if not interim:
        assert len(owners)==8 # failed P00 + retry + six additional patients
        assert read('OWNED_ACTIVE_PROCESS.json')['active'] is False
    active=[]
    for f in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            cmd=f.read_bytes().replace(b'\0',b' ').decode(errors='replace')
            if str(P)+'/continuous_runner.py' in cmd or str(P)+'/owned_run.py' in cmd:active.append(dict(pid=int(f.parent.name),command=cmd))
        except (FileNotFoundError,PermissionError):pass
    if not interim:assert not active,active
    out=dict(status='INTERIM_CLOSED_SUBSET_PASS' if interim else 'PASS',unix=time.time(),starts_closed=True,independent_full_raw_recompute_count=acc['total_recomputed_complete_tasks'],
        histories=histories,decisions=decisions,continuity_records=len(cont['continuity']),boundary_checks=boundaries,H150_positive_ownership=ownership,
        split_isolation=True,split_isolation_scope='Formal development / validation / heldout patient groups',
        internal_development_validation_caveat='LOO fits share the development-only scaler; not strictly independent calibration',
        executed_source_revisions=revisions,training_label_checks=label_checks,measured_raw_source_hashes_reverified=source_hash_checks,
        native_step_budget_reconciled=True,complete_native_rows=native_complete,other_native_steps=native_other,
        model_hashes_unchanged=True,future_outcomes_consumed=False,owned_processes_active=active,
        scope='Separate arithmetic/source replay audit by the same research agent; not independent human peer review')
    put('audit/INTERIM_EVIDENCE_AUDIT.json' if interim else 'audit/FINAL_EVIDENCE_AUDIT.json',out)
    put('derived/INTERIM_TERMINAL_RECHECK.json' if interim else 'derived/TERMINAL_RECHECK.json',dict(rows=termination,evaluation_only=True))
    print(out['status'],len(histories),len(decisions),flush=True)
if __name__=='__main__':
    if '--protected' in sys.argv:protected()
    else:evidence()
