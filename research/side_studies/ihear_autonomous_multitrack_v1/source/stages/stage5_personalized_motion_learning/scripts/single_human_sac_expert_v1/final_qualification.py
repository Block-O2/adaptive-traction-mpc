"""Final-period pre-training qualification and explicit previous-reference replay."""
from pathlib import Path
import json,sys,time,hashlib,traceback,subprocess,resource
from qualify import *
from qualification_batch import reset_stress
def gate(name,passed,detail):
    p=D/'FINAL_QUALIFICATION_GATES.json';data=json.loads(p.read_text()) if p.exists() else dict(gates={},formal_training_steps=0)
    data['gates'][name]=dict(pass_=bool(passed),detail=detail);save(p.name,data)
    if not passed:raise RuntimeError('QUALIFICATION_GATE_FAILED:'+name)
def compact_archive(env):
    path=env.episode_dir/'runtime_artifacts.json'
    if path.exists():
        dest=Path(str(path)+'.gz');source_hash=sha(path)
        with path.open('rb') as src,gzip.open(dest,'wb',compresslevel=3) as dst:shutil.copyfileobj(src,dst)
        with gzip.open(dest,'rb') as stream:
            h=hashlib.sha256()
            for chunk in iter(lambda:stream.read(2**20),b''):h.update(chunk)
        assert h.hexdigest()==source_hash;path.unlink()
        return dict(path=str(dest.relative_to(R)),original_sha256=source_hash,archive_sha256=sha(dest))
def old_comparator(scope):
    case,options=load_case_options();out=O/'comparators'/f'old_nominal_{scope}';env=SACExpertEnv(out,case,options,.02,scope,True)
    env.episode_dir=out;out.mkdir(parents=True,exist_ok=False);env.host_start=time.monotonic()
    try:
        env.summary=rt.run_executed_case(out,qualification_case=case,qualification_arm='commissioning_only',simulate_planning_latency=True,formal_qualification=False,dev_a_recovery=True,dev_c_bumpless_transfer=False,dev_d_rigid_table_reference=True,autonomous_recovery_options=options,task_timeout_s=30.,runtime_capture=env.capture,execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_s=0.,session_context={},sac_hooks=env)
        record=metric_record(env,'old_nominal',scope);record['model_handoff']=env.summary['commissioning']['handoff_belief']
        record['reference_semantics']='Original controller with unchanged planner; commissioned frozen Human and current native/matched clocks.'
        save(f'COMPARATOR_old_nominal_{scope}.json',record);return record
    finally:compact_archive(env);env.close()
def metric_record(env,name,scope):
    audit=physical_audit(env);z=np.load(env.episode_dir/'trace.npz');mask=z['stage']=='TASK';t=z['time_s'][mask];f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);m=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1)
    transitions=env.summary['task']['phase_transitions'];start=t[0];times={x['to']:x['time_s'] for x in transitions}
    phase_times=dict(OUTBOUND=times.get('HOLD',t[-1])-start,HOLD=times.get('RETURN',t[-1])-times.get('HOLD',t[-1]),RETURN=times.get('COMPLETE',t[-1])-times.get('RETURN',t[-1]))
    matched=scope!='MATCHED' or all(abs(phase_times[k]-v)<=.010000001 for k,v in dict(OUTBOUND=9.,HOLD=1.,RETURN=9.).items())
    return dict(name=name,scope=scope,status=env.summary['status'],valid=bool(audit['pass_'] and matched),physical_audit=audit,matched_timing_valid=matched,phase_durations=phase_times,J_F=float(f[:-1]@np.diff(t)),force_mean=float(np.mean(f)),force_rms=float(np.sqrt(np.mean(f*f))),force_peak=float(np.max(f)),moment_integral=float(m[:-1]@np.diff(t)),moment_peak=float(np.max(m)),duration_s=float(t[-1]-t[0]),clearance=env.summary['task']['minimum_session_clearance_m_deployable'],physical_clearance=env.summary['task']['minimum_true_physical_clearance_m_evaluation_only'],model_updates_task=env.summary['task']['continual_adaptation_update_count'],model_beta=z['task_beta'][0].tolist(),model_residual=z['task_residual_weights_nm'][0].tolist(),initial_estimated_state=z['estimated_human_state_rad_rad_s'][mask][0].tolist(),initial_reference=z['reference_q_rad'][mask][0].tolist(),host_s=time.monotonic()-env.host_start,trace=str((env.episode_dir/'trace.npz').relative_to(R)),trace_sha256=sha(env.episode_dir/'trace.npz'),rejections=env.rejections,modification_fraction=env.rejections/max(1,len(env.action_records)),raw_actions=env.action_records)
