"""Add phase/model endpoint evidence from existing traces only."""
import os,sys
for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
from pathlib import Path
import json,gzip,numpy as np
W=Path('<SIDE_STUDIES_ROOT>/lab-human-adaptation-contrast-v1')
def load(p):return json.loads(p.read_text() if p.exists() else gzip.open(str(p)+'.gz','rt').read())
def save(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def observed_updates(d):
 records=[]
 for p in list(d.glob('prediction_updates_*.jsonl'))+list(d.glob('prediction_updates_*.jsonl.gz')):
  stream=gzip.open(p,'rt') if p.suffix=='.gz' else p.open()
  with stream:
   for line in stream:
    r=json.loads(line)
    records.append(r)
 return records
def phase_ranges(z):
 rows=[]
 for stage in np.unique(z['stage']):
  mask=z['stage']==stage;t=z['time_s'][mask];q=z['evaluation_only_human_state_rad_rad_s'][mask]
  rows.append(dict(stage=str(stage),samples=len(t),time_range_s=[float(t[0]),float(t[-1])],observed_span_s=float(t[-1]-t[0]),truth_q_min_rad=np.min(q[:,:2],axis=0).tolist(),truth_q_max_rad=np.max(q[:,:2],axis=0).tolist(),maximum_force_N=float(np.max(np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1))),safety_mode_counts={str(v):int(n) for v,n in zip(*np.unique(z['safety_mode'][mask],return_counts=True))}))
 return rows
def main():
 for d in sorted((W/'runs_R2').iterdir()):
  if not (d/'PRIMARY_RESULT.json').exists():continue
  r=load(d/'PRIMARY_RESULT.json');q=load(d/'qualification.json')
  if not (d/'trace.npz').exists():continue
  s=load(d/'summary.json')
  with np.load(d/'trace.npz') as z:
   phases=phase_ranges(z);r['phase_evidence']=phases
   handoff=s['commissioning']['handoff_belief']
   evidence=dict(population_initial_beta=s['commissioning'].get('population_beta_initial'),population_initial_residual_weights_nm=s['commissioning'].get('population_residual_weights_initial_nm'),commissioning_handoff=handoff,first_task_beta=z['task_beta'][0].tolist() if len(z['task_beta']) else None,last_task_trace_beta=z['task_beta'][-1].tolist() if len(z['task_beta']) else None,first_task_residual_weights_nm=z['task_residual_weights_nm'][0].tolist() if len(z['task_residual_weights_nm']) else None,last_task_trace_residual_weights_nm=z['task_residual_weights_nm'][-1].tolist() if len(z['task_residual_weights_nm']) else None,updater_final_beta=q.get('final_beta'),endpoint_distinction='Final updater can include an update after the final executed control command; actual consumption is independently hashed.')
   save(d/'MODEL_ENDPOINTS.json',evidence);r['model_endpoints']=evidence
   r['commissioning_geometry_fit_status']=s['commissioning']['geometry_fit']
   r['commissioning_update_count']=s['commissioning'].get('aligned_update_count')
   r['commissioning_duration_s']=s['commissioning'].get('duration_s')
   r['commissioning_samples']=s['commissioning'].get('sample_count')
   r['safety_counts']=s.get('safety_mode_counts',r.get('safety_counts'))
   if str(r.get('abort_reason','')).startswith('ACTIVE_RECOVERY'):
    r['failure_stage']='ACTIVE_RECOVERY_BEFORE_MEANINGFUL_TASK'
    r['task_status']='NOT_STARTED_OR_ENTRY_ONLY'
   elif r['status']=='ABORTED':r['failure_stage']='TASK_OR_TRANSITION_INSPECT_PHASE_EVIDENCE'
   else:r['failure_stage']=None
  updates=observed_updates(d)
  beta=[];residual=[]
  for update in updates:
   diag=update.get('diagnostics',{})
   b=diag.get('beta_update',{})
   if b.get('attempted'):beta.append(b)
   residual.append({k:v for k,v in diag.items() if any(x in k.lower() for x in ['accepted','reason','residual'])})
  r['all_stage_observed_update_summary']=dict(observe_calls=len(updates),beta_attempts=len(beta),beta_accepted=sum(bool(x.get('accepted')) for x in beta),beta_rejected=sum(not x.get('accepted',False) for x in beta),beta_rejection_reasons={str(reason):sum(x.get('reason')==reason and not x.get('accepted',False) for x in beta) for reason in set(x.get('reason') for x in beta if not x.get('accepted',False))},residual_diagnostic_fields_sample=residual[:2],includes_commissioning_and_TASK=True)
  save(d/'PRIMARY_RESULT.json',r)
 print('SUPPLEMENT_EXISTING_TRACES_COMPLETE')
if __name__=='__main__':main()
