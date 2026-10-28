"""SOURCE CANDIDATE ONLY: original B -> native boundary -> original B.

No physics at import. Main-agent reviewed config + unique source freeze and
the root PHYSICS.lock are required before main() may execute. No learning,
non-B direct recipe, fake child, fork, or Human-state assignment is present.
"""
from pathlib import Path
import copy
import fcntl
import json
import os
import random
import signal
import sys
import time
import traceback

sys.dont_write_bytecode=True
P=Path(os.environ['ACL2_PACKAGE']).resolve()
sys.path[:0]=[str(P/'source'),str(Path(__file__).resolve().parent)]
import v8_worker_v1 as base
import numpy as np
from persistent_session_bridge import PersistentSessionBridge
from trial_interface import capture_boundary,summarize,feature_vector

ACCOUNTING={}


def emit(kind,record):
    ident=record['id'];ACCOUNTING[ident]=copy.deepcopy(record)
    base.put('audit/persistent/'+ident+'_'+kind.split('/')[0]+'.json',record)


def stop_check():
    if time.time()>=min(base.A['hard_stop_unix'],base.PLAN['physics_hard_stop_unix']):
        raise TimeoutError('ORIGINAL_V8_PHYSICS_HARD_STOP')
    if (P/'STOP_REQUESTED').exists():raise RuntimeError('ORIGINAL_STOP_REQUESTED')
    base.sc.guard()


def model_counter():
    from traction_mpc_stage4 import estimator_v2
    return getattr(estimator_v2,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',None)


class DirectB(base.Study):
    def __init__(self,ident,bridge):
        super().__init__();self.ident=ident;self.bridge=bridge
        self.current=copy.deepcopy(base.C['B']);self.active_action={'family':'B'}
        self.rule_action={'family':'B'};self.active_policy_tag='B';self.causal=[]
        mark=bridge.stamp();self.invocation_start_s=0. if mark is None else mark['physical_time_s']

    def decision_boundary(self,b):
        if self.child is not None:raise RuntimeError('DIRECT_B_MUST_NOT_FAKE_OR_FORK_CHILD')
        # Exact existing registered B control, including legal prefix handling.
        self.control(b)

    def boundary(self,b):
        # base.Study.boundary's counter uses absolute native time and would
        # apply its 180000 per-attempt guard to both persistent tasks together.
        # Reuse its original base instrumentation, then the same necessary B
        # audits with a true invocation-local counter. No controller is changed.
        base.frozen.Campaign.boundary(self,b)
        self.bridge.observe_existing_runtime(b)
        if not self.actual_plant_binding_saved:
            plant=b['plant'];human=base.sc.clean(plant.human);geometry=base.sc.clean(plant.geometry)
            if human!=base.sc.clean(b['physical_human']) or geometry!=base.sc.clean(b['physical_geometry']):
                raise RuntimeError('ACTUAL_NATIVE_CASE_BINDING_CHANGED')
            arrays={key:np.asarray(getattr(plant.model,key)).copy()
                    for key in ['body_mass','body_inertia','body_pos','geom_size','geom_pos','dof_damping','jnt_stiffness']}
            base.put('audit/persistent/'+self.ident+'_ACTUAL_PLANT_BINDING_EVALUATION_ONLY.json',
                dict(case_path=base.C['case_path'],case_sha256=base.C['case_sha256'],
                    physical_s=float(b['physical_now']),plant_identity=id(plant),
                    human=human,geometry=geometry,model_parameter_fingerprint=base.sc.digest(arrays),
                    actor_input=False,extra_model_calls=0,extra_observe_refresh_step=0,
                    source='existing persistent objects; no cold-start inference'))
            self.actual_plant_binding_saved=True
        self.risk_history.update(b)
        if time.time()-self.last_counter>3.:
            self.last_counter=time.time();current=round((float(b['physical_now'])-self.invocation_start_s)/base.sc.rt.NOMINAL_PHYSICS_DT_S)
            if current>180000:raise RuntimeError('ORIGINAL_PER_ATTEMPT_NATIVE_GUARD')
            mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
            if int(mem['MemAvailable'].split()[0])*1024<=6*2**30:raise RuntimeError('ORIGINAL_RAM_FLOOR')
            stop_check()
            base.put('audit/LIVE_PHYSICS_COUNTERS.json',dict(utc=base.utc(),id=self.ident,pid=os.getpid(),
                actual_new_native_live=current,invocation_start_s=self.invocation_start_s,
                persistent_repetition=self.bridge.context.get('repetition_index',0)+1,
                remaining_wall_s=base.A['hard_stop_unix']-time.time()))
        self.causal.append(capture_boundary(b))


def freeze_sources():
    files={}
    for directory in ['runtime/source','runtime/control','runtime/code','runtime/deps','source']:
        for file in (P/directory).rglob('*'):
            if file.is_file() and file.suffix in ['.py','.json','.xml','.so'] and 'results' not in file.relative_to(P/directory).parts:
                files[str(file.relative_to(P))]=base.sha(file)
    for filename in ['persistent_worker_v1.py','persistent_session_bridge.py','trial_interface.py']:
        file=Path(__file__).with_name(filename);files[str(file.relative_to(P))]=base.sha(file)
    for name in ['RUN_PLAN.json','FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','PARAMETER_MAP.json','ACTION_SET.json']:
        files['runtime/'+name]=base.sha(P/'runtime'/name)
    files['ACTIVATION.json']=base.sha(P/'ACTIVATION.json')
    files['runtime/output/SHARED_COORDINATION_ACTION_CONTRACT.json']=base.sha(P/'runtime/output/SHARED_COORDINATION_ACTION_CONTRACT.json')
    for relative,expected in base.C.get('frozen_artifacts',{}).items():
        if base.sha(P/relative)!=expected:raise RuntimeError('CONFIG_FROZEN_ARTIFACT_CHANGED:'+relative)
        files[relative]=expected
    manifest=dict(frozen_utc=base.utc(),files=files,config_sha256=base.sha(P/sys.argv[1]),
        origin=base.read('audit/CLOSURE_RELOCATION.json')['origin_manifest_sha256'],
        process=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])),
        engineering_contract='B_BOUNDARY_B_ONLY_NO_LEARNING')
    base.SOURCE_MANIFEST=manifest;base.put('jobs/'+base.GROUP+'/SOURCE_MANIFEST.json',manifest)


