"""Independent issued-reference sampled kinematics; no filtering or controller changes."""
from pathlib import Path
import os,sys,json,datetime
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def stats(x):
 return dict(rms=np.sqrt(np.mean(x*x,axis=0)).tolist(),peak_abs=np.max(abs(x),axis=0).tolist(),p95_abs=np.quantile(abs(x),.95,axis=0).tolist(),p99_abs=np.quantile(abs(x),.99,axis=0).tolist())
def evaluate(ident):
 with np.load(P/'runtime/source/results'/ident/'trace.npz') as z:
  k=np.flatnonzero(z['stage']=='TASK');t=z['time_s'][k];_,u=np.unique(t,return_index=True);k=k[u];t=z['time_s'][k];q=z['reference_q_rad'][k];v=z['reference_dq_rad_s'][k];a=z['reference_ddq_rad_s2'][k]
 numerical_v=np.gradient(q,t,axis=0,edge_order=2);numerical_a=np.gradient(numerical_v,t,axis=0,edge_order=2);numerical_j=np.gradient(numerical_a,t,axis=0,edge_order=2)
 held=(np.max(abs(np.diff(q,axis=0)),axis=1)<1e-12)&(np.max(abs(v[:-1]),axis=1)>.02)
 d=dict(id=ident,sampling_s=float(np.median(np.diff(t))),velocity_field_minus_sampled_q_derivative_deg_s=stats(np.degrees(v-numerical_v)),acceleration_field_minus_sampled_dq_derivative_deg_s2=stats(np.degrees(a-np.gradient(v,t,axis=0,edge_order=2))),issued_position_sampled_velocity_deg_s=stats(np.degrees(numerical_v)),issued_position_sampled_acceleration_deg_s2=stats(np.degrees(numerical_a)),issued_position_sampled_jerk_deg_s3=stats(np.degrees(numerical_j)),advertised_acceleration_field_sampled_derivative_deg_s3=stats(np.degrees(np.gradient(a,t,axis=0,edge_order=2))),consecutive_equal_q_with_nonzero_dq_intervals=int(held.sum()),scope='Original 5ms issued/admitted reference trace. Native human derivatives and original gates unchanged. Sampled position derivatives quantify discrete handoff inconsistency; they do not reconstruct a continuous submillisecond reference or imply mechanical jerk equals reference jerk.',filtered=False)
 dest=P/'analysis/reference_consistency'/(ident+'.json');dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(d,indent=2)+'\n');return d
if __name__=='__main__':
 for ident in sys.argv[1:]:
  d=evaluate(ident);print(ident,'q_sampled_jerk_RMS',d['issued_position_sampled_jerk_deg_s3']['rms'],'advertised_a_derivative_RMS',d['advertised_acceleration_field_sampled_derivative_deg_s3']['rms'],'q_dq_inconsistency_RMS',d['velocity_field_minus_sampled_q_derivative_deg_s']['rms'])
