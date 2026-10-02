"""Diagnostic only: authoritative schedules and splice classes, no plant actuation."""
from pathlib import Path
import sys, json, gzip, hashlib, inspect, resource
from dataclasses import replace
from datetime import datetime, timezone
import numpy as np

R=Path('/home/hank/coding/adaptive-traction-mpc-learning')
S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/direct_rl_expert_v1'
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):
    sys.path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedule, _quintic_coefficients
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import TaskPhase
from traction_mpc_stage5.full3d_adaptive_integration_v1.rolling_suffix_splice import RollingSuffixCompositeSchedule
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import validate_activation

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    if p.suffix=='.gz':
        with gzip.open(p,'rt') as f:return json.load(f)
    return json.loads(p.read_text())
def sample_schedule(s,phase_goal):
    c=HumanWaypointCandidate(label='frozen_source_reference',phase=TaskPhase(s['phase']),phase_goal_rad=np.array(phase_goal),q_waypoint_rad=np.array(s['target_q_rad']),dq_waypoint_rad_s=np.array(s['target_dq_rad_s']))
    q,dq=np.array(s['start_q_rad']),np.array(s['start_dq_rad_s'])
    return QuinticHumanWaypointSchedule(candidate=c,start_q_rad=q,start_dq_rad_s=dq,duration_s=s['duration_s'],coefficients=_quintic_coefficients(q,dq,c.q_waypoint_rad,c.dq_waypoint_rad_s,s['duration_s']),**{k:np.array(s[k]) for k in ['maximum_reference_velocity_rad_s','maximum_reference_acceleration_rad_s2','maximum_causal_20ms_reference_acceleration_rad_s2','maximum_nominal_tracking_acceleration_rad_s2']},nominal_completion_time_s=s['nominal_completion_time_s'],minimum_reference_shank_clearance_m=s['minimum_reference_shank_clearance_m'],reference_period_s=s['reference_period_s'],feasibility_semantics=s['feasibility_semantics'],continuous_clearance_certificate=s.get('continuous_clearance_certificate'))

