from study_common import *
from task_bootstrap import save as write
import csv
def main():
 version=sys.argv[1] if len(sys.argv)>1 else 'v1';prefix=sys.argv[2] if len(sys.argv)>2 else '040'
 config=json.loads((STUDY/('MATRIX_CONTRACT_'+version+'.json')).read_text());rows=[];groups={};failures=[]
 case,_=load_case_options();origin=np.radians(case['task']['start_deg']);span=np.radians(case['task']['goal_deg'])-origin
 for p in sorted((STUDY/'queue').glob(prefix+'_'+version+'_*.json')):
  request=json.loads(p.read_text());result_path=Path(request['result_path'])
  if not result_path.exists():failures.append(dict(id=request['id'],reason='NOT_RUN'));continue
  result=json.loads(result_path.read_text());m=result.get('metric',{});row=dict(id=request['id'],group=request['group'],method=request['method'],worker_status=result['status'],valid=m.get('valid',False),reason=result.get('error'),weights=request.get('weights'),seed=request.get('seed'),prefix=request.get('prefix'),**{k:m.get(k) for k in ('J_F','force_peak','moment_integral','moment_peak','duration_s','clearance','physical_clearance','phase_durations','rejections','host_s','initial_estimated_state','initial_reference','model_beta','model_residual','trace')})
  row.update(task_valid=m.get('task_valid'),matched_eligible=m.get('matched_eligible'),physical_audit=m.get('physical_audit'),call_audit=result.get('call_audit'),main_model_calls=m.get('actual_new_main_model_inverse_dynamics_api_calls'),native_worker_model_calls_separate=m.get('actual_new_native_worker_model_inverse_dynamics_api_calls'))
  f=L/(request['id']+'_SELECTIONS.json')
  if f.exists():
   rr=json.loads(f.read_text());sel=rr['rows'];lat=[r['end_to_end_s'] for r in sel];row.update(coordinator_mean_s=float(np.mean(lat)) if lat else 0,coordinator_max_s=max(lat or [0]),late_fraction=float(np.mean([r['late'] for r in sel])) if sel else 0,Q_calls=rr['network_Q_calls'],G_calls=rr['network_G_calls'],candidates=sum(r['candidate_count'] for r in sel),plan_changes=sum(r['plan_changed'] for r in sel),late_discards=sum(r['late_discard'] for r in sel),native_rejected_candidates=sum(not r.get('proposal_accepted',False) for s in sel for r in s['candidate_records']),P_calls=rr['P_performance_calls'])
  else:row.update(Q_calls=0,G_calls=0,candidates=0,plan_changes=0,P_calls=result.get('P_full_performance_calls'))
  if m.get('trace'):
   folder=R/Path(m['trace']).parent;summary=json.loads((folder/'summary.json').read_text());timing=summary.get('timing',{}).get('requests',[])
   task=[t for t in timing if t.get('stage')=='TASK'];ages=[t['activation_age_ms']/1000 for t in task if t.get('activation_age_ms') is not None]
   row.update(native_activation_mean_s=float(np.mean(ages)) if ages else None,native_activation_max_s=max(ages or [0]),host_55ms_exceed_fraction=float(np.mean(np.asarray(ages)>.055)) if ages else None,host_100ms_exceed_fraction=float(np.mean(np.asarray(ages)>=.1)) if ages else None,timing_mode=summary.get('execution_mode','SCIENTIFIC_SIMULATION'))
   with np.load(R/m['trace']) as z:
    phase=z['task_phase'].astype(str);t=z['time_s'];q=z['reference_q_rad'];truth=z['evaluation_only_human_state_rad_rad_s'][:,:2];tracking=truth-q
    task_mask=np.isin(phase,['OUTBOUND','HOLD','RETURN'])
    row['tracking_rms_deg']=np.degrees(np.sqrt(np.mean(tracking[task_mask]**2,axis=0))).tolist()
    # Store only compact executed phase progress for exact paired wave comparison.
    curves={}
    for name in ('OUTBOUND','RETURN'):
     mask=phase==name
     if not np.any(mask):continue
     qq=q[mask];base=origin if name=='OUTBOUND' else origin+span;direction=span if name=='OUTBOUND' else -span;progress=(qq-base)/direction
     physical_progress=(truth[mask]-base)/direction
     curves[name]=dict(t=(t[mask]-t[mask][0]).tolist(),common=progress.mean(1).tolist(),differential=((progress[:,0]-progress[:,1])/2).tolist(),physical_common=physical_progress.mean(1).tolist(),physical_differential=((physical_progress[:,0]-physical_progress[:,1])/2).tolist())
    row['_curves']=curves
  rows.append(row);groups.setdefault(row['group'],{})[row['method']]=row
 paired=[]
 for group,methods in groups.items():
  base=methods.get('M0')
  if base is None:continue
  for method,r in methods.items():
   if method=='M0':continue
   matched=all(np.array_equal(r.get(k),base.get(k)) for k in ('initial_estimated_state','initial_reference','model_beta','model_residual'))
   phases=r.get('phase_durations') or {};bp=base.get('phase_durations') or {};phase_error=max([abs(phases[k]-bp[k]) for k in phases if k in bp] or [float('inf')])
   valid=r['valid'] and base['valid'] and matched
   wave={}
   for phase,cur in r.get('_curves',{}).items():
    bcur=base.get('_curves',{}).get(phase)
    if bcur is None:continue
    grid=np.linspace(0,min(max(cur['t']),max(bcur['t'])),1001)
    for name in ('common','differential','physical_common','physical_differential'):
     delta=np.interp(grid,cur['t'],cur[name])-np.interp(grid,bcur['t'],bcur[name]);wave[phase+'_'+name]=dict(RMS=float(np.sqrt(np.mean(delta**2))),peak=float(np.max(np.abs(delta))))
   p=dict(group=group,method=method,valid_comparable=valid,initial_and_belief_equal=matched,phase_max_difference_s=phase_error,wave=wave)
   if valid:p.update(J_F_improvement_N_s=base['J_F']-r['J_F'],J_F_improvement_pct=100*(base['J_F']-r['J_F'])/base['J_F'],moment_change_pct=100*(r['moment_integral']-base['moment_integral'])/base['moment_integral'])
   paired.append(p)
 for row in rows:row.pop('_curves',None)
 summary={}
 for method in ('M0','M1','M2','M3','M4'):
  rr=[r for r in rows if r['method']==method];vv=[r for r in rr if r['valid']];pp=[p for p in paired if p['method']==method and p['valid_comparable']]
  summary[method]=dict(attempts=len(rr),valid=len(vv),J_F_mean=float(np.mean([r['J_F'] for r in vv])) if vv else None,moment_mean=float(np.mean([r['moment_integral'] for r in vv])) if vv else None,duration_mean=float(np.mean([r['duration_s'] for r in vv])) if vv else None,paired_improvement_pct=float(np.mean([p['J_F_improvement_pct'] for p in pp])) if pp else None,paired_min_pct=min([p['J_F_improvement_pct'] for p in pp] or [0]),quality_engineering_gate=bool(len(pp)>=4 and all(p['J_F_improvement_pct']>0 and p['phase_max_difference_s']<=.005 for p in pp) and np.mean([p['J_F_improvement_pct'] for p in pp])>=.5),coordinator_max_s=max([r.get('coordinator_max_s',0) for r in rr] or [0]),online_qualified=False)
 write(STUDY/('ANALYSIS_'+version+'.json'),dict(version=version,summary=summary,rows=rows,paired=paired,failures=failures,information='estimated B, exposed Human; nominal seeds are replication only',scientific_pass_not_realtime=True))
 with (STUDY/('RESULTS_'+version+'.csv')).open('w',newline='') as f:
  fields=['id','group','method','worker_status','valid','J_F','moment_integral','force_peak','moment_peak','duration_s','physical_clearance','coordinator_mean_s','coordinator_max_s','late_fraction','Q_calls','G_calls','candidates','plan_changes','native_activation_max_s','host_55ms_exceed_fraction'];writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
 print(json.dumps(summary))
if __name__=='__main__':main()
