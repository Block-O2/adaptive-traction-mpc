"""Explicitly approved <=60s SYNTHETIC_ONLY math/control fixture; 0 real fit.

Does not import any worker/runtime/plant. The owner methods are AST-extracted
into mocks; fake fork callbacks never create a process or step a plant.
"""
from pathlib import Path
import ast,copy,hashlib,json,math,os,sys,time,types
from unittest.mock import patch
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
F=Path(__file__).resolve().parent
sys.path.insert(0,str(F))
import numpy as np
import c2b_component_selector_v2 as selector
import continuous_bo_owner_hook_v2 as hook


def action(x):return dict(family='modal8_retimed',x=[0.,0.,0.,x,0.,0.,0.,0.],legacy=[0.,0.])


def bundle():
    roles={r:dict(id='SYN_'+r,qualified=True,action=({'family':'B'} if r=='B' else {'family':'H150','legacy':[0.,0.]} if r=='H150' else action(-.25 if r=='FIXED_X3_MINUS025' else .25 if r=='FIXED_X3_PLUS025' else 0.))) for r in selector.ROLES}
    rows=[]
    for x,r in [(-.25,'FIXED_X3_MINUS025'),(0.,'H150'),(.25,'FIXED_X3_PLUS025')]:
        rows.append(dict(id=roles[r]['id'],x3=x,action_sha256=selector.digest(roles[r]['action']),
            delta_JF_N_s=x+2*x*x,delta_JM_Nm_s=-.1*x+.2*x*x,motion_margins={'synthetic_margin_A':.7+.3*x,'synthetic_margin_B':.8-.2*x*x},
            qualified=True,clean_completed_legal_response=True,parent_snapshot_sha256='SYNTHETIC_PARENT'))
    gates={g:True for g in ('all_roles_completed_or_verified_alias','core_original_qualified','zero_raw_exact','signed_actual_nonzero_clean','same_full_parent_snapshot','same_full_H150_recipe','same_source_case_config_scorer_activation','child_END_joined')}
    return dict(schema='C2B_SAME_LIVE_PARENT_BUNDLE_V2',dataset_class='SYNTHETIC_ONLY',stage=3,scope='CURRENT_T3_ONLY_NO_OLD_TRIAL_POPULATION_VALUE_LABELS',
        native_advanced_since_snapshot=False,owner_live_quiescent=True,parent_snapshot_sha256='SYNTHETIC_PARENT',gates=gates,
        roles=roles,observations=rows,margin_names=['synthetic_margin_A','synthetic_margin_B'],attempted_x3=[-.25,0.,.25])