matrix=load(S/'docs/coordination_pacing_exploration_v1/CONDITION_MATRIX.json')
rows=[]
for condition_id in ('sync_120','low_ordinary_early'):
    condition=next(x for x in matrix['conditions'] if x['id']==condition_id)
    case=load(R/condition['case_path'])
    root=S/'results/best_known_coordination_search_v2/runs'/f'A_{condition_id}_NATIVE_baseline_0'
    result=load(root/'rollout_result.json')
    assert result['status']=='VALID'
    artifact_path=next(root.glob('rep_*/runtime_artifacts.json*'))
    artifact=load(artifact_path)
    for phase in ('OUTBOUND','RETURN'):
        decisions=[d for d in artifact['task_decisions'] if d.get('phase')==phase and 'evaluations' in d]
        selected=next(x for x in decisions[0]['evaluations'] if x['label']==decisions[0]['executed_label'])
        goal=np.radians(case['task']['goal_deg'] if phase=='OUTBOUND' else case['task']['start_deg'])
        original=sample_schedule(selected['schedule'],goal)
        for period in (.02,.05):
            assert original.duration_s>period
            boundary=original.sample(period)
            # Same target is sufficient: even reissuing it mid-segment resets ddq.
            suffix=replace(original,start_q_rad=boundary.q_rad,start_dq_rad_s=boundary.dq_rad_s,coefficients=_quintic_coefficients(boundary.q_rad,boundary.dq_rad_s,original.candidate.q_waypoint_rad,original.candidate.dq_waypoint_rad_s,original.duration_s))
            new=suffix.sample(0.)
            error=np.max(np.abs(new.ddq_rad_s2-boundary.ddq_rad_s2))
            try:
                RollingSuffixCompositeSchedule(original,period,suffix,1)
                outcome='ACCEPTED'
            except ValueError as e:outcome=str(e)
            endpoint=original.sample(original.duration_s)
            legal_suffix=replace(suffix,start_q_rad=endpoint.q_rad,start_dq_rad_s=endpoint.dq_rad_s,coefficients=_quintic_coefficients(endpoint.q_rad,endpoint.dq_rad_s,original.candidate.q_waypoint_rad,original.candidate.dq_waypoint_rad_s,original.duration_s))
            deferred=RollingSuffixCompositeSchedule(original,period,legal_suffix,2)
            times=np.arange(period,original.duration_s-1e-10,period)
            accelerations=np.array([original.sample(float(t)).ddq_rad_s2 for t in times])
            rows.append({'condition_id':condition_id,'phase':phase,'policy_period_s':period,'source_artifact':str(artifact_path.relative_to(R)),'source_artifact_sha256':sha(artifact_path),'source_result_sha256':sha(root/'rollout_result.json'),'source_status':'VALID','source_J_F_task_n_s':result['J_F_task_n_s'],'source_duration_s':original.duration_s,'midpoint_q_error_rad':float(np.max(np.abs(new.q_rad-boundary.q_rad))),'midpoint_dq_error_rad_s':float(np.max(np.abs(new.dq_rad_s-boundary.dq_rad_s))),'midpoint_old_ddq_rad_s2':boundary.ddq_rad_s2.tolist(),'replacement_initial_ddq_rad_s2':new.ddq_rad_s2.tolist(),'C2_acceleration_jump_rad_s2':float(error),'midsegment_C2_valid':bool(error<=1e-10),'authoritative_splice_outcome':outcome,'endpoint_splice_accepted':True,'endpoint_deferred_effect_s':deferred.splice_elapsed_s,'midsegment_zero_ddq_reset_invalid_fraction':float(np.mean(np.max(np.abs(accelerations),axis=1)>1e-10)),'probe_scope':'reference/safety compatibility only; no new physical run or validated candidate'})

assert len(rows)==8
assert all(not x['midsegment_C2_valid'] and x['authoritative_splice_outcome']=='rolling suffix is not C2 at the original prefix endpoint' and x['endpoint_splice_accepted'] for x in rows)
source=inspect.getsource(validate_activation)
assert 'np.max(np.abs(first.ddq_rad_s2)) <= 1e-10' in source
assert 'np.max(np.abs(first.ddq_rad_s2-reference_ddq)) <= 1e-10' in source
report={'status':'EXPANDED_PERIODIC_ACTION_INTERFACE_INCOMPATIBLE','created_utc':datetime.now(timezone.utc).isoformat(),'rows':rows,'probe_assertions_pass':True,'tested_replacements':'same target reissued at period, authoritative q/dq quintic constructor; legal endpoint control included','diagnostic_peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'not_a_physical_or_learning_result':True,'interpretation':'Existing zero-start-ddq scheduler cannot make an immediate C2 midsegment replacement. Existing rolling suffix splices only at original endpoint. General C2 polynomials with nonzero ddq also violate validate_activation zero-start-ddq predicate. This demonstrates a representation-specific integration incompatibility, not impossibility of safe direct RL or measured closed-loop rejection rate.','needed_change':'Versioned acceleration-aware reference/action safety interface, full coefficient-aware clearance/mechanics, midsegment activation and certified fallback; validate before Direct RL campaign. Do not weaken threshold or silently defer every action to old endpoints.'}
(D/'SAFETY_ACTION_COMPATIBILITY_PROBE.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':report['status'],'rows':len(rows),'peak_RSS_KiB':report['diagnostic_peak_RSS_KiB'],'range_C2_jump_rad_s2':[min(x['C2_acceleration_jump_rad_s2'] for x in rows),max(x['C2_acceleration_jump_rad_s2'] for x in rows)],'range_deferred_effect_s':[min(x['endpoint_deferred_effect_s'] for x in rows),max(x['endpoint_deferred_effect_s'] for x in rows)]}))
