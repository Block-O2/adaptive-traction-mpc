"""Evaluation only: original raw motion, 5 ms measured wrench, execution evidence."""
from pathlib import Path
import os,sys,json,gzip,collections,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
import numpy as np
P=Path(os.environ.get('ACL2_PACKAGE',str(Path(__file__).resolve().parents[1])))
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if hasattr(x,'tolist'):return clean(x.tolist())
 if hasattr(x,'item'):return x.item()
 return x
def put(n,d):
 p=P/n;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(clean(d),indent=2,ensure_ascii=False,allow_nan=False)+'\n');tmp.replace(p)
def stats(x):
 x=np.asarray(x)
 if not np.all(np.isfinite(x)):
  valid=np.all(np.isfinite(x),axis=tuple(range(1,x.ndim))) if x.ndim>1 else np.isfinite(x)
  return dict(valid_sample_statistics=stats(x[valid]) if np.any(valid) else None,missing_nonfinite_rows=int(np.sum(~valid)),total_rows=len(x),scope='Missing original torque-component records explicitly excluded; original physical signals/scorer unchanged.')
 return dict(rms=np.sqrt(np.mean(x*x,axis=0)),peak_abs=np.max(abs(x),axis=0),p50_abs=np.quantile(abs(x),.5,axis=0),p95_abs=np.quantile(abs(x),.95,axis=0),p99_abs=np.quantile(abs(x),.99,axis=0),p999_abs=np.quantile(abs(x),.999,axis=0))
def fluctuation(t,x):
 # Independent auxiliary metric; raw traces and original scoring never filtered.
 bins=np.floor((t-t[0])/.1+1e-7).astype(int);res=[]
 for b in np.unique(bins):
  k=np.flatnonzero(bins==b)
  if len(k)<3:continue
  u=t[k]-t[k].mean();D=np.column_stack([np.ones(len(k)),u]);res.append(x[k]-D@np.linalg.lstsq(D,x[k],rcond=None)[0])
 return stats(np.concatenate(res)) if res else None
def wrench(t,x):
 norm=np.linalg.norm(x,axis=1);rate=np.gradient(x,t,axis=0,edge_order=2);nr=np.gradient(norm,t,edge_order=2)
 return dict(vector=stats(x),norm=stats(norm),vector_rate=stats(rate),norm_rate=stats(nr),TV_vector=float(np.linalg.norm(np.diff(x,axis=0),axis=1).sum()),TV_norm=float(abs(np.diff(norm)).sum()),local_linear_residual_100ms=fluctuation(t,x),samples=len(t),median_dt_s=float(np.median(np.diff(t))))
def gate_margins(comp,m,b):
 rows={}
 for key,value in comp['burden_ratios'].items():rows[key]=1.1-np.asarray(value)
 rows['excursion_deg']=.5-np.asarray(comp['excursion_delta_deg']);rows['endpoint_deg']=.5-np.asarray(comp['endpoint_abs_delta_deg'])
 rows['phase_boundary_deg']=.5-comp['phase_boundary_max_delta_deg'];rows['duration_s']=.1-comp['duration_abs_delta_s']
 travel=np.asarray(comp['cumulative_ratio']);rows['travel_ratio_upper']=1.05-travel;rows['travel_ratio_lower']=travel-.95
 rows['moment_integral_ratio']=1.25-comp['moment_integral_ratio'];rows['force_peak_N']=1.05*b['force_peak_N']-m['force_peak_N'];rows['moment_peak_Nm']=1.05*b['moment_peak_Nm']-m['moment_peak_Nm']
 rows['tracking_RMS_deg']=.5-(np.asarray(m['tracking_RMS_deg'])-b['tracking_RMS_deg'])
 for ph in ['OUTBOUND','HOLD','RETURN']:rows['phase_duration_'+ph+'_s']=.1-abs(m['phase_durations'][ph]-b['phase_durations'][ph])
 return dict(margins=rows,passed=comp['acceptance_pass'],failed_requirements=comp['failed_requirements'],scope='Original gate units kept per requirement; no aggregate minimum across unlike units.')
