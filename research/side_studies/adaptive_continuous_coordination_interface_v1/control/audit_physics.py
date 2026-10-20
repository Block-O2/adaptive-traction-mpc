"""Post-hoc raw-data auditor. Does not import planner/controller or step physics."""
from pathlib import Path
import os,sys,json,hashlib,time,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
from stream_runtime_evidence import array_items

def load(n):return json.loads((P/n).read_text())
def encode(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(x):return hashlib.sha256(encode(x).encode()).hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,allow_nan=False))
def polynomial(c,T,t):
 u=np.clip(t/T,0,1);c=np.asarray(c,float)
 return [np.asarray([np.polynomial.polynomial.polyval(u,np.polynomial.polynomial.polyder(row,m=k)) for row in c])/T**k for k in range(3)]
def sample(r,t,actual=True):
 if actual and r['canonical_zero_identity_evaluation']:
  p=r['identity_payload']['original'];return polynomial(p['values'],p['duration_s'],t)
 i=min(len(r['segments'])-1,max(0,int(np.searchsorted(r['knots_s'],t,side='right')-1)));p=r['segments'][i]
 return polynomial(p['immutable_coefficients'],p['duration_s'],t-r['knots_s'][i])
def raw_audit(arm):
 root=P/'source/results'/arm;s=load('source/results/'+arm+'/summary.json');m=load('reports/'+arm+'_MEASURED.json');receipts=list(array_items(root/'runtime_artifacts.json.gz','command_receipts'));positive=[r for r in receipts if r.get('applied') and r.get('native_steps',0)>0];starts=np.array([r['start_physics_s'] for r in positive]);ends=np.array([r['end_physics_s'] for r in positive]);assert np.all(abs(starts[1:]-ends[:-1])<1e-8)
 counts=np.zeros(len(positive),int);errors=[];annotated=[r for r in positive if 'multisegment_reference' in r];objects=load('output/'+arm+'_REFERENCE_OBJECTS.json')['references'];issued=load('output/'+arm+'_ISSUED_REFERENCE.json')['rows'];ref_errors=np.zeros(3);piece_errors=np.zeros(3)
 for key,r in objects.items():
  assert sha(r['identity_payload'])==key==r['reference_id'];assert sha([key,encode(r['path_certificate'])])==r['certificate_id'];assert r['path_certificate']['feasible'];assert abs(sum(x['duration_s'] for x in r['segments'])-r['duration_s'])<1e-12
 for r in annotated:
  a=r['multisegment_reference'];obj=objects[a['reference_id']];expected=sample(obj,a['selected_local_progress_s']);piece=sample(obj,a['selected_local_progress_s'],actual=False)
  ref_errors=np.maximum(ref_errors,[np.max(abs(x-np.asarray(a[k]))) for x,k in zip(expected,['q_rad','dq_rad_s','ddq_rad_s2'])]);piece_errors=np.maximum(piece_errors,[np.max(abs(x-np.asarray(a[k]))) for x,k in zip(piece,['q_rad','dq_rad_s','ddq_rad_s2'])])
  assert np.array_equal(a['q_rad'],r['q_ref_rad']) and np.array_equal(a['dq_rad_s'],r['dq_ref_rad_s']);assert a['worker_certificate_id']==obj['certificate_id'];assert a['source_sample_time_s']==obj['binding']['source_sample_time_s'] and a['source_capture_ns']==obj['binding']['sensor_capture_ns'];assert a['current_certificate_id'] and a['current_model_sequence']>=obj['binding']['request_model_sequence']
 assert max(ref_errors)<1e-10 and max(piece_errors)<1e-9
 selected=[];native_count=0
 for row in array_items(root/'runtime_artifacts.json.gz','native_states_evaluation_only'):
  native_count+=1;begin=row['time_s']-.00025;i=int(np.searchsorted(starts,begin+1e-9,side='right')-1)
  assert i>=0 and starts[i]-1e-8<=begin<ends[i]+1e-8
  assert np.array_equal(row['command_torque_nm'],positive[i]['command_torque_nm']);counts[i]+=1
  if 'multisegment_reference' in positive[i]:selected.append(row)
 assert np.array_equal(counts,np.asarray([r['native_steps'] for r in positive]));assert native_count==m['native_steps']
 z=np.load(root/'trace.npz');mask=z['stage']=='TASK';t=z['time_s'][mask];force=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);moment=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1);dt=np.maximum(0,np.diff(t));jf=float(force[:-1]@dt);jm=float(moment[:-1]@dt);assert abs(jf-m['J_F_N_s'])<1e-8 and abs(jm-m['moment_integral_Nm_s'])<1e-8
 transitions={r['to']:r['time_s'] for r in s['task']['phase_transitions']};bounds=[t[0],transitions['HOLD'],transitions['RETURN'],transitions['COMPLETE']];phases={}
 for ph,a,b in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:]):
  d=np.maximum(0,np.minimum(t[1:],b)-np.maximum(t[:-1],a));phases[ph]=dict(duration_s=float(d.sum()),J_F_N_s=float(force[:-1]@d),moment_integral_Nm_s=float(moment[:-1]@d))
 assert abs(sum(r['J_F_N_s'] for r in phases.values())-jf)<1e-8
 # Recompute motion stats from separately archived native-derived series.
 series=np.load(P/'motion_series'/(arm+'.npz'));tt=series['time_s'];v=series['true_dq_rad_s'];acc=np.gradient(v,tt,axis=0,edge_order=2);jerk=np.gradient(acc,tt,axis=0,edge_order=2);stat_errors=[]
 for k,x in [('velocity_deg_s',v),('acceleration_deg_s2',acc),('jerk_deg_s3',jerk)]:
  x=np.rad2deg(x)
  for stat,value in [('max_abs',np.max(abs(x),axis=0)),('p95_abs',np.quantile(abs(x),.95,axis=0)),('rms',np.sqrt(np.mean(x*x,axis=0)))]:stat_errors.append(float(np.max(abs(value-np.asarray(m['motion']['raw']['full'][k][stat])))))
 assert max(stat_errors)<1e-8
 full_identity=load('output/'+arm+'_DATA.json')['branch_start']['full_hash'] if '_parent' not in arm else None
 activated=[r['decision_index'] for r in s['learning_records'] if r['selected_plan_activated'] and r['selected_plan']['schedule'].get('reference_id') in objects]
 row=dict(id=arm,status='PASS',clock='SCIENTIFIC_SIMULATION',full_fork_identity=full_identity,native_rows=native_count,receipts=len(receipts),positive_receipts=len(positive),native_ownership_errors=0,annotated_applied_receipts=len(annotated),annotated_native_steps=sum(r['native_steps'] for r in annotated),issued_rows=len(issued),activated_multisegment_decisions=activated,reference_ids=list(objects),current_certificate_ids=sorted({r['multisegment_reference']['current_certificate_id'] for r in annotated}),reference_reconstruction_max_errors=ref_errors.tolist(),piece_reconstruction_max_errors=piece_errors.tolist(),q_dq_receipt_exact=True,reference_and_worker_certificate_hash_reconstructed=True,current_certificate_scope='receipt records hash of runtime current full path check; complete current certificate is not archived in this log, so independent current-certificate content reconstruction NOT_AVAILABLE',request_count=len(s['decisions']),learning_record_count=len(s['learning_records']),raw_integral_J_F_N_s=jf,raw_moment_integral_Nm_s=jm,phase_integrals=phases,force_closure_error_N_s=jf-m['J_F_N_s'],motion_stat_recompute_max_error=max(stat_errors),original_physical_axes=m['axes'],all_multisegment_receipt_source_ids_preserved=True)
 if annotated:
  dest=P/'key_traces'/arm;dest.mkdir(parents=True,exist_ok=True);put(str(dest.relative_to(P)/'APPLIED_MULTISEGMENT_RECEIPTS.json'),dict(rows=annotated));np.savez_compressed(dest/'native_during_multisegment.npz',time_s=np.array([r['time_s'] for r in selected]),qpos=np.array([r['qpos_evaluation_only'] for r in selected]),qvel=np.array([r['qvel_evaluation_only'] for r in selected]),torque=np.array([r['command_torque_nm'] for r in selected]));put(str(dest.relative_to(P)/'RAW_SOURCES.json'),dict(full_raw=str(root),sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in root.iterdir() if f.is_file()}))
 put('reports/'+arm+'_INDEPENDENT_AUDIT.json',row);print('INDEPENDENT_AUDIT_PASS',arm,len(annotated),row['annotated_native_steps'],flush=True);return row

