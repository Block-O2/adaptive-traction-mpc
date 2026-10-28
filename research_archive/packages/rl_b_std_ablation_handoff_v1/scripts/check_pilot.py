from pathlib import Path
import sys,json
from research_common import ROOT,read,atomic,now,sha
sys.path.insert(0,str(ROOT/'runtime'))
import numpy as np
plan=read(ROOT/'configs/STD_PLAN_v3.json');checks=[]
for item in plan['plans']:
 if item['split']!='pilot':continue
 cfg=read(item['config']);job=cfg['job_id'];end=read(ROOT/'jobs'/job/'END.json');assert end and end['success']
 run=Path(read(ROOT/'runtime/jobs'/job/'RESULT.json')['rows'][0]['run']);row=read(run/'RESULT.json');ts=read(run/'RESEARCH_TRANSITIONS.json');z=np.load(cfg['noise_path'])
 good=dict(interface_and_audits=end['success'] and row['independent_audit_pass'],identity_restored=read(run.parent/'RESUME_AUDIT.json')['pass_'],policy_unchanged=row['frozen_snapshot_before']['policy']==row['frozen_snapshot_after']['policy'],optimizer_unchanged=row['frozen_snapshot_before']['optimizer']==row['frozen_snapshot_after']['optimizer'],counters_unchanged=all(row['frozen_snapshot_before'][k]==row['frozen_snapshot_after'][k] for k in ['num_timesteps','n_updates','episode_num']),zero_updates=row['gradient_updates']==0,noise_array_unchanged=sha(cfg['noise_path'])==cfg['noise_sha256'])
 for i,t in enumerate(ts):
  mean=np.asarray(t['mean'],np.float32);std=np.asarray(t['std'] if cfg['arm']=='A' else [.2,.2],np.float32);raw=mean+std*z[i]
  good[f'noise_index_{i}']=np.array_equal(np.asarray(t['noise'],np.float32),z[i]) and t['noise_index']==i
  good[f'sample_formula_{i}']=np.array_equal(raw,np.asarray(t['raw_action'],np.float32))
  good[f'clip_formula_{i}']=np.array_equal(np.clip(raw,-1,1),np.asarray(t['action'],np.float32))
 checks.append(dict(job=job,checks=good,pass_=all(good.values()),task_success=row['success'],status=row['status'],task_s=row['task_s']))
assert len(checks)==2
result=dict(time_utc=now(),cases=checks,pass_=all(x['pass_'] for x in checks),task_success_is_not_interface_gate=True,source_sha256=sha(__file__))
atomic(ROOT/'audit/PILOT_ACCEPTANCE.json',result);print(json.dumps(result,ensure_ascii=False));assert result['pass_']
