"""Final assertions independent of policy execution; no physics imports."""
from pathlib import Path
import sys,json,hashlib,time,ast,collections
import numpy as np
from repetition_paths import rep_path,RepeatRoot
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
def sha(f):
    h=hashlib.sha256()
    with f.open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):h.update(block)
    return h.hexdigest()
checks={};closures=[]
for f in sorted(P.glob('EXECUTION_CODE_MANIFEST*.json')):
    ob=json.loads(f.read_text());bad=[]
    for name,h in ob['files'].items():
        expected=h if isinstance(h,str) else h['sha256'];path=Path(name);path=path if path.is_absolute() else P/path
        if not path.is_file() or sha(path)!=expected:bad.append(name)
    closures.append(dict(file=f.name,sha256=sha(f),files=len(ob['files']),mismatches=bad));assert not bad,f.name
checks['frozen_execution_closures']=closures
f=read('models/VALUE_FREEZE.json');assert sha(P/f['model_file'])==f['model_sha256'];assert sha(P/'derived/DATASET_development.npz')==f['dataset_sha256']
for path,h in read('models/TRAINING_CODE_MANIFEST.json')['files'].items():assert sha(Path(path))==h
events=[json.loads(s) for s in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END']
assert len(starts)<=100 and collections.Counter(r['id'] for r in starts)==collections.Counter(r['id'] for r in ends)
assert all(e.get('joined') for e in ends)
assert f['frozen_unix']<min(s['unix'] for s in starts if s['id'].startswith('U'))
checks['test_after_model_freeze']=True
ds=read('derived/DATASET_all.json');groups=ds['groups'];plans=[read(g+'_PLAN.json')['condition'] for g in groups]
prefixes=[json.dumps(c['prefix'],sort_keys=True) for c in plans];assert len(set(prefixes))==len(prefixes)
train=set(f['training_parents']);val=set(f['validation_parents']);test={c['name'] for c in plans if c['split']=='test'}
assert not(train&val or train&test or val&test)
assert train|val|test==set(groups)
registration=read('SPLIT_REGISTRATION.json')
registered={r['name']:r for r in registration['conditions']}
for g in sorted(test):
    original=read(g+'_PLAN.json');executed=read(g+'_TEST_PLAN.json')
    assert original['condition']==executed['condition']==registered[g]
    assert executed['arms'][:5]==read('ACTION_SET.json')['arms']
    assert registration['frozen_unix']<f['frozen_unix']
    group_starts=[s for s in starts if s.get('group')==g]
    assert group_starts and all(s['group_plan_sha256']==sha(P/(g+'_TEST_PLAN.json')) for s in group_starts)
    assert all(s['code_manifest_sha256']==sha(P/'EXECUTION_CODE_MANIFEST_v3.json') for s in group_starts)
checks['original_test_conditions_seeds_fixed_actions_and_START_hashes_unchanged']=True
for g in groups:
    records=[r for r in ds['records'] if r['parent']==g];assert len(records)==4
    features=[r['state']['features'] for r in records];assert all(x==features[0] for x in features)
    assert all(r['state']['truth_used'] is False and r['state']['future_matched_B_used'] is False for r in records)
    result=read(g+'_RESULTS.json');branches=[r['branch']['full_hash'] for r in result['rows']];assert len(set(branches))==1
    assert read(g+'_PAIR_GATE.json')['all_parent_unchanged'] and read(g+'_PARENT_GATE.json')['status']=='PASS'
checks['parent_split_and_live_matched_states']=dict(groups=len(groups),train=sorted(train),validation=sorted(val),test=sorted(test),unique_prefixes=True)
# Compare actual policy raw arrays to selected fixed arm. Scope excludes host timing.
qraw=[]
for g in sorted(test):
    dec=read('output/'+g+'_Q_POLICY_DECISION.json');choice=dec['selected']
    for name in ['trace.npz']:
        a=np.load(P/'source/results'/(g+'_Q')/name);b=np.load(P/'source/results'/(g+'_'+choice)/name)
        assert set(a.files)==set(b.files)
        for key in a.files:assert np.array_equal(a[key],b[key],equal_nan=True) if a[key].dtype.kind in 'fc' else np.array_equal(a[key],b[key]),(g,key)
    qa=np.load(P/'motion_series'/(g+'_Q.npz'));qb=np.load(P/'motion_series'/(g+'_'+choice+'.npz'))
    for key in qa.files:assert np.array_equal(qa[key],qb[key]),(g,key)
    qraw.append(dict(group=g,selected=choice,all_trace_arrays_equal=True,all_native_motion_arrays_equal=True))
checks['actual_policy_matches_selected_action']=qraw
early=read('models/EARLY_VALUE_FREEZE.json');assert sha(P/early['model_file'])==early['model_sha256'];assert early['frozen_unix']<min(s['unix'] for s in starts if s['id'].startswith('U'))
assert sha(P/'learning/train_early.py')==early['training_code_sha256']
eraw=[]
for g in sorted(test):
    dec=read('output/'+g+'_QE_POLICY_DECISION.json');choice=dec['selected']
    a=np.load(P/'source/results'/(g+'_QE')/'trace.npz');b=np.load(P/'source/results'/(g+'_'+choice)/'trace.npz')
    for key in a.files:assert np.array_equal(a[key],b[key],equal_nan=True) if a[key].dtype.kind in 'fc' else np.array_equal(a[key],b[key]),(g,'QE',key)
    na=np.load(P/'motion_series'/(g+'_QE.npz'));nb=np.load(P/'motion_series'/(g+'_'+choice+'.npz'))
    for key in na.files:assert np.array_equal(na[key],nb[key]),(g,'QE_native',key)
    eraw.append(dict(parent=g,selected=choice,all_trace_arrays_equal=True,all_native_motion_arrays_equal=True))
checks['earlier_selector_frozen_and_actual_policy_matches_action']=eraw
for feedback_group in ['REP','REPR']:
    FR=RepeatRoot(feedback_group)
    def fr_read(n):return read(rep_path(n,feedback_group))
    if (FR/'models/REPETITION_MEMORY_V1.json').exists():
        memory=fr_read('models/REPETITION_MEMORY_V1.json');identity=fr_read('models/REPETITION_MEMORY_FREEZE.json')
        assert sha(FR/'models/REPETITION_MEMORY_V1.json')==identity['sha256']
        assert memory['previous_complete'] and not memory['truth_consumed'] and not memory['future_comparator_consumed']
        assert memory['previous_causal_state']==fr_read('output/REP_FIRST_CAUSAL_STATE.json')
        z=np.load(FR/'source/results/REP_FIRST/trace.npz');ix=z['stage']=='TASK'
        times=z['time_s'][ix];force=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1)
        measured=float(force[:-1]@np.diff(times))
        assert abs(measured-memory['previous_measured_force_integral_N_s'])<1e-8
        head=np.load(FR/'models/repetition_base.npz');features=np.array(memory['previous_causal_state']['features'])
        prediction=float(np.r_[1.,(features-head['mu'])/head['sd']]@head['w'][:,0])
        assert abs(prediction-memory['prior_value_prediction_N_s'])<1e-10
        residual=memory['previous_measured_force_integral_N_s']-prediction
        update=float(np.clip(.5*residual,-head['loo_max_error_N_s'],head['loo_max_error_N_s']))
        assert abs(update-memory['online_kernel_weight_N_s'])<1e-10 and memory['online_updates']==1
        second=[s for s in starts if s['id']==rep_path('REP_parent',feedback_group)]
        if second:assert identity['frozen_unix']<second[0]['unix'] and second[0]['feedback_sha256']==identity['sha256']
        if (FR/'output/REP_MEMORY_POLICY_DECISION.json').exists():
            sys.path.insert(0,str(FR/'control'))
            import importlib
            feedback_select=importlib.import_module('feedback_selector_retry' if feedback_group=='REPR' else 'feedback_selector').select
            decision=fr_read('output/REP_MEMORY_POLICY_DECISION.json')
            assert decision==feedback_select(decision['state'])
        checks['actual_previous_feedback_recomputed_'+feedback_group]=dict(measured_force_integral_N_s=measured,prior_prediction_N_s=prediction,bounded_update_N_s=update,memory_hash=identity['sha256'],weights_recomputed=True,choice_recomputed=(FR/'output/REP_MEMORY_POLICY_DECISION.json').exists())
