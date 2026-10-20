"""Offline planner-assertion evidence (default P06). No physics/controller imports."""
import argparse,gzip,hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path
import numpy as np

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--mirror',type=Path);ap.add_argument('--patient',default='P06');args=ap.parse_args();p=args.package;pid=args.patient;sources={}
 def source(rel):
  f=p/rel;sources[rel]={'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size};return f
 def read(rel):
  f=source(rel)
  with (gzip.open(f,'rt') if f.suffix=='.gz' else f.open()) as h:return json.load(h)
 done=read(pid+'_DONE.json');owner=read('audit/'+pid+'_OWNER.json');assert done['all_children_joined'] and owner['joined']
 pair=read(pid+'_COMPARISON.json');raw=read('output/'+pid+'_H150.json');summary=read('source/results/'+pid+'_H150/summary.json');r=read('source/results/'+pid+'_H150/runtime_artifacts.json.gz')
 with np.load(source('source/results/'+pid+'_H150/trace.npz'),allow_pickle=False) as z:
  t=z['time_s'];phase=z['task_phase'];origin=float(t[np.flatnonzero(phase=='RETURN')[0]])
  request_rows=[]
  for req in r['requests']:
   if req.get('outcome')!='FAILED':continue
   rid=req['request_id'];snap=next(x for x in r['causal_tracking_request_snapshots'] if x['request_id']==rid);idx=int(np.argmin(abs(t-req['source_sample_time_s'])))
   start=snap['proposed_schedule_origin_rad_rad_s'];request_rows.append(dict(request=req,return_elapsed_s=req['source_sample_time_s']-origin,
    recorded_causal_snapshot=snap,schedule_origin_deg_deg_s=np.rad2deg(start).tolist(),
    recorded_start_knee_velocity_conjunct_pass=bool(abs(start[3])<1e-10),
    failed_original_target_and_candidate_endpoint_velocity_recorded=False,
    nearest_trace_physics_s=float(t[idx]),nearest_trace_true_state_deg_deg_s=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][idx]).tolist(),
    nearest_trace_reference_deg=np.rad2deg(z['reference_q_rad'][idx]).tolist(),nearest_trace_reference_velocity_deg_s=np.rad2deg(z['reference_dq_rad_s'][idx]).tolist()))
  final=dict(physics_s=float(t[-1]),phase=str(phase[-1]),true_state_deg_deg_s=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][-1]).tolist(),reference_deg=np.rad2deg(z['reference_q_rad'][-1]).tolist(),reference_velocity_deg_s=np.rad2deg(z['reference_dq_rad_s'][-1]).tolist())
 decisions=[]
 for d in r['task_decisions'][-3:]:
  ds={k:v for k,v in d.items() if k not in ['evaluations','execution_screen','schedule','candidate_evaluations']}
  if 'evaluations' in d:
   ds['evaluations_compact']=[{k:e.get(k) for k in ['label','target_q_rad','feasible','rejection_reason']} for e in d['evaluations']]
  decisions.append(ds)
 for rel in ['control/terminal_planner.py','control/campaign_v6.py','control/early_return_planner.py','source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py','source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_online_v1.py']:
  source(rel)
 out=dict(schema='IHEAR_PLANNER_ASSERTION_EVIDENCE_V1',patient_id=pid,generated_utc=datetime.now(timezone.utc).isoformat(),physics_starts=0,simulator_imports=False,
  done=done,owner=owner,abort_reason=summary.get('abort_reason'),summary_status=summary.get('status'),
  assertion='abs(target[1]-start[1])<1e-10 and abs(start[3])<1e-10 and abs(velocity[1])<1e-10',
  assertion_units='radians and radians/second; start=current_reference_state, not true physical state',
  full_integral_comparison_valid=pair.get('full_integral_comparison_valid'),gain_percent=pair.get('gain_percent'),
  B={k:pair['B'].get(k) for k in ['qualification','axes','J_F_N_s','observed_prefix','interventions','motion_extra']},
  H150={k:pair['H150'].get(k) for k in ['qualification','axes','J_F_N_s','observed_prefix','interventions']},
  H150_prefix_only={k:raw.get(k) for k in ['J_F','duration_s','phase_durations','status','model_beta']},
  commissioning_effective_reference_waypoints_rad=summary.get('commissioning',{}).get('effective_reference_waypoints_rad'),
  failed_requests=request_rows,last_task_decisions=decisions,final_trace=final,
  limitation='Failed original decision target and old candidate endpoint velocity are not serialized in retained failed task decisions. Only the recorded start-reference-velocity conjunct can be identified directly; remaining exact failed conjuncts are unresolved.',sources=sources)
 f=p/'audit_human'/(pid+'_FAILURE_DETAILS.json');f.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
 if args.mirror:shutil.copy2(f,args.mirror/f.name)
 print(json.dumps({'output':str(f),'abort_reason':out['abort_reason'],'failed_requests':[{k:x[k] for k in ['return_elapsed_s','schedule_origin_deg_deg_s','recorded_start_knee_velocity_conjunct_pass']} for x in request_rows],'final_trace':final,'physics_starts':0}))

if __name__=='__main__':main()
