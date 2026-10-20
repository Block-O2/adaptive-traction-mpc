import os,sys,json,time,hashlib,gzip
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
import numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_w1_d_qualification_v1')
def load(p):return json.loads(Path(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,(np.integer,np.bool_)):return x.item()
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n');tmp.replace(p)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def stats(v):
 return dict(max_abs=np.max(abs(v),axis=0),p95_abs=np.quantile(abs(v),.95,axis=0),rms=np.sqrt(np.mean(v*v,axis=0)))
def analyze(ident):
 from stream_runtime_evidence import array_items
 from scipy.signal import savgol_filter
 p=S/'source/results'/ident;axis=load(S/'reports'/(ident+'_AXES.json'));metric=axis['metric'];summary=load(p/'summary.json')
 with np.load(p/'trace.npz') as z:
  ix=np.flatnonzero(z['stage']=='TASK');ts=z['time_s'][ix];_,rev=np.unique(ts[::-1],return_index=True);ix=ix[np.sort(len(ts)-1-rev)];ts=z['time_s'][ix];truth=z['evaluation_only_human_state_rad_rad_s'][ix];ref=z['reference_q_rad'][ix]
  tracking=np.rad2deg(np.sqrt(np.mean((truth[:,:2]-ref)**2,axis=0)))
 rows=[]
 for r in array_items(p/'runtime_artifacts.json.gz','native_states_evaluation_only'):
  if ts[0]-1e-9<=r['time_s']<=ts[-1]+1e-9:rows.append((r['time_s'],r['qpos_evaluation_only'],r['qvel_evaluation_only']))
 t=np.array([r[0] for r in rows]);qpos=np.array([r[1] for r in rows]);qvel=np.array([r[2] for r in rows]);del rows
 assert len(t)>2 and np.all(np.diff(t)>0),'NATIVE_TRACE_INTEGRITY'
 mi=np.clip(np.searchsorted(t,ts),0,len(t)-1);left=np.maximum(mi-1,0);mi=np.where(abs(t[left]-ts)<abs(t[mi]-ts),left,mi);close=abs(t[mi]-ts)<1e-8
 eq=np.max(abs(qpos[mi[close],:,None]-truth[close,None,:2]),axis=0);ev=np.max(abs(qvel[mi[close],:,None]-truth[close,None,2:]),axis=0);qi=np.argmin(eq,axis=0);vi=np.argmin(ev,axis=0)
 assert np.max(eq[qi,np.arange(2)])<1e-8 and np.max(ev[vi,np.arange(2)])<1e-8,'HUMAN_MAPPING_FAILURE'
 q=qpos[:,qi];v=qvel[:,vi];phase=np.full(len(t),'OUTBOUND',dtype='<U10')
 for r in summary['task']['phase_transitions']:
  if r['to'] in ['OUTBOUND','HOLD','RETURN']:phase[t>=r['time_s']-1e-9]=r['to']
 shapes={};boundaries={}
 for ph in ['OUTBOUND','HOLD','RETURN']:
  j=np.flatnonzero(phase==ph);assert len(j)>2,'MISSING_COMPLETE_PHASE'
  u=(t[j]-t[j[0]])/(t[j[-1]]-t[j[0]]);shapes[ph]=np.rad2deg(np.column_stack([np.interp(np.linspace(0,1,201),u,q[j,d]) for d in range(2)]));boundaries[ph]=dict(start_deg=np.rad2deg(q[j[0]]),end_deg=np.rad2deg(q[j[-1]]))
 motion={}
 for w in [0,5,21]:
  vv=v if w==0 else savgol_filter(v,w,3,axis=0,mode='interp');acc=np.gradient(vv,t,axis=0,edge_order=2);jerk=np.gradient(acc,t,axis=0,edge_order=2)
  signals=dict(velocity_deg_s=np.rad2deg(vv),acceleration_deg_s2=np.rad2deg(acc),jerk_deg_s3=np.rad2deg(jerk));motion['raw' if w==0 else 'SG'+str(w)]=dict(full={k:stats(a) for k,a in signals.items()},phases={ph:{k:stats(a[phase==ph]) for k,a in signals.items()} for ph in ['OUTBOUND','HOLD','RETURN']})
  if w==0:np.savez_compressed(S/'motion_series'/(ident+'.npz'),time_s=t,true_q_rad=q,true_dq_rad_s=v,acceleration_rad_s2=acc,jerk_rad_s3=jerk,phase=phase)
 dose=dict(duration_s=t[-1]-t[0],excursion_deg=np.rad2deg(np.ptp(q,axis=0)),cumulative_travel_deg=np.rad2deg(np.sum(abs(np.diff(q,axis=0)),axis=0)),endpoint_deg=np.rad2deg(q[-1]),phase_boundaries=boundaries,phase_shapes=shapes)
 e=load(S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json'))
 for r in e['rows']:
  for m in r['native_coordination_metadata']:
   if m.get('status')=='ACCEPTED':assert abs(m['common_error'])<1e-12,'NATIVE_SEMANTIC_FAILURE'
 out=dict(id=ident,clock='REALTIME_CHARACTERIZATION',J_F_N_s=metric['J_F'],phase_cost=axis['phase_cost'],force_peak_N=metric['force_peak'],moment_integral_Nm_s=metric['moment_integral'],moment_peak_Nm=metric['moment_peak'],tracking_RMS_deg=tracking,clearance=metric.get('physical_clearance'),native_physical_audit=metric['physical_audit'],phase_durations=metric['phase_durations'],motion=motion,dose=dose,axes={k:v for k,v in axis.items() if k!='metric'},native_steps=axis['native_steps'],execution_lineage_path=str(S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')),commissioning=dict(model_beta=metric.get('model_beta'),model_residual=metric.get('model_residual'),initial_estimated_state=metric.get('initial_estimated_state'),initial_reference=metric.get('initial_reference')),quality=dict(native_samples=len(t),common_nodes=int(close.sum()),qpos_indices=qi,qvel_indices=vi,mapping_max_error=max(np.max(eq[qi,np.arange(2)]),np.max(ev[vi,np.arange(2)])),native_dt_min_s=np.min(np.diff(t)),native_dt_max_s=np.max(np.diff(t))),sources={str(f):sha(f) for f in [p/'trace.npz',p/'summary.json',p/'runtime_artifacts.json.gz',S/'queue'/(ident+'.json')]})
 save(S/'reports'/(ident+'_MEASURED.json'),out);return clean(out)
def compare(a,b):
 pr=load(S/'MOTION_ACCEPTANCE_PROTOCOL.json')['primary'];fails=[];ratios={};sens={}
 for sig,key in [('velocity_deg_s','velocity'),('acceleration_deg_s2','acceleration'),('jerk_deg_s3','jerk')]:
  for met in pr[key]:
   av=np.asarray(a['motion']['raw']['full'][sig][met]);bv=np.asarray(b['motion']['raw']['full'][sig][met]);r=av/np.maximum(bv,1e-12);ratios[sig+'/'+met]=r
   if np.any(av>bv*pr['burden_ratio']+1e-7):fails.append(sig+'/'+met)
 for r in [1.,1.05,1.10,1.25]:sens[str(r)]=all(np.max(v)<=r+1e-7 for v in ratios.values())
 da=a['dose'];db=b['dose'];exc=abs(np.asarray(da['excursion_deg'])-db['excursion_deg']);travel=np.asarray(da['cumulative_travel_deg'])/db['cumulative_travel_deg'];endpoint=abs(np.asarray(da['endpoint_deg'])-db['endpoint_deg']);duration=abs(da['duration_s']-db['duration_s']);boundary=0;shape=0
 for ph in ['OUTBOUND','HOLD','RETURN']:
  shape=max(shape,float(np.max(abs(np.asarray(da['phase_shapes'][ph])-db['phase_shapes'][ph]))))
  for k in ['start_deg','end_deg']:boundary=max(boundary,float(np.max(abs(np.asarray(da['phase_boundaries'][ph][k])-db['phase_boundaries'][ph][k]))))
  if abs(a['phase_durations'][ph]-b['phase_durations'][ph])>pr['each_phase_duration_abs_delta_s']+1e-8:fails.append(ph+'_duration')
 if np.any(exc>pr['excursion_abs_delta_deg']+1e-7):fails.append('excursion')
 if np.any(travel>pr['cumulative_ratio_upper']+1e-7) or np.any(travel<pr['cumulative_ratio_lower']-1e-7):fails.append('cumulative_dose')
 if np.any(endpoint>pr['endpoint_and_phase_boundary_abs_delta_deg']+1e-7) or boundary>pr['endpoint_and_phase_boundary_abs_delta_deg']+1e-7:fails.append('endpoint_phase_boundary')
 if duration>pr['total_duration_abs_delta_s']+1e-8:fails.append('task_duration')
 for k,lim in [('moment_integral_Nm_s','moment_integral_ratio'),('force_peak_N','force_peak_ratio'),('moment_peak_Nm','moment_peak_ratio')]:
  if a[k]>b[k]*pr[lim]+1e-7:fails.append(k)
 if np.any(np.asarray(a['tracking_RMS_deg'])>np.asarray(b['tracking_RMS_deg'])+pr['tracking_RMS_add_deg']+1e-7):fails.append('tracking')
 if a['axes']['PHYSICAL_TASK_VALID']!='PASS':fails.append('physical_task')
 if a['axes']['HOST_EXECUTION_CAUSAL_VALID']!='PASS':fails.append('causal_ownership')
 out=dict(candidate=a['id'],B=b['id'],acceptance_pass=not fails,failed_requirements=fails,gain_N_s=b['J_F_N_s']-a['J_F_N_s'],gain_percent=100*(b['J_F_N_s']-a['J_F_N_s'])/b['J_F_N_s'],burden_ratios=ratios,burden_sensitivity=sens,excursion_delta_deg=exc,cumulative_ratio=travel,endpoint_abs_delta_deg=endpoint,phase_boundary_max_delta_deg=boundary,phase_shape_max_delta_deg=shape,phase_shape_diagnostic={str(x):shape<=x+1e-7 for x in [.5,1.,2.]},duration_abs_delta_s=duration,phase_J_F_delta_N_s={ph:a['phase_cost']['phases'][ph]['J_F_N_s']-b['phase_cost']['phases'][ph]['J_F_N_s'] for ph in ['OUTBOUND','HOLD','RETURN']},moment_integral_ratio=a['moment_integral_Nm_s']/b['moment_integral_Nm_s'],force_peak_delta_N=a['force_peak_N']-b['force_peak_N'],moment_peak_delta_Nm=a['moment_peak_Nm']-b['moment_peak_Nm'])
 return clean(out)