complete=[]
for folder in sorted((P/'source/results').iterdir()):
    if not folder.is_dir() or not (folder/'summary.json').exists():continue
    summary=json.loads((folder/'summary.json').read_text());trans=summary.get('task',{}).get('phase_transitions',[])
    if trans and trans[-1]['to']=='COMPLETE':
        independent=P/'derived'/(folder.name+'_INDEPENDENT.json');assert independent.exists(),'MISSING_COMPLETE_RAW_AUDIT:'+folder.name
        audit=json.loads(independent.read_text());assert audit['status']=='PASS' and audit['raw_hashes_verified'];complete.append(folder.name)
        data=read('output/'+folder.name+'_DATA.json');branch=data['branch_start']
        origin=branch['physical_time_s'] if branch else read(rep_path('output/REPETITION_CONTINUITY_BEFORE_SECOND.json',folder.name.split('_')[0]))['second_initial']['physical_time_s'] if folder.name in ['REP_parent','REPR_parent'] else 0.
        z=np.load(folder/'trace.npz');expected_steps=round((float(z['time_s'][-1])-origin)/.00025)
        assert expected_steps==data['metric']['actual_new_native_physics_steps'],('NATIVE_INCREMENT_MISMATCH',folder.name,expected_steps,data['metric']['actual_new_native_physics_steps'])
checks['all_complete_tasks_raw_recomputed']=complete
checks['new_native_steps_rederived_from_branch_clock']=True
assert read('audit/HISTORICAL_RAW_RECOMPUTATION.json')['status']=='PASS'
checks['historical_full_raw_recomputation']=True
assert read('audit/W2_FULL_RAW_REPRODUCTION.json')['status']=='PASS'
checks['W2_full_raw_reproduction']=True
initial=read('audit/prediction_initial/RESIDUAL_PREDICTOR.json');current=read('models/RESIDUAL_PREDICTOR.json');assert initial==current
checks['residual_predictor_not_retuned_after_new_prefixes']=True
checks['analysis_modules_do_not_load_physics']=not any('mujoco' in n for n in sys.modules)
assert checks['analysis_modules_do_not_load_physics']
out=dict(status='PASS',unix=time.time(),checks=checks,scope='independent arithmetic and assertion process; same agent, not independent personnel')
(P/'audit/SCIENTIFIC_VERIFICATION_FINAL.json').write_text(json.dumps(out,indent=2)+'\n')
print('SCIENTIFIC_VERIFICATION_PASS',len(complete),'FULL_TASKS',flush=True)
