from common import *
from scipy.signal import savgol_filter
import collections, itertools
PROFILES=load(OUT/'MOTION_QUALITY_PROTOCOL.json')['research_layer']['profiles']
def dose(t,q,v,phase):
 shapes={};boundaries={}
 for ph in ['OUTBOUND','HOLD','RETURN']:
  ix=np.flatnonzero(phase==ph)
  if not len(ix):continue
  u=(t[ix]-t[ix[0]])/max(t[ix[-1]]-t[ix[0]],1e-12)
  shapes[ph]=np.array([np.interp(np.linspace(0,1,201),u,q[ix,d]) for d in range(2)]).T
  boundaries[ph]=dict(start_deg=np.rad2deg(q[ix[0]]),end_deg=np.rad2deg(q[ix[-1]]),duration_s=t[ix[-1]]-t[ix[0]])
 return dict(duration_s=t[-1]-t[0],start_q_deg=np.rad2deg(q[0]),terminal_q_deg=np.rad2deg(q[-1]),terminal_dq_deg_s=np.rad2deg(v[-1]),excursion_deg=np.rad2deg(np.ptp(q,axis=0)),cumulative_q_travel_deg=np.rad2deg(np.sum(abs(np.diff(q,axis=0)),axis=0)),integrated_abs_dq_deg=np.rad2deg(np.trapz(abs(v),t,axis=0)),phase_boundaries=boundaries,phase_shape_deg={k:np.rad2deg(x) for k,x in shapes.items()})
def compare_motion(a,b,prof,burden_a,burden_b,secondary_a=None,secondary_b=None):
 failures=[];ratios={}
 for sig,mets in [('velocity_deg_s',['max_abs','p95_abs','rms']),('acceleration_deg_s2',['p95_abs','rms'])]:
  for met in mets:
   aa=np.asarray(burden_a[sig][met]);bb=np.asarray(burden_b[sig][met]);ratios[sig+'/'+met]=(aa/np.maximum(bb,1e-12)).tolist()
   if np.any(aa>prof['burden_ratio']*bb+1e-7):failures.append(sig+'/'+met)
 duration=abs(a['duration_s']-b['duration_s'])
 excursion=abs(np.asarray(a['excursion_deg'])-b['excursion_deg'])
 travel=np.asarray(a['cumulative_q_travel_deg'])/np.maximum(b['cumulative_q_travel_deg'],1e-12)
 endpoint=abs(np.asarray(a['terminal_q_deg'])-b['terminal_q_deg'])
 phase_boundary=0.;shape=0.
 for ph in b['phase_shape_deg']:
  if ph not in a['phase_shape_deg']:failures.append('missing_phase_'+ph);continue
  shape=max(shape,float(np.max(abs(np.asarray(a['phase_shape_deg'][ph])-b['phase_shape_deg'][ph]))))
  for k in ['start_deg','end_deg']:
   phase_boundary=max(phase_boundary,float(np.max(abs(np.asarray(a['phase_boundaries'][ph][k])-b['phase_boundaries'][ph][k]))))
 if duration>.1+1e-8:failures.append('task_duration')
 if np.any(excursion>prof['excursion_delta_deg']+1e-7):failures.append('actual_excursion')
 if np.any(travel>prof['cumulative_ratio']+1e-7):failures.append('cumulative_angular_travel')
 if np.any(endpoint>prof['endpoint_delta_deg']+1e-7) or phase_boundary>prof['endpoint_delta_deg']+1e-7:failures.append('phase_or_terminal_endpoint')
 if shape>prof['phase_shape_delta_deg']+1e-7:failures.append('phase_progress_q_shape')
 if secondary_a is not None:
  if secondary_a['moment']>secondary_b['moment']*1.25+1e-8:failures.append('moment_integral_bound')
  if np.any(np.asarray(secondary_a['tracking'])>np.asarray(secondary_b['tracking'])+.5+1e-8):failures.append('tracking_bounded_change')
 jerk_ok=all(np.all(np.asarray(burden_a['jerk_deg_s3'][m])<=prof['burden_ratio']*np.asarray(burden_b['jerk_deg_s3'][m])+1e-7) for m in ['p95_abs','rms'])
 return dict(screen_pass=not failures,failed_requirements=failures,burden_ratios=ratios,excursion_abs_delta_deg=excursion,cumulative_travel_ratio=travel,terminal_abs_delta_deg=endpoint,phase_boundary_max_delta_deg=phase_boundary,phase_shape_max_delta_deg=shape,duration_abs_delta_s=duration,optional_jerk_screen_pass=jerk_ok)
