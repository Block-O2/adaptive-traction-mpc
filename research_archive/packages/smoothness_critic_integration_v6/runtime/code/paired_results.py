from pathlib import Path
import sys,os,json,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
S=Path('/home/hank/ihear-lab/smoothness_critic_integration_v6/runtime');sys.path.insert(0,str(S/'code'))
from jitter_attribution import q
import numpy as np
def main():
 registration=json.loads((S/'reports/PAIR_REGISTRATION.json').read_text());pairs=[]
 for p in registration['pairs']:
  records=[]
  for ident in p['ids']:
   path=S/'reports'/(ident+'_AXES.json')
   if path.exists():records.append(json.loads(path.read_text()))
  if len(records)!=2:
   pairs.append(dict(pair_id=p['pair_id'],status='NOT_RUN' if not records else 'INCOMPLETE_PAIR',attempted_ids=[r['id'] for r in records],valid_paired_gain=None));continue
  records.sort(key=lambda r:json.loads((S/'queue'/(r['id']+'.json')).read_text())['method'])
  B,M2=records;bc=json.loads((S/'queue'/(B['id']+'.json')).read_text());mc=json.loads((S/'queue'/(M2['id']+'.json')).read_text())
  differences={k:[bc.get(k),mc.get(k)] for k in set(bc)|set(mc) if bc.get(k)!=mc.get(k)}
  allowed={'id','method','durable_config_path'};assert not(set(differences)-allowed),differences
  valid=all(r['PHYSICAL_TASK_VALID']=='PASS' and r['HOST_EXECUTION_CAUSAL_VALID']=='PASS' for r in records)
  row=dict(pair_id=p['pair_id'],status='VALID_PAIR' if valid else 'FAILED_PAIR_NOT_RANKED',B_id=B['id'],M2_id=M2['id'],matched_config=True,config_differences=differences,valid_paired_gain=None,axes={r['id']:{k:r[k] for k in ('PHYSICAL_TASK_VALID','HOST_EXECUTION_CAUSAL_VALID','FAST_RUNTIME_ENGINEERING_QUALIFIED','LEGACY_R2_MATCHED','LEGACY_STRICT55')} for r in records})
  if valid:
   jfB,jfM=B['metric']['J_F'],M2['metric']['J_F'];miB,miM=B['metric']['moment_integral'],M2['metric']['moment_integral'];phases={}
   for phase in ('OUTBOUND','HOLD','RETURN'):
    b=B['phase_cost']['phases'][phase];m=M2['phase_cost']['phases'][phase];tb,tm=b['integrated_trace_duration_s'],m['integrated_trace_duration_s'];fb,fm=b['mean_force_N'],m['mean_force_N'];duration=(tm-tb)*(fm+fb)/2.;mean=(fm-fb)*(tm+tb)/2.;delta=m['J_F_N_s']-b['J_F_N_s'];assert abs(duration+mean-delta)<1e-8
    phases[phase]=dict(B=b,M2=m,delta_J_F_M2_minus_B_N_s=delta,duration_contribution_N_s=duration,mean_force_contribution_N_s=mean,delta_phase_clock_duration_s=m['phase_clock_duration_s']-b['phase_clock_duration_s'],delta_moment_integral_Nm_s=m['moment_integral_Nm_s']-b['moment_integral_Nm_s'])
   worker={}
   for r in records:
    e=json.loads((S/'output'/(r['id']+'_MULTIRATE.json')).read_text());task=[t for t in e['native_requests'] if t['stage']=='TASK'];co=json.loads((S/'output'/(r['id']+'_HOST_COORDINATOR.json')).read_text());sels=[z['selection_row'] for z in co['rows'] if z.get('selection_row')]
    worker[r['id']]=dict(original_full_native_compute_ms=q([t['compute_ms'] for t in task if t.get('compute_ms') is not None]),original_activation_age_ms=r['activation_age_ms'],Q_inference_ms=q([s['Q_inference_s']*1000 for s in sels]),coordinator_preproof_ms=q([z['worker_elapsed_ms'] for z in co['rows']]),late_carry=r['late_carry_count'],outcomes=r['request_outcomes'],rejections=r['rejections'])
   bm=B['metric'];mm=M2['metric'];physical={}
   for r in records:
    scorer=r['metric']['physical_audit']['unchanged_evaluator']['raw_scorer_v2']
    with np.load(S/'source/results'/r['id']/'trace.npz') as z:
     mask=z['stage']=='TASK';err=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][mask,:2]-z['reference_q_rad'][mask]);haterr=np.rad2deg(z['estimated_human_state_rad_rad_s'][mask,:2]-z['reference_q_rad'][mask])
    physical[r['id']]=dict(original_physical_task_status=r['metric']['physical_audit']['unchanged_evaluator']['physical_task_result']['status'],minimum_true_shank_clearance_m=scorer['minimum_true_shank_clearance_m'],minimum_session_shank_clearance_m=scorer['minimum_session_shank_clearance_m'],minimum_measured_sleeve_gap_m=scorer['minimum_measured_sleeve_gap_m'],peak_robot_torque_fraction=scorer['peak_robot_torque_fraction'],maximum_estimation_error_deg=scorer['maximum_estimation_error_deg'],true_reference_tracking_RMS_deg=np.sqrt(np.mean(err**2,axis=0)).tolist(),true_reference_tracking_max_abs_deg=np.max(np.abs(err),axis=0).tolist(),estimated_reference_tracking_RMS_deg=np.sqrt(np.mean(haterr**2,axis=0)).tolist(),scope='TASK trace samples; evaluation truth used only in post-execution audit; original safety scorer unchanged')
   row.update(valid_paired_gain=jfB-jfM,raw_B_J_F_N_s=jfB,raw_M2_J_F_N_s=jfM,gain_percent=(jfB-jfM)/jfB*100,raw_B_moment_integral_Nm_s=miB,raw_M2_moment_integral_Nm_s=miM,moment_delta_percent=(miM-miB)/miB*100,force_mean_N=dict(B=bm['force_mean'],M2=mm['force_mean']),force_peak_N=dict(B=bm['force_peak'],M2=mm['force_peak']),moment_peak_Nm=dict(B=bm['moment_peak'],M2=mm['moment_peak']),phases=phases,duration_contribution_sum_N_s=sum(z['duration_contribution_N_s'] for z in phases.values()),mean_force_contribution_sum_N_s=sum(z['mean_force_contribution_N_s'] for z in phases.values()),nonzero_M2_execution_count=M2['nonzero_execution_count'],nonzero_M2_plan_owned_native_steps=M2['nonzero_native_steps'],worker=worker,physical_summary=physical,physical_audits={r['id']:r['metric']['physical_audit'] for r in records},commissioning_note='Same case/initial physical configuration/waypoints/seed and host instrumentation; real-time observations and fitted commissioning models can differ. No exact post-commission trajectory identity imposed.')
  pairs.append(row)
 summary={}
 for condition in ('nominal','deviation'):
  rows=[p for p in pairs if p['pair_id'].startswith(condition) and p['status']=='VALID_PAIR'];gains=[p['valid_paired_gain'] for p in rows]
  summary[condition]=dict(valid_pairs=len(rows),gain_N_s=gains,mean_gain_N_s=None if not gains else float(np.mean(gains)),both_improved=bool(len(gains)==2 and min(gains)>0),moment_deltas_percent=[p['moment_delta_percent'] for p in rows],interpretation='descriptive matched development repeats; no significance or personalization claim')
 out=dict(status='PAIRED_EVALUATION_COMPLETE' if all(p['status']=='VALID_PAIR' for p in pairs) else 'INCOMPLETE_OR_FAILED_PAIRS_RETAINED',pairs=pairs,summary=summary,Q_updates=0,old_scientific_1335_comparison_used=False,phase_decomposition='exact symmetric product decomposition delta(time*mean force); clock durations separately retained; no HOLD clipping or fabricated intervals')
 (S/'PAIRED_RESULTS.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(status=out['status'],summary=summary,pairs=[{k:p.get(k) for k in ('pair_id','status','raw_B_J_F_N_s','raw_M2_J_F_N_s','valid_paired_gain','moment_delta_percent','nonzero_M2_execution_count')} for p in pairs])),flush=True)
if __name__=='__main__':main()
