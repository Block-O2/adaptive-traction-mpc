"""Separate post-run raw quadrature/native-receipt check; no controller imports."""
from pathlib import Path
import json,gzip,hashlib,time,datetime,sys
import numpy as np
P=Path(__file__).resolve().parents[1];R=P/'runtime'
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for x in iter(lambda:s.read(4*2**20),b''):h.update(x)
 return h.hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def stats(x):return {'max_abs':np.max(abs(x),axis=0),'p95_abs':np.quantile(abs(x),.95,axis=0),'rms':np.sqrt(np.mean(x*x,axis=0))}
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return x.item()
 return x

def audit(ident):
 path=R/'source/results'/ident;mp=R/'reports'/(ident+'_MEASURED.json');dp=R/'output'/(ident+'_DATA.json');raw=path/'runtime_artifacts.json.gz'
 if not (mp.exists() and dp.exists() and raw.exists()):
  part=R/'output'/(ident+'_PARTIAL_COMPUTE.json')
  return {'id':ident,'status':'PARTIAL_OR_UNMEASURED_PRESERVED','formal_force_rank_allowed':False,'partial_compute':json.loads(part.read_text()) if part.exists() else None,'raw_exists':raw.exists()}
 m=json.loads(mp.read_text());data=json.loads(dp.read_text());su=json.loads((path/'summary.json').read_text());errors=[]
 with np.load(path/'trace.npz') as z:
  ix=np.flatnonzero(z['stage']=='TASK');t=z['time_s'][ix];f=z['physical_cuff_force_world_n'][ix];moment=z['physical_cuff_moment_world_nm'][ix];qref=z['reference_q_rad'][ix];true=z['evaluation_only_human_state_rad_rad_s'][ix];last_steps=int(z['physics_steps'][-1])
 dt=np.diff(t);assert np.all(dt>0),'TASK_CLOCK'
 jf=float(np.linalg.norm(f[:-1],axis=1)@dt);jm=float(np.linalg.norm(moment[:-1],axis=1)@dt)
 jferr=jf-m['J_F_N_s'];jmerr=jm-m['moment_integral_Nm_s']
 if abs(jferr)>1e-7 or abs(jmerr)>1e-7:errors.append('TRACE_WRENCH_INTEGRAL')
 transitions={tr['to']:tr['time_s'] for tr in su['task']['phase_transitions']};bounds=[t[0],transitions['HOLD'],transitions['RETURN'],transitions['COMPLETE']];phases={}
 for ph,lo,hi in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:]):
  clipped=np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo));val=float(np.linalg.norm(f[:-1],axis=1)@clipped);phases[ph]=val
  if abs(val-m['phase_cost']['phases'][ph]['J_F_N_s'])>1e-7:errors.append('PHASE_INTEGRAL:'+ph)
 # Independent complete JSON decode; original scorer uses a streaming parser.
 with gzip.open(raw,'rt') as s:artifact=json.load(s)
 native=artifact['wall_physics']['native_states_evaluation_only'];receipts=[r for r in artifact['wall_physics']['command_receipts'] if r.get('applied') and r.get('native_steps',0)>0];receipts.sort(key=lambda r:r['start_physics_s'])
 starts=np.array([r['start_physics_s'] for r in receipts]);ends=np.array([r['end_physics_s'] for r in receipts]);nt=np.array([r['time_s'] for r in native]);ni=np.searchsorted(starts,nt-.00025+1e-9,side='right')-1
 if np.any(ni<0):errors.append('NATIVE_UNOWNED_PREFIX')
 ni=np.clip(ni,0,len(receipts)-1);within=np.all((nt-.00025>=starts[ni]-1e-8)&(nt-.00025<ends[ni]+1e-8));counts=np.bincount(ni,minlength=len(receipts));expected=np.array([r['native_steps'] for r in receipts]);torque=np.array([r['command_torque_nm'] for r in native]);requested=np.array([r['command_torque_nm'] for r in receipts]);torque_err=float(np.max(abs(torque-requested[ni])))
 if not within:errors.append('NATIVE_RECEIPT_TIME')
 if not np.array_equal(counts,expected):errors.append('RECEIPT_NATIVE_COUNT')
 if torque_err!=0:errors.append('APPLIED_TORQUE_IDENTITY')
 if len(native)!=last_steps:errors.append('NATIVE_TRACE_COUNT')
 actual_new=last_steps-(0 if data['child'] is None else data['child']['physics_step_at_fork'])
 if actual_new!=data['metric']['actual_new_native_physics_steps']:errors.append('NEW_NATIVE_ACCOUNTING')
 # Original native q/dq evaluator indices are checked against every common trace node.
 qi=np.asarray(m['quality']['qpos_indices']);vi=np.asarray(m['quality']['qvel_indices']);qall=np.asarray([r['qpos_evaluation_only'] for r in native]);vall=np.asarray([r['qvel_evaluation_only'] for r in native]);use=(nt>=t[0]-1e-9)&(nt<=t[-1]+1e-9);tu=nt[use];q=qall[use][:,qi];v=vall[use][:,vi];idx=np.searchsorted(tu,t);idx=np.clip(idx,0,len(tu)-1);left=np.maximum(idx-1,0);idx=np.where(abs(tu[left]-t)<abs(tu[idx]-t),left,idx)
 mapping=float(max(np.max(abs(q[idx]-true[:,:2])),np.max(abs(v[idx]-true[:,2:]))))
 if mapping>1e-8:errors.append('NATIVE_HUMAN_MAPPING')
 acc=np.gradient(v,tu,axis=0,edge_order=2);jerk=np.gradient(acc,tu,axis=0,edge_order=2);signals={'velocity_deg_s':np.degrees(v),'acceleration_deg_s2':np.degrees(acc),'jerk_deg_s3':np.degrees(jerk)};motion={};maxerr=0
 for k,val in signals.items():
  motion[k]=stats(val)
  for stat,a in motion[k].items():maxerr=max(maxerr,float(np.max(abs(a-np.asarray(m['motion']['raw']['full'][k][stat])))))
 if maxerr>1e-6:errors.append('RAW_MOTION_RECOMPUTE')
 ret=tu>=transitions['RETURN']-1e-9;out=tu<transitions['HOLD']-1e-9;start=np.array([5.,10.]);goal=np.array([120.,120.]);qdeg=np.degrees(q)
 overshoot={'RETURN_below_registered_start_deg':np.maximum(0,start-np.min(qdeg[ret],axis=0)).tolist(),'OUTBOUND_above_registered_goal_deg':np.maximum(0,np.max(qdeg[out],axis=0)-goal).tolist(),'terminal_abs_goal_error_deg':abs(qdeg[-1]-start).tolist(),'definition':'true native extremes against frozen task goals5/10 and120/120; not a clinical threshold'}
 contact_pairs=sum(bool(r.get('contact_pairs_evaluation_only')) for r in native)
 result={'id':ident,'status':'PASS' if not errors else 'FAIL','errors':errors,'actual_new_native_steps':int(actual_new),'full_archived_native_steps':len(native),'positive_step_receipts':len(receipts),'torque_max_abs_error_Nm':torque_err,'receipt_step_counts_exact':bool(np.array_equal(counts,expected)),'native_time_intervals_owned':bool(within),'JF_N_s':jf,'JM_Nm_s':jm,'JF_error_vs_original':jferr,'JM_error_vs_original':jmerr,'phase_JF_N_s':phases,'tracking_RMS_deg':np.degrees(np.sqrt(np.mean((true[:,:2]-qref)**2,axis=0))).tolist(),'native_motion':clean(motion),'native_motion_max_error_vs_original':maxerr,'native_mapping_max_error':mapping,'overshoot':overshoot,'any_contact_pair_native_rows':contact_pairs,'shank_bed_contact_task_rows':su['task'].get('shank_bed_contact_sample_count_evaluation_only'),'minimum_true_clearance_m':su['task'].get('minimum_true_physical_clearance_m_evaluation_only'),'peak_robot_torque_fraction':su['task'].get('peak_robot_torque_fraction'),'input_sha256':{str(f.relative_to(P)):sha(f) for f in [path/'trace.npz',path/'summary.json',raw,dp,mp]}}
 del artifact,native,receipts,qall,vall
 return result

def main():
 starts=[r for r in map(json.loads,(R/'ATTEMPTS.jsonl').read_text().splitlines()) if r['event']=='START'];rows=[];begin=time.time()
 for r in starts:
  row=audit(r['id']);rows.append(row);put('audit/INDEPENDENT_RAW_AUDIT_PROGRESS.json',{'rows':rows,'wall_s':time.time()-begin});print('INDEPENDENT_AUDIT',row['id'],row['status'],flush=True)
 final={'status':'PASS' if all(r['status']=='PASS' for r in rows) else 'REVIEW_REQUIRED','method':'separate stdlib full JSON decode, trace quadrature, native receipt interval join and native dq derivatives; original scorer untouched','independence':'second code path by same agent, not an independent researcher or independent dataset','attempt_denominator':len(starts),'rows':rows,'wall_s':time.time()-begin,'source_sha256':sha(Path(__file__)),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 put('audit/INDEPENDENT_RAW_AUDIT.json',final)
if __name__=='__main__':main()
