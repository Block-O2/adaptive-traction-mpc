"""Read-only model feasibility gate on retained accepted pass-through endpoints."""
import sys,json,math,hashlib
from pathlib import Path
from dataclasses import replace
import numpy as np
ROOT=Path(__file__).resolve().parents[4]; STAGE=ROOT/'stages/stage5_personalized_motion_learning';DOC=Path(__file__).resolve().parent
for p in ('stages/stage5_personalized_motion_learning/src','stages/stage4_adaptive_control/src','stages/stage3_full3d/src'):sys.path.insert(0,str(ROOT/p))
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import SessionClearanceContract
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1,RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanBeliefV22,AdaptiveMechanicsScreenV22
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.high_rom_v1 import deployable_prior,CONFIG_PATH
from traction_mpc_stage5.task import load_goal_task_spec,TaskPhase

def main():
    freeze=json.loads((STAGE/'docs/simulation_research_baseline_v1/PREREGISTRATION.json').read_text())
    cases=[(r,'representative') for r in freeze['representative'] if r['plant']=='high_rom']
    cases += [(next(r for r in freeze['development49'] if r['id']=='high_rom_function_fresh_03_v1'),'development49')]
    results=[]
    for row,group in cases:
        case=json.loads((ROOT/row['case']).read_text());path=STAGE/'results/simulation_research_baseline_v1'/group/row['id']/'summary.json'
        summary=json.loads(path.read_text());spec=replace(load_goal_task_spec(CONFIG_PATH),start_return_target_rad=tuple(np.radians(case['task']['start_deg'])),outbound_goal_target_rad=tuple(np.radians(case['task']['goal_deg'])))
        for rec in summary['learning_records']:
            selected=rec['selected_plan'];sch=selected['schedule'];v=np.asarray(sch['target_dq_rad_s'])
            if not np.any(abs(v)>1e-12):continue
            b=rec['adaptive_state'];g=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in b['effective_geometry'].items()})
            kw={k:b[k] for k in ('beta','state_residual_weights_nm','sequence','dynamics_sample_count','accepted_beta_update_count','residual_update_count','residual_limit_nm')}
            belief=AdaptiveHumanBeliefV22(geometry=g,rom_human=deployable_prior(),**kw)
            clearance=CombinedRigidTableClearanceV1(SessionClearanceContract(g),RigidTableReferenceEnvelopeV1(g),True)
            scheduler=QuinticHumanWaypointSchedulerV1(spec,belief.human_model(),clearance_evaluator=clearance,require_continuous_nonpenetrating_path=True,preserve_task_endpoint_clearance_floor=True,reference_velocity_fraction=.5,reference_acceleration_fraction=.25)
            T=max(.005,math.ceil((1.5*np.max(abs(v)/(np.asarray(spec.task_joint_acceleration_limit_rad_s2)*.25))-1e-12)/.005)*.005)
            phase=TaskPhase(sch['phase']);goal=spec.start_return_target_rad if phase is TaskPhase.RETURN else spec.outbound_goal_target_rad
            decision=summary['decisions'][rec['decision_index']]
            offset=np.asarray(selected['execution_screen']['causal_tracking_offset_clearance']['position_error_rad'])
            out={'case':row['id'],'decision_index':rec['decision_index'],'phase':phase.value,'duration_s':T,'source_belief_sequence':belief.sequence,'summary_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'attempts':[]}
            # Finite original bridge reference grid; latest strictly pre-endpoint feasible fork.
            for step in range(7,-1,-1):
                t=step*.005;q0=np.asarray(sch['target_q_rad'])+t*v;qstop=q0+.5*T*v
                cand=HumanWaypointCandidate('retained_escape',phase,np.asarray(goal),qstop,np.zeros(2))
                a={'commit_bridge_progress_s':t,'start_q_deg':np.degrees(q0).tolist(),'stop_q_deg':np.degrees(qstop).tolist()}
                try:
                    stop=scheduler.plan_fixed_duration_reference_contract(current_q_hat_rad=q0,current_dq_hat_rad_s=v,candidate=cand,duration_s=T,phase_elapsed_s=decision['phase_elapsed_s']+sch['duration_s']+t)
                    mechanics=AdaptiveMechanicsScreenV22().evaluate(belief,cand,stop)
                    shifted=stop.coefficients.copy();shifted[:,0]+=offset
                    lower=clearance.certified_minimum(shifted,T)
                    a.update(feasible=bool(mechanics['feasible'] and lower>=0),mechanics=mechanics,shifted_clearance_lower_m=lower,nominal_clearance_lower_m=stop.minimum_reference_shank_clearance_m)
                except (ValueError,RuntimeError) as exc:a.update(feasible=False,reason=str(exc))
                out['attempts'].append(a)
                if a['feasible']:break
            out['feasible']=out['attempts'][-1]['feasible'];results.append(out)
    output={'category':'retained_deployable_model_analysis_not_dynamic_validation','question':'Does the minimal zero-acceleration constant-bridge fork admit a prevalidated finite stop for retained accepted endpoints?','count':len(results),'feasible':sum(r['feasible'] for r in results),'rows':results}
    (DOC/'RETAINED_ESCAPE_GATE.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:output[k] for k in ('count','feasible')}))
    for r in results:
        if not r['feasible']:print(json.dumps(r))
if __name__=='__main__':main()
