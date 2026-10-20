"""Independent raw audit without importing planner, runner or optimizer."""
from pathlib import Path
import os,json,time,hashlib,itertools,collections,subprocess
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
from evidence import array_items
P=Path(__file__).resolve().parents[1]
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,np.generic):return x.item()
 return x
def load(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,allow_nan=False)+'\n')
checks=[]
for ident in ['baseline_parent','baseline_B0_original','baseline_frozen18D_identity','baseline_zero_exact_refinement']:
 f=P/'source/results'/ident;s=json.loads((f/'summary.json').read_text());m=load('reports/'+ident+'_MEASURED.json');output=load('output/'+ident+'_DATA.json')['metric']
 with np.load(f/'trace.npz') as z:
  ix=z['stage']=='TASK';t=z['time_s'][ix];force=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1);moment=np.linalg.norm(z['physical_cuff_moment_world_nm'][ix],axis=1);JF=float(force[:-1]@np.diff(t));MI=float(moment[:-1]@np.diff(t));truth=z['evaluation_only_human_state_rad_rad_s'][ix];ref=z['reference_q_rad'][ix]
  _,rev=np.unique(t[::-1],return_index=True);unique=np.sort(len(t)-1-rev);tracking=np.rad2deg(np.sqrt(np.mean((truth[unique,:2]-ref[unique])**2,axis=0)))
 assert abs(JF-m['J_F_N_s'])<1e-8 and abs(MI-m['moment_integral_Nm_s'])<1e-8
 assert np.max(abs(tracking-np.asarray(m['tracking_RMS_deg'])))<1e-8
 bounds=[t[0]]+[r['time_s'] for r in s['task']['phase_transitions'] if r['to'] in ['HOLD','RETURN','COMPLETE']];phase={}
 for ph,lo,hi in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:]):
  dt=np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo));phase[ph]=dict(J_F_N_s=float(force[:-1]@dt),duration_s=float(dt.sum()));assert abs(phase[ph]['J_F_N_s']-m['phase_cost']['phases'][ph]['J_F_N_s'])<1e-8
 assert abs(sum(r['J_F_N_s'] for r in phase.values())-JF)<1e-8
 with np.load(P/'motion_series'/(ident+'.npz')) as z:
  nt=z['time_s'];v=z['true_dq_rad_s'];a=np.gradient(v,nt,axis=0,edge_order=2);jerk=np.gradient(a,nt,axis=0,edge_order=2);assert np.array_equal(a,z['acceleration_rad_s2']) and np.array_equal(jerk,z['jerk_rad_s3'])
  for key,x in [('velocity_deg_s',v),('acceleration_deg_s2',a),('jerk_deg_s3',jerk)]:
   xx=np.rad2deg(x);stats=dict(max_abs=np.max(abs(xx),axis=0),p95_abs=np.quantile(abs(xx),.95,axis=0),rms=np.sqrt(np.mean(xx*xx,axis=0)))
   for name,value in stats.items():assert np.max(abs(value-np.asarray(m['motion']['raw']['full'][key][name])))<1e-8
 line=load('reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json');assert line['status']=='PASS' and line['ownership_error_count']==0
 checks.append(dict(id=ident,status='PASS',J_F_N_s=JF,moment_integral_Nm_s=MI,duration_s=float(t[-1]-t[0]),phase=phase,tracking_RMS_deg=tracking,actual_new_native_steps=output['actual_new_native_physics_steps'],actual_new_seconds=output['actual_new_simulation_seconds'],motion_recomputed=True,receipt_native_ownership=line['status'],native_rows=line['native_steps'],receipt_count=line['receipt_count']))
 print('RECOMPUTED',ident,JF,flush=True)
# Historical/new full physical body, contact and actual command equivalence;
# all host profiling timestamps are intentionally excluded from SCI identity.
pairs=[]
for ident,old in [('baseline_B0_original','development_repair2_B0_original'),('baseline_frozen18D_identity','development_repair2_quality_NATIVE_SCALAR_18_063')]:
 a=P/'source/results'/ident/'runtime_artifacts.json.gz';b=P/'key_traces'/old/'runtime_artifacts.json.gz';native=receipt=0
 for x,y in itertools.zip_longest(array_items(a,'native_states_evaluation_only'),array_items(b,'native_states_evaluation_only')):
  assert x is not None and y is not None
  for key in ['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only']:assert x[key]==y[key],(ident,key,native)
  native+=1
 keys=['applied','start_physics_s','end_physics_s','native_steps','source_sample_time_s','command_torque_nm','q_ref_rad','dq_ref_rad_s','reference_version','validation_model_version','plan_request_id','command_kind']
 for x,y in itertools.zip_longest(array_items(a,'command_receipts'),array_items(b,'command_receipts')):
  assert x is not None and y is not None
  for key in keys:assert x.get(key)==y.get(key),(ident,key,receipt)
  receipt+=1
 pairs.append(dict(new=ident,historical=old,status='PASS',native_rows=native,receipts=receipt,host_clock_excluded=True));print('RAW_HISTORICAL_PAIR_PASS',ident,flush=True)
events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];assert len(starts)==len(ends)==4 and all(r['returncode']==0 and r['joined'] for r in ends)
assert collections.Counter(r['id'] for r in starts)==collections.Counter(r['id'] for r in ends)
assert all(r.get('parent_hash_equal',True) for r in ends)
owner=load('control/BASELINE_OWNER.json');assert owner['returncode']==0 and owner['joined']
assert load('BASELINE_PARENT_GATE.json')['status']=='PASS' and load('BASELINE_ZERO_COLLAPSE_GATE.json')['status']=='PASS'
put('audit/INDEPENDENT_RAW_VERIFICATION.json',dict(status='PASS',unix=time.time(),method='standalone script, no planner/plant/optimizer imported; not an independent person/agent audit',checks=checks,historical_new_exact_pairs=pairs,actual_new_native_steps=sum(r['actual_new_native_steps'] for r in checks),actual_new_simulation_seconds=sum(r['actual_new_seconds'] for r in checks),physical_starts=len(starts),physical_ends=len(ends),full_parent_fork_exact=True,unresolved=['new nonzero representation physical qualification','host qualification','cross-state motion robustness']))
print('INDEPENDENT_RAW_VERIFICATION_PASS',flush=True)