def host_audit():
 rows=[];brefs=[]
 for pair in load(OLD/'MOTION_BURDEN_AUDIT.json')['pairs']:
  pkg=pair['package'];data=[]
  for key in ['B_id','M2_id']:
   ident=pair[key];p=OLD/'motion_series'/f'{pkg}_{ident}.npz'
   with np.load(p) as z: d=dose(z['time_s'],z['true_q_rad'],z['true_dq_rad_s'],z['phase'])
   r=load(OLD/'motion_series'/f'{pkg}_{ident}_AUDIT.json');data.append((d,r))
   if key=='B_id':brefs.append(dict(id=ident,package=pkg,source=str(p),sha256=sha(p),dose=d,burden=r['actual_human']['raw']['full']))
  (b,br),(a,ar)=data
  profiles={pr['id']:compare_motion(a,b,pr,ar['actual_human']['raw']['full'],br['actual_human']['raw']['full'],dict(moment=ar['native_moment_integral_Nm_s'],tracking=ar['tracking_RMS_deg']),dict(moment=br['native_moment_integral_Nm_s'],tracking=br['tracking_RMS_deg'])) for pr in PROFILES}
  rows.append(dict(package=pkg,B_id=pair['B_id'],M2_id=pair['M2_id'],B_dose=b,M2_dose=a,excursion_delta_deg=np.asarray(a['excursion_deg'])-b['excursion_deg'],cumulative_travel_delta_deg=np.asarray(a['cumulative_q_travel_deg'])-b['cumulative_q_travel_deg'],endpoint_delta_deg=np.asarray(a['terminal_q_deg'])-b['terminal_q_deg'],J_F_delta_N_s=pair['J_F_delta_N_s'],profiles=profiles))
 save('FROZEN_B_REFERENCE_DISTRIBUTION.json',dict(references=brefs,status='RETROSPECTIVE_EXPOSED_REFERENCE',protocol_sha256=sha(OUT/'MOTION_QUALITY_PROTOCOL.json')))
 save('MOTION_DOSE_HOST_AUDIT.json',dict(pairs=rows,profile_pass_counts={pr['id']:sum(r['profiles'][pr['id']]['screen_pass'] for r in rows) for pr in PROFILES},interpretation='Actual peak-to-peak excursion is not endpoint change. Cumulative angular travel and phase-progress shape distinguish trajectory dose from task goal identity. No clinical dose inference.'))
 print('HOST_DOSE',[(r['B_id'],clean(r['excursion_delta_deg']),clean(r['cumulative_travel_delta_deg'])) for r in rows],flush=True)
