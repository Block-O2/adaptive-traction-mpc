from pathlib import Path
import sys,json,gzip,time,csv
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/adaptive_human_online_interface_v1'
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):sys.path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_reference import realize,validate_online_activation,OnlineReferenceOwner
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import SessionClearanceContract,_jsonable
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1,RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedule,_quintic_coefficients
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanBeliefV22
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.task import TaskPhase
def load(p):
    if not p.exists():p=Path(str(p)+'.gz')
    return json.loads(gzip.open(p,'rt').read() if p.suffix=='.gz' else p.read_text())
def save(name,x):(D/name).write_text(json.dumps(_jsonable(x),indent=2,allow_nan=False)+'\n')
def context(condition):
    matrix=load(S/'docs/coordination_pacing_exploration_v1/CONDITION_MATRIX.json');c=next(x for x in matrix['conditions'] if x['id']==condition)
    case=load(R/c['case_path']);truth,geometry,spec,_=hidden_plant(case)
    root=S/'results/best_known_coordination_search_v2/runs'/f'A_{condition}_NATIVE_baseline_0';rep=next(root.glob('rep_*'))
    summary=load(rep/'summary.json');b=summary['commissioning']['handoff_belief'];g=b['effective_geometry']
    g=PlanarCuffGeometry(**{k:np.array(v) if isinstance(v,list) else v for k,v in g.items()})
    belief=AdaptiveHumanBeliefV22(g,np.array(b['beta']),np.array(b['state_residual_weights_nm']),b['sequence'],b['dynamics_sample_count'],b['accepted_beta_update_count'],b['residual_update_count'],rom_human=spec_to_prior(case))
    clearance=CombinedRigidTableClearanceV1(SessionClearanceContract(g),RigidTableReferenceEnvelopeV1(g))
    return case,spec,belief,clearance,load(rep/'runtime_artifacts.json')
def spec_to_prior(case):
    from traction_mpc_stage5.human import STAGE5_HUMAN
    from traction_mpc_stage5.high_rom_v1 import deployable_prior
    return deployable_prior() if 'research_model' in case else STAGE5_HUMAN
def original(artifact,phase,goal):
    ds=[x for x in artifact['task_decisions'] if x.get('phase')==phase and 'evaluations' in x];d=ds[0]
    s=next(x['schedule'] for x in d['evaluations'] if x['label']==d['executed_label'])
    c=HumanWaypointCandidate(label='inherited_probe',phase=TaskPhase(phase),phase_goal_rad=goal,q_waypoint_rad=np.array(s['target_q_rad']),dq_waypoint_rad_s=np.array(s['target_dq_rad_s']))
    q,v=np.array(s['start_q_rad']),np.array(s['start_dq_rad_s'])
    return QuinticHumanWaypointSchedule(candidate=c,start_q_rad=q,start_dq_rad_s=v,duration_s=s['duration_s'],coefficients=_quintic_coefficients(q,v,c.q_waypoint_rad,c.dq_waypoint_rad_s,s['duration_s']),**{k:np.array(s[k]) for k in ['maximum_reference_velocity_rad_s','maximum_reference_acceleration_rad_s2','maximum_causal_20ms_reference_acceleration_rad_s2','maximum_nominal_tracking_acceleration_rad_s2']},nominal_completion_time_s=s['nominal_completion_time_s'],minimum_reference_shank_clearance_m=s['minimum_reference_shank_clearance_m'],reference_period_s=s['reference_period_s'])
def limits(spec):
    v=np.asarray(spec.task_joint_velocity_limit_rad_s)*.6;a=np.asarray(spec.task_joint_acceleration_limit_rad_s2)*.5
    return dict(max_velocity=v,max_acceleration=a,max_jerk=a/.02)