def evaluate(ident):
 dest=P/'analysis/extended'/(ident+'.json')
 if dest.exists():return json.loads(dest.read_text())
 f=P/'attempts'/(ident+'_RESULT.json');row=json.loads(f.read_text())
 if not row['complete']:return None
 m=json.loads((P/row['metrics_path']).read_text());b=json.loads((P/'runtime/reports'/(ident.split('_')[0]+'_B_MEASURED.json')).read_text());rp=P/'runtime/source/results'/ident
 su=json.loads((rp/'summary.json').read_text())
 with np.load(rp/'trace.npz') as z:
  ii=np.flatnonzero(z['stage']=='TASK');tt=z['time_s'][ii];_,idx=np.unique(tt,return_index=True);ii=ii[idx];t=z['time_s'][ii];trace={k:z[k][ii] for k in z.files if z[k].shape[0]==len(z['time_s'])}
 with np.load(P/'runtime/motion_series'/(ident+'.npz')) as z:ns={k:z[k].copy() for k in z.files}
 with gzip.open(rp/'runtime_artifacts.json.gz','rt') as z:raw=json.load(z)
 q,v,a,j=[ns[k] for k in ['true_q_rad','true_dq_rad_s','acceleration_rad_s2','jerk_rad_s3']];nt=ns['time_s'];phase=ns['phase']
 original_motion={k:stats(np.degrees(x)) for k,x in [('velocity_deg_s',v),('acceleration_deg_s2',a),('jerk_deg_s3',j)]}
 native_phases={ph:{k:stats(np.degrees(x[phase==ph])) for k,x in [('velocity_deg_s',v),('acceleration_deg_s2',a),('jerk_deg_s3',j)]} for ph in ['OUTBOUND','HOLD','RETURN']}
 ref_v=trace['reference_dq_rad_s'];ref_a=trace['reference_ddq_rad_s2'];ref_j=np.gradient(ref_a,t,axis=0,edge_order=2)
 reference=dict(velocity_deg_s=stats(np.degrees(ref_v)),acceleration_deg_s2=stats(np.degrees(ref_a)),jerk_deg_s3_at_5ms=stats(np.degrees(ref_j)),velocity_TV_vector_rad_s=float(np.linalg.norm(np.diff(ref_v,axis=0),axis=1).sum()),acceleration_TV_vector_rad_s2=float(np.linalg.norm(np.diff(ref_a,axis=0),axis=1).sum()))
 fw=trace['physical_cuff_force_world_n'];mw=trace['physical_cuff_moment_world_nm'];w=dict(force=wrench(t,fw),moment=wrench(t,mw),sampling='5 ms original measured physical cuff stream; no submillisecond force-resolution claim',native_wrench_available=bool(raw['wall_physics']['native_states_evaluation_only'] and 'cuff_wrench_world_evaluation_only' in raw['wall_physics']['native_states_evaluation_only'][0]))
 boundaries={r['to']:r['time_s'] for r in su['task']['phase_transitions']};wphase={}
 for ph,lo,hi in [('OUTBOUND',t[0],boundaries['HOLD']),('HOLD',boundaries['HOLD'],boundaries['RETURN']),('RETURN',boundaries['RETURN'],boundaries['COMPLETE'])]:
  kk=(t>=lo-1e-9)&(t<=hi+1e-9);wphase[ph]=dict(force=wrench(t[kk],fw[kk]),moment=wrench(t[kk],mw[kk]))
 events=[e for e in raw['execution_attempts'] if t[0]-1e-9<=e['source_sample_time_s']<=t[-1]+1e-9];ge=[e for e in events if e.get('clearance_feedback')];cross=[e for e in ge if e['clearance_feedback']['v4_branch_diagnostic']['directional_stencil_crosses']]
 corr=np.asarray([e['clearance_feedback']['correction_nm'] for e in ge]);az=np.array([e['clearance_feedback']['v4_branch_diagnostic']['model_axis_z'] for e in ge]);changes=int(np.sum(np.signbit(az[1:])!=np.signbit(az[:-1])))
 torque=trace['cr12_actuator_command_nm'];pre=torque-trace['robot_torque_component_clipping_nm'];clipped=np.any(abs(trace['robot_torque_component_clipping_nm'])>1e-9,axis=1)
 overshoot={}
 for ph in ['OUTBOUND','RETURN']:
  use=phase==ph;goal=np.asarray(su['task'].get('outbound_goal_target_rad' if ph=='OUTBOUND' else 'start_return_target_rad',[]))
  # Requested endpoint comes from final signed reference of this phase.
  lr=[r for r in su['learning_records'] if r.get('selected_plan',{}).get('schedule',{}).get('phase')==ph]
  target=np.asarray(lr[-1]['selected_plan']['schedule']['target_q_rad']) if lr else trace['reference_q_rad'][-1]
  direction=1 if ph=='OUTBOUND' else -1;overshoot[ph]=np.degrees(np.maximum(0,np.max(direction*(q[use]-target),axis=0)))
 windows=[]
 for lo,hi in [(4.,6.),(15.,16.)]:
  kn=(nt>=t[0]+lo)&(nt<=t[0]+hi);kw=(t>=t[0]+lo)&(t<=t[0]+hi)
  windows.append(dict(task_window_s=[lo,hi],motion={k:stats(np.degrees(x[kn])) for k,x in [('velocity',v),('acceleration',a),('jerk',j)]},force=wrench(t[kw],fw[kw]),moment=wrench(t[kw],mw[kw])))
 out=dict(id=ident,complete=True,qualified=row['qualified'],action=row['action'],JF=row['JF'],JM=row['JM'],phase_cost=row['phase_cost'],phase_durations=m['phase_durations'],duration_s=float(t[-1]-t[0]),native_dt_s=float(np.median(np.diff(nt))),native_motion=original_motion,native_phases=native_phases,reference=reference,wrench=w,wrench_phases=wphase,tracking_RMS_deg=m['tracking_RMS_deg'],excursion_deg=m['dose']['excursion_deg'],terminal_overshoot_deg=overshoot,motion_gate=gate_margins(row['motion_vs_B'],m,b),axes=m['axes'],clearance=m['clearance'],guard=dict(events=len(ge),active=sum(e['clearance_feedback']['active'] for e in ge),stencil_cross_count=len(cross),endpoint_branch_switch_count=changes,min_abs_model_axis_z=float(np.min(abs(az))),min_model_curvature_m_s2=min(e['clearance_feedback']['model_curvature_m_s2'] for e in ge),unsatisfied=sum(not e['clearance_feedback']['constraint_satisfied'] for e in ge),correction_nm=stats(corr),crossing_records=[dict(time_s=e['source_sample_time_s'],guard=e['clearance_feedback'],applied_robot_tau_nm=e.get('applied_robot_tau_nm')) for e in cross]),torque=dict(requested_preclip_trace_nm=stats(pre),applied_trace_nm=stats(torque),applied_rate_nm_s=stats(np.gradient(torque,t,axis=0,edge_order=2)),clipping_samples=int(clipped.sum()),requested_definition='sum of original base/position/velocity/allocator components = applied minus clipping; raw trace retained; accepted write tracked in command_receipts',execution_modes=dict(collections.Counter(e.get('mode','MISSING') for e in events))),fallbacks=raw.get('safe_fallback_events',[]),rolling_splice_count=len(raw.get('rolling_splice_events',[])),activation_validations_count=len(raw.get('activation_validations',[])),local_windows=windows,source_raw_sha256=hashlib.sha256((rp/'runtime_artifacts.json.gz').read_bytes()).hexdigest(),evaluation_truth_only=True)
 put('analysis/extended/'+ident+'.json',out)
 print('EXTENDED',ident,'qual',row['qualified'],'JF',row['JF'],'JM',row['JM'],'jerkRMS',original_motion['jerk_deg_s3']['rms'],'forceRateRMS',w['force']['norm_rate']['rms'],'cross',len(cross),flush=True)
 return clean(out)
if __name__=='__main__':
 for ident in sys.argv[1:] or [f.name[:-12] for f in sorted((P/'attempts').glob('*_RESULT.json'))]:evaluate(ident)
