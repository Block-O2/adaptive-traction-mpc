"""Reference/receipt kinematic consistency around real rolling handoffs, evaluation only."""
from pathlib import Path
import os,sys,json,gzip
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def analyze(ident,root=P):
 rp=root/'runtime/source/results'/ident
 with np.load(rp/'trace.npz') as z:
  k=z['stage']=='TASK';t=z['time_s'][k];q=z['reference_q_rad'][k];v=z['reference_dq_rad_s'][k];tau=z['cr12_actuator_command_nm'][k];fq=z['physical_cuff_force_world_n'][k]
  _,ix=np.unique(t,return_index=True);t,q,v,tau,fq=[x[ix] for x in [t,q,v,tau,fq]]
 with np.load(root/'runtime/motion_series'/(ident+'.npz')) as z:nt=z['time_s'];j=z['jerk_rad_s3']
 with gzip.open(rp/'runtime_artifacts.json.gz','rt') as f:raw=json.load(f)
 dt=np.diff(t);dq=np.diff(q,axis=0);hold=(np.max(abs(dq),axis=1)<1e-12)&(np.max(abs(v[:-1]),axis=1)>.02)
 indices=np.flatnonzero(hold);groups=np.split(indices,np.flatnonzero(np.diff(indices)>1)+1) if len(indices) else []
 groups=[a for a in groups if len(a)>0];mask=np.zeros(len(nt),bool);events=[]
 for ix in groups:
  lo=float(t[ix[0]]);hi=float(t[ix[-1]+1]);window=(nt>=lo-.005-1e-9)&(nt<=hi+.035+1e-9);mask|=window
  rr=[r for r in raw['wall_physics']['command_receipts'] if r.get('applied') and lo-1e-9<=r['source_sample_time_s']<=hi+1e-9]
  guard=[e['clearance_feedback'] for e in raw['execution_attempts'] if e.get('clearance_feedback') and lo-.005-1e-9<=e['source_sample_time_s']<=hi+.035+1e-9]
  events.append(dict(start_task_s=lo-t[0],duration_s=hi-lo,samples=len(ix),reference_q_held_deg=np.degrees(q[ix[0]]).tolist(),reference_dq_nonzero_deg_s=np.degrees(v[ix[0]]).tolist(),receipt_indices=[r['receipt_index'] for r in rr],receipt_reference_hold_verified=bool(rr and all(np.max(abs(np.asarray(r['q_ref_rad'])-q[ix[0]]))<1e-9 for r in rr if 'q_ref_rad' in r)),window_native_jerk_RMS_deg_s3=np.sqrt(np.mean(np.degrees(j[window])**2,axis=0)).tolist(),guard_active_in_window=sum(c['active'] for c in guard),guard_stencil_crosses_in_window=sum(c.get('v4_branch_diagnostic',{}).get('directional_stencil_crosses',False) for c in guard)))
 total=np.sum(j*j,axis=0);energy=np.sum(j[mask]*j[mask],axis=0)
 out=dict(id=ident,events=events,held_q_with_nonzero_dq_intervals=int(hold.sum()),native_jerk_energy_fraction_in_registered_windows=(energy/total).tolist(),registered_window='[held reference start-5ms, held interval end+35ms]; no alignment fit; native squared-jerk sum descriptive, not unique causal mediation',raw_reference_sampling_s=float(np.median(dt)),interpretation='During these original execution intervals successive commanded q samples are equal while commanded dq is nonzero. This is directly observable at 5ms and receipt-level, distinct from clearance finite differences. Bounded legal pass-velocity interventions test total physical effect; no executor/guard replacement.')
 dest=P/'analysis/handoffs'/(ident+'.json');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(out,indent=2)+'\n')
 print('HANDOFF',ident,'intervals',len(events),'frozen_samples',hold.sum(),'jerk_energy_fraction',energy/total,flush=True)
 return out
if __name__=='__main__':
 for ident in sys.argv[1:] or ['CORE01_B','CORE01_BEST']:analyze(ident)
