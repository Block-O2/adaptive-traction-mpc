"""Evaluation-only complete TASK derivative windows with pre-TASK anchors.

Does not replace or relax any original qualification. Reads full retained native
raw, computes the first TASK interval using actual prior history, no new physics.
"""
from common import ROOT,put
from stream_json import array_items,read_evidence
from pathlib import Path
import json,time,math
import numpy as np

def read(p):
 with read_evidence(p,encoding='utf-8') as f:return json.load(f)
def audit(run):
 ep=run/'env/episode_0001';m=read(ep/'episode_summary.json');begin=m['native_steps_total']*.00025-m['task_s'];end=m['native_steps_total']*.00025;qi=m['physical_evaluation_only']['human_qpos_indices'];vi=m['physical_evaluation_only']['human_dof_indices'];rows=[]
 for x in array_items(ep/'runtime_artifacts.json','native_states_evaluation_only'):
  if begin-.020000001<=x['time_s']<=end+1e-9:rows.append([x['time_s'],*[x['qpos_evaluation_only'][i] for i in qi],*[x['qvel_evaluation_only'][i] for i in vi]])
 z=np.asarray(rows);t=z[:,0];q=z[:,1:3];v=z[:,3:5];task=t>begin+1e-9;anchor=int(np.sum(~task));vq=v[task];qq=q[task]
 acc={};jerk={}
 for name,n in [('native',1),('5ms',20),('20ms',80)]:
  a=(v[n:]-v[:-n])/(t[n:]-t[:-n])[:,None];ta=t[n:];acc[name]=a[ta>begin+1e-9]
  if name in ['native','5ms']:
   j=(a[n:]-a[:-n])/(ta[n:]-ta[:-n])[:,None];jerk[name]=j[ta[n:]>begin+1e-9]
 peak=lambda a:np.degrees(np.abs(a).max(0)).tolist();rms=lambda a:np.degrees(np.sqrt((a*a).mean(0))).tolist()
 qdeg=np.degrees(qq);vpeak=peak(vq);apeak={k:peak(a) for k,a in acc.items()};checks={'pre_TASK_history_at_least_20ms':anchor>=80,'all_TASK_native_steps':len(qq)==m['task_native_steps'],'all_TASK_native_derivative_windows':all(len(a)==m['task_native_steps'] for a in acc.values()),'finite_actual_human':bool(np.isfinite(z).all()),'original_ROM_0_125':bool((qdeg>=-1e-7).all() and (qdeg<=125.+1e-7).all()),'original_velocity_45_75':all(x<=y+1e-7 for x,y in zip(vpeak,[45.,75.])),'original_acceleration_300_600_all_three_windows':all(all(x<=y+1e-6 for x,y in zip(a,[300.,600.])) for a in apeak.values())}
 result={'unix':time.time(),'category':'SAVED_NATIVE_EVALUATION_ONLY_NO_NEW_PHYSICS','run':str(run.relative_to(ROOT)),'pass':all(checks.values()),'checks':checks,'pre_TASK_anchor_rows':anchor,'TASK_native_steps':len(qq),'velocity_peak_deg_s':vpeak,'acceleration_peak_deg_s2':apeak,'jerk_peak_deg_s3':{k:peak(j) for k,j in jerk.items()},'jerk_rms_deg_s3':{k:rms(j) for k,j in jerk.items()},'definition':'Backward native/5ms/20ms velocity differences, using true pre-TASK samples as anchors. Every derivative ending in TASK is included. Jerk is diagnostic, no invented pass threshold.','formal_B_H150_qualification':'NOT_GRANTED_BY_THIS_OBSERVED_AUDIT'}
 put(run/'NATIVE_BOUNDARY_MOTION_AUDIT.json',result);return result
if __name__=='__main__':
 rows=[json.loads(s) for s in (ROOT/'ALL_EVALUATION_LOG.jsonl').read_text().splitlines()];out=[]
 for row in rows:
  p=ROOT/row['run']/'NATIVE_BOUNDARY_MOTION_AUDIT.json';x=read(p) if p.exists() else audit(ROOT/row['run']);out.append(x);print(json.dumps({'run':row['run'],'pass':x['pass'],'native_acc_peak':x['acceleration_peak_deg_s2']['native']}),flush=True)
 put(ROOT/'audit/EVALUATION_NATIVE_BOUNDARY_MOTION.json',{'unix':time.time(),'evaluations':out,'all_pass':all(x['pass'] for x in out),'no_new_physics':True})
 if not all(x['pass'] for x in out):raise SystemExit(1)
