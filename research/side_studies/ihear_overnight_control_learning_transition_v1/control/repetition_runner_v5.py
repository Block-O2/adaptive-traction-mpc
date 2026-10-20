"""Persistent native session, real completed feedback, serial full-state comparison."""
from pathlib import Path
import sys,os,json,time,signal,random,ast,textwrap,hashlib,copy,traceback,fcntl
sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'control'),str(P/'code')]
import campaign_v5 as c
import numpy as np
sc=c.sc;mh=c.mh;am=c.am;rt=sc.rt
context={};original_run=rt.run_executed_case;original_persist=rt.persist_runtime_artifacts;invocation_main_calls={}
def put(n,x):c.put(n,x)
def invoke(name,interface):
    from traction_mpc_stage4 import estimator_v2 as accounting
    invocation_main_calls[name]=getattr(accounting,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',0)
    def persistent(*args,**kw):
        assert kw['execution_mode']=='SCIENTIFIC_SIMULATION'
        kw['session_context']=context;return original_run(*args,**kw)
    rt.run_executed_case=persistent
    try:return sc.run(name,interface,execution_mode='SCIENTIFIC_SIMULATION')
    finally:
        rt.run_executed_case=original_run
        import streaming_reuse
        streaming_reuse.restore(rt)
def stamp():
    if not context:return None
    plant=context['runtime']['plant']
    return dict(plant_identity=id(plant),updater_identity=id(context['updater']),updater_sequence=context['updater'].sequence,physical_time_s=float(plant.data.time),repetition_index=context['repetition_index'])
def recorded_boundary():
    # Instrument only observation of the original native steps. Never assign
    # physical state or change the held command during the original boundary.
    plant=context['runtime']['plant'];cls=type(plant);original=cls.step_native
    receipts=context['runtime']['wall_session'].applied_commands
    last=next(r for r in reversed(receipts) if r.get('applied') and r.get('native_steps',0)>0)
    rows=[];initial_ctrl=np.asarray(plant.data.ctrl).copy()
    def observed(instance,*args,**kw):
        before=float(instance.data.time);ctrl=np.asarray(instance.data.ctrl).copy()
        answer=original(instance,*args,**kw)
        if instance is plant:
            assert np.array_equal(ctrl,initial_ctrl),'BOUNDARY_HELD_COMMAND_CHANGED'
            rows.append(dict(start_s=before,end_s=float(instance.data.time),actual_control=ctrl.tolist(),qpos_evaluation_only=instance.data.qpos.copy().tolist(),qvel_evaluation_only=instance.data.qvel.copy().tolist(),inherited_receipt_index=last['receipt_index']))
        return answer
    cls.step_native=observed
    try:return rt.advance_inter_rep_boundary(context,max_wait_s=2.,stop_check=lambda:sc.guard())
    finally:
        cls.step_native=original
        put('output/REPR_BOUNDARY_NATIVE.json',dict(source='observation wrapper around unchanged original step_native',prior_final_positive_receipt=last,held_control=initial_ctrl.tolist(),native_steps=len(rows),rows=rows,truth_used_by_policy=False))
def fix_parent_accounting(name,start_time):
    m=json.loads((P/'output'/(name+'.json')).read_text());data=json.loads((P/'output'/(name+'_DATA.json')).read_text())
    new_s=float(context['runtime']['plant'].data.time)-start_time
    m['actual_new_simulation_seconds']=new_s;m['actual_new_native_physics_steps']=round(new_s/rt.NOMINAL_PHYSICS_DT_S)
    if m.get('main_model_inverse_dynamics_api_calls') is not None:
        m['actual_new_main_model_inverse_dynamics_api_calls']=m['main_model_inverse_dynamics_api_calls']-invocation_main_calls[name]
        data['metric']['actual_new_main_model_inverse_dynamics_api_calls']=m['actual_new_main_model_inverse_dynamics_api_calls']
    data['metric']['actual_new_simulation_seconds']=new_s;data['metric']['actual_new_native_physics_steps']=m['actual_new_native_physics_steps']
    put('output/'+name+'.json',m);put('output/'+name+'_DATA.json',data)
class DirectFirst(c.Campaign):
    def decision_boundary(self,b):
        if self.current is None and b['task_state'].phase.value=='OUTBOUND' and self.count['OUTBOUND']>=1:
            self.current=copy.deepcopy(next(a for a in json.loads((P/'ACTION_SET.json').read_text())['arms'] if a['id']=='H150'));self.current['id']='FIRST'
        self.control(b)
# Use the exact frozen control wrapper for a non-fork first task. Only the
# logging/intervention ownership condition changes from child presence to action presence.
source=(P/'control/campaign_v5.py').read_text();tree=ast.parse(source);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Campaign');node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='control')
body=textwrap.dedent(ast.get_source_segment(source,node)).replace('self.child is not None','self.current is not None')
namespace=dict(c.__dict__);exec(body,namespace);DirectFirst.control=namespace['control']
def main():
    assert json.loads((P/'PREPHYSICAL_CHECKS_v5.json').read_text())['status']=='PASS'
    lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('REPETITION_RETRY_OWNED_TIMEOUT')))
    signal.alarm(max(1,min(1800,int(c.PLAN['physics_hard_stop_unix']-time.time()))))
    condition=c.CONFIG['condition'];random.seed(condition['seed']);np.random.seed(condition['seed'])
    first=DirectFirst(condition);name='REPR_FIRST'
    c.dispatch(name,kind='FIRST_ACTUAL_COMPLETE_REPETITION',condition=condition)
    try:
        metric=invoke(name,first);assert metric['task_valid'];fix_parent_accounting(name,0.)
        mh.event('END',name,returncode=0,joined=True,task_valid=True)
        first_measured=am.measure(name)
        reproduction=c.bc.compare_raw(P/'source/results'/name,P/'source/results/D02_H150')
        put('audit/REPETITION_RETRY_FIRST_REPRODUCTION.json',reproduction);assert reproduction['status']=='PASS','FIRST_H150_NOT_REPRODUCED'
        comparison=am.compare(first_measured,json.loads((P/'reports/D02_B_MEASURED.json').read_text()));assert comparison['acceptance_pass'],'FIRST_TASK_MOTION_FAIL'
        state=json.loads((P/'output/REPR_FIRST_CAUSAL_STATE.json').read_text());head=np.load(P/'models/repetition_base.npz')
        pred=float(np.r_[1.,(np.array(state['features'])-head['mu'])/head['sd']]@head['w'][:,0])
        observed=float(metric['J_F']+metric['tick_integral_vs_evaluation_J_F_error'])
        residual=observed-pred;weight=float(np.clip(.5*residual,-head['loo_max_error_N_s'],head['loo_max_error_N_s']))
        memory=dict(created_unix=time.time(),previous_task=name,previous_complete=True,previous_causal_state=state,previous_measured_force_integral_N_s=observed,measurement_integral_minus_evaluation_N_s=metric['tick_integral_vs_evaluation_J_F_error'],prior_value_prediction_N_s=pred,observed_residual_N_s=residual,learning_rate=.5,online_kernel_weight_N_s=weight,online_updates=1,truth_consumed=False,future_comparator_consumed=False)
        put('models/REPETITION_RETRY_MEMORY_V1.json',memory);put('models/REPETITION_RETRY_MEMORY_FREEZE.json',dict(sha256=sc.sha(P/'models/REPETITION_RETRY_MEMORY_V1.json'),frozen_unix=time.time(),update_completed_before_second_repetition=True))
        before=stamp();c.dispatch('REPR_boundary',kind='ORIGINAL_INTER_REPETITION_RETRY_SETTLE_HOLD')
        try:
            boundary=recorded_boundary()
            assert boundary['physical_object_unchanged'];put('output/REPR_INTER_BOUNDARY.json',boundary)
            mh.event('END','REPR_boundary',returncode=0,joined=True,actual_new_native_steps=round((boundary['end_time_s']-boundary['start_time_s'])/rt.NOMINAL_PHYSICS_DT_S))
        except BaseException as e:
            mh.event('END','REPR_boundary',returncode=1,joined=True,error=str(e),actual_new_native_steps=round((stamp()['physical_time_s']-before['physical_time_s'])/rt.NOMINAL_PHYSICS_DT_S));raise
        initial=stamp();assert initial['plant_identity']==before['plant_identity'] and initial['updater_identity']==before['updater_identity']
        put('output/REPETITION_RETRY_CONTINUITY_BEFORE_SECOND.json',dict(first_end=before,second_initial=initial,physical_clock_not_reset=True,native_Human_state_not_assigned=True))
        it=c.Campaign(condition);ident='REPR_parent';c.dispatch(ident,kind='SECOND_PERSISTENT_REPETITION_RETRY_PARENT',condition=condition)
        try:
            metric=invoke(ident,it)
            if it.child is not None:os._exit(0)
            assert metric['task_valid'];fix_parent_accounting(ident,initial['physical_time_s'])
            mh.event('END',ident,returncode=0,joined=True,task_valid=True)
            am.measure(ident);gate=c.bc.compare_raw(P/'source/results'/ident,P/'source/results/REPR_B');put('REPR_PARENT_GATE.json',gate);assert gate['status']=='PASS'
            end=stamp();assert initial['plant_identity']==end['plant_identity'] and initial['updater_identity']==end['updater_identity']
            put('REPR_DONE.json',dict(status='PASS',unix=time.time(),all_children_joined=True,rows=it.results,first_task=name,initial=initial,end=end,actual_online_updates=1,feedback=memory,inter_rep_boundary_native_steps=round((boundary['end_time_s']-boundary['start_time_s'])/rt.NOMINAL_PHYSICS_DT_S)))
            print('ACTUAL_REPETITION_RETRY_PILOT_COMPLETE',flush=True)
        except BaseException as e:
            if it.child is not None:
                put('reports/REPR_'+it.child['kind']+'_ERROR.json',dict(error=str(e),traceback=traceback.format_exc()));os._exit(1)
            if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(e),actual_new_native_steps=round((stamp()['physical_time_s']-initial['physical_time_s'])/rt.NOMINAL_PHYSICS_DT_S))
            raise
    except BaseException as e:
        if not any(r['event']=='END' and r['id']==name for r in mh.records()):mh.event('END',name,returncode=1,joined=True,error=str(e))
        put('audit/REPETITION_RETRY_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time(),continuous_state=stamp()));raise
    finally:signal.alarm(0);put('audit/REPETITION_RETRY_WORKER_EXIT.json',dict(pid=os.getpid(),unix=time.time()))
if __name__=='__main__':main()
