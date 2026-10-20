from attribution import load,clean,save,firstdiff
from pathlib import Path
import os,sys,time,hashlib,inspect,collections,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
import numpy as np
from scipy.signal import savgol_filter
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
from stream_runtime_evidence import array_items
def stats(v):return dict(max_abs=np.max(abs(v),axis=0),p95_abs=np.quantile(abs(v),.95,axis=0),rms=np.sqrt(np.mean(v*v,axis=0)))
def phasecost(ident,metric):
 s=load(S/'source/results'/ident/'summary.json')
 with np.load(S/'source/results'/ident/'trace.npz') as z:
  j=z['stage']=='TASK';t=z['time_s'][j];f=np.linalg.norm(z['physical_cuff_force_world_n'][j],axis=1);m=np.linalg.norm(z['physical_cuff_moment_world_nm'][j],axis=1)
 trans={r['to']:r['time_s'] for r in s['task']['phase_transitions']};bounds=[t[0],trans['HOLD'],trans['RETURN'],trans['COMPLETE']];rows={}
 for ph,a,b in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:]):
  dt=np.maximum(0,np.minimum(t[1:],b)-np.maximum(t[:-1],a));used=dt>0;jf=float(f[:-1]@dt);mi=float(m[:-1]@dt);duration=float(dt.sum())
  rows[ph]=dict(J_F_N_s=jf,moment_integral_Nm_s=mi,integrated_trace_duration_s=duration,phase_clock_duration_s=metric['phase_durations'][ph],mean_force_N=jf/duration,mean_moment_Nm=mi/duration,force_peak_N=float(f[:-1][used].max()),moment_peak_Nm=float(m[:-1][used].max()))
 error=sum(r['J_F_N_s'] for r in rows.values())-metric['J_F'];me=sum(r['moment_integral_Nm_s'] for r in rows.values())-metric['moment_integral'];assert abs(error)<1e-8 and abs(me)<1e-8,'INTEGRAL_CLOSURE'
 return dict(status='COMPLETE_RAW_CLOSURE_PASS',phases=rows,raw_full_J_F_N_s=metric['J_F'],raw_full_moment_integral_Nm_s=metric['moment_integral'],closure_error_N_s=error,moment_closure_error_Nm_s=me,method='unchanged full TASK left quadrature, exact clipping of every interval at actual phase boundaries')