def main():
    rows=[];adversarial=[]
    for condition in ('sync_120','low_ordinary_early'):
        case,spec,b,c,artifact=context(condition);lim=limits(spec)
        for phase in ('OUTBOUND','RETURN'):
            goal=np.array(spec.outbound_goal_target_rad if phase=='OUTBOUND' else spec.start_return_target_rad);old=original(artifact,phase,goal)
            for period in (.005,.01,.02,.05):
                at=old.sample(period);state=(at.q_rad,at.dq_rad_s,at.ddq_rad_s2)
                row=dict(condition=condition,phase=phase,command_period_s=period,old_initial_acceleration_rad_s2=at.ddq_rad_s2,old_endpoint_deferred_effect_s=old.duration_s)
                try:
                    new=realize(state,old.candidate.q_waypoint_rad,spec=spec,phase=TaskPhase(phase),**lim)
                    cert=validate_online_activation(schedule=new,owned_state=state,belief=b,clearance=c,phase=TaskPhase(phase),remaining_s=spec.phase_timeout_s)
                    first=new.sample(0.);jump=[np.max(np.abs(x-y)) for x,y in zip((first.q_rad,first.dq_rad_s,first.ddq_rad_s2),state)]
                    same=new.sample(period);owner=OnlineReferenceOwner(state,epoch_s=period,initial_schedule=new)
                    r=owner.offer(old.candidate.q_waypoint_rad,received_s=period,ready_s=period,requested_s=period,spec=spec,phase=TaskPhase(phase),remaining_s=spec.phase_timeout_s,belief=b,clearance=c,**lim)
                    before=owner.sample(2*period);repeat=owner.offer(old.candidate.q_waypoint_rad,received_s=2*period,ready_s=2*period,requested_s=2*period,spec=spec,phase=TaskPhase(phase),remaining_s=spec.phase_timeout_s,belief=b,clearance=c,**lim);after=owner.sample(2*period)
                    row.update(C2_jumps=jump,C2_pass=bool(max(jump)<=1e-10),activation_validation=cert,new_status=r['status'],same_target_status=repeat['status'],same_target_acceleration_jump_rad_s2=float(np.max(np.abs(before.ddq_rad_s2-after.ddq_rad_s2))),new_initial_ddq_rad_s2=first.ddq_rad_s2,new_duration_s=new.duration_s)
                    # Replay a changed intention in every original/extended case,
                    # separately from the exact identical-target preservation test.
                    changed=owner.offer(before.q_rad.copy(),received_s=2*period,ready_s=2*period,requested_s=2*period,spec=spec,phase=TaskPhase(phase),remaining_s=spec.phase_timeout_s-period,belief=b,clearance=c,**lim)
                    effect=changed.get('first_reference_effect_s')
                    effect_verified=False
                    if effect is not None:
                        got=owner.sample(effect);prior=new.sample(effect-period)
                        effect_verified=bool(max(np.max(np.abs(x-y)) for x,y in zip((got.q_rad,got.dq_rad_s,got.ddq_rad_s2),(prior.q_rad,prior.dq_rad_s,prior.ddq_rad_s2)))>1e-10)
                    row.update(changed_command=changed,changed_effect_sample_verified=effect_verified,changed_effect_before_original_endpoint=bool(effect is not None and effect<old.duration_s),all_blocker_criteria_pass=bool(cert['feasible'] and max(jump)<=1e-10 and repeat['status']=='IDENTICAL_CONTINUATION' and row['same_target_acceleration_jump_rad_s2']==0. and changed['status']=='ACCEPTED' and changed['activation_validation']['C2'] and effect_verified and effect<old.duration_s))
                    if cert['feasible']:
                        times=np.linspace(0,new.duration_s,1001);samples=[new.sample(float(t)) for t in times];v=np.array([s.dq_rad_s for s in samples]);a=np.array([s.ddq_rad_s2 for s in samples]);j=np.diff(a,axis=0)/np.diff(times)[:,None]
                        row.update(sampled_max_velocity_rad_s=np.max(np.abs(v),axis=0),sampled_max_acceleration_rad_s2=np.max(np.abs(a),axis=0),sampled_max_jerk_rad_s3=np.max(np.abs(j),axis=0),limits={k:v.tolist() for k,v in lim.items()})
                except (ValueError,RuntimeError) as e:row.update(new_status='REJECTED',reason=str(e),C2_pass=False)
                rows.append(row)
            # Commands originate from the same moving reference state for comparison.
            at=old.sample(min(.2,old.duration_s/2));state=(at.q_rad,at.dq_rad_s,at.ddq_rad_s2);target=old.candidate.q_waypoint_rad
            tests={'identical':target,'small_forward':target+.003,'larger_forward':target+.03,'reverse':at.q_rad-.01,'alternating':target+np.array([.02,-.02]),'hip_to_knee_switch':target+np.array([-.04,.04]),'outside_short_horizon':goal,'near_ROM':np.asarray(spec.q_bounds_rad)[:,1]-.001,'outside_ROM':np.asarray(spec.q_bounds_rad)[:,1]+.1,'late':at.q_rad-.01,'missing':None}
            for name,targ in tests.items():
                seed=realize(state,target,spec=spec,phase=TaskPhase(phase),**lim)
                owner=OnlineReferenceOwner(state,epoch_s=0.,initial_schedule=seed)
                init=owner.offer(target,received_s=0.,ready_s=0.,requested_s=0.,spec=spec,phase=TaskPhase(phase),remaining_s=spec.phase_timeout_s,belief=b,clearance=c,**lim)
                if targ is None:r=dict(status='MISSING_CONTINUE_CERTIFIED',has_certified_continuation=owner.certificate is not None)
                elif init['status'] not in ('ACCEPTED','IDENTICAL_CONTINUATION'):r=dict(status='NO_INITIAL_CERTIFIED_CONTINUATION',initial=init)
                else:
                    ready=.027 if name=='late' else .02
                    before=owner.sample(.02)
                    r=owner.offer(targ,received_s=.02,ready_s=ready,requested_s=.02,spec=spec,phase=TaskPhase(phase),remaining_s=spec.phase_timeout_s-.02,belief=b,clearance=c,**lim)
                    if name=='late':
                        retained=owner.sample(.025);expected=owner.owned_segments[0][1].sample(.025)
                        r['prefix_retained']=bool(np.max(np.abs(retained.q_rad-expected.q_rad))<=1e-10)
                adversarial.append(dict(condition=condition,phase=phase,test=name,result=r))
    save('ONLINE_INTERFACE_BLOCKER_RETEST.json',dict(scope='reference_and_activation_certification_only_not_physical',rows=rows,original_eight_reconstructed=True,extended_periods_s=[.005,.01],pass_count=sum(x.get('all_blocker_criteria_pass',False) for x in rows)))
    save('ONLINE_INTERFACE_ADVERSARIAL_TEST.json',dict(scope='reference_and_certification',tests=adversarial))
    save('ONLINE_INTERFACE_RATE_TEST.json',dict(rows=rows,physical_response_latency='not measured by reference probes',host_latency='separately profiled certification; no hardware realtime claim'))
    with (D/'ONLINE_INTERFACE_RATE_TEST.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['condition','phase','command_period_s','C2_pass','new_status','same_target_status','same_target_acceleration_jump_rad_s2','old_endpoint_deferred_effect_s']);writer.writeheader();writer.writerows({k:x.get(k) for k in writer.fieldnames} for x in rows)
    print(json.dumps({'cases':len(rows),'certified_pass':sum(x.get('activation_validation',{}).get('feasible',False) for x in rows),'adversarial':len(adversarial)}))
if __name__=='__main__':main()
