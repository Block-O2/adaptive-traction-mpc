"""Compact R2 dynamic aggregates; no physics and no source mutation."""
from pathlib import Path
import json,csv,hashlib,gzip
from datetime import datetime,timezone
W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/lab-human-adaptation-contrast-v1')
def save(n,x):(W/n).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def load(p):return json.loads(p.read_text())
def success(r):return r.get('status')=='COMPLETE' and r.get('physical_verdict')=='PASS' and r.get('scientific_verdict')=='PASS'
def csvfile(n,rows,fields):
 with (W/n).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows({k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)
def aggregate():
 c=load(W/'CONTRACT_R2.json');rows=[];ident=[];consumer=[];intervals=[];contrasts=[]
 for e in c['conditions']:
  group={}
  for letter,arm in c['arms'].items():
   d=W/'runs_R2'/f"{e['id']}__{arm}";p=d/'PRIMARY_RESULT.json'
   r=load(p) if p.exists() else dict(condition=e['id'],arm=arm,status='NOT_RUN',physical_verdict='NOT_EVALUATED',scientific_verdict='NOT_EVALUATED')
   r['primary_success']=success(r);rows.append(r);group[letter]=r
   if p.exists():
    q=load(d/'qualification.json')
    ident.append(dict(condition=e['id'],arm=arm,setup_status=r.get('setup_status'),commissioning_status=r.get('commissioning_status'),task_status=r.get('task_status'),geometry_estimate=r.get('geometry_estimate'),geometry_used=r.get('geometry_used'),effective_cuff_geometry_evaluation=r.get('effective_cuff_geometry_evaluation'),initial_beta=q.get('initial_beta'),final_beta=q.get('final_beta'),initial_residual_checkpoint='COMMISSIONED_MODEL_TASK_CHECKPOINT.json',final_residual_checkpoint='trace.npz:task_residual_weights_nm[-1]',TASK_updates=r.get('TASK_updates'),dynamic_identifier_record=q.get('dynamic_identifier_record'),residual_update_count=q.get('residual_update_count'),prediction=r.get('prediction')))
    consumer.append(dict(condition=e['id'],arm=arm,actual_model_consumption=r.get('actual_model_consumption'),logging_gaps=r.get('consumption_logging_gaps'),handoff_geometry=r.get('geometry_used'),initial_beta=q.get('initial_beta'),final_beta=q.get('final_beta')))
    rp=d/'RESOURCE_RUN.json'
    if rp.exists():intervals.append(load(rp))
  for name,a,b in [('B-A','A','B'),('C-B','B','C')]:
   first,second=group[a],group[b];pair_available=first['status']!='NOT_RUN' and second['status']!='NOT_RUN'
   common=pair_available and success(first) and success(second)
   contrast=dict(condition=e['id'],contrast=name,pair_available=pair_available,first_success=success(first),second_success=success(second),interaction_comparable_full_successes=common,reason='Short aborted task integrals are never ranked against complete successes')
   for metric in ['J_F_task_n_s','duration_s','force_peak_n','force_rms_n','moment_integral_nm_s','minimum_clearance_m']:
    x,y=first.get(metric),second.get(metric)
    contrast[metric+'_delta']=y-x if common and isinstance(x,(float,int)) and isinstance(y,(float,int)) else None
    if metric=='J_F_task_n_s':contrast['J_F_percent_change']=100*(y/x-1) if common and x else None
   x,y=first.get('tracking_rmse_rad'),second.get('tracking_rmse_rad')
   contrast['tracking_rmse_rad_delta']=[v-u for u,v in zip(x,y)] if common and x and y else None
   contrasts.append(contrast)
 done=sum(r['status']!='NOT_RUN' for r in rows)
 counts={letter:sum(success(r) and r['arm']==arm for r in rows) for letter,arm in c['arms'].items()}
 save('PRIMARY_MATRIX_R2.json',dict(status='COMPLETE' if done==21 else 'PARTIAL',executed_primary_runs=done,success_counts=counts,runs=rows,contrasts=contrasts,primary_order='complete physical/scientific success; safety/tracking; interaction among comparable full successes'))
 fields=['condition','arm','status','primary_success','physical_verdict','scientific_verdict','outbound_reached','hold_satisfied','true_return_satisfied','duration_s','J_F_task_n_s','force_mean_n','force_rms_n','force_peak_n','moment_integral_nm_s','moment_peak_nm','minimum_clearance_m','minimum_true_clearance_m_evaluation_only','tracking_rmse_rad','tracking_truth_rmse_rad_evaluation_only','abort_reason']
 csvfile('PRIMARY_MATRIX_R2.csv',rows,fields)
 save('MODEL_IDENTIFICATION_RESULTS_R2.json',dict(status='DYNAMIC_EVIDENCE' if ident else 'NOT_RUN',runs=ident,prediction_interpretation='TASK torque reconstruction, finite-difference acceleration, not a future forecast or common exogenous held-out distribution. Within-arm frozen-vs-prequential shares the same observations; across-arm ranges/trajectories differ.'))
 csvfile('MODEL_IDENTIFICATION_RESULTS_R2.csv',ident,['condition','arm','commissioning_status','task_status','effective_cuff_geometry_evaluation','initial_beta','final_beta','TASK_updates','residual_update_count','prediction'])
 save('MODEL_CONSUMPTION_EVIDENCE_R2.json',dict(status='ACTUAL_PER_PID_CONSUMPTION' if consumer else 'NOT_RUN',runs=consumer,numeric_hash_definition='SHA256 little-endian f64 beta concatenated residual coefficients; separate canonical geometry SHA256',source_commit=c['source_commit'],source_provenance_sha256=c['source_provenance_sha256'],options_sha256=c['options_sha256']))
 save('CONTRASTS_R2.json',dict(contrasts=contrasts,success_counts=counts,primary_done=done))
 old=load(W/'RESOURCE_OVERLAP_LOG_R2.json');old.update(side_dynamic_intervals=intervals,first_resource_qualification=load(W/'RESOURCE_DYNAMIC_QUALIFICATION.json'),status='OBSERVED_RUN_INTERVALS',clean_wall_benchmark=False);save('RESOURCE_OVERLAP_LOG_R2.json',old)
 print(json.dumps({'done':done,'success_counts':counts,'results':[dict(condition=r['condition'],arm=r['arm'],status=r['status'],success=r['primary_success'],J_F=r.get('J_F_task_n_s')) for r in rows if r['status']!='NOT_RUN']}))
if __name__=='__main__':aggregate()