def lineage(ident,summary,native):
 p=S/'source/results'/ident;receipts=list(array_items(p/'runtime_artifacts.json.gz','command_receipts'));lookup={r['receipt_index']:r for r in receipts if r.get('applied')};errors=[];counts=collections.Counter();positive=sorted([r for r in receipts if r.get('applied') and r.get('native_steps',0)>0],key=lambda r:r['start_physics_s']);starts=np.array([r['start_physics_s'] for r in positive]);ends=np.array([r['end_physics_s'] for r in positive]);join_kind='direct recorded command_id'
 if any(r.get('command_id') is None for r in native):
  join_kind='original scientific native trace lacks command_id; unique contiguous positive-step receipt interval reconstructed from exact native grid, then torque and step counts checked'
  assert len(positive)>0 and np.all(abs(starts[1:]-ends[:-1])<1e-8),'RECEIPT_NOT_CONTIGUOUS'
 for row in native:
  cid=row.get('command_id')
  if cid is None:
   begin=row['time_s']-.00025;index=int(np.searchsorted(starts,begin+1e-9,side='right')-1);cid=positive[index]['receipt_index'] if index>=0 and begin<ends[index]-1e-9 else None
  counts[cid]+=1;r=lookup.get(cid)
  if r is None:errors.append(dict(type='UNOWNED_NATIVE_STEP',time_s=row['time_s'],command_id=cid));continue
  if not r['start_physics_s']-1e-8<=row.get('physical_interval_start_s',row['time_s']-.00025)<r['end_physics_s']+1e-8:errors.append(dict(type='OUTSIDE_RECEIPT_INTERVAL',time_s=row['time_s'],command_id=cid))
  if not np.array_equal(np.asarray(row['command_torque_nm']),np.asarray(r['command_torque_nm'])):errors.append(dict(type='COMMAND_MISMATCH',time_s=row['time_s'],command_id=cid))
 for cid,n in counts.items():
  if cid in lookup and lookup[cid]['native_steps']!=n:errors.append(dict(type='STEP_COUNT',command_id=cid,receipt_steps=lookup[cid]['native_steps'],native_steps=n))
 age=[];expired=[]
 for r in receipts:
  if r.get('applied') and r.get('apply_ns') is not None:
   value=r.get('sensor_age_at_apply_ms');age.append(value)
   if value is not None and value>100+1e-7:expired.append(r['receipt_index'])
 rows=[];decisions=summary['decisions']
 for rec in summary['learning_records']:
  idx=rec.get('decision_index');d=decisions[idx] if idx is not None and idx<len(decisions) else {};meta=rec.get('selected_plan',{}).get('execution_screen',{}).get('coordination_residual_v2',{});start=rec.get('start_time_s');end=rec.get('end_time_s');activated=bool(rec.get('selected_plan_activated'));owned=[r for r in receipts if r.get('applied') and r.get('native_steps',0)>0 and activated and start is not None and end is not None and start-1e-9<=r['start_physics_s']<end-1e-9]
  nonzero=meta.get('status')=='ACCEPTED' and abs(meta.get('delta',0))>1e-12
  if meta.get('status')=='ACCEPTED':assert abs(meta['common_error'])<1e-12 and np.allclose(np.asarray(meta['modified_progress'])-meta['nominal_progress'],[meta['delta'],-meta['delta']],rtol=0,atol=1e-12),'NATIVE_RESIDUAL_SEMANTICS'
  phase=rec.get('phase',d.get('phase'))
  if phase is None:
   request=d.get('decision_request_time_s',start);phase='OUTBOUND'
   for tr in summary['task']['phase_transitions']:
    if tr['time_s']<=request+1e-9 and tr['to'] in ['OUTBOUND','HOLD','RETURN']:phase=tr['to']
  rows.append(dict(decision_index=idx,request_id=d.get('timing_request_id'),phase=phase,proposal_physics_s=d.get('decision_request_time_s'),activation_outcome=d.get('activation_outcome'),selected_plan_activated=activated,native_coordination_metadata=[meta],native_nonzero=nonzero,actual_native_steps=sum(r['native_steps'] for r in owned),physically_executed_nonzero=bool(nonzero and activated and owned),first_execution_physics_s=min([r['start_physics_s'] for r in owned],default=None),actual_command_receipts=[{k:r.get(k) for k in ['receipt_index','source_sample_time_s','apply_ns','sensor_age_at_apply_ms','start_physics_s','end_physics_s','native_steps','q_ref_rad','dq_ref_rad_s','command_torque_nm','validation_model_version','reference_version']} for r in owned],plan_age_s=d.get('plan_age_s'),stale=d.get('stale'),deadline_miss=d.get('deadline_miss'),rejection_reason=d.get('activation_rejected_reason')))
 out=dict(id=ident,clock='SCIENTIFIC_SIMULATION',status='PASS' if not errors and not expired else 'FAIL',native_steps=len(native),receipt_count=len(receipts),ownership_errors=errors[:50],ownership_error_count=len(errors),expired_actual_write_receipts=expired,age_ms=dict(n=len(age),max=max([x for x in age if x is not None],default=None)),rows=rows,actual_nonzero_count=sum(r['physically_executed_nonzero'] for r in rows),actual_nonzero_native_steps=sum(r['actual_native_steps'] for r in rows if r['physically_executed_nonzero']),native_lifecycle=summary['timing'],proposal_only_not_execution=True,host_clock_causal_qualification='NOT_EVALUABLE',join_kind=join_kind,source_semantics='unchanged wall_physics._step increments active_receipt_index.native_steps and records applied torque after each mj native step; scientific_scheduler.apply sets active_receipt_index on successful current-state certified write',scope='every archived native substep joined uniquely to positive-step receipt interval, exact torque and native count; original mode-aware native safety/admission retained')
 save(S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json'),out);return out
def measure(ident):
 p=S/'source/results'/ident;summary=load(p/'summary.json');metric=load(S/'output'/(ident+'.json'));data=load(S/'output'/(ident+'_DATA.json'))
 with np.load(p/'trace.npz') as z:
  ix=np.flatnonzero(z['stage']=='TASK');ts=z['time_s'][ix];_,rev=np.unique(ts[::-1],return_index=True);ix=ix[np.sort(len(ts)-1-rev)];ts=z['time_s'][ix];truth=z['evaluation_only_human_state_rad_rad_s'][ix];ref=z['reference_q_rad'][ix];tracking=np.rad2deg(np.sqrt(np.mean((truth[:,:2]-ref)**2,axis=0)))
 native=list(array_items(p/'runtime_artifacts.json.gz','native_states_evaluation_only'));line=lineage(ident,summary,native);wall_steps=np.asarray([(r['host_step_finish_ns']-r['host_step_start_ns'])/1e6 for r in native]);fast=dict(clock='host profiling within frozen scientific epochs',native_step_wall_ms=dict(n=len(wall_steps),p50=float(np.quantile(wall_steps,.5)),p95=float(np.quantile(wall_steps,.95)),p99=float(np.quantile(wall_steps,.99)),mean=float(wall_steps.mean()),max=float(wall_steps.max())),original_host_FAST_service_gap='NOT_EVALUABLE in this scientific execution route',host_clock_runtime_qualification='NOT_EVALUABLE',wall_activation_age_profile=metric['physical_audit']['unchanged_evaluator']['wall_runtime_characterization'])
 rows=[r for r in native if ts[0]-1e-9<=r['time_s']<=ts[-1]+1e-9];del native
 t=np.array([r['time_s'] for r in rows]);qp=np.asarray([r['qpos_evaluation_only'] for r in rows]);vp=np.asarray([r['qvel_evaluation_only'] for r in rows]);del rows
 assert len(t)>2 and np.all(np.diff(t)>0),'TRACE_TIME';assert np.max(abs(np.diff(t)-.00025))<1e-10,'PHYSICS_STEP_CONTRACT'
 mi=np.clip(np.searchsorted(t,ts),0,len(t)-1);left=np.maximum(mi-1,0);mi=np.where(abs(t[left]-ts)<abs(t[mi]-ts),left,mi);close=abs(t[mi]-ts)<1e-8;eq=np.max(abs(qp[mi[close],:,None]-truth[close,None,:2]),axis=0);ev=np.max(abs(vp[mi[close],:,None]-truth[close,None,2:]),axis=0);qi=np.argmin(eq,axis=0);vi=np.argmin(ev,axis=0);mapping=max(np.max(eq[qi,np.arange(2)]),np.max(ev[vi,np.arange(2)]));assert mapping<1e-8,'HUMAN_MAPPING'
 q=qp[:,qi];v=vp[:,vi];phase=np.full(len(t),'OUTBOUND',dtype='<U10')
 for r in summary['task']['phase_transitions']:
  if r['to'] in ['OUTBOUND','HOLD','RETURN']:phase[t>=r['time_s']-1e-9]=r['to']
 motion={};shapes={};boundaries={}
 for ph in ['OUTBOUND','HOLD','RETURN']:
  j=np.flatnonzero(phase==ph);assert len(j)>2;u=(t[j]-t[j[0]])/(t[j[-1]]-t[j[0]]);shapes[ph]=np.rad2deg(np.column_stack([np.interp(np.linspace(0,1,201),u,q[j,d]) for d in range(2)]));boundaries[ph]=dict(start_deg=np.rad2deg(q[j[0]]),end_deg=np.rad2deg(q[j[-1]]))
 for w in [0,5,21]:
  vv=v if w==0 else savgol_filter(v,w,3,axis=0,mode='interp');acc=np.gradient(vv,t,axis=0,edge_order=2);jerk=np.gradient(acc,t,axis=0,edge_order=2);signals=dict(velocity_deg_s=np.rad2deg(vv),acceleration_deg_s2=np.rad2deg(acc),jerk_deg_s3=np.rad2deg(jerk));motion['raw' if w==0 else 'SG'+str(w)]=dict(full={k:stats(a) for k,a in signals.items()},phases={ph:{k:stats(a[phase==ph]) for k,a in signals.items()} for ph in ['OUTBOUND','HOLD','RETURN']})
  if w==0:np.savez_compressed(S/'motion_series'/(ident+'.npz'),time_s=t,true_q_rad=q,true_dq_rad_s=v,acceleration_rad_s2=acc,jerk_rad_s3=jerk,phase=phase)
 force=phasecost(ident,metric);dose=dict(duration_s=t[-1]-t[0],excursion_deg=np.rad2deg(np.ptp(q,axis=0)),cumulative_travel_deg=np.rad2deg(np.sum(abs(np.diff(q,axis=0)),axis=0)),endpoint_deg=np.rad2deg(q[-1]),phase_boundaries=boundaries,phase_shapes=shapes)
 a=dict(id=ident,clock='SCIENTIFIC_SIMULATION',J_F_N_s=metric['J_F'],phase_cost=force,force_peak_N=metric['force_peak'],moment_integral_Nm_s=metric['moment_integral'],moment_peak_Nm=metric['moment_peak'],tracking_RMS_deg=tracking,clearance=metric.get('physical_clearance'),native_physical_audit=metric['physical_audit'],phase_durations=metric['phase_durations'],motion=motion,dose=dose,axes=dict(PHYSICAL_TASK_VALID='PASS' if metric['task_valid'] else 'FAIL',SCIENTIFIC_EXECUTION_CAUSAL_VALID=line['status'],HOST_EXECUTION_CAUSAL_VALID='NOT_EVALUABLE',LEGACY_R2_MATCHED='PASS' if metric['matched_eligible'] else 'FAIL'),native_steps=metric['native_physics_steps'],actual_new_native_steps=data['metric']['actual_new_native_physics_steps'],execution_lineage_path=str(S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')),commissioning={k:metric.get(k) for k in ['model_beta','model_residual','initial_estimated_state','initial_reference']},FAST_observations=fast,quality=dict(native_samples=len(t),common_nodes=int(close.sum()),qpos_indices=qi,qvel_indices=vi,mapping_max_error=mapping,native_dt_min_s=np.min(np.diff(t)),native_dt_max_s=np.max(np.diff(t))),branch=data['branch_start'],sources={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [p/'trace.npz',p/'summary.json',p/'runtime_artifacts.json.gz',S/'output'/(ident+'_DATA.json')]})
 save(S/'reports'/(ident+'_MEASURED.json'),a);assert a['axes']['PHYSICAL_TASK_VALID']=='PASS' and line['status']=='PASS','PHYSICAL_OR_OWNERSHIP_FAILURE';return clean(a)
def compare(a,b):
 import explore_common as ec
 src=inspect.getsource(ec.compare);assert src.count("a['axes']['HOST_EXECUTION_CAUSAL_VALID']")==1
 src=src.replace("a['axes']['HOST_EXECUTION_CAUSAL_VALID']","a['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']")
 namespace=dict(ec.__dict__);exec(compile(src,'<original frozen comparison, mode-aware ownership field binding>','exec'),namespace);out=namespace['compare'](a,b);out['clock']='SCIENTIFIC_SIMULATION';out['HOST_EXECUTION_CAUSAL_VALID']='NOT_EVALUABLE';out['evaluator_binding']='identical prior thresholds and formulas, only ownership field bound to original scientific-mode native receipt audit'
 phases={}
 for ph in ['OUTBOUND','HOLD','RETURN']:
  x=a['phase_cost']['phases'][ph];y=b['phase_cost']['phases'][ph];dc=(x['integrated_trace_duration_s']-y['integrated_trace_duration_s'])*(x['mean_force_N']+y['mean_force_N'])/2;fc=(x['mean_force_N']-y['mean_force_N'])*(x['integrated_trace_duration_s']+y['integrated_trace_duration_s'])/2;delta=x['J_F_N_s']-y['J_F_N_s'];assert abs(dc+fc-delta)<1e-8;phases[ph]=dict(delta_J_F_N_s=delta,duration_contribution_N_s=dc,mean_force_contribution_N_s=fc)
 out['symmetric_phase_decomposition']=phases;return out
def negcontrol(a,b):
 line=load(S/'reports'/(a+'_EXECUTED_RESIDUAL_RECEIPTS.json'));times=[r['first_execution_physics_s'] for r in line['rows'] if r['physically_executed_nonzero']];first=min(times) if times else None;fields=[];mismatches=[]
 with np.load(S/'source/results'/a/'trace.npz') as za,np.load(S/'source/results'/b/'trace.npz') as zb:
  mask=(za['time_s']<first-1e-9) if first is not None else np.ones(len(za['time_s']),bool)
  for key in za.files:
   if za[key].shape[0]!=len(mask):continue
   x=za[key][mask];keep=zb['time_s']<first-1e-9 if first is not None else np.ones(len(zb['time_s']),bool);y=zb[key][keep];same=x.shape==y.shape and (np.array_equal(x,y,equal_nan=True) if x.dtype.kind in 'fc' else np.array_equal(x,y));fields.append(dict(variable=key,equal=same,missing_values_equal_only=x.dtype.kind in 'fc' and bool(np.any(~np.isfinite(x)))))
   if not same:mismatches.append(key)
 return dict(candidate=a,B=b,first_actual_nonzero_physics_s=first,all_pre_intervention_fields_exact_equal=not mismatches,mismatches=mismatches,fields=fields,interpretation='negative control, no pre-intervention force/motion benefit attribution')
def main():
 ids=[p.name[:-10] for p in sorted((S/'output').glob('*_DATA.json'))];measured={}
 for ident in ids:
  if ident not in [r['id'] for r in [json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()] if r['event']=='START']:continue
  path=S/'reports'/(ident+'_MEASURED.json');cached=load(path) if path.exists() else None;measured[ident]=cached if cached is not None and cached['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS' else measure(ident);print('MEASURED '+ident,flush=True)
 save(S/'MOTION_FORCE_TRADEOFFS.json',dict(clock='SCIENTIFIC_SIMULATION',clinical_thresholds=False,runs=list(measured.values()),denominator=len(measured)))
 save(S/'NATIVE_EXECUTION_LINEAGE.json',dict(clock='SCIENTIFIC_SIMULATION',HOST_EXECUTION_CAUSAL_VALID='NOT_EVALUABLE',runs=[load(S/'reports'/(i+'_EXECUTED_RESIDUAL_RECEIPTS.json')) for i in measured],denominator=len(measured)))
 group='matched_discovery' if 'matched_discovery_parent_B0' in measured else 'discovery'
 base=group+'_parent_B0_replacement' if group+'_parent_B0_replacement' in measured else group+'_parent_B0'
 if base not in measured:return
 b=measured[base];comparisons={tag:compare(measured[group+'_'+tag],b) for tag in ['O','R','OR','Frozen_M2'] if group+'_'+tag in measured}
 negative=negcontrol(group+'_R',base) if group+'_R' in measured else None
 effects={tag:c['gain_N_s'] for tag,c in comparisons.items()};interaction=effects.get('OR',0)-effects.get('O',0)-effects.get('R',0) if all(tag in effects for tag in ['O','R','OR']) else None
 return_pair=compare(measured[group+'_RETURN_entry_R'],measured[group+'_RETURN_entry_zero']) if group+'_RETURN_entry_R' in measured else None
 entry_states={}
 for tag in ['parent_B0','O','R','OR']:
  ident=base if tag=='parent_B0' else group+'_'+tag
  if ident not in measured:continue
  with np.load(S/'motion_series'/(ident+'.npz')) as z:
   i=np.flatnonzero(z['phase']=='RETURN')[0];entry_states[tag]=dict(physics_s=float(z['time_s'][i]),q_rad=z['true_q_rad'][i],dq_rad_s=z['true_dq_rad_s'][i])
 save(S/'PHASE_ISOLATION_RESULTS.json',dict(clock='SCIENTIFIC_SIMULATION',comparisons=comparisons,RETURN_same_entry_pair=return_pair,pre_intervention_negative_control=negative,RETURN_entry_states=entry_states,RETURN_entry_state_warning='O/OR naturally alter state before RETURN; full 2x2 effects are total trajectory effects, same-RETURN-entry pair isolates R after B0 history',host_clock_qualified=False))
 save(S/'BIDIRECTIONAL_COMPARISON.json',dict(clock='SCIENTIFIC_SIMULATION',comparisons=comparisons,gain_N_s=effects,interaction_gain_N_s=interaction,interaction_formula='(J_B0-J_OR)-(J_B0-J_O)-(J_B0-J_R); positive synergistic gain, negative cancellation',OR_vs_single_gain_N_s={tag:measured[group+'_'+tag]['J_F_N_s']-measured[group+'_OR']['J_F_N_s'] for tag in ['O','R'] if group+'_OR' in measured and group+'_'+tag in measured},do_not_identify_independent_RETURN_causality_from_2x2=True))
 if not (S/'CANDIDATE_SELECTION.json').exists():
  eligible=[]
  for tag,c in comparisons.items():
   if tag=='Frozen_M2':continue
   line=load(S/'reports'/(group+'_'+tag+'_EXECUTED_RESIDUAL_RECEIPTS.json'));executed={r['phase'] for r in line['rows'] if r['physically_executed_nonzero']};phases=['OUTBOUND'] if tag=='O' else ['RETURN'] if tag=='R' else ['OUTBOUND','RETURN'];phase_gain=all(c['phase_J_F_delta_N_s'][ph]<0 for ph in phases);execution=all(ph in executed for ph in phases)
   c['eligibility']=dict(motion_force_acceptance=c['acceptance_pass'],total_gain_at_least_0_5percent=c['gain_percent']>=.5,each_target_phase_force_gain=phase_gain,actual_target_phase_execution=execution,negative_control=negative is not None and negative['all_pre_intervention_fields_exact_equal']);c['eligible']=all(c['eligibility'].values())
   if c['eligible']:eligible.append(tag)
  selected=min(eligible,key=lambda tag:(measured[group+'_'+tag]['J_F_N_s'],2 if tag=='OR' else 1,tag)) if eligible else None
  save(S/'CANDIDATE_SELECTION.json',dict(frozen_unix=time.time(),selected=selected,status='DISCOVERY_PASS_PENDING_VALIDATION' if selected else 'NEGATIVE_RESULT',eligible=eligible,comparisons=comparisons,no_heldout_used=True,protocol_sha256=hashlib.sha256((S/'EXPERIMENT_PROTOCOL.json').read_bytes()).hexdigest()))
 selection=load(S/'CANDIDATE_SELECTION.json');val=[]
 for cond in ['P1','P2']:
  if selection['selected'] and cond+'_parent_B0' in measured and cond+'_'+selection['selected'] in measured:val.append(compare(measured[cond+'_'+selection['selected']],measured[cond+'_parent_B0']))
 save(S/'VALIDATION_RESULTS.json',dict(selected=selection['selected'],clock='SCIENTIFIC_SIMULATION',host_clock_qualified=False,denominator=len(val),comparisons=val,PASS=sum(c['acceptance_pass'] and c['gain_percent']>=.5 for c in val),status='NOT_RUN_DISCOVERY_GATE_FAILED' if selection['selected'] is None else 'SCI_VALIDATED' if len(val)==2 and all(c['acceptance_pass'] and c['gain_percent']>=.5 for c in val) else 'DISCOVERY_ONLY' if len(val)<2 else 'DISCOVERY_NOT_VALIDATED',new_Human=False,no_reselection=True))
 print(json.dumps(dict(selected=selection['selected'],discovery={k:dict(gain=c['gain_percent'],accept=c['acceptance_pass'],fail=c['failed_requirements']) for k,c in comparisons.items()},validation=val)),flush=True)
if __name__=='__main__':main()
