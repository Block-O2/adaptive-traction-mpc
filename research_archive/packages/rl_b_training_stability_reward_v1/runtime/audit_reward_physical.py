"""Independent training-wrapper reward reconstruction from saved causal ticks."""
from pathlib import Path
import argparse,json,math
import numpy as np
def audit(run,episode_index=1,transition_index=0):
    ep=run/f'env/episode_{episode_index:04d}';metrics=json.loads((ep/'episode_summary.json').read_text())
    spec=json.loads((ep/'public_reward_contract.json').read_text());z=np.load(run/f'transitions_{transition_index}.npz')
    start=spec['start_return_target_rad'];goal=spec['outbound_goal_target_rad']
    def phi(row):
        q=row['online_estimated_state'][:2]
        clip=lambda x:max(0.,min(1.,x))
        if row['phase']=='OUTBOUND':return min(clip((q[i]-start[i])/(goal[i]-start[i])) for i in range(2))
        if row['phase']=='HOLD':return 1.+min(1.,row['hold_elapsed_s']/spec['hold_duration_s'])
        if row['phase']=='RETURN':return 2.+min(clip((goal[i]-q[i])/(goal[i]-start[i])) for i in range(2))
        if row['phase']=='COMPLETE':return 3.
        raise ValueError('UNEXPECTED_TASK_PHASE')
    norm=lambda x:math.sqrt(sum(v*v for v in x))
    force=moment=variation=0.;previous=None;first=None;last=None;tick_count=0
    phases=[];monotonic=True;zero_time=[];zero_valid=True
    with (ep/'online_tick_evidence.jsonl').open() as f:
        for line in f:
            row=json.loads(line);tick_count+=1
            if first is None:first=row
            if not phases or phases[-1]!=row['phase']:phases.append(row['phase'])
            if previous is not None:
                dt=row['task_s']-previous['task_s'];monotonic &=dt>=0
                if dt==0:
                    sensors_same=all(row[k]==previous[k] for k in ('online_estimated_state','measured_force_world_n','measured_moment_world_nm'))
                    terminal_notification=(row['phase']=='ABORTED' and previous['phase']!='ABORTED' and
                        metrics['status']=='ABORTED' and not metrics['success'] and
                        bool(metrics.get('abort_reason')) and abs(row['task_s']-metrics['task_s'])<1e-10 and
                        (ep/'reward_v2_contract.json').exists())
                    same=sensors_same and (terminal_notification or
                        (row['phase']==previous['phase'] and phi(row)==phi(previous)))
                    zero_valid &=same
                    zero_time.append({'task_s':row['task_s'],'identical_physical_sensor_state':sensors_same,
                        'valid_same_boundary_notification':same,'declared_v2_failure_terminal':terminal_notification,
                        'phase_from':previous['phase'],'phase_to':row['phase'],
                        'internal_phase_elapsed_delta_s':row['phase_elapsed_s']-previous['phase_elapsed_s']})
                force+=norm(previous['measured_force_world_n'])*dt;moment+=norm(previous['measured_moment_world_nm'])*dt
                if dt>0:
                    variation+=sum(((row['online_estimated_state'][2+i]-previous['online_estimated_state'][2+i])/dt/math.radians(spec['acceleration_normalization_deg_s2'][i]))**2 for i in range(2))/2.*dt
            previous=last=row
    success=metrics['success'];final_phi=3. if success else (0. if (ep/'reward_v2_contract.json').exists() else phi(last))
    parts={'progress':spec['progress_weight']*(final_phi-phi(first)),
        'completion':spec['completion_bonus'] if success else spec['failure_penalty'],
        'force':-spec['force_weight']*force/100.,'variation':-spec['variation_weight']*variation}
    if not success and (ep/'pilot_reward_contract.json').exists():
        observed_cost=-parts['force']-parts['variation']
        floor=1.5
        if (ep/'stage2_reward_contract.json').exists():floor=json.loads((ep/'stage2_reward_contract.json').read_text())['reward']['failure_cost_floor']
        parts['completion']-=max(0.,floor-observed_cost)
    diff={k:parts[k]-metrics['reward_totals'][k] for k in parts}
    checks={'finite_transitions':all(np.isfinite(z[k]).all() for k in ('obs','actions','rewards','next_obs')),
        'actor_41d':z['obs'].shape[1:]==(41,), 'bounded_actions':bool(np.all(np.abs(z['actions'])<=1)),
        'only_final_transition_terminal':bool(z['terminated'][-1] and not z['terminated'][:-1].any()),
        'finite_horizon_no_timeout_bootstrap':bool(not z['truncated'].any()),'absorbing_terminal':bool(np.all(z['next_obs'][-1]==0)),
        'nondecreasing_online_callback_time':monotonic,'zero_duration_notifications_preserve_sensors_and_potential':zero_valid,
        'reward_parts_independent':max(abs(x) for x in diff.values())<1e-8,
        'reward_sum_independent':abs(float(z['rewards'].sum())-sum(parts.values()))<1e-8,
        'force_integral_independent':abs(force-metrics['force_integral_N_s'])<1e-8,
        'moment_integral_independent':abs(moment-metrics['moment_integral_Nm_s'])<1e-8,
        'task_duration_native_grid':abs(metrics['task_native_steps']*.00025-metrics['task_s'])<1e-7,
        'completion_semantics':(metrics['status']=='COMPLETE')==success and (not success or phases==['OUTBOUND','HOLD','RETURN'])}
    return {'category':'INDEPENDENT_REWARD_AND_TERMINAL_RECOMPUTATION_REAL_PHYSICS','run':str(run),'pass':all(checks.values()),'checks':checks,
        'status':metrics['status'],'abort_reason':metrics['abort_reason'],'success':success,'task_s':metrics['task_s'],'phases':phases,
        'tick_count':tick_count,'zero_duration_notifications':zero_time,'reward_parts':parts,'reward_difference':diff,'sum_reward':float(z['rewards'].sum()),'J_F':force,'J_M':moment,'variation_integral':variation,
        'callback_time_note':'An original fallback may notify the same physical boundary twice. Zero-duration notifications contribute no force/variation time and must preserve sensor state and reward potential. Native integration time is audited strictly separately.',
        'limitations':'Full physical safety and command ownership audited separately; these are developer validation episodes, not heldout tests.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--out',required=True);a=p.parse_args();out=audit(a.run);Path(a.out).write_text(json.dumps(out,indent=2));print(json.dumps(out))
