"""Frozen-reward replay audit, evidence cross-checks and root-cause synthesis."""
from inventory_v1 import *
import csv, shutil, collections
def run():
    primary=json.loads((D/'ALL_22_EVALUATION_AUDIT.json').read_text())
    early=json.loads((D/'EARLY_AND_MEMORY_EVALUATION_AUDIT.json').read_text())
    all_eval=primary+early;health=json.loads((D/'SAC_HEALTH_SNAPSHOTS.json').read_text())
    replay=json.loads((D/'REPLAY_COVERAGE.json').read_text());training=json.loads((D/'TRAINING_ACTION_AND_REWARD_TREND.json').read_text())
    diagnostics=[]
    for p in sorted(D.glob('DIAGNOSTIC_*_*.json')):
        r=json.loads(p.read_text())
        if not isinstance(r,dict) or 'transition_archive' not in r:continue
        with np.load(R/r['transition_archive']) as z:
            rewards=z['rewards'];discount=np.exp(-.02/150.)**np.arange(len(rewards))
            parts={k:float(z['reward_'+k].sum()) for k in ('force','shaping','completion','failure','rejection')}
            assert abs(float(rewards.sum())-r['reward_total'])<1e-8
            assert all(abs(parts[k]-r['reward_totals'][k])<1e-8 for k in parts)
            phi=np.mean(np.clip((z['observations'][:,:2]*125-[5,10])/[115,110],0,1),axis=1)
            diagnostics.append(dict(name=r['name'],scope=r['scope'],valid=r['valid'],status=r['status'],termination_reason=r['abort_reason'],duration_s=r['metric']['duration_s'],phase_durations=r['metric']['phase_durations'],reward_total=r['reward_total'],discounted_return=float(rewards@discount),reward_parts=parts,discounted_reward_parts={k:float(z['reward_'+k]@discount) for k in parts},steps=len(rewards),trace=r['metric']['trace'],trace_sha256=r['metric']['trace_sha256'],transitions=r['transition_archive'],transition_archive_sha256=sha(R/r['transition_archive']),J_F=r['metric']['J_F'],force_peak=r['metric']['force_peak'],moment_peak=r['metric']['moment_peak'],minimum_clearance=r['metric']['clearance'],minimum_true_clearance=r['metric']['physical_clearance'],policy_phase_counts=dict(collections.Counter(z['phase'].tolist())),success_physical_audit=r['independent_physical_audit']['pass_']))
    assert len(diagnostics)==5
    comparator=[r for r in diagnostics if r['name']=='fixed_hip_lead'];assert len(comparator)==2 and all(r['valid'] for r in comparator)
    sac=next(r for r in diagnostics if r['name']=='SAC300k');original=next(r for r in primary if r['step']==300000 and r['scope']=='NATIVE')
    for k,oldkey in [('duration_s','termination_time_s'),('J_F','J_F_unranked_if_invalid'),('reward_total','deterministic_return_offline_estimate')]:assert abs(sac[k]-original[oldkey])<1e-7
    assert sac['termination_reason']==original['termination_reason']
    # Discounted shaping telescopes to -5*Phi_initial for absorbing terminal Phi=0;
    # this is intentionally policy-invariant, not a new reward or surrogate task.
    for r in all_eval:
        if r['scope']!='NATIVE':continue
        ep=Path(r['trace']).parent
        with np.load(ep/'trace.npz') as z:
            mask=z['stage']=='TASK';t=z['time_s'][mask];t=t-t[0];force=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1)
        with np.load(ep/'SAC_ACTOR_ACTIONS.npz') as z:
            at=z['task_s'].astype(float);reject=~np.isin(z['status'],['ACCEPTED','IDENTICAL_CONTINUATION'])
        jf=np.r_[0.,np.cumsum(force[:-1]*np.diff(t))]
        boundaries=np.r_[at,t[-1]];cost=np.diff(np.interp(boundaries,t,jf));n=len(at);g=np.exp(-.02/150.)
        terminal=(-1000.)*g**(n-1);discount=g**np.arange(n)
        # Initial Phi is computed directly from the original causal trace.
        with np.load(ep/'trace.npz') as z:
            q0=z['estimated_human_state_rad_rad_s'][z['stage']=='TASK'][0,:2]
        phi0=float(np.clip((np.degrees(q0)-[5,10])/[115,110],0,1).mean())
        r['discounted_return_offline_estimate']=float(-cost@discount/100-.2*reject@discount+terminal-5*phi0)
    save('NATIVE_TREND_WITH_DISCOUNTED_RETURN.json',sorted([r for r in all_eval if r['scope']=='NATIVE'],key=lambda r:r['step']))
    source_evidence=[]
    for p,needles in [(S/'scripts/single_human_sac_expert_v1/sac_env.py',['def action_to_target','def potential','def _reward','handle_timeout_termination','terminal[41:44]']), (S/'scripts/single_human_sac_expert_v1_r2/campaign_r2.py',['def metric(','matched_eligible','DECISION_ALLOWANCE']), (S/'src/traction_mpc_stage5/task.py',['def within_q_bounds','def at_goal(','def task_limit_violation','def transition_phase']), (S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py',['transition_reference_ready = bool','sac_hooks.transition_allowed','sac_hooks.realized']), (S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/online_reference.py',['def offer(','IDENTICAL_CONTINUATION','full_continuation_to_zero_velocity_acceleration'])]:
        lines=p.read_text().splitlines();source_evidence.append(dict(path=str(p),sha256=sha(p),relevant_lines=[dict(line=i+1,text=line) for i,line in enumerate(lines) if any(n in line for n in needles)]))
    authority=json.loads((S/'docs/single_human_sac_expert_v1/SAC_ACTION_PERIOD_QUALIFICATION.json').read_text())
    save('SOURCE_EVIDENCE.json',dict(sources=source_evidence,historical_action_authority=dict(path=str(S/'docs/single_human_sac_expert_v1/SAC_ACTION_PERIOD_QUALIFICATION.json'),sha256=sha(S/'docs/single_human_sac_expert_v1/SAC_ACTION_PERIOD_QUALIFICATION.json'),latency_source=authority.get('latency_source'),rows=[dict(period_s=r['period_s'],physical_success=r.get('physical_success'),modification_fraction=r.get('action_modification_fraction')) for r in authority['rows']]),action_mapping_checks=dict(minus1_deg=[0,0],zero_deg=[62.5,62.5],goal_action=[.92,.92],goal_deg=[120,120],plus1_deg=[125,125],delta_action_001_deg=.0625),interpretation='Mapping is absolute target, not joint increment or torque. Executed_action records the accepted/fallback target; trace reference and Human q are physical realization.'))
    classes=[dict(code='A',finding='Not supported as primary cause: same-wrapper fixed comparator VALID in both scopes;300k reproducible; independent physics agrees. No exact R2 source defect established.'),dict(code='B',finding='Secondary acquisition difficulty/scale, not demonstrated complete-task reward misranking. Success +485..491 vs failures around-1000; absorbing potential gives tiny net shaping and no settled-arrival bonus; all-failure replay offers weak sequence credit.'),dict(code='C',finding='Secondary representation difficulty, not mapping/units bug: broad0..125deg independent targets, near-bound proposals, changing knee direction, and settling a target/reference before phase transition.'),dict(code='D',finding='Strong early distortion (random40.76%,50k deterministic37.8% rejection), but not current dominant cause: final training0.984%,275k/300k deterministic0%.'),dict(code='E',finding='Primary: scratch exploration/task acquisition never produced HOLD/RETURN/completion evidence; final replay entirely OUTBOUND,873 successful training episodes=0.'),dict(code='F',finding='No positive explosion/nonfinite evidence; finite Adam/network, Q about-995, final frozen TD/loss small, entropy near target. Historical loss time series not retained, so cannot exclude earlier instability.'),dict(code='G',finding='Limited partial motion and rejection-avoidance learning, but no sustained complete-task acquisition.225k passes near goal at excessive speed;300k regresses. Blind budget extension not justified.'),dict(code='H',finding='Mean clipped q progress can report1.0 during overshoot; it is not settled arrival, HOLD, valid success, or a policy-ranking score.')]
    result=dict(status='SAC_SEED1_300K_FAILURE_DIAGNOSED',training_steps=0,optimizer_updates=0,diagnostic_rollouts=5,main_evaluations=22,termination_counts=dict(collections.Counter(r['termination_reason'] for r in primary)),entered_hold=sum(r['entered_hold'] for r in primary),started_return=sum(r['started_return'] for r in primary),valid_evaluations=sum(r['valid'] for r in primary),new_diagnostics=diagnostics,primary_root_cause='E',secondary_root_causes=['B: acquisition credit/scale','C: target/settling difficulty','D: early only'],classification=classes,checkpoint='KEEP as preserved negative control/partial-learning reference; do not blindly extend or overwrite it',next_recommended_experiment='Teacher/demo replay initialization, prospectively versioned task-acquisition study; use same-wrapper independently VALID fixed_hip_lead full OUTBOUND/HOLD/RETURN demonstrations, preserve R2 science, fresh SAC initialization as acquisition test; no current checkpoint500k extension and no execution this round',exact10k_evaluation_available=False,early_anchor=12194,historical_training_losses_unavailable=True,simulation_truth='post-run diagnostics only; original policies and teacher use causal deployable observations',science_changes=[],git_mutations=[])
    save('FAILURE_DIAGNOSIS_RESULT.json',result);save('FROZEN_REWARD_REPLAY_AUDIT.json',dict(rows=diagnostics,comparison_scope='same immutable R2 reward; unweighted AND actual gamma-discounted returns',alignment='Both discounted and undiscounted complete trajectories outrank observed failure/no-motion/early-abort trajectories. Early abort can look attractive within undiscounted all-failure returns; discounted timing has a different effect, so do not call early stopping globally optimal.',shaping='For absorbing Phi_terminal=0, discounted sum5*(gamma*Phi_next-Phi_current) telescopes to-5*Phi_initial. Unweighted sum adds-5*(1-gamma)*sum intermediate Phi. This is frozen potential shaping, not a task-success reward.',rank_J_F='Only independently complete VALID tasks. No SAC cost ranking available.'))
    shutil.copy2(Path(__file__),P/Path(__file__).name)
    print(json.dumps(dict(status=result['status'],classes=['E','B secondary','C secondary','D early'],rollouts=5,termination_counts=result['termination_counts'],teacher_transitions={r['scope']:r['steps'] for r in comparator},reward_discounted={r['name']+'_'+r['scope']:r['discounted_return'] for r in diagnostics})),flush=True)
if __name__=='__main__':run()