def cem_comparator(scope):
    db=json.loads((S/'docs/best_known_coordination_search_v2/BEST_KNOWN_REFERENCE_DATABASE.json').read_text())
    entry=next(e for e in db['entries'] if e['condition']=='sync_120' and e['matched_native_label']=='NATIVE')
    descriptor=entry['trajectory_descriptor']['planned_segments'];case,options=load_case_options();env=SACExpertEnv(O/'comparators'/f'cem_reference_{scope}',case,options,.02,scope,True)
    try:
        obs,info=env.reset(seed=20261003)
        for i in range(1800):
            phase=info['phase'];items=descriptor.get(phase,[])
            target=env.soft_target.copy()
            if items:
                elapsed=float(obs[47]*10.)
                selected=next((x for x in reversed(items) if elapsed>=x['phase_elapsed_s']-1e-10),items[0])
                target=np.asarray(selected['target_q_rad'])
                # The archived terminal target is within the unchanged arrival box.
                # Zero-terminal-velocity OTG is a transfer through the new interface,
                # not a claim that archived RSS/CEM dynamics were replayed exactly.
            obs,reward,term,trunc,info=env.step(target_to_action(target,env.spec).astype(np.float32))
            if term or trunc:break
        record=metric_record(env,'cem_reference_transfer',scope)
        record['source_reference']=dict(result_path=entry['result_path'],result_sha256=entry['rollout_result_sha256'],historical_J_F=entry['J_F_n_s'],parameters=entry['coordination_parameters'],descriptor=descriptor)
        record['reference_semantics']='Prospectively transfer archived scheduler-screened target/phase-clock descriptor through same validated online interface and frozen initial condition. Uses reference targets, never evaluation-only Human state. This is a new comparator replay, not the old CEM numeric result or a new CEM search.'
        save(f'COMPARATOR_cem_reference_{scope}.json',record);return record
    finally:compact_archive(env);env.close()
def simple_comparator(scope):
    case,options=load_case_options();env=SACExpertEnv(O/'comparators'/f'fixed_hip_lead_{scope}',case,options,.02,scope,True)
    try:
        obs,info=env.reset(seed=20261003)
        for i in range(1800):
            action=policy('fixed_hip_lead',env,obs,info);obs,reward,term,trunc,info=env.step(action)
            if term or trunc:break
        record=metric_record(env,'fixed_hip_lead',scope);record['reference_semantics']='Simple fixed 1.5s outbound hip-leading intent, then endpoint; no tuning after these comparator results.'
        save(f'COMPARATOR_fixed_hip_lead_{scope}.json',record);return record
    finally:compact_archive(env);env.close()
def final_rewards():
    reference=rollout('reference',.02);gate('final_reference',reference.get('physical_success'),reference.get('result'))
    ref_return=reference['result']['reward_total'];rows=[]
    for name in ('no_motion','minimal_motion','early_failure','timeout','skip_hold','incomplete_return','repeated_rejection_after_prefix','alternating_extreme_after_prefix','force_moment_tradeoff','rapid_completion','stalling'):
        record=rollout(name,.02);rows.append(record)
        valid=record.get('physical_success',False)
        passed=record['status']!='EXCEPTION' and abs(record.get('reward_J_F_error',1))<1e-6 and (valid or record['result'].get('reward_total',1e9)<ref_return-100.)
        if name=='repeated_rejection_after_prefix':passed=passed and record['result'].get('rejections',0)>=3
        if name=='alternating_extreme_after_prefix':passed=passed and len(record.get('action_records',[]))>=5
        record['reward_hacking_pass']=passed
        save('SAC_REWARD_AUDIT.json',dict(status='RUNNING',period_s=.02,reference_return=ref_return,rows=rows))
        if not passed:gate('reward_'+name,False,record)
    gamma=gamma_for(.02);max_n=1500;lower=500*gamma**max_n-60.-15.-.2*max_n;upper=-1000*gamma**max_n+15.
    save('SAC_REWARD_AUDIT.json',dict(status='PASS',period_s=.02,reference_return=ref_return,rows=rows,discounted_valid_lower_bound=lower,discounted_invalid_upper_bound=upper,finite_timeout_replay_no_bootstrap=True))
    gate('final_reward_audit',lower>upper and all(r['reward_hacking_pass'] for r in rows),dict(lower_valid=lower,upper_invalid=upper))
    (D/'SAC_REWARD_AUDIT.md').write_text('# Final reward qualification\n\n20ms final configuration, eleven adversaries, exact 5ms measured-force quadrature and every reward component are in JSON. Repeated/alternating extremes establish a certified reference prefix first, so they test multiple commands rather than only first-command failure. All incomplete or physically invalid tasks must score at least 100 below the legal reference; finite timeout truncation never bootstraps. Legal complete force/moment tradeoffs are separately measured and constrained.\n')
    return reference
