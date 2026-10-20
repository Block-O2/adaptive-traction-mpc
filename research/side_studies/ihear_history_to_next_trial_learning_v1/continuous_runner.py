"""One patient, continuous native plant, serial complete-address-space forks.
Learner decisions freeze before any Trial 2 result is produced.
"""
from pathlib import Path
import os,sys,json,time,signal,random,traceback,fcntl,hashlib,copy,inspect,ast,textwrap,gc
P=Path(__file__).resolve().parent
GROUP=sys.argv[1]; MODE=sys.argv[2] if len(sys.argv)>2 else 'development'
os.environ.update(STUDY_GROUP=GROUP,STUDY_MODE='history',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True
sys.path[:0]=[str(P),str(P/'control'),str(P/'code')]
import campaign_v6 as frozen
import study_common as sc,matched_harness as mh, fork_core as fc
import cross_analysis as ca
import history_features as hf
from bounded_planner import HistoryPosturePlanner
import numpy as np
ca.configure(P)
PLAN=json.loads((P/'RUN_PLAN.json').read_text());CONFIG=json.loads((P/(GROUP+'_TEST_PLAN.json')).read_text());PATIENT=CONFIG['patient']
CASE=json.loads((P/PATIENT['case_path']).read_text()); ORIGINAL_CASE,OPTIONS=sc.load_case_options()
assert CASE['task']==ORIGINAL_CASE['task']
sc.load_case_options=lambda:(copy.deepcopy(CASE),copy.deepcopy(OPTIONS))
context={};rt=sc.rt;original_run=rt.run_executed_case
ARMS=json.loads((P/'ACTION_SET.json').read_text())['arms']
def put(n,x):mh.put(P/n,sc.clean(x))
def read(n):return json.loads((P/n).read_text())
_original_initialize=rt._initialize_loaded_runtime
def audited_initialize(*args,**kwargs):
    from traction_mpc_stage5.high_rom_v1 import deployable_prior
    static=read('patients/'+PATIENT['patient_id']+'/static/MODEL_STATIC_AUDIT.json')
    assert sc.clean(kwargs['physical_human'])==static['human_dataclass'],'PHYSICAL_PATIENT_IDENTITY_CHANGED'
    assert sc.clean(kwargs['control_human'])==sc.clean(deployable_prior()),'CONTROLLER_RECEIVED_PATIENT_TRUTH'
    runtime=_original_initialize(*args,**kwargs)
    put('audit/'+GROUP+'_RUNTIME_MODEL_IDENTITY.json',dict(status='PASS',physical_human=sc.clean(runtime['plant'].human),
        control_prior=sc.clean(kwargs['control_human']),patient_case_sha256=PATIENT['case_sha256'],xml_sha256=static['xml_sha256'],
        scope='generation-side identity audit only; true coefficients never supplied to history or policy'))
    return runtime
rt._initialize_loaded_runtime=audited_initialize
def stamp():
    if not context:return None
    runtime=context['runtime'];plant=runtime['plant']
    return dict(plant_identity=id(plant),updater_identity=id(context['updater']),physical_time_s=float(plant.data.time),
        repetition_index=context['repetition_index'],belief_sequence=context['updater'].sequence,
        wall_active=runtime['wall_session'].active,outstanding=runtime['plan_lifecycle']._outstanding is not None)
def dispatch(ident,**extra):
    rs=mh.records();n=sum(r['event']=='START' for r in rs)
    assert n<PLAN['physics_budget'],'80_START_CAP'
    assert time.time()<PLAN['dispatch_cutoff_unix']-PLAN['physical_timeout_s'],'CLOSEOUT_RESERVE'
    assert not (P/'PHYSICS_STOP.json').exists(),'PHYSICS_STOPPED'
    assert not any(r['event']=='START' and r['id']==ident for r in rs),'DUPLICATE_START'
    assert sc.sha(P/PATIENT['case_path'])==PATIENT['case_sha256']
    for rel,h in read('EXECUTION_CODE_MANIFEST.json')['files'].items():assert sc.sha(P/rel)==h,'SOURCE_CHANGED:'+rel
    mh.event('START',ident,patient_id=PATIENT['patient_id'],run_group=GROUP,split=PATIENT['split'],controller_version=sc.sha(P/'EXECUTION_CODE_MANIFEST.json'),
        patient_case_sha256=PATIENT['case_sha256'],parent_state=stamp(),**extra)
    put('STATE.json',dict(phase='CONTINUOUS_'+MODE,last=ident,physics_starts=n+1,owned_pids=[os.getpid()],updated_unix=time.time()))
mh.dispatch=dispatch

# Bind only the existing evaluator's nominal provenance path to this patient's case.
import mode_metadata as mm, qualify as oq, final_qualification as ofq
orig_eval=inspect.getsource(oq.physical_audit)
old_case="case_path=S/'configs/high_rom_v1/high_rom_nominal_sync_120_v1.json'"
assert orig_eval.count(old_case)==1
adapt_eval=orig_eval.replace(old_case,'case_path=PATIENT_CASE_PATH').replace('str(case_path.relative_to(R))','str(case_path)').replace("execution_mode='SCIENTIFIC_SIMULATION'","execution_mode=env.summary['execution_mode']")
ns=dict(oq.__dict__,PATIENT_CASE_PATH=P/PATIENT['case_path']);exec(compile(adapt_eval,'<actual patient provenance; original gates>','exec'),ns)
orig_install=mm.install
def install_eval():
    orig_install();oq.physical_audit=ofq.physical_audit=ns['physical_audit'];mm.INSTALLED_AUDIT=ns['physical_audit']
mm.install=install_eval
put('audit/'+GROUP+'_EVALUATOR_BINDING.json',dict(original_sha256=hashlib.sha256(orig_eval.encode()).hexdigest(),adapted_sha256=hashlib.sha256(adapt_eval.encode()).hexdigest(),thresholds_changed=False,patient_case_path=PATIENT['case_path']))

# Frozen H150 control method is reused without fork-only logging conditions.
source=(P/'control/campaign_v6.py').read_text();tree=ast.parse(source)
node=next(n for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='Campaign' for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='control')
body=textwrap.dedent(ast.get_source_segment(source,node)).replace('self.child is not None','self.current is not None')
body=body.replace("GROUP+'_'+self.current['id']",'self.ident')
ns_control=dict(frozen.__dict__);exec(body,ns_control)
direct_control=ns_control['control']

class Trial(frozen.Campaign):
    def __init__(self,ident,action,history_sha=None,branch=None,zero_wrapper=False):
        super().__init__(CONFIG['condition']);self.ident=ident;self.selected_action=copy.deepcopy(action)
        self.history_sha=history_sha;self.branch_start=branch;self.zero_wrapper=zero_wrapper
        self.current=copy.deepcopy(next(a for a in ARMS if a['id']=='B'))
        self.causal_rows=[];self.causal_decisions=[];self.belief_record=None
    def decision_boundary(self,b):
        ph=b['task_state'].phase.value;slot=self.count.get(ph,0)
        if self.selected_action['base']=='H150' and (ph!='OUTBOUND' or slot>=1):
            self.current=copy.deepcopy(next(a for a in ARMS if a['id']=='H150'))
        direct_control(self,b)
        if self.selected_action['base']=='B' and (self.selected_action['knee_delta_deg']!=0 or self.zero_wrapper):
            planner=b['planner'];planner.__class__=HistoryPosturePlanner;planner.history_posture_intent=None
            if ph==self.selected_action['phase'] and slot==self.selected_action['slot']:
                planner.history_posture_intent={**self.selected_action,'history_sha256':self.history_sha}
        self.causal_decisions.append(dict(phase=ph,slot=slot,physical_s=float(b['physical_now']),request_id=b['request'].request_id,
            source_sample_time_s=float(b['request'].source_sample_time_s),proposed_action=self.selected_action))
    def boundary(self,b):
        super().boundary(b)
        ph=b['task_state'].phase.value;ref=b['reference'];obs=np.asarray(b['observation'].as_array(),float)
        start=np.asarray(b['spec'].start_return_target_rad);goal=np.asarray(b['spec'].outbound_goal_target_rad)
        prog=float(np.mean((ref.q_rad-start)/(goal-start)))
        if ph=='RETURN':prog=1-prog
        measured=b['interface'];sample=float(b['observation'].sample_timestamp_s)
        self.causal_rows.append(dict(phase=ph,physical_s=float(b['physical_now']),phase_elapsed_s=float(b['task_state'].phase_elapsed_s),
            estimated_q_dq=obs[:4].tolist(),reference_q_dq=np.r_[ref.q_rad,ref.dq_rad_s].tolist(),reference_ddq=ref.ddq_rad_s2.tolist(),
            reference_progress=prog,force_world_N=measured.measured_force_world_n.tolist(),moment_world_Nm=measured.measured_moment_world_nm.tolist(),
            source_sample_time_s=sample,source_age_s=float(b['physical_now'])-sample,proposed_slot=dict(self.count),truth_used=False))
        if self.belief_record is None:self.belief_record=sc.clean(b['belief'].value_state_record())
    def finish(self,env,metric):
        super().finish(env,metric)
        # Terminal trace node is a causal boundary without a following cost interval.
        trace=context['runtime']['trace'];last=next(r for r in reversed(trace) if r['stage']=='TASK')
        if self.causal_rows and float(last['time_s'])>self.causal_rows[-1]['physical_s']+1e-10:
            row=copy.deepcopy(self.causal_rows[-1]);row.update(physical_s=float(last['time_s']),source_sample_time_s=float(last['time_s']),source_age_s=0.,
                estimated_q_dq=np.asarray(last['estimated_state']).tolist(),reference_q_dq=np.r_[last['q_ref_rad'],last['dq_ref_rad_s']].tolist(),
                reference_ddq=np.asarray(last['ddq_ref_rad_s2']).tolist(),force_world_N=np.asarray(last['cuff_force_world_n']).tolist(),
                moment_world_Nm=np.asarray(last['cuff_moment_world_nm']).tolist(),terminal_boundary=True)
            self.causal_rows.append(row)
        meta=dict(patient_id=PATIENT['patient_id'],trial_id=self.ident,complete_task_observed=env.summary['status']=='COMPLETE',
            action=self.selected_action,commissioned_belief=self.belief_record,source='causal boundary allowlist; no native truth arrays')
        receipts=context['runtime']['wall_session'].applied_commands
        allowed=['receipt_index','applied','start_physics_s','end_physics_s','native_steps','source_sample_time_s','command_torque_nm',
            'q_ref_rad','dq_ref_rad_s','reference_version','validation_model_version','plan_request_id','command_kind','mode','rejection_reason']
        applied=[{k:r[k] for k in allowed if k in r} for r in receipts]
        put('learning/'+self.ident+'_RAW_HISTORY.json',dict(metadata=meta,rows=self.causal_rows,decisions=self.causal_decisions,applied_receipts=applied))
        if meta['complete_task_observed']:
            history=hf.summarize(self.causal_rows,meta)
            assert abs(history['JF_N_s']-(metric['J_F']+metric['tick_integral_vs_evaluation_J_F_error']))<1e-6,'CAUSAL_HISTORY_FORCE_CLOSURE'
            put('learning/'+self.ident+'_HISTORY.json',history)

def invoke(ident,it):
    initial=stamp();start=0. if initial is None else initial['physical_time_s']
    def persistent(*args,**kw):kw['session_context']=context;return original_run(*args,**kw)
    rt.run_executed_case=persistent
    try:
        metric=sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
        new_steps=round((stamp()['physical_time_s']-start)/rt.NOMINAL_PHYSICS_DT_S)
        metric['actual_new_native_physics_steps']=new_steps;metric['actual_new_simulation_seconds']=new_steps*rt.NOMINAL_PHYSICS_DT_S
        put('output/'+ident+'.json',metric);data=read('output/'+ident+'_DATA.json');data['metric']=metric;put('output/'+ident+'_DATA.json',data)
        put('audit/'+ident+'_CONTINUITY.json',dict(before=initial,after=stamp(),plant_unchanged=initial is None or initial['plant_identity']==stamp()['plant_identity'],
            updater_unchanged=initial is None or initial['updater_identity']==stamp()['updater_identity'],human_state_written=False,new_native_steps=new_steps))
        if initial is not None:
            put('output/'+ident+'_PREPARATION.json',dict(fresh_track_bootstrap=context['runtime'].get('fresh_track_bootstrap'),
                offline_support_setup=context['runtime'].get('offline_support_setup'),same_persistent_plant=True,
                extra_steps_included_in_attempt_native_count=True,task_cost_excludes_preparation=True))
        return metric
    finally:
        rt.run_executed_case=original_run
        import streaming_reuse
        if rt in streaming_reuse.BASE:streaming_reuse.restore(rt)

def boundary(ident,from_trial=1):
    before=stamp();dispatch(ident,kind='ORIGINAL_INTER_REPETITION_BOUNDARY',trial_number=from_trial,learning_method='COMMON_PREPARATION')
    plant=context['runtime']['plant'];cls=type(plant);original=cls.step_native;rows=[];ctrl=plant.data.ctrl.copy()
    last=next(r for r in reversed(context['runtime']['wall_session'].applied_commands) if r.get('applied') and r.get('native_steps',0)>0)
    def observed(instance,*args,**kw):
        t=float(instance.data.time);u=instance.data.ctrl.copy();ans=original(instance,*args,**kw)
        if instance is plant:
            assert np.array_equal(u,ctrl),'BOUNDARY_HELD_COMMAND_CHANGED'
            rows.append(dict(start_s=t,end_s=float(instance.data.time),control=u.tolist(),inherited_receipt_index=last['receipt_index'],
                qpos_evaluation_only=instance.data.qpos.tolist(),qvel_evaluation_only=instance.data.qvel.tolist()))
        return ans
    cls.step_native=observed;code=1;error=None
    try:
        result=rt.advance_inter_rep_boundary(context,max_wait_s=2.,stop_check=sc.guard);code=0
        put('output/'+ident+'.json',result)
        assert result['physical_object_unchanged']
        return result
    except BaseException as e:error=str(e);raise
    finally:
        cls.step_native=original
        put('output/'+ident+'_NATIVE.json',dict(rows=rows,held_command_receipt=last,before=before,after=stamp(),no_human_state_assignment=True))
        mh.event('END',ident,returncode=code,joined=True,error=error,actual_new_native_steps=len(rows))

def full_snapshot(decisions):
    runtime=context['runtime'];dummy=sc.Interface()
    b=dict(plant=runtime['plant'],runtime=runtime,lifecycle=runtime['plan_lifecycle'],updater=context['updater'],
        arguments=dict(session_context=context,frozen_decisions=decisions))
    fc.quiesce(b);gc.collect();return fc.state_manifest(b,dummy)

def decisions_for(history):
    decisions=[dict(method='B',history_enabled=False,action=hf.make_action()),
        dict(method='ILC',**{k:v for k,v in hf.ilc(history).items() if k!='method'})]
    if MODE=='development':
        for n,a in zip(['O_MINUS','O_PLUS','R_MINUS','R_PLUS'],hf.grid()[1:]):decisions.append(dict(method=n,action=a,history_enabled=False,design='preregistered_grid'))
        if PATIENT['patient_id']=='P00':decisions.insert(1,dict(method='B_REPEAT_ZERO',history_enabled=False,action=hf.make_action(),zero_wrapper=True))
    else:
        from learning_models import select
        population=read('models/POPULATION_HISTORY.json')
        disabled=hf.ilc(population);disabled.update(method='ILC_DISABLED',history_enabled=False,
            prior_source='frozen mean of development histories; current patient history not passed',model_updates=0)
        decisions.append(disabled)
        for method in ['BO','VALUE']:
            for enabled in [True,False]:decisions.append(select(P,method,history if enabled else None,enabled))
    decisions.append(dict(method='H150',history_enabled=False,action=hf.make_action(kind='H150')))
    for d in decisions:d.update(frozen_unix=time.time(),history_file_sha256=sc.sha(P/'learning'/f'{GROUP}_T1_HISTORY.json') if d['history_enabled'] else None,
        prior_trial=f'{GROUP}_T1',future_trial_outcomes_consumed=False)
    return decisions

original_intervention=ca.intervention_audit
def intervention(summary,arm,candidate=None):
    if candidate is None or candidate.get('base')=='H150':return original_intervention(summary,'H150' if candidate and candidate['base']=='H150' else 'B',candidate)
    records=[]
    for r in summary.get('learning_records',[]):
        meta=r.get('selected_plan',{}).get('execution_screen',{}).get('history_posture')
        if meta:records.append(dict(metadata=meta,activated=r.get('selected_plan_activated'),decision_index=r.get('decision_index')))
    required=abs(candidate['knee_delta_deg'])>1e-12
    accepted=[r for r in records if r['metadata']['status']=='ACCEPTED' and r['activated'] is True]
    return dict(status='PASS' if (len(accepted)==1 if required else len(records)==0) else 'FAIL',rows=records,
        proposal_required=required,proposed_action=candidate,accepted_count=len(accepted),actual_action_adapted=required and len(accepted)==1)
ca.intervention_audit=intervention

def evaluate(ident,action):
    row=ca.evaluate_run(ident,arm='H150' if action['base']=='H150' else 'B',case=CASE,candidate=action)
    if action['base']!='H150' and row.get('measured_path') and row['interventions'].get('proposal_required'):
        lineage=read('reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json');owners={r['decision_index']:r for r in lineage['rows']}
        steps=[owners.get(r['decision_index'],{}).get('actual_native_steps',0) for r in row['interventions']['rows']]
        row['interventions']['receipt_owned_native_steps']=steps
        row['interventions']['actual_action_adapted']=row['interventions']['actual_action_adapted'] and bool(steps) and all(n>0 for n in steps)
        if not row['interventions']['actual_action_adapted']:row['absolute_task_execution_qualified']=False
    put('reports/'+ident+'_EVALUATION.json',row);return row

def third_pair(previous_action):
    """Continue only the actual ILC branch. Compare update to KEEP and matched B."""
    h=read('learning/'+GROUP+'_T2_ILC_HISTORY.json')
    update=hf.ilc(h,previous=previous_action)
    decisions=[dict(method='B',action=hf.make_action(),history_enabled=False),
        dict(method='KEEP',action=previous_action,history_enabled=False),
        dict(method='ILC',**{k:v for k,v in update.items() if k!='method'})]
    put('learning/'+GROUP+'_T3_DECISIONS_FROZEN.json',dict(decisions=decisions,previous_actual_trial=GROUP+'_T2_ILC',
        frozen_unix=time.time(),same_continuous_branch=True,future_outcomes_consumed=False))
    boundary(GROUP+'_BOUNDARY_2_3',from_trial=2)
    parent=full_snapshot(decisions);put('audit/'+GROUP+'_T3_PARENT_SNAPSHOT.json',parent)
    static=read('patients/'+PATIENT['patient_id']+'/static/MODEL_STATIC_AUDIT.json');rows=[];checks=[]
    for d in decisions:
        ident=f"{GROUP}_T3_{d['method']}";before=full_snapshot(decisions);assert before['hash']==parent['hash']
        branch=dict(full_hash=before['hash'],native_hash=hashlib.sha256(json.dumps(before['manifest']['native_integration'],sort_keys=True).encode()).hexdigest(),
            physical_time_s=stamp()['physical_time_s'],patient_id=PATIENT['patient_id'],case_sha256=PATIENT['case_sha256'],model_xml_sha256=static['xml_sha256'])
        dispatch(ident,kind='THIRD_TRIAL_FROM_OWN_ILC_BRANCH',trial_number=3,learning_method=d['method'],
            proposed_action=d['action'],parent_snapshot_hash=before['hash'],previous_actual_trial=GROUP+'_T2_ILC',
            decision_file_sha256=sc.sha(P/'learning'/f'{GROUP}_T3_DECISIONS_FROZEN.json'))
        start=stamp()['physical_time_s'];pr=random.getstate();nr=np.random.get_state();pid=os.fork()
        if pid==0:
            os.setsid();code=1
            signal.alarm(min(PLAN['physical_timeout_s'],max(1,int(PLAN['physics_hard_stop_unix']-time.time()))))
            try:
                random.setstate(pr);np.random.set_state(nr);restored=full_snapshot(decisions)
                assert restored['hash']==before['hash'],'THIRD_FORK_MISMATCH'
                put('audit/'+ident+'_FORK.json',dict(before=before['hash'],restored=restored['hash'],fork_address_space=True))
                invoke(ident,Trial(ident,d['action'],h['raw_history_sha256'] if d['history_enabled'] else None,branch));code=0
            except BaseException as e:put('reports/'+ident+'_ERROR.json',dict(error=str(e),traceback=traceback.format_exc()))
            finally:
                put('audit/'+ident+'_EXIT.json',dict(returncode=code,pid=os.getpid(),new_native_steps=round((stamp()['physical_time_s']-start)/rt.NOMINAL_PHYSICS_DT_S)))
                os._exit(code)
        try:_,status=os.waitpid(pid,0)
        except BaseException:
            try:os.killpg(pid,signal.SIGTERM)
            except ProcessLookupError:pass
            _,status=os.waitpid(pid,0);mh.event('END',ident,returncode=os.waitstatus_to_exitcode(status),joined=True,interrupted=True);raise
        exit_data=read('audit/'+ident+'_EXIT.json') if (P/'audit'/f'{ident}_EXIT.json').exists() else {}
        after=full_snapshot(decisions);same=before['hash']==after['hash']
        mh.event('END',ident,returncode=os.waitstatus_to_exitcode(status),joined=True,parent_unchanged=same,actual_new_native_steps=exit_data.get('new_native_steps'))
        assert same;checks.append(dict(id=ident,unchanged=same,before=before['hash'],after=after['hash']))
        row=evaluate(ident,d['action']);row.update(method=d['method'],decision=d,patient_id=PATIENT['patient_id'],trial_number=3)
        rows.append(row)
    base=rows[0]
    for r in rows:
        if r is base:r['complete_qualified']=r['absolute_task_execution_qualified'];r['motion_relative']='SELF_REFERENCE';continue
        cmp=ca.compare_pair(PATIENT['patient_id'],copy.deepcopy(base),copy.deepcopy(r))
        r.update(motion_relative=cmp['motion_relative'],motion_comparison=cmp['H150'].get('motion_comparison'),
            complete_qualified=cmp['complete_qualified_H150'],gain_N_s=cmp['gain_N_s'],gain_percent=cmp['gain_percent'],pair_identity_valid=cmp['pair_identity_valid'])
    put(GROUP+'_T3_RESULTS.json',dict(rows=rows,parent_checks=checks,previous_actual_trial=GROUP+'_T2_ILC',
        improvement_vs_KEEP_N_s=None if any(r['J_F_N_s'] is None for r in rows[1:]) else rows[1]['J_F_N_s']-rows[2]['J_F_N_s'],
        no_cross_branch_state_splicing=True))

def main():
    assert read('PREPHYSICAL_CHECKS.json')['status']=='PASS'
    static=read('patients/'+PATIENT['patient_id']+'/static/MODEL_STATIC_AUDIT.json');assert static['model_static_valid']
    if MODE!='development':assert (P/'models/METHOD_FREEZE.json').exists()
    lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_TIMEOUT')))
    signal.alarm(max(1,int(PLAN['physics_hard_stop_unix']-time.time())))
    random.seed(CONFIG['condition']['seed']);np.random.seed(CONFIG['condition']['seed'])
    first=f'{GROUP}_T1';dispatch(first,kind='COLD_COMMISSIONING_FIRST_COMPLETE_TASK',trial_number=1,learning_method='B',proposed_action=hf.make_action())
    try:
        metric=invoke(first,Trial(first,hf.make_action()));mh.event('END',first,returncode=0,joined=True,task_valid=metric['task_valid'],actual_new_native_steps=metric['actual_new_native_physics_steps'])
        first_result=evaluate(first,hf.make_action());assert first_result['absolute_task_execution_qualified'],'FIRST_TASK_NOT_QUALIFIED'
        if PATIENT['patient_id']=='P00':
            gate=frozen.bc.compare_raw(P/'source/results'/first,P.parent/'ihear_cross_patient_b_h150_v1/source/results/P00_B')
            put('audit/'+GROUP+'_FIRST_FROZEN_B_REPRODUCTION.json',gate);assert gate['status']=='PASS','FIRST_B_CHANGED'
        history=read('learning/'+first+'_HISTORY.json')
        decisions=decisions_for(history);put('learning/'+GROUP+'_T2_DECISIONS_FROZEN.json',dict(decisions=decisions,created_before_boundary_and_all_T2_results=True))
        boundary(GROUP+'_BOUNDARY_1_2')
        snapshot=full_snapshot(decisions);put('audit/'+GROUP+'_T2_PARENT_SNAPSHOT.json',snapshot)
        results=[];parent_checks=[]
        for d in decisions:
            ident=f"{GROUP}_T2_{d['method']}";before=full_snapshot(decisions)
            assert before['hash']==snapshot['hash'],'PARENT_CHANGED_BEFORE_FORK'
            branch=dict(full_hash=before['hash'],native_hash=hashlib.sha256(json.dumps(before['manifest']['native_integration'],sort_keys=True).encode()).hexdigest(),
                physical_time_s=stamp()['physical_time_s'],patient_id=PATIENT['patient_id'],case_sha256=PATIENT['case_sha256'],model_xml_sha256=static['xml_sha256'])
            dispatch(ident,kind='FULL_LIVE_SESSION_FORK_SECOND_TASK',trial_number=2,learning_method=d['method'],proposed_action=d['action'],parent_snapshot_hash=before['hash'],decision_file_sha256=sc.sha(P/'learning'/f'{GROUP}_T2_DECISIONS_FROZEN.json'))
            start=stamp()['physical_time_s'];python_rng=random.getstate();numpy_rng=np.random.get_state();pid=os.fork()
            if pid==0:
                os.setsid();code=1;own_task_steps=None;own_task_end=None
                signal.alarm(min(PLAN['physical_timeout_s'],max(1,int(PLAN['physics_hard_stop_unix']-time.time()))))
                try:
                    random.setstate(python_rng);np.random.set_state(numpy_rng)
                    restored=full_snapshot(decisions)
                    if restored['hash']!=before['hash']:put('audit/'+ident+'_FORK_MISMATCH_SNAPSHOT.json',restored)
                    assert restored['hash']==before['hash'],'FORK_STATE_MISMATCH'
                    put('audit/'+ident+'_FORK.json',dict(before=before['hash'],restored=restored['hash'],fork_address_space=True,plant_identity=stamp()['plant_identity']))
                    it=Trial(ident,d['action'],history['raw_history_sha256'] if d['history_enabled'] else None,branch,d.get('zero_wrapper',False))
                    m=invoke(ident,it);code=0;own_task_steps=m['actual_new_native_physics_steps'];own_task_end=stamp()
                    if GROUP in ['P05','P08'] and d['method']=='ILC' and m['task_valid']:
                        try:third_pair(d['action'])
                        except BaseException as error:
                            put('audit/'+GROUP+'_THIRD_REPETITION_FAILURE.json',dict(error=str(error),traceback=traceback.format_exc(),first_two_trials_preserved=True))
                except BaseException as error:put('reports/'+ident+'_ERROR.json',dict(error=str(error),traceback=traceback.format_exc()))
                finally:
                    end=stamp();steps=own_task_steps if own_task_steps is not None else (None if end is None else round((end['physical_time_s']-start)/rt.NOMINAL_PHYSICS_DT_S))
                    # Runtime may abort before session_context is refreshed; preserved PARTIAL_COMPUTE carries actual plant clock.
                    if (P/'output'/f'{ident}_PARTIAL_COMPUTE.json').exists():
                        partial=read('output/'+ident+'_PARTIAL_COMPUTE.json');steps=round((partial['simulation_seconds']-start)/rt.NOMINAL_PHYSICS_DT_S) if partial.get('simulation_seconds') is not None else steps
                    put('audit/'+ident+'_EXIT.json',dict(pid=os.getpid(),returncode=code,new_native_steps=steps,after=own_task_end or end,branch_final_state=end,
                        nested_preparation_and_forks_counted_separately=True));os._exit(code)
            try:_,status=os.waitpid(pid,0)
            except BaseException:
                try:os.killpg(pid,signal.SIGTERM)
                except ProcessLookupError:pass
                _,status=os.waitpid(pid,0);mh.event('END',ident,returncode=os.waitstatus_to_exitcode(status),joined=True,interrupted=True);raise
            code=os.waitstatus_to_exitcode(status);after=full_snapshot(decisions);same=before['hash']==after['hash']
            exit_data=read('audit/'+ident+'_EXIT.json') if (P/'audit'/f'{ident}_EXIT.json').exists() else {}
            mh.event('END',ident,returncode=code,joined=True,parent_unchanged=same,actual_new_native_steps=exit_data.get('new_native_steps'))
            parent_checks.append(dict(id=ident,before=before['hash'],after=after['hash'],unchanged=same,returncode=code));assert same
            result=evaluate(ident,d['action']);result.update(method=d['method'],decision=d,patient_id=PATIENT['patient_id'],trial_number=2)
            results.append(result);put(GROUP+'_RESULTS.json',dict(first=first_result,rows=results,parent_checks=parent_checks))
            print('ARM_END',ident,json.dumps(dict(JF=result['J_F_N_s'],axes={k:result['axes'][k] for k in ['task','absolute_safety','causal_execution']},adapted=result['interventions'].get('actual_action_adapted'),error=result.get('child_error'))),flush=True)
            if d['method']=='B':assert result['absolute_task_execution_qualified'],'MATCHED_B_NOT_QUALIFIED'
            if d['method']=='B_REPEAT_ZERO':
                gate=frozen.bc.compare_raw(P/'source/results'/f'{GROUP}_T2_B',P/'source/results'/ident);put('audit/'+GROUP+'_CONTINUOUS_ZERO_GATE.json',gate);assert gate['status']=='PASS','CONTINUOUS_ZERO_REPRODUCTION_FAIL'
        base=results[0]
        for r in results:
            if r['id']==base['id']:r['motion_relative']='SELF_REFERENCE';r['complete_qualified']=r['absolute_task_execution_qualified'];continue
            comparison=ca.compare_pair(PATIENT['patient_id'],copy.deepcopy(base),copy.deepcopy(r))
            r.update(motion_relative=comparison['motion_relative'],motion_comparison=comparison['H150'].get('motion_comparison'),complete_qualified=comparison['complete_qualified_H150'],gain_N_s=comparison['gain_N_s'],gain_percent=comparison['gain_percent'],pair_identity_valid=comparison['pair_identity_valid'])
        put(GROUP+'_RESULTS.json',dict(first=first_result,rows=results,parent_checks=parent_checks))
        put(GROUP+'_DONE.json',dict(status='EXECUTED_QUALIFICATIONS_SEPARATE',unix=time.time(),all_children_joined=True,parent_unchanged=all(r['unchanged'] for r in parent_checks),rows=len(results)))
    except BaseException as error:
        if not any(r['event']=='END' and r['id']==first for r in mh.records()):mh.event('END',first,returncode=1,joined=True,error=str(error))
        put('audit/'+GROUP+'_FAILURE.json',dict(error=str(error),traceback=traceback.format_exc(),state=stamp(),unix=time.time()));raise
    finally:signal.alarm(0);put('audit/'+GROUP+'_WORKER_EXIT.json',dict(pid=os.getpid(),unix=time.time(),all_owned_children_joined=True))
if __name__=='__main__':main()