def branch(r):
 budget();ident=r['id'];out=OUT/'branch_audits'/f'{ident}.json'
 if out.exists():return load(out)
 raw=load(r['source_file']);src=MATRIX/'source/results'/ident;at=raw['child']['physical_time_at_fork']
 with np.load(src/'trace.npz',allow_pickle=False) as z: s={k:z[k].copy() for k in z.files}
 ix=np.flatnonzero(s['stage']=='TASK');ts=s['time_s'][ix]
 _,rev=np.unique(ts[::-1],return_index=True);ix=ix[np.sort(len(ts)-1-rev)];ts=s['time_s'][ix]
 rows=[]
 for v in array_items(src/'runtime_artifacts.json.gz','native_states_evaluation_only'):
  if ts[0]-1e-8<=v['time_s']<=ts[-1]+1e-8:rows.append((v['time_s'],v['qpos_evaluation_only'],v['qvel_evaluation_only']))
 t=np.array([v[0] for v in rows]);nq=np.array([v[1] for v in rows]);nv=np.array([v[2] for v in rows]);del rows
 assert len(t)>10 and np.all(np.diff(t)>0),'INVALID_NATIVE_NODES'
 mi=np.clip(np.searchsorted(t,ts),0,len(t)-1);le=np.maximum(mi-1,0);mi=np.where(abs(t[le]-ts)<abs(t[mi]-ts),le,mi);close=abs(t[mi]-ts)<1e-8
 truth=s['evaluation_only_human_state_rad_rad_s'][ix];eq=np.max(abs(nq[mi[close],:,None]-truth[close,None,:2]),axis=0);ev=np.max(abs(nv[mi[close],:,None]-truth[close,None,2:]),axis=0);qi=np.argmin(eq,axis=0);vi=np.argmin(ev,axis=0)
 assert np.max(eq[qi,np.arange(2)])<1e-8 and np.max(ev[vi,np.arange(2)])<1e-8,'HUMAN_MAPPING'
 q=nq[:,qi];dq=nv[:,vi];del nq,nv
 summary=load(src/'summary.json');phase=np.full(len(t),'OUTBOUND',dtype='<U10')
 for v in summary['task']['phase_transitions']:
  if v['to'] in ['OUTBOUND','HOLD','RETURN']:phase[t>=v['time_s']-1e-9]=v['to']
 rem=t>=at-1e-8;si=ts>=at-1e-8;allstats={};windows=[]
 events=[('PHASE_'+v['to'],v['time_s'],.1) for v in summary['task']['phase_transitions'] if v['time_s']>=at-1e-8]
 for d in range(2):
  for i in np.flatnonzero(dq[:-1,d]*dq[1:,d]<0):
   if t[i]>=at-1e-8 and np.max(abs(np.rad2deg(dq[max(0,i-80):min(len(t),i+81),d])))>=.5:events.append(('REVERSAL_JOINT_'+str(d),t[i],.02))
 acc=np.gradient(dq,t,axis=0,edge_order=2);jerk=np.gradient(acc,t,axis=0,edge_order=2)
 for window in [0,5,21]:
  v=dq if not window else savgol_filter(dq,window,3,axis=0,mode='interp');a=np.gradient(v,t,axis=0,edge_order=2);j=np.gradient(a,t,axis=0,edge_order=2)
  sig=dict(velocity_deg_s=np.rad2deg(v),acceleration_deg_s2=np.rad2deg(a),jerk_deg_s3=np.rad2deg(j));filt='raw' if not window else 'savgol_'+str(window)
  allstats[filt]=dict(full={k:stat(x) for k,x in sig.items()},remaining={k:stat(x[rem]) for k,x in sig.items()},phases={ph:{k:stat(x[(phase==ph)&rem]) for k,x in sig.items()} for ph in ['OUTBOUND','HOLD','RETURN'] if np.any((phase==ph)&rem)})
  if window==0:
   for label,et,half in events:
    mask=abs(t-et)<=half
    if mask.any():windows.append(dict(kind=label,time_s=et,halfwidth_s=half,signals={k:stat(x[mask]) for k,x in sig.items()}))
 tracefile=OUT/'dense_branch_series'/f'{ident}.npz';tracefile.parent.mkdir(exist_ok=True)
 np.savez_compressed(tracefile,time_s=t,true_q_rad=q,true_dq_rad_s=dq,acceleration_rad_s2=acc,jerk_rad_s3=jerk,phase=phase,fork_physical_s=np.array(at))
 receipts=[v for v in array_items(src/'runtime_artifacts.json.gz','command_receipts') if v.get('end_physics_s',0)>at+1e-9]
 receipt_index=OUT/'receipt_series'/f'{ident}.npz';receipt_index.parent.mkdir(exist_ok=True)
 np.savez_compressed(receipt_index,start_physics_s=np.array([v['start_physics_s'] for v in receipts]),end_physics_s=np.array([v['end_physics_s'] for v in receipts]),native_steps=np.array([v.get('native_steps',0) for v in receipts]),receipt_index=np.array([v.get('receipt_index',-1) for v in receipts]),reference_effective_physics_s=np.array([v.get('reference_effective_physics_s',np.nan) for v in receipts]),q_ref_rad=np.array([v.get('q_ref_rad',[np.nan,np.nan]) for v in receipts]),dq_ref_rad_s=np.array([v.get('dq_ref_rad_s',[np.nan,np.nan]) for v in receipts]))
 requests=[v for v in array_items(src/'runtime_artifacts.json.gz','requests') if v.get('stage')=='TASK' and v.get('source_sample_time_s',0)>=at-1e-8]
 decisions=load(MATRIX/'output'/(ident+'_DECISIONS.json'))
 mask=np.ones((2,5,3),bool);counts=raw['branch_start']['counts']
 for d,ph in enumerate(['OUTBOUND','RETURN']):mask[d,:min(counts[ph],5)]=False
 plan=np.asarray(raw['table']);x=np.asarray(raw['branch_start']['input'],np.float32)
 assert np.max(abs((plan*mask).ravel()-x[58:88]))<1e-6
 cost=raw['metric']['J_F']-raw['child']['start_J_F'];vr=raw['value_rows'][0]['remaining_J_F'];assert abs(cost-r['y'])<1e-6 and abs(cost-vr)<1e-6
 # Interval logger stores force accumulated since preceding evaluation. Strictly
 # after-fork samples avoid charging the pre-fork interval twice.
 integral=np.sum(s['interval_force_cost_n_s'][ix][ts>at+1e-8]);err=float(integral-cost)
 full_err=np.rad2deg(truth[:,:2]-s['reference_q_rad'][ix]);future_err=full_err[si]
 nativeaudit=raw['metric']['physical_audit'];mode=nativeaudit['unchanged_evaluator'];phys=mode['physical_task_result'];sci=mode.get('scientific_validity',{})
 outrow=dict(id=ident,parent=r['parent'],split=r['split'],snapshot=r['snapshot'],phase=raw['branch_start']['context']['phase'],task_s=raw['branch_start']['context']['task_s'],model_hash=raw['branch_start']['context']['model_hash'],model_beta=raw['metric']['model_beta'],candidate_source=r['candidate_source'],candidate_table=plan,eligible_slot_mask=mask,counts=counts,carry=raw['branch_start']['carry'],x120=x,context=raw['branch_start']['context'],candidate_identity_sha256=hashlib.sha256(np.asarray(x[58:88],dtype='<f4').tobytes()).hexdigest(),mask_identity=hashlib.sha256(mask.tobytes()).hexdigest(),remaining_J_F_N_s=cost,full_J_F_N_s=raw['metric']['J_F'],remaining_moment_Nm_s=raw['remaining_M'],full_moment_Nm_s=raw['metric']['moment_integral'],force_peak_N=raw['metric']['force_peak'],moment_peak_Nm=raw['metric']['moment_peak'],tracking_RMS_deg=np.sqrt(np.mean(full_err**2,axis=0)),remaining_tracking_RMS_deg=np.sqrt(np.mean(future_err**2,axis=0)),clearance=raw['metric']['physical_clearance'],status='HISTORICAL_VALID_COMMITTED_SCIENTIFIC',host_contract_status='NOT_EVALUABLE',physical_pass=bool(raw['metric']['valid'] and phys['status']=='PASS'),scientific_causal_status=sci.get('status'),raw_plan_age_condition=mode['raw_scorer_v2']['conditions']['plan_age'],hard_tracking_original='Original native qualification retained; no extra clinical tracking threshold invented.',quality=dict(native_samples=len(t),remaining_native_samples=int(rem.sum()),dt_min_s=np.min(np.diff(t)),dt_max_s=np.max(np.diff(t)),mapping_q_indices=qi,mapping_dq_indices=vi,common_verified_nodes=int(close.sum()),mapping_max_error=max(np.max(eq[qi,np.arange(2)]),np.max(ev[vi,np.arange(2)]))),motion=allstats,full_dose=dose(t,q,dq,phase),remaining_dose=dose(t[rem],q[rem],dq[rem],phase[rem]),windows=windows,remaining_integral_check=dict(terminal_minus_prefix_N_s=cost,first_value_row_N_s=vr,trace_interval_sum_after_fork_N_s=integral,trace_sum_error_N_s=err),execution=dict(command_receipt_file=str(receipt_index),receipt_count=len(receipts),receipt_native_steps_sum=sum(v.get('native_steps',0) for v in receipts),metric_new_native_steps=raw['metric']['actual_new_native_physics_steps'],requests=requests,decisions=decisions,contract='Candidate table is consumed at original B-owned request counts, with native certification/fallback and zero after slot5. Receipts prove actual commands; proposal actions alone do not prove residual activation.'),sources={str(p):sha(p) for p in [Path(r['source_file']),src/'trace.npz',src/'runtime_artifacts.json.gz',src/'summary.json',MATRIX/'output'/(ident+'_DECISIONS.json')]},derived_dense_trace=str(tracefile))
 save('branch_audits/'+ident+'.json',outrow)
 print('DENSE_BRANCH',ident,len(t),'integral_error',err,flush=True)
 return clean(outrow)
