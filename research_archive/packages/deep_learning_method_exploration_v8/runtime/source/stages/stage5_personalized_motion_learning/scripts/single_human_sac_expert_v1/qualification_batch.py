"""Run sequential gated qualification; preserve every failure, no formal learning."""
import json,time,sys,threading,resource,subprocess,shutil,gzip
from pathlib import Path
from qualify import *
def rss_growth(samples,warmup=3):
    post=samples[warmup:]
    return max(0,max(post)-post[0]) if post else None
def compact_previous():
    for path in (O/'qualification').rglob('runtime_artifacts.json'):
        dest=Path(str(path)+'.gz')
        if dest.exists():raise RuntimeError('ARCHIVE_COLLISION')
        source_hash=sha(path)
        with path.open('rb') as src,gzip.open(dest,'wb',compresslevel=3) as dst:shutil.copyfileobj(src,dst)
        with gzip.open(dest,'rb') as f:assert hashlib.sha256(f.read()).hexdigest()==source_hash
        path.unlink()
        save('INITIAL_REFERENCE_ARCHIVE.json',dict(path=str(dest.relative_to(R)),uncompressed_sha256=source_hash,sha256=sha(dest),lossless_verified=True))
def reset_stress(period):
    case,options=load_case_options();env=SACExpertEnv(O/f'reset_stress_{int(period*1000)}ms',case,options,period,retain_trace=False);proc=Process();rows=[];initial=None;model=None
    baseline_threads=threading.active_count()
    try:
        for i in range(20):
            start=time.monotonic();obs,info=env.reset(seed=20261003);initial_hash=hashlib.sha256(obs.tobytes()).hexdigest()
            if initial is None:initial=initial_hash;model=env.model_hash
            before=dict(force=env.force_integral,steps=env.step_count,rejections=env.rejections,old_actions=len(env.action_records),phase=info['phase'],model_hash=env.model_hash)
            for k in range(3):obs,reward,terminated,truncated,info=env.step(policy('reference',env,obs,info))
            env.close()
            ok=initial_hash==initial and before==dict(force=0.,steps=0,rejections=0,old_actions=0,phase='OUTBOUND',model_hash=model) and threading.active_count()==baseline_threads and env.thread is None and not env.pending
            row=dict(episode=i+1,pass_=ok,seed=20261003,initial_observation_hash=initial_hash,frozen_model_hash=model,pre_rollout=before,rss_bytes=proc.memory_info().rss,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,host_s=time.monotonic()-start,threads=threading.active_count(),owner_joined=env.thread is None,stale_result=False)
            rows.append(row);save('SAC_RESET_STRESS.json',dict(status='RUNNING',rows=rows,required=20))
            print(json.dumps(dict(reset=i+1,pass_=ok,rss_mb=row['rss_bytes']/2**20,host_s=row['host_s'])),flush=True)
            if not ok:break
    finally:env.close()
    rss=[x['rss_bytes'] for x in rows];growth=rss_growth(rss) if len(rss)>4 else None
    passed=len(rows)==20 and all(x['pass_'] for x in rows) and growth<64*2**20
    save('SAC_RESET_STRESS.json',dict(status='PASS' if passed else 'FAIL',rows=rows,required=20,post_warmup_positive_rss_growth_bytes=growth,post_warmup_rss_range_bytes=max(rss[3:])-min(rss[3:]),max_allowed_growth_bytes=64*2**20,no_state_reference_planner_reward_model_leak=passed))
    (D/'SAC_RESET_STRESS.md').write_text(f'# Reset stress\n\nStatus: {"PASS" if passed else "FAIL"}. {len(rows)} sequential fresh-plant commissioning + three-step rollouts on the same Gym instance. Identical seed, exact initial observation and frozen belief hashes, zero accumulators/actions, OUTBOUND initialization and joined owner checked every reset. RSS after three warmup resets must stay within 64 MiB; observed range {growth} bytes.\n')
    return passed
