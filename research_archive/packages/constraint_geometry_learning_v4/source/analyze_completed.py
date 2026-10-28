"""Per-completed-branch causal diagnostics and predictions; no new physics."""
from pathlib import Path
import os,sys,json,gzip,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'));from acl2_shared import put,read,sha,utc
import numpy as np
pred={a['tag']:a.get('prediction') for a in read('predictions/DEV_PREREGISTERED_PREDICTIONS.json')['actions']};model=read('analysis/FROZEN_BRANCH_MODEL.json')
for f in sorted((P/'attempts').glob('*_RESULT.json')):
 row=json.loads(f.read_text());ident=row['id'];out=P/'analysis/branches'/(ident+'.json')
 if out.exists() or not row['complete']:continue
 raw=P/'runtime/source/results'/ident/'runtime_artifacts.json.gz'
 if not raw.exists():continue
 with gzip.open(raw,'rt') as z:d=json.load(z)
 es=[e for e in d['execution_attempts'] if e.get('clearance_feedback')];event=min(es,key=lambda e:e['clearance_feedback']['model_curvature_m_s2']);cross=[e for e in es if e['clearance_feedback'].get('v4_branch_diagnostic',{}).get('directional_stencil_crosses')];c=event['clearance_feedback'];trace=d['trace'];clipped=sum(any(abs(float(v))>1e-9 for v in tr.get('robot_torque_components',{}).get('clipping',[])) for tr in trace);m=read(row['metrics_path']);su=json.loads((raw.parent/'summary.json').read_text());reference=[]
 for lr in su['learning_records']:
  plan=lr.get('selected_plan',{});sch=plan.get('schedule') or {};modal=plan.get('execution_screen',{}).get('coordination_modal_v2');reference.append(dict(decision_index=lr['decision_index'],request_time_s=lr['request_time_s'],accepted_modal=None if modal is None else modal['status'],activated=lr.get('selected_plan_activated'),duration_s=sch.get('duration_s'),target_q_rad=sch.get('target_q_rad'),target_dq_rad_s=sch.get('target_dq_rad_s'),modal=modal))
 pr=pred.get(ident[4:]) if ident.startswith('DEV_') else row.get('prediction')
 statecell=None
 if ident.startswith('DEV_') and (ident=='DEV_C19' or 'LOCAL_' in ident):
  receipts=d['wall_physics']['command_receipts'];r=min(receipts,key=lambda x:abs(x['source_sample_time_s']-27.07000000003824));ss=np.array(r['validation_state']);actual=[ss[0]-ss[1],ss[2]-ss[3]];estimated=[pr['predicted_phi'],pr['predicted_rate']];statecell=dict(actual_causal_phi_and_rate=actual,prediction_errors=np.array(estimated)-actual,cell_time_s=r['source_sample_time_s'],prediction_created_utc=read('predictions/DEV_PREREGISTERED_PREDICTIONS.json')['frozen_utc'])
 outrow=dict(id=ident,qualified=row['qualified'],JF=row['JF'],JM=row['JM'],axes=row['axes'],motion_failed_requirements=row['motion_vs_B']['failed_requirements'],motion_vs_B=row['motion_vs_B'],tracking_RMS_deg=m['tracking_RMS_deg'],clearance=m['clearance'],dose=m['dose'],native_motion=m['motion']['raw']['full'],force_peak_N=m['force_peak_N'],moment_peak_Nm=m['moment_peak_Nm'],guard_event_count=len(es),crossing_events=[dict(time_s=e['source_sample_time_s'],record=e['clearance_feedback'],applied=e['applied'],actual_robot_torque=e['applied_robot_tau_nm'],mode=e['mode']) for e in cross],minimum_curvature_event=dict(time_s=event['source_sample_time_s'],guard=c,mode=event['mode'],actual_robot_torque=event['applied_robot_tau_nm']),guard_unsatisfied_samples=sum(not e['clearance_feedback']['constraint_satisfied'] for e in es),post_filter_gap_unsatisfied_samples=sum(not e['clearance_feedback'].get('post_filter_gap_constraint_satisfied',True) for e in es),guard_active_samples=sum(e['clearance_feedback']['active'] for e in es),trace_torque_clipping_samples=clipped,prediction=pr,prediction_motion_match=None if not pr or 'predicted_motion_pass' not in pr else pr['predicted_motion_pass']==row['qualified'],local_cell_prediction=statecell,issued_reference_decisions=reference,actual_new_native_steps=row['actual_new_native_steps'],physical_wall_s=row['wall_s'],raw_sha256=sha(raw),scope='Measured branch fields are direct guard-consumed causal inputs; native truth appears only in evaluation metrics. No controller replacement.')
 put('analysis/branches/'+ident+'.json',outrow);print(ident,'qualified',row['qualified'],'crosses',len(cross),'mincurv',c['model_curvature_m_s2'],'motionmatch',outrow['prediction_motion_match'],'guard_axes',c.get('v4_branch_diagnostic'),flush=True)