def response(arm,zero):
 a=np.load(P/'source/results'/arm/'trace.npz');b=np.load(P/'source/results'/zero/'trace.npz');assert np.array_equal(a['time_s'],b['time_s']);rs=load('key_traces/'+arm+'/APPLIED_MULTISEGMENT_RECEIPTS.json')['rows'];objects=load('output/'+arm+'_REFERENCE_OBJECTS.json')['references'];r=next(iter(objects.values()));first=rs[0]['start_physics_s'];fields=['reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','evaluation_only_human_state_rad_rad_s','cr12_actuator_command_nm','physical_cuff_force_world_n','physical_cuff_moment_world_nm'];deltas={};pre=True
 for k in fields:
  x,y=a[k],b[k];mask=a['time_s']<first-1e-9;pre=pre and np.array_equal(x[mask],y[mask],equal_nan=True);deltas[k]=np.max(abs(x-y),axis=0).tolist()
 assert pre and max(deltas['reference_q_rad'])>1e-5 and max(deltas['evaluation_only_human_state_rad_rad_s'])>1e-6 and max(deltas['cr12_actuator_command_nm'])>1e-5
 ts=np.linspace(0,r['duration_s'],2001);curve_delta=np.array([sample(r,float(t))[0]-polynomial(r['identity_payload']['original']['values'],r['duration_s'],float(t))[0] for t in ts]);outside=(ts<r['knots_s'][1]-1e-12)|(ts>r['knots_s'][3]+1e-12)
 assert np.max(abs(curve_delta[outside]))<1e-10
 result=dict(status='PASS',candidate=arm,matched_zero=zero,first_issued_multisegment_physics_s=first,reference_time_support_s=[r['knots_s'][1],r['knots_s'][3]],max_mathematical_delta_rad=np.max(abs(curve_delta),axis=0).tolist(),outside_support_max_rad=float(np.max(abs(curve_delta[outside]))),max_actual_trace_deltas=deltas,all_pre_multisegment_trace_fields_exact=pre,activation_to_native_chain='MATHEMATICAL_TRAJECTORY -> full path CERTIFIED_REFERENCE -> ACTIVATED_REFERENCE -> reconstructed ISSUED_REFERENCE -> positive-step APPLIED_COMMAND -> independently logged ACTUAL_HUMAN_MOTION',attribution='same complete parent and identical pre-activation control/physical history, one bounded internal knee position intervention; later closed-loop state/reference changes are physical propagation, not claimed to remain local',new_planner_calls=False)
 put('reports/'+arm+'_RESPONSE.json',result);return result

def main():
 ids=['interface2_B0','interface2_zero_multi','interface2_knee_002','interface2_knee_002_repeat'];rows=[raw_audit(a) for a in ids];assert len({r['full_fork_identity'] for r in rows})==1;assert len({r['request_count'] for r in rows})==1
 responses=[response(a,'interface2_zero_multi') for a in ids[2:]];gate=load('P0_ZERO_PHYSICAL_GATE.json');repeat=load('NONZERO_REPEAT_GATE.json');assert gate['status']==repeat['status']=='PASS'
 put('PHYSICAL_VALIDATION.json',dict(status='PASS',unix=time.time(),level='PHYSICAL_LEVEL1 isolated MuJoCo scientific-mode execution',P0=gate,repeat=repeat,arms=rows,responses=responses,all_same_complete_parent=True,all_request_counts_equal=True,independent_raw_integration_and_native_torque_ownership=True,not_certified=['official B Native LEVEL2','host-clock LEVEL3/deadlines','hardware/clinical','continuous true wrench/tracking invariant','unseen patients/conditions'],scope='one original task/model/seed/parent; repeat is deterministic matched-state qualification, not external generalization'))
 print('PHYSICAL_VALIDATION_PASS',flush=True)
if __name__=='__main__':main()