def fix_incremental_metric(ident):
    delta=ACCOUNTING[ident]
    if delta['actual_new_native_steps'] is None:raise RuntimeError('MISSING_REAL_INCREMENT')
    mp=P/'runtime/output'/f'{ident}.json';dp=P/'runtime/output'/f'{ident}_DATA.json'
    metric=json.loads(mp.read_text());data=json.loads(dp.read_text())
    base.put('audit/persistent/'+ident+'_ORIGINAL_ABSOLUTE_METRIC.json',metric)
    base.put('audit/persistent/'+ident+'_ORIGINAL_ABSOLUTE_DATA.json',data)
    for target in [metric,data['metric']]:
        target['actual_new_native_physics_steps']=delta['actual_new_native_steps']
        target['actual_new_simulation_seconds']=delta['actual_new_simulation_seconds']
        target['actual_new_main_model_inverse_dynamics_api_calls']=delta['actual_new_main_model_calls']
        target['persistent_increment_source']='actual current invocation plant-time and main-call deltas; absolute trace fields preserved'
    base.put('runtime/output/'+ident+'.json',metric);base.put('runtime/output/'+ident+'_DATA.json',data)
    return metric


def complete_history(ident,it,bridge):
    # Terminal data are already produced by the original runtime. No new
    # plant.observe, estimator update, or physics occurs during extraction.
    with np.load(P/'runtime/source/results'/ident/'trace.npz',allow_pickle=False) as z:
        last=int(np.flatnonzero(z['stage']=='TASK')[-1])
        if not bool(z['terminal_boundary_node'][last]):raise RuntimeError('MISSING_REAL_TERMINAL_BOUNDARY')
        terminal=dict(time_s=float(z['time_s'][last]),task_phase=str(z['task_phase'][last]),
            estimated_state=z['estimated_human_state_rad_rad_s'][last],
            q_ref_rad=z['reference_q_rad'][last],dq_ref_rad_s=z['reference_dq_rad_s'][last],
            cuff_force_world_n=z['physical_cuff_force_world_n'][last],
            cuff_moment_world_nm=z['physical_cuff_moment_world_nm'][last])
    transitions=json.loads((P/'runtime/source/results'/ident/'summary.json').read_text())['task']['phase_transitions']
    commit=next(row for row in transitions if row['to']=='COMPLETE')
    if not np.array_equal(np.asarray(commit['estimated_state']),np.asarray(terminal['estimated_state'])):
        raise RuntimeError('TERMINAL_ESTIMATOR_COMMIT_MISMATCH')
    endrow=dict(time_s=float(terminal['time_s']),phase=terminal['task_phase'],
        estimated_q_dq=np.asarray(terminal['estimated_state']).tolist(),
        reference_q_dq=np.r_[terminal['q_ref_rad'],terminal['dq_ref_rad_s']].tolist(),
        measured_force=np.asarray(terminal['cuff_force_world_n']).tolist(),
        measured_moment=np.asarray(terminal['cuff_moment_world_nm']).tolist(),
        source_sample_time_s=float(commit['state_source_time_s']),truth_used=False)
    rows=it.causal+[endrow]
    start=rows[0]['reference_q_dq'][:2];goal=np.asarray(bridge.context['spec'].outbound_goal_target_rad).tolist()
    h=summarize(rows,trial_id=ident,patient_id=base.GROUP,trial_number=bridge.context['repetition_index'],
        actual_action_tag='B',task_start_s=rows[0]['time_s'],task_end_s=endrow['time_s'],complete=True,
        identity=dict(case_sha256=base.C['case_sha256'],source_manifest_sha256=base.sha(P/'jobs'/base.GROUP/'SOURCE_MANIFEST.json')),
        public_phase_targets={'OUTBOUND':[start,goal],'RETURN':[goal,start]})
    metric=json.loads((P/'runtime/output'/f'{ident}.json').read_text())
    if abs(h['JF_N_s']-metric['J_F'])>1e-6 or abs(h['JM_Nm_s']-metric['moment_integral'])>1e-6:
        raise RuntimeError('COMPLETE_CAUSAL_JF_JM_CLOSURE')
    base.put('history/'+ident+'_COMPLETE_HISTORY.json',h)
    return h


