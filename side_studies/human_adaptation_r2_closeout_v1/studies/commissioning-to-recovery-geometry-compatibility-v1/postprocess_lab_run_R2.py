"""Study-only scorer adapter; never executes a plant or controller."""
from pathlib import Path
import os,sys,json,gzip,tempfile,hashlib,csv
for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
W=Path('<SIDE_STUDIES_ROOT>/commissioning-to-recovery-geometry-compatibility-v1');R=W/'snapshot';S=R/'stages/stage5_personalized_motion_learning'
for stage in ['stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning']:sys.path.insert(0,str(R/'stages'/stage/'src'))
sys.path.insert(0,str(S/'scripts/high_rom_v1'))
import numpy as np
from evaluate_execution_mode import evaluate
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import _jsonable
def load(p):return json.loads(p.read_text() if p.exists() else gzip.open(str(p)+'.gz','rt').read())
def save(p,x):p.write_text(json.dumps(_jsonable(x),indent=2,allow_nan=False)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def summarize_predictions(path):
 p=path/'TASK_PREDICTION_SAMPLES.jsonl'
 if not p.exists():return {'status':'NO_TASK_PREDICTION_DATA','metrics':None}
 rows=[json.loads(l) for l in p.read_text().splitlines() if l.strip()]
 if not rows:return {'status':'NO_TASK_PREDICTION_DATA','metrics':None}
 metrics={}
 for scope,selected in [('all_TASK',rows),('nonlinear_soft_limit_inactive',[r for r in rows if not r['soft_limit_active']])]:
  metrics[scope]={'count':len(selected)}
  if not selected:continue
  for key in ['commissioning_frozen_error','prequential_error']:
   values=np.array([r[key] for r in selected]);metrics[scope][key]={'RMS_Nm':np.sqrt(np.mean(values**2,axis=0)).tolist(),'mean_Nm':np.mean(values,axis=0).tolist(),'peak_abs_Nm':np.max(np.abs(values),axis=0).tolist()}
  metrics[scope]['data_ranges']={key:{'min':np.min(np.array([r[key] for r in selected]),axis=0).tolist(),'max':np.max(np.array([r[key] for r in selected]),axis=0).tolist()} for key in ['q','dq','ddq','causal_reconstructed_torque']}
  metrics[scope]['time_range_s']=[selected[0]['time_s'],selected[-1]['time_s']]
 return {'status':'CAUSAL_TASK_ERROR_CHARACTERIZATION','metrics':metrics,'interpretation':rows[0]['definition'],'held_out_from_commissioning':True,'independent_population_or_future_forecast':False}
def process(path):
 q=load(path/'qualification.json');c=json.loads((W/'CONTRACT_R2.json').read_text());entry=next(x for x in c['conditions'] if x['id']==q['condition'])
 result={'condition':entry['id'],'arm':q['arm'],'status':q['completion'],'setup_status':'STATIC_NECESSARY_PRECHECK_PASS','commissioning_status':'UNKNOWN','task_status':'NOT_EVALUATED','physical_verdict':'NOT_EVALUATED','scientific_verdict':'NOT_EVALUATED','row_scope':'primary','case_sha256':entry['case_sha256'],'launch_exception':q.get('exception')}
 if q['completion']=='EXCEPTION':
  result['failure_stage']='Inspect retained capture/exception; do not invent TASK metrics'
  save(path/'PRIMARY_RESULT.json',result);return result
 summary=load(path/'summary.json');artifacts=load(path/'runtime_artifacts.json')
 case=entry['case'];scoring=json.loads((S/'docs/high_rom_v1/PHASE_B_MATRIX.json').read_text())['scoring']
 with tempfile.TemporaryDirectory(prefix='scorer_',dir=W) as temp:
  tmp=Path(temp);save(tmp/'summary.json',summary);save(tmp/'runtime_artifacts.json',artifacts)
  save(tmp/'HIGH_ROM_CASE_RESULT.json',{'status':summary['status'],'abort_reason':summary.get('abort_reason'),'case_sha256':entry['case_sha256'],'elapsed_host_s':q['elapsed_host_s'],'execution_mode':'SCIENTIFIC_SIMULATION','scientific_host_delay_ms':0.})
  (tmp/'trace.npz').symlink_to(path/'trace.npz')
  evaluation=evaluate(tmp,{'case_key':case['case_key'],'physical_variant':case['cell']['family'],'candidate':case.get('coordination_candidate'),'path':entry['case_path'],'sha256':entry['case_sha256']},scoring,goal_deg=case['task']['goal_deg'],start_deg=case['task']['start_deg'])
 save(path/'MODE_AWARE_AUDIT.json',evaluation)
 raw=evaluation['raw_scorer_v2'];handoff=summary['commissioning']['handoff_belief']
 result.update(commissioning_status='HANDOFF_AVAILABLE',task_status=summary['status'],physical_verdict=evaluation['physical_task_result']['status'],scientific_verdict=evaluation['scientific_validity']['status'],mode_overall=evaluation['overall_result_for_mode'],outbound_reached=None,hold_satisfied=raw['conditions'].get('true_goal_dwell'),true_return_satisfied=raw.get('true_return'),wall_characterization=evaluation['wall_runtime_characterization'],abort_reason=summary.get('abort_reason'))
 # Inherited runtime already calculates interaction integrals; no short/full ranking.
 keys=['J_F_task_n_s','force_mean_n','force_rms_n','force_peak_n','moment_integral_nm_s','moment_peak_nm','duration_s','minimum_clearance_m','minimum_true_clearance_m_evaluation_only','tracking_rmse_rad','tracking_truth_rmse_rad_evaluation_only','initial_beta','final_beta','geometry_estimate','geometry_used','accepted_dynamic_updates_total','residual_update_count','no_nan_task']
 result.update({key:q.get(key) for key in keys})
 with np.load(path/'trace.npz') as z:
  mask=z['stage']=='TASK';hat=z['estimated_human_state_rad_rad_s'][mask,:2];truth=z['evaluation_only_human_state_rad_rad_s'][mask,:2];ref=z['reference_q_rad'][mask]
  result['outbound_reached']=bool(np.any(np.all(np.abs(truth-np.radians(case['task']['goal_deg']))<=np.radians(scoring['angle_completion_tolerance_deg']),axis=1)&np.all(np.abs(z['evaluation_only_human_state_rad_rad_s'][mask,2:])<=np.radians(scoring['velocity_completion_tolerance_deg_s']),axis=1))) if len(truth) else None
  result['estimated_peak_tracking_error_rad']=np.max(np.abs(hat-ref),axis=0).tolist() if len(hat) else None
  result['evaluation_peak_tracking_error_rad']=np.max(np.abs(truth-ref),axis=0).tolist() if len(truth) else None
 changes=artifacts.get('adaptation_trace',summary.get('adaptation_trace',[]));attempts=[x.get('diagnostics',{}).get('beta_update',{}) for x in changes];attempts=[x for x in attempts if x.get('attempted')]
 result['TASK_updates']={'accepted_beta':sum(bool(x.get('accepted')) for x in attempts),'rejected_beta':sum(not x.get('accepted',False) for x in attempts),'rejection_reasons':{reason:sum(x.get('reason')==reason and not x.get('accepted') for x in attempts) for reason in {x.get('reason') for x in attempts if not x.get('accepted')}},'residual_changes':sum(x.get('diagnostics',{}).get('accepted_for_belief',False) for x in changes)}
 fit=summary['commissioning'].get('geometry_fit');truelever=case['physical']['cuff_fraction_of_shank']*.233*1.72
 result['effective_cuff_geometry_evaluation']={'true_knee_to_cuff_m':truelever,'estimated_knee_to_cuff_m':None if fit is None else fit.get('knee_to_cuff_m'),'absolute_error_m':None if fit is None or fit.get('knee_to_cuff_m') is None else abs(fit['knee_to_cuff_m']-truelever),'full_shank_and_rho_separately_identified':False,'scope':'evaluation only; truth never fed to fit/controller'}
 result['safety_counts']=summary.get('task',{}).get('safety_mode_counts',summary.get('task',{}).get('safety_counts'))
 result['fallback_events']=len(artifacts.get('safe_fallback_events',[]));result['activation_rejections']=sum(x.get('feasible') is not True for x in artifacts.get('activation_validations',[]))
 consumed=[]
 for p in path.glob('model_consumption_*.jsonl'):consumed.extend(json.loads(l) for l in p.read_text().splitlines() if l.strip())
 result['actual_model_consumption']={kind:{'calls':sum(r['kind']==kind for r in consumed),'numeric_beta_residual_hashes':sorted({r['payload']['numeric_model_sha256'] for r in consumed if r['kind']==kind}),'geometry_hashes':sorted({r['payload']['geometry_sha256'] for r in consumed if r['kind']==kind}),'PIDs':sorted({r['pid'] for r in consumed if r['kind']==kind})} for kind in ['planner','mechanics','execution']}
 result['consumption_logging_gaps']=[k for k,v in result['actual_model_consumption'].items() if v['calls']==0]
 result['prediction']=summarize_predictions(path)
 save(path/'TASK_PREDICTION_SUMMARY.json',result['prediction']);save(path/'HANDOFF_CHECKPOINT.json',handoff);save(path/'PRIMARY_RESULT.json',result)
 save(path/'RETENTION_REVIEW.json',{'status':'PENDING_OWN_RAW_RETENTION_REVIEW','full_trace_eligible':entry['id']=='C0' or result['mode_overall']!='PASS','key_adaptation_success_requires_triplet_comparison':True,'delete_authorization':'Only exact own generated temporary/reproducible artifacts after all compact metrics/scoring/model evidence hashed. Never delete unique failures or main/history.','raw_files':[{'path':p.name,'sha256':digest(p),'bytes':p.stat().st_size} for p in path.iterdir() if p.is_file()]})
 return result
if __name__=='__main__':
 if sys.argv[1:]==['--check']:
  assert str(Path(evaluate.__globals__['__file__']).resolve()).startswith(str(R))
  print('POSTPROCESS_IMPORT_CHECK_PASS; no data read or simulation')
 else:
  path=Path(sys.argv[1]).resolve();assert path.parent==W/'runs_R2'
  print(json.dumps({'result':process(path)['status']}))