def main():
    began=time.monotonic();cpu=time.process_time();checks=[];solve_log=[];predict_log=[];receipts=[];api=[]
    target=F/'C2B_V2_SYNTHETIC_ONLY_FIXTURE.json'
    if target.exists():raise RuntimeError('SYNTHETIC_FIXTURE_RECEIPT_ALREADY_EXISTS_DO_NOT_OVERWRITE')
    def check(name,ok,details=None):
        checks.append(dict(name=name,pass_=bool(ok),details=details))
    original_solve=np.linalg.solve;original_predict=selector._fit_predict
    def solve(a,b):solve_log.append(dict(shape=list(a.shape),head_columns=int(b.shape[1]) if b.ndim==2 else 1));return original_solve(a,b)
    def predict(np_,model,x,y,q):
        predict_log.append(dict(model=model,train=len(x),heads=y.shape[1],queries=len(q),dataset_class='SYNTHETIC_ONLY'))
        return original_predict(np_,model,x,y,q)
    approval=dict(authorized=True,approval_id='PARENT_APPROVED_SYNTHETIC_ONLY_60S',dataset_class='SYNTHETIC_ONLY')
    def call(data):
        api.append('SYNTHETIC_ONLY_FIT_SELECT')
        return selector.fit_select(data,parent_fit_approval=approval,wall_cap_s=30,on_fit_receipt=receipts.append)
    data=bundle()
    with patch.object(np.linalg,'solve',solve),patch.object(selector,'_fit_predict',predict):
        first=call(data)
        changedJM=copy.deepcopy(data)
        for row in changedJM['observations']:row['delta_JM_Nm_s']*=7.
        second=call(changedJM)
        changedMargin=copy.deepcopy(data)
        for row in changedMargin['observations']:row['motion_margins']['synthetic_margin_A']+=2.*row['x3']
        third=call(changedMargin)
    check('six_declared_model_variants',set(first['predictions'])==set(selector.MODELS))
    check('every_matrix_solve_counted',len(solve_log)==sum(r['fit_matrix_solves'] for r in (first,second,third))==len(receipts)==72)
    check('three_synthetic_calls_four_independent_heads',all(r['scalar_heads']==4 and r['real_data_training_runs']==0 and r['dataset_class']=='SYNTHETIC_ONLY' for r in (first,second,third)))
    jf_same=True;jm_changes=False;margin_same=True;anchors=True;lengths=set()
    for model in selector.MODELS:
        for a,b,c in zip(first['predictions'][model],second['predictions'][model],third['predictions'][model]):
            jf_same &= abs(a['mean']['delta_JF_N_s']-b['mean']['delta_JF_N_s'])<1e-12 and abs(a['mean']['delta_JF_N_s']-c['mean']['delta_JF_N_s'])<1e-12
            margin_same &= abs(a['mean']['synthetic_margin_B']-c['mean']['synthetic_margin_B'])<1e-12
            jm_changes |= abs(a['mean']['delta_JM_Nm_s']-b['mean']['delta_JM_Nm_s'])>1e-6
            if a['x3']==0.:
                anchors &= abs(a['mean']['delta_JF_N_s'])<1e-12 and abs(a['mean']['delta_JM_Nm_s'])<1e-12 and abs(a['mean']['synthetic_margin_A']-.7)<1e-12 and abs(a['mean']['synthetic_margin_B']-.8)<1e-12
        if 'length_x3' in first['model_fits'][model]:lengths.add(first['model_fits'][model]['length_x3'])
    check('JF_JM_margin_heads_independent',jf_same and jm_changes and margin_same)
    check('all_models_exact_paired_f0_anchor',anchors)
    check('two_declared_kernel_lengths',lengths=={.25,.5})
    for name,mutator,expected in [
        ('missing_core_gate',lambda d:d['gates'].__setitem__('core_original_qualified',False),'PREREQUISITE:'),
        ('truth_feature_leak',lambda d:d.__setitem__('evaluation_only_human_parameters',[1,2]),'INPUT_LEAKAGE'),
        ('future_label_leak',lambda d:d['observations'][0].__setitem__('future_T4_JF',-99),'INPUT_LEAKAGE'),
        ('mixed_parent',lambda d:d['observations'][0].__setitem__('parent_snapshot_sha256','OTHER'),'MIXED_PARENTS'),
        ('fake_B_as_zero',lambda d:d['observations'][1].__setitem__('id',d['roles']['B']['id']),'FAKE_B_AS_X3'),
        ('unregistered_old_child',lambda d:d['observations'][0].__setitem__('id','OLD_TRIAL'),'OBSERVATION_NOT_CURRENT'),
    ]:
        invalid=copy.deepcopy(data);mutator(invalid);out=call(invalid)
        check(name,out['status']=='ABSTAIN' and out.get('fits_executed')==0 and out['reason'].startswith(expected),out['reason'])
    mismatch=selector.fit_select(data,parent_fit_approval=dict(authorized=True,approval_id='NOT_REAL',dataset_class='REAL_CURRENT_T3'))
    check('synthetic_real_approval_separation',mismatch['reason']=='SYNTHETIC_REAL_APPROVAL_CLASS_MISMATCH' and mismatch['fits_executed']==0)
    no_new=copy.deepcopy(data);no_new['attempted_x3']=list(selector.GRID)
    # Reuse already fitted predictions to verify the predeclared observed-point
    # exclusion policy, without running a fourth unneeded synthetic fit.
    check('already_attempted_points_excluded',all('ALREADY_ATTEMPTED_SEMANTIC_X3' in p['reasons'] for p in first['grid_audit'] if p['x3'] in data['attempted_x3']))

    class Clock:
        value=100.;cpu=0.
        def monotonic(self):return self.value
        def process_time(self):return self.cpu
    class Timer:
        ITIMER_REAL=0
        def __init__(self,remaining):self.remaining=remaining;self.calls=[]
        def getitimer(self,_):return (self.remaining,0.)
        def setitimer(self,_,seconds,interval=0.):self.calls.append((seconds,interval))
    owner=types.SimpleNamespace(stage=3,child=None,count={'OUTBOUND':0},stage_prefix='SYN_STAGE',manifest=lambda b:{'hash':'SYN_HASH'})
    b={'task_state':types.SimpleNamespace(phase=types.SimpleNamespace(value='OUTBOUND'))}
    frozen={k:'SAME' for k in ['families/history_conditioned/'+s for s in ['C2B_COMPONENT_BO_CONTRACT_V2.json','c2b_component_selector_v2.py','c2b_evidence_bundle_v2.py','continuous_bo_owner_hook_v2.py']]}
    config=dict(c2b_component_bo_v2_fit_authorized=True,c2b_component_bo_v2_fit_approval_id='SYNTHETIC_CONTROL_FLOW',frozen_artifacts=frozen)
    for remaining in (400.,20.):
        clock=Clock();timer=Timer(remaining);emitted=[]
        def extract(*a,**k):clock.value+=2.;clock.cpu+=.1;return data
        def select(*a,**k):clock.value+=5.;clock.cpu+=.2;return dict(status='ABSTAIN',reason='SYNTHETIC_CONTROL_FLOW_ONLY',fit_matrix_solves=0)
        with patch.object(hook,'time',clock),patch.object(hook,'signal',timer),patch.object(hook,'sha',lambda p:'SAME'),patch.object(hook,'build_bundle',extract),patch.object(hook,'fit_select',select):
            out=hook.select_freeze_for_live_owner(owner,b,root=F,group='SYN',config=config,original_quiesce=lambda b:None,original_compare_raw=lambda *a:None,emit_frozen=lambda k,r:emitted.append((k,r)),stop_check=lambda:None)
        check('deadline_only_decreases_'+str(remaining),timer.calls[0][0]==min(120.,remaining) and abs(timer.calls[-1][0]-(remaining-7.))<1e-12,timer.calls)
    rejected=False
    with patch.object(hook,'sha',lambda p:'CHANGED'):
        try:hook.select_freeze_for_live_owner(owner,b,root=F,group='SYN',config=config,original_quiesce=lambda b:None,original_compare_raw=lambda *a:None,emit_frozen=lambda *a:None,stop_check=lambda:None)
        except hook.EvidenceError as exc:rejected='SOURCE_NOT_PROSPECTIVELY_FROZEN' in str(exc)
    check('source_change_rejected_before_fit',rejected)

    # Execute only the new owner's two AST-extracted methods under explicit
    # mocks, never import a worker or the runtime. Every file below is synthetic.
    tree=ast.parse((F/'continuous_ilc_worker_v2.py').read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='StageStudy')
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('_consider_bo_once','decision_boundary')]
    sandbox=F/'audit/SYNTHETIC_ONLY_V2_OWNER';sandbox.mkdir(parents=True,exist_ok=False)
    (sandbox/'attempts').mkdir();stage='SYN_STAGE';puts={};forks=[];controls=[];selections=[]
    arms=[dict(tag=r,action=copy.deepcopy(data['roles'][r]['action'])) for r in selector.ROLES]
    for arm in arms:
        if arm['tag'] in ('ILC_ENABLED_G025','ILC_ENABLED_G010','ILC_HISTORY_DISABLED'):
            arm['action']=action({'ILC_ENABLED_G025':-.20,'ILC_ENABLED_G010':-.08,'ILC_HISTORY_DISABLED':.10}[arm['tag']])
    fake=types.SimpleNamespace(stage=3,child=None,count={'OUTBOUND':0},fork_done=False,bo_considered=False,bo_decision=None,
        stage_prefix=stage,initial_arms=copy.deepcopy(arms),arms=copy.deepcopy(arms),results=[],parent_checks=[],active_owned_child_pid=None)
    def manifest(b):
        meta=selector.digest(fake.arms)
        return dict(hash=selector.digest({'native':'SYN_NATIVE','interface':'SYN_INTERFACE','arms':fake.arms}),native_hash='SYN_NATIVE',unaugmented_scientific_interface_hash='SYN_INTERFACE',continuous_contract_sha256=meta)
    fake.manifest=manifest;initial=manifest(b)
    def put(path,row):puts[path]=copy.deepcopy(row)
    def read(path):
        if path.endswith('_B_SNAPSHOT.json'):return initial
        if path in puts:return puts[path]
        return json.loads((sandbox/path).read_text())
    def fork(b,tag,table):
        forks.append(tag);arm=next(r for r in fake.arms if r['tag']==tag)
        (sandbox/'attempts'/(stage+'_'+tag+'_RESULT.json')).write_text(json.dumps(dict(id=stage+'_'+tag,action=arm['action'],complete=True,qualified=True)))
        return False
    def select_owner(*a,**k):
        selections.append(dict(completed=len(fake.results),control_calls=len(controls)))
        return dict(status='PROPOSE_ONE_FROZEN_GRID_ACTION',selected_action=action(.125),input_sha256='SYNTHETIC_INPUT')
    for arm in arms:(sandbox/'attempts'/(stage+'_'+arm['tag']+'_RESULT.json')).write_text(json.dumps(dict(id=stage+'_'+arm['tag'],action=arm['action'],complete=True,qualified=True)))
    base=types.SimpleNamespace(C=dict(c2b_component_bo_v2_candidate_physics_authorized=True),GROUP='SYN',PLAN=dict(dispatch_cutoff_unix=time.time()+6000,physics_hard_stop_unix=time.time()+6000,physical_timeout_s=600),
        read=read,put=put,append=lambda *a:None,sc=types.SimpleNamespace(digest=selector.digest),mh=types.SimpleNamespace(fc=types.SimpleNamespace(quiesce=lambda b:None)),frozen=types.SimpleNamespace(bc=types.SimpleNamespace(compare_raw=lambda *a:{'status':'PASS'})))
    namespace=dict(base=base,P=sandbox,BO_ROLES=selector.ROLES,BO_GRID=selector.GRID,bo_digest=selector.digest,select_freeze_for_live_owner=select_owner,
        pw=types.SimpleNamespace(stop_check=lambda:None),copy=copy,json=json,time=time,np=np,alarm=lambda seconds:None)
    exec(compile(ast.Module(body=methods,type_ignores=[]),'<SYNTHETIC_ONLY AST owner methods>','exec'),namespace)
    fake._consider_bo_once=types.MethodType(namespace['_consider_bo_once'],fake);fake.fork=fork;fake.control=lambda b:controls.append('FIRST_NATIVE_CONTROL_WOULD_START_HERE')
    namespace['decision_boundary'](fake,b)
    metadata=puts['freeze/'+stage+'_C2B_V2_ARMS_METADATA_CHANGE.json']
    check('owner_hook_after_all_joined_before_control',selections==[{'completed':8,'control_calls':0}])
    check('one_new_arm_uses_same_original_loop',len(forks)==9 and forks[-1]=='BO_V2_NEW' and len(controls)==1 and len(fake.results)==9)
    check('arms_metadata_fullhash_change_explicit_native_unchanged',metadata['full_hash_changed'] and metadata['native_hash_unchanged'] and metadata['scientific_interface_hash_unchanged'])
    check('one_hook_and_no_second_fit_or_proposal',fake.bo_considered and fake._consider_bo_once(b) is False and len(selections)==1)
    elapsed=time.monotonic()-began;used=time.process_time()-cpu
    check('single_CPU_under_60s',elapsed<60. and used<60.,{'wall_s':elapsed,'cpu_s':used})
    result=dict(status='PASS' if all(r['pass_'] for r in checks) else 'FAIL',dataset_class='SYNTHETIC_ONLY',checks=checks,
        synthetic_numeric_import_initializations=1,synthetic_bundle_initializations=3,synthetic_fit_select_API_calls=len(api),
        synthetic_successful_fit_select_calls=3,synthetic_matrix_solves=len(solve_log),synthetic_solve_receipts=len(receipts),
        synthetic_scalar_head_solves=sum(r['heads'] for r in predict_log),synthetic_query_vectors=sum(r['queries'] for r in predict_log),
        synthetic_scalar_predictions=sum(r['queries']*r['heads'] for r in predict_log),synthetic_loop_fork_callbacks=len(forks),
        real_data_fit_calls=0,real_training_runs=0,real_physics_steps=0,real_forks=0,real_raw_data_read=False,
        wall_s=elapsed,cpu_s=used,source_sha256={n:hashlib.sha256((F/n).read_bytes()).hexdigest() for n in ['c2b_component_selector_v2.py','c2b_evidence_bundle_v2.py','continuous_bo_owner_hook_v2.py','continuous_ilc_worker_v2.py',Path(__file__).name]})
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps({'output':str(target),'status':result['status'],'checks':len(checks),'failed':[r['name'] for r in checks if not r['pass_']],
        'synthetic_matrix_solves':len(solve_log),'real_training_runs':0,'real_physics_steps':0,'cpu_s':used,'wall_s':elapsed}))


if __name__=='__main__':main()