def run_task(ident,bridge,repetition):
    it=DirectB(ident,bridge);before=bridge.stamp();started=time.time()
    base.dispatch(ident,kind='INITIAL_COLD_ORIGINAL_B' if repetition==1 else 'CONTINUED_SESSION_ORIGINAL_B',
        persistent_session=True,trial_number=repetition,session_before=before,
        learning_method='NONE_ORIGINAL_B_ENGINEERING',actual_action={'family':'B'})
    signal.alarm(max(1,int(min(base.PLAN['physical_timeout_s'],base.PLAN['physics_hard_stop_unix']-time.time()))))
    try:
        bridge.invoke(ident,it);metric=fix_incremental_metric(ident)
        measured=base.am.measure(ident);comparison=base.am.compare(measured,measured)
        qualified=bool(comparison['acceptance_pass'] and measured['native_physical_audit']['pass_']
            and measured['axes']['PHYSICAL_TASK_VALID']=='PASS'
            and measured['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS'
            and measured['axes']['LEGACY_R2_MATCHED']=='PASS')
        history=complete_history(ident,it,bridge)
        row=dict(id=ident,complete=True,qualified=qualified,JF=measured['J_F_N_s'],JM=measured['moment_integral_Nm_s'],
            actual_new_native_steps=ACCOUNTING[ident]['actual_new_native_steps'],
            axes=measured['axes'],motion_vs_self=comparison,learning=False,action={'family':'B'},
            original_physical_audit=measured['native_physical_audit'],history_sha256=history['history_sha256'],
            scope='PERSISTENT_ENGINEERING_GATE_NO_LEARNING_OR_PERFORMANCE_INCREMENT',
            repetition=repetition,session_after=bridge.stamp())
        base.put('attempts/'+ident+'_RESULT.json',row);base.append('ALL_RESULTS.jsonl',row)
        if not qualified:raise RuntimeError('ORIGINAL_B_ENGINEERING_QUALIFICATION_FAILED')
        base.mh.event('END',ident,returncode=0,joined=True,actual_new_native_steps=row['actual_new_native_steps'],
            task_valid=metric['task_valid'],wall_seconds=time.time()-started,persistent_session=True)
        return row,measured
    except BaseException as exc:
        delta=ACCOUNTING.get(ident,{});after=bridge.stamp()
        base.put('audit/persistent/'+ident+'_ERROR.json',dict(error=str(exc),traceback=traceback.format_exc(),
            before=before,after=after,increment=delta,partial_never_ranked=True))
        if not any(row['event']=='END' and row['id']==ident for row in base.mh.records()):
            base.mh.event('END',ident,returncode=1,joined=True,error=str(exc),actual_new_native_steps=delta.get('actual_new_native_steps'),
                wall_seconds=time.time()-started,persistent_session=True)
        raise
    finally:signal.alarm(0)


def main():
    if base.C.get('persistent_engineering_contract')!='B_BOUNDARY_B_V1' or base.C.get('persistent_physics_authorized') is not True:
        raise RuntimeError('REVIEWED_MAIN_AGENT_PERSISTENT_B_CONFIG_REQUIRED')
    if base.C.get('algorithm') or any(a.get('action',{}).get('family')!='B' for a in base.C.get('actions',[])):
        raise RuntimeError('ONLY_ORIGINAL_B_NO_LEARNED_OR_NON_B_ACTION')
    lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    split=base.read('freeze/VARIED_HUMAN_SPLIT_V1.json')
    if Path(base.C['case_path']).stem in split['heldout_cases']:
        protocol=base.C.get('holdout_protocol')
        if not protocol or base.sha(P/protocol)!=base.C.get('holdout_protocol_sha256'):
            raise RuntimeError('ORIGINAL_HELDOUT_PROTOCOL_NOT_FROZEN')
        heldout=base.read(protocol)
        if base.GROUP not in heldout['authorized_groups'] or heldout['frozen_unix']>=time.time():
            raise RuntimeError('ORIGINAL_HELDOUT_GROUP_NOT_AUTHORIZED')
        for relative,expected in heldout.get('frozen_artifacts',{}).items():
            if base.sha(P/relative)!=expected:raise RuntimeError('ORIGINAL_HELDOUT_ARTIFACT_CHANGED:'+relative)
    import v8_case_adapter_v1 as adapter
    installed=adapter.install(base.sc,base.C,P,base.sha,base.put)
    base.put('audit/persistent/'+base.GROUP+'_CASE_SCOPE.json',dict(adapter_install_preserved=installed,
        initial_task_cold=True,second_task_cold=False,second_task_uses_existing_plant_updater_observer=True,
        original_cold_install_metadata_scope='first invocation only; explicit persistent bridge supersedes per-call empty-session inference',
        case_and_original_scorer_identity_unchanged=True))
    freeze_sources();random.seed(base.C['condition']['seed']);np.random.seed(base.C['condition']['seed'])
    bridge=PersistentSessionBridge(base.sc.rt,base.sc,emit=emit,
        hard_deadline_unix=min(base.A['hard_stop_unix'],base.PLAN['physics_hard_stop_unix']),stop_check=stop_check,model_counter=model_counter)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('ORIGINAL_OWNED_LOCAL_TIMEOUT')))
    try:
        first,first_m=run_task(base.GROUP+'_T1_B',bridge,1)
        boundary_id=base.GROUP+'_BOUNDARY_1_2';before=bridge.stamp();base.dispatch(boundary_id,kind='ORIGINAL_INTER_REP_NATIVE_SETTLE_HOLD',session_before=before)
        signal.alarm(max(1,int(min(base.PLAN['physical_timeout_s'],base.PLAN['physics_hard_stop_unix']-time.time()))))
        try:
            boundary=bridge.advance_boundary(boundary_id,max_wait_s=2.)
            base.put('audit/persistent/'+boundary_id+'_CAUSAL_COST.json',boundary)
            audit=ACCOUNTING[boundary_id]
            if not audit['counter_matches_observation']:raise RuntimeError('BOUNDARY_INCREMENT_COUNT_MISMATCH')
            base.mh.event('END',boundary_id,returncode=0,joined=True,actual_new_native_steps=audit['actual_new_native_steps'])
        except BaseException as exc:
            base.mh.event('END',boundary_id,returncode=1,joined=True,error=str(exc),actual_new_native_steps=ACCOUNTING.get(boundary_id,{}).get('actual_new_native_steps'));raise
        finally:signal.alarm(0)
        second,second_m=run_task(base.GROUP+'_T2_B',bridge,2)
        base.put('audit/persistent/'+base.GROUP+'_CROSS_TRIAL_DESCRIPTIVE.json',dict(
            comparison=base.am.compare(second_m,first_m),scope='descriptive different real continuous start states; no learning claim'))
        total=sum(ACCOUNTING[key]['actual_new_native_steps'] for key in [first['id'],boundary_id,second['id']])
        base.put('jobs/'+base.GROUP+'/WORKER_DONE.json',dict(status='PERSISTENT_B_ENGINEERING_GATE_PASS',
            tasks=[first,second],boundary=boundary,actual_new_native_steps=total,
            accounting='each of T1/boundary/T2 increments counted exactly once',
            learning=False,non_B_direct_recipe_validated=False,session=bridge.stamp(),all_children_joined=True))
    except BaseException as exc:
        base.put('jobs/'+base.GROUP+'/WORKER_DONE.json',dict(status='FAILED_PRESERVED',error=str(exc),traceback=traceback.format_exc(),
            accounting=ACCOUNTING,session=bridge.stamp(),learning=False));raise
    finally:
        signal.alarm(0);base.put('owned/'+base.GROUP+'_EXIT.json',dict(pid=os.getpid(),utc=base.utc(),active_child=None,
            bridge_running=bridge.running,all_computation_foreground=True))


if __name__=='__main__':main()
