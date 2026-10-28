"""Fresh-process final audit from saved raw only; redirects auditor writes to new files."""
from pathlib import Path
import sys,json
from research_common import ROOT,RUNTIME,read,atomic,sha,now
sys.path.insert(0,str(RUNTIME))
import numpy as np
import audit_reward_physical,cloud_motion_audit,cloud_case_audit,force_audit,native_boundary_motion_audit
from motion_metrics import metrics

def verify(row):
 run=Path(row['run']);out=ROOT/'audit/final_independent_recheck'/row['job_id'];out.mkdir(parents=True,exist_ok=True)
 def capture(path,value):atomic(out/Path(path).name,value)
 for module in [audit_reward_physical,cloud_motion_audit,cloud_case_audit,force_audit,native_boundary_motion_audit]:module.put=capture
 a=cloud_case_audit.audit(run);f=force_audit.audit(run/'env/episode_0001');m=native_boundary_motion_audit.audit(run);motion=metrics(run,out)
 ts=read(run/'RESEARCH_TRANSITIONS.json');cfg=read(run.parent/'EFFECTIVE_CONFIG.json');links=a['native_actions'];noise=np.load(cfg['noise_path']) if cfg['arm']!='C' else None
 checks=dict(independent_native_receipt_reward_motion=a['pass'],force_original_left_quadrature=f['pass'],motion_all_native_derivative_windows=m['pass'],JF_matches=abs(f['independent_J_F_N_s']-row['JF'])<1e-7,JM_matches=abs(f['independent_J_M_Nm_s']-row['JM'])<1e-7,native_steps_match=a['ownership']['native_steps_all']==row['native_steps'],task_native_steps_match=a['ownership']['native_task_steps']==row['task_native_steps'],policy_unchanged=row['frozen_snapshot_before']['policy']==row['frozen_snapshot_after']['policy'],Adam_unchanged=row['frozen_snapshot_before']['optimizer']==row['frozen_snapshot_after']['optimizer'],counters_unchanged=all(row['frozen_snapshot_before'][k]==row['frozen_snapshot_after'][k] for k in ['num_timesteps','n_updates','total_timesteps','episode_num']),gradient_updates_zero=row['gradient_updates']==0,one_link_per_transition=len(links)==len(ts),noise_file_unchanged=True if cfg['arm']=='C' else sha(cfg['noise_path'])==cfg['noise_sha256'])
 samples_ok=clip_ok=links_ok=True
 for i,t in enumerate(ts):
  mean=np.asarray(t['mean'],np.float32);std=np.asarray(t['std'] if cfg['arm']=='A' else [.2,.2],np.float32)
  expected=mean if cfg['arm']=='C' else mean+std*noise[i]
  samples_ok &= np.array_equal(expected,np.asarray(t['raw_action'],np.float32))
  clip_ok &= np.array_equal(np.clip(expected,-1,1),np.asarray(t['action'],np.float32))
  links_ok &= links[i]['action_id']==i and np.array_equal(np.asarray(links[i]['proposed_rl_action'],np.float32),np.asarray(t['action'],np.float32))
 checks.update(sample_formula=bool(samples_ok),clip_formula=bool(clip_ok),policy_proposal_matches_native_request=bool(links_ok))
 end=ts[-1]['reward_after'];initial_phi=ts[0]['reward_before']['phi'];cost=.0005*end['force']+.005*end['moment']+.02*end['variation']
 expected=2*((end['phi'] if row['success'] else 0)-initial_phi)+(20-cost if row['success'] else -15-max(15,cost))
 actual=sum(t['reward'] for t in ts)
 checks['R1_reward_independent_total']=abs(actual-expected)<1e-7 and abs(actual-row['training_reward'])<1e-7
 checks['failed_partial_not_positive_reward']=row['success'] or actual<0
 checks['observed_execution_costs_monotone']=all(all(t['reward_after'][k]>=t['reward_before'][k]-1e-9 for k in ['force','moment','variation']) for t in ts)
 base=read(run/'COMMON_MOTION_METRICS.json');checks['independent_Human_metrics_match']=all(np.allclose(motion[k],base[k],rtol=0,atol=1e-8) for k in ['tracking_RMS_deg','velocity_RMS_deg_s','velocity_peak_deg_s','acceleration_RMS_deg_s2','acceleration_peak_deg_s2','jerk_RMS_deg_s3','jerk_peak_deg_s3','terminal_return_absolute_error_deg'])
 return dict(job=row['job_id'],run=str(run),checks=checks,pass_=all(checks.values()),JF=f['independent_J_F_N_s'],JM=f['independent_J_M_Nm_s'],integral_scope=motion['integral_scope'],source_sha256=sha(run/'RESEARCH_TRANSITIONS.json'))

def main():
 rows=[json.loads(x) for x in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()];results=[]
 for row in rows:
  result=verify(row);results.append(result);print(row['job_id'],result['pass_'],flush=True)
  atomic(ROOT/'audit/FINAL_FROZEN_RECHECK.json',dict(time_utc=now(),process_identity=__import__('research_common').pid_identity(__import__('os').getpid()),expected=28,rechecked=len(results),cases=results,pass_=len(results)==28 and all(x['pass_'] for x in results),new_physics=0,Adam=0))
 assert len(results)==28 and all(x['pass_'] for x in results)
if __name__=='__main__':main()