def main():
    status('FINAL_20MS_CONTRACT_QUALIFICATION',status='QUALIFICATION_IN_PROGRESS')
    try:
        if len(sys.argv)>1 and sys.argv[1]=='resume_comparators':
            assert json.loads((D/'SAC_REWARD_AUDIT.json').read_text())['status']=='PASS'
            assert json.loads((D/'SAC_RESET_STRESS.json').read_text())['status']=='PASS'
        else:
            ref=final_rewards();status('FINAL_20MS_RESET_STRESS');gate('20_reset_stress',reset_stress(.02),'Exact reset/model hashes, no stale owners, resources')
        status('FINAL_COMPARATOR_QUALIFICATION');rows=[]
        for scope in ('NATIVE','MATCHED'):
            r=rollout('final_reference',.02,scope)
            case,opts=load_case_options();env=SACExpertEnv('/tmp/not_started',case,opts,.02,scope,True);env.episode_dir=O/'qualification'/f'final_reference_20ms_{scope}'/'episode_00001';env.summary=json.loads((env.episode_dir/'summary.json').read_text());env.host_start=time.monotonic();env.rejections=r['result']['rejections'];env.action_records=r['action_records']
            record=metric_record(env,'online_reference',scope);env.close();rows.append(record);gate('online_reference_'+scope,record['valid'],record['phase_durations'])
            for fn in (old_comparator,simple_comparator,cem_comparator):
                record=fn(scope);rows.append(record)
                print(json.dumps({k:record.get(k) for k in ('name','scope','status','valid','J_F','duration_s','host_s')}),flush=True)
                save('SAC_COMPARATOR_TABLE.json',dict(status='RUNNING',rows=rows))
                if fn is old_comparator:gate('old_nominal_'+scope,record['valid'],record['phase_durations'])
        baseline=next(r for r in rows if r['name']=='online_reference' and r['scope']=='NATIVE')
        causal_comparable=all(np.allclose(row['model_beta'],baseline['model_beta'],atol=1e-12,rtol=0.) and np.allclose(row['model_residual'],baseline['model_residual'],atol=1e-12,rtol=0.) and np.allclose(row['initial_estimated_state'],baseline['initial_estimated_state'],atol=1e-12,rtol=0.) for row in rows)
        gate('comparator_initial_conditions',causal_comparable,'Identical commissioned model beta/residual and causal initial physical estimate, no task adaptation.')
        gate('strong_comparators_available',all(any(r['valid'] and r['scope']==scope and r['name']=='cem_reference_transfer' for r in rows) for scope in ('NATIVE','MATCHED')),'Same-interface replay of existing CEM descriptor must be valid; no ranking against historical unmatched numeric values.')
        save('SAC_COMPARATOR_TABLE.json',dict(status='PASS',rows=rows,historical_numbers_not_directly_ranked=True))
        table('SAC_COMPARATOR_TABLE.csv',[{k:r.get(k) for k in ('name','scope','valid','J_F','force_mean','force_rms','force_peak','moment_integral','moment_peak','duration_s','clearance','physical_clearance','rejections','modification_fraction','trace','trace_sha256')} for r in rows])
        status('FINAL_ENVIRONMENT_GATES_PASS',next_action='Actual final compact environment + SAC CUDA throughput, runtime distributions, source freeze; then automatically train if all remaining gates pass.')
    except Exception as error:
        save('FINAL_QUALIFICATION_EXCEPTION.json',dict(error=str(error),traceback=traceback.format_exc(),formal_training_steps=0))
        status('QUALIFICATION_STOP',status='SINGLE_HUMAN_SAC_EXPERT_V1_BLOCKED',blocker=str(error),next_action='No formal training. Preserve failed qualification and close out.')
        print(traceback.format_exc(),flush=True)
if __name__=='__main__':main()