def main():
 host_audit();old=load(OLD/'BRANCH_LABELS.json');rows=[branch(r) for r in old['rows']]
 save('COUNTERFACTUAL_BRANCH_RESULTS.json',dict(new_attempts=[],new_valid_rows=0,historical_rows=rows,historical_failed_rows=old['failed_rows'],historical_excluded_rows=old['excluded_rows'],historical_count=len(rows),scientific_label_contract='native-certified-committed-K3-suffix-v1',host_contract_valid_labels=0))
 save('COUNTERFACTUAL_DATASET_MANIFEST.json',dict(status='HISTORICAL_DENSE_AUDIT_ONLY_NO_NEW_STATE',sources=old['all_sources'],rows=len(rows),snapshots=len(set(r['snapshot'] for r in rows)),parent_groups=sorted(set(r['parent'] for r in rows)),grouping='parent/source group, not branch row; one exposed simulated Human',dense_trace_index=[dict(id=r['id'],path=r['derived_dense_trace'],sha256=sha(r['derived_dense_trace']),source_hashes=r['sources']) for r in rows],invalid_attempts=old['failed_rows'],exclusions=old['excluded_rows'],new_branch_attempts=0,new_training_dataset_status='NOT_CREATED_NO_NEW_VALID_STATE',read_only_reusable_export='HISTORICAL_DENSE_COMMITTED_AUDIT.npz, historical cohort unchanged; no training performed'))
 np.savez_compressed(OUT/'HISTORICAL_DENSE_COMMITTED_AUDIT.npz',x=np.array([r['x120'] for r in rows],np.float32),remaining_J_F_N_s=np.array([r['remaining_J_F_N_s'] for r in rows]),source_id=np.array([r['id'] for r in rows]),snapshot=np.array([r['snapshot'] for r in rows]),parent=np.array([r['parent'] for r in rows]),split=np.array([r['split'] for r in rows]),dense_trace=np.array([r['derived_dense_trace'] for r in rows]))
 print('ANALYSIS_EXTRACT_COMPLETE',len(rows),flush=True)
if __name__=='__main__': main()