def main():
    compact_previous();status('POLICY_PERIOD_AND_ACTION_AUTHORITY')
    rates=[]
    for p in (.01,.02,.05):
        record=rollout('authority',p)
        rates.append(record)
        if record['status']!='COMPLETE' or not record.get('physical_success') or abs(record.get('reward_J_F_error',1))>1e-6:
            save('SAC_ACTION_PERIOD_QUALIFICATION.json',dict(status='FAIL',rows=rates));status('QUALIFICATION_STOP',status='SINGLE_HUMAN_SAC_EXPERT_V1_BLOCKED',blocker='ACTION_OR_REFERENCE_PHYSICAL_QUALIFICATION_FAILED',next_action='Close out failed qualification; do not train.');return
    # All rates have the same reference authority. Slowest qualified cadence is prospective preference.
    selected=.05
    save('SAC_ACTION_PERIOD_QUALIFICATION.json',dict(status='PASS',rows=rates,selected_period_s=selected,reason='Slowest candidate preserves short-prefix switches, reduced progression, lead reversal and physical completion.',latency_source='Inherited recorded next-5ms reference and ~10ms physical-response evidence; fresh authority rollouts confirm valid physics and new target acceptance.'))
    table('SAC_POLICY_PERIOD_TABLE.csv',[dict(period_s=x['period_s'],host_s=x['host_s'],agent_steps=x['steps'],agent_steps_s=x['steps']/x['host_s'],simulated_seconds_s=x['result']['duration_s']/x['host_s'],force_peak=x['trace_force_peak'],moment_peak=x['trace_moment_peak'],J_F=x['trace_J_F'],physical_success=x['physical_success'],rejection_fraction=x['action_modification_fraction']) for x in rates])
    status('REWARD_ADVERSARIES')
    reference=json.loads((D/'RUN_reference_50ms_NATIVE.json').read_text());ref_return=reference['result']['reward_total'];rows=[]
    for name in ('no_motion','minimal_motion','early_failure','timeout','skip_hold','incomplete_return','repeated_rejection','alternating_extreme','force_moment_tradeoff','rapid_completion','stalling'):
        record=rollout(name,selected);rows.append(record)
        invalid=not record.get('physical_success',False)
        passed=record['status']!='EXCEPTION' and abs(record.get('reward_J_F_error',1))<1e-6 and (not invalid or record['result'].get('reward_total',1e9)<ref_return-100.)
        record['reward_hacking_pass']=passed
        save('SAC_REWARD_AUDIT.json',dict(status='RUNNING',reference_return=ref_return,rows=rows))
        if not passed:
            save('SAC_REWARD_AUDIT.json',dict(status='FAIL',reference_return=ref_return,rows=rows));status('QUALIFICATION_STOP',status='SINGLE_HUMAN_SAC_EXPERT_V1_BLOCKED',blocker='UNRESOLVED_REWARD_EXPLOIT_OR_BOOKKEEPING',next_action='Preserve failed contract qualification; no formal training.');return
    max_decisions=600;gamma=gamma_for(selected)
    lower_valid=500*gamma**max_decisions-200*30/100-15-.2*max_decisions
    upper_failure=-1000*gamma**max_decisions+15
    passed=lower_valid>upper_failure and all(r['reward_hacking_pass'] for r in rows)
    save('SAC_REWARD_AUDIT.json',dict(status='PASS' if passed else 'FAIL',rows=rows,reference_return=ref_return,discounted_lower_valid_return=lower_valid,discounted_upper_invalid_return=upper_failure,conservative_force_bound=200,task_horizon_s=30,timeout_no_bootstrap=True,valid_tradeoffs='Lower force with legal moment/peak and complete task is intended, not hacking; report peaks separately.'))
    (D/'SAC_REWARD_AUDIT.md').write_text(f'# Reward audit\n\nStatus: {"PASS" if passed else "FAIL"}. Eleven requested adversaries and measured 5-ms reward-integral reconciliation are in JSON. All invalid tasks must score at least 100 below the valid reference. Conservative discounted valid lower bound {lower_valid:.3f}, invalid upper bound {upper_failure:.3f}. Timeout is failed truncation with terminal replay mask (no bootstrap). No moment paper score or timing bonus. Legal rapid completion/force tradeoffs are interpreted separately under matched timing.\n')
    if not passed:return
    status('RESET_STRESS')
    if not reset_stress(selected):
        status('QUALIFICATION_STOP',status='SINGLE_HUMAN_SAC_EXPERT_V1_BLOCKED',blocker='RESET_STRESS_FAILED',next_action='Close out qualification failure; no training.');return
    status('MATCHED_PROTOCOL_COMPARATOR_GATE')
    matched=rollout('reference',selected,'MATCHED')
    if not matched.get('physical_success'):
        status('QUALIFICATION_STOP',status='SINGLE_HUMAN_SAC_EXPERT_V1_BLOCKED',blocker='MATCHED_TIMING_COMPARATOR_INVALID',next_action='Close out qualification; no training.');return
    status('PRE_THROUGHPUT_GATES_PASS',next_action='Final configuration throughput, SB3 CUDA benchmark, runtime distributions and comparator preregistration before formal freeze.')
if __name__=='__main__':main()
