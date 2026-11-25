"""Replay owned B references on the original planner/model; never step a plant."""
from env_rt2 import *
import time,copy
from collections import Counter
import numpy as np,mujoco
def forbidden(*a,**kw): raise AssertionError('physical stepping in software test')
for k in ('mj_step','mj_step1','mj_step2'):setattr(mujoco,k,forbidden)
from fixtures import native_context
from offer import offer
from reactive import *
from native_rt2 import validate_current
from traction_mpc_stage5.full3d_adaptive_integration_v1.terminal_reference import TerminalSetHumanWaypointPlannerV1
from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCConfigV1
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanWaypointHWMPCV22
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import FallbackLatch,prepare_decision
from traction_mpc_stage5.task import TaskPhase

def reconstruct():
    a=read(BASE/'runtime_artifacts.json')
    w=a['wall_physics']
    z=np.load(BASE/'trace.npz')
    stamps=z['time_s'];forces=z['physical_cuff_force_world_n'];moments=z['physical_cuff_moment_world_nm']
    samples={round(r['sample_time_s'],7):r for r in w['causal_sensor_estimates']}
    receipts=w['command_receipts']
    b,spec,sch,_=native_context()
    assert np.array_equal(b.beta,read(BASE/'summary.json')['commissioning']['handoff_belief']['beta'])
    options=read(ROOT/read(CONTRACT)['options_path'])
    sch.use_duration_lower_bound=options.get('duration_lower_bound',False)
    prev=np.zeros(2);previous=None
    for i,d in enumerate(a['task_decisions']):
        phase=TaskPhase(d['phase'])
        if phase is not previous:prev=np.zeros(2)
        planner=TerminalSetHumanWaypointPlannerV1(spec,copy.deepcopy(sch),HumanWaypointFeedbackMPCConfigV1(mechanics_duration_search=True))
        for k in ('robust_terminal_center','robust_hold_reference','causal_tracking_offset_clearance'):setattr(planner,k,options.get(k,False))
        planner.pass_through_waypoints=True;planner.safe_fallback_enabled=True
        planner.tracking_reference_snapshot=copy.deepcopy(next(e['execution_screen']['causal_tracking_offset_clearance']['reference_snapshot'] for e in d['evaluations'] if e['feasible']))
        planner.previous_executed_delta_q_rad=prev.copy()
        dec=AdaptiveHumanWaypointHWMPCV22(planner).decide(belief=b,current_deployable_state=np.array(d['deployable_state_rad_rad_s']),current_reference_state=np.array(d['reference_state_rad_rad_s']),phase=phase,phase_elapsed_s=d['phase_elapsed_s'],phase_remaining_s=d['phase_remaining_s'])
        path=dec.executed.schedule
        assert path.record()==next(e['schedule'] for e in d['evaluations'] if e['label']==d['executed_label'])
        prev=np.array(d['executed_action_delta_q_rad']);previous=phase
        t0=d['actual_schedule_start_physics_s']
        stop=a['task_decisions'][i+1]['actual_schedule_start_physics_s'] if i+1<len(a['task_decisions']) else float('inf')
        rr=[r for r in receipts if t0-1e-9<=r['start_physics_s']<stop-1e-9 and r.get('reference_progress')]
        for k,r in enumerate(rr[::8]):
            t=r['source_sample_time_s'];s=r['reference_progress']['selected_progress_s']
            splice=(d.get('rolling_composite') or {}).get('splice_elapsed_s',0.)
            if s<splice-1e-10:continue
            s=max(0.,s-splice)
            owned=path.sample(s)
            if not np.allclose(owned.q_rad,r['q_ref_rad'],rtol=0,atol=1e-10) or not np.allclose(owned.dq_rad_s,r['dq_ref_rad_s'],rtol=0,atol=1e-10):continue
            e=samples[round(t,7)];j=np.argmin(abs(stamps-t));assert abs(stamps[j]-t)<1e-9
            elapsed=d['phase_elapsed_s']+t-d['request_measurement_timestamp_s']
            env=dict(belief=b,spec=spec,phase=phase,request_phase=phase,remaining=spec.phase_timeout_s-elapsed,elapsed=elapsed,
                clearance=planner.scheduler.clearance_evaluator,sequence=b.sequence,stamp=t,x=np.array(e['estimated_state']),a=np.array(e['human_motion_acceleration_rad_s2']),
                wrench=np.r_[forces[j],moments[j]],owned=owned,valid=e['human_motion_valid'],now=time.monotonic_ns,
                vmax=sch.reference_velocity_fraction*np.array(spec.task_joint_velocity_limit_rad_s),
                amax=sch.reference_acceleration_fraction*np.array(spec.task_joint_acceleration_limit_rad_s2),
                span=np.asarray(spec.outbound_goal_target_rad)-spec.start_return_target_rad,sign=-1 if phase is TaskPhase.RETURN else 1)
            yield i,k,path,s,planner,dec,env

def main():
    rows=[];faults={};identity=0
    for i,k,path,s,p,d,e in reconstruct():
        for kind in ('I','II','III'):
            e['capture']=e['recheck']=time.monotonic_ns() # launch a timed offline calculation; archived source stamps never used for live actuation
            z=offer(kind,path,s,p,d,e,enabled=False);assert z['native'] is None and z['status']=='retain'
            identity+=1
            e['capture']=e['recheck']=time.monotonic_ns()
            r=offer(kind,path,s,p,d,e)
            row={key:value for key,value in r.items() if key not in ('native','validation')}
            rows.append(dict(i=i,k=k,phase=e['phase'].value,s=s,physical_stamp=e['stamp'],kind=kind,**row))
            if i==0 and k==0:
                stale=dict(e,capture=e['capture']-100_000_000)
                changed=dict(e,sequence=e['sequence']-1)
                empty=dict(e,vmax=np.array([-1.,-1.]))
                pred=observe(e['belief'].human_model(),e['x'],e['wrench'],e['owned'],e['vmax'],e['amax'],e['span'],e['sign'])
                velocity=path.sample(.04).dq_rad_s
                fun,action=target(kind,pred,path,s,.04,mobile=np.array([False,True]))
                f=dict(timeout=offer(kind,path,s,p,d,stale)['reason'],model=offer(kind,path,s,p,d,changed)['reason'],
                       held_axis_delta_v=float(fun(.04)[1][0]-velocity[0]) if kind!='I' else None)
                for name,patch in [('state',dict(x=np.r_[20.,20.,0.,0.])),('version',dict(version='changed')),('expiry',dict(capture=time.monotonic_ns()-101_000_000))]:
                    start=time.monotonic_ns()
                    ee=dict(e,capture=start,recheck=start);ee.update(patch)
                    f[name]=validate_current(prepare_decision(d,p,e['belief']).executed.schedule,ee)['feasible']
                latch=FallbackLatch(None);f['expired_primary']=latch.choose_primary(validated=True,age_ns=100_000_000)
                f['braking_latched']=latch.commit() and not latch.choose_primary(validated=True,age_ns=0)
                if kind=='III':
                    try:QP().action(Input(pred.excess,pred.inertia,pred.torque_scale,pred.lag,-pred.vmax,pred.amax,pred.span,pred.sign),velocity,.04,np.ones(2,bool),np.zeros(2))
                    except ValueError as exc:f['empty_qp']=str(exc)
                faults[kind]=f
    save(HERE/'software_aligned.json',dict(rows=rows,identity=identity,faults=faults,physics_steps=0))
    print({k:Counter(r['reason'] for r in rows if r['kind']==k) for k in ('I','II','III')})
if __name__=='__main__':main()
