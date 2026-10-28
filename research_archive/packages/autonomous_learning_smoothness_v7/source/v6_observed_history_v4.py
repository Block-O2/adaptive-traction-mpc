"""Whole-task causal history from the existing observer/measured-wrench trace.
Never indexes evaluation-only Human, future torque, receipts or outcome fields.
"""
import numpy as np
NAMES=['observed_vmax_hip','observed_vmax_knee','observed_amax_hip','observed_amax_knee','observed_jmax_hip','observed_jmax_knee','observed_excursion_hip','observed_excursion_knee','observed_travel_hip','observed_travel_knee','measured_JF_to_now','measured_JM_to_now','measured_force_peak_to_now','measured_moment_peak_to_now','task_history_duration_s','current_phase_outbound','current_phase_hold','current_phase_return']
FLOORS=[.5,.8,3.,6.,500.,1000.,.05,.05,.05,.05,100.,10.,10.,1.,.5,1.,1.,1.]
def arrays(t,x,force,moment,at,phase):
 t=np.asarray(t);use=t<=at+1e-9;t=t[use];x=np.asarray(x)[use];force=np.asarray(force)[use];moment=np.asarray(moment)[use];keep=np.r_[True,np.diff(t)>1e-10];t,x,force,moment=t[keep],x[keep],force[keep],moment[keep];dt=np.diff(t);a=np.diff(x[:,2:],axis=0)/dt[:,None];j=np.diff(a,axis=0)/dt[1:,None];fn=np.linalg.norm(force,axis=1);mn=np.linalg.norm(moment,axis=1)
 values=np.r_[np.max(abs(x[:,2:]),0),np.max(abs(a),0),np.max(abs(j),0),np.ptp(x[:,:2],0),np.sum(abs(np.diff(x[:,:2],axis=0)),axis=0),fn[:-1]@dt,mn[:-1]@dt,fn.max(),mn.max(),t[-1]-t[0],[phase==p for p in ['OUTBOUND','HOLD','RETURN']]]
 assert values.shape==(18,) and np.isfinite(values).all();return values.tolist()
def boundary(b):
 # runtime invokes coordination boundary before appending the current trace row.
 rows=[r for r in b['trace'] if r.get('stage')=='TASK'];now=float(b['physical_now']);rows=rows+[dict(time_s=now,estimated_human_state_rad_rad_s=b['observation'].as_array(),physical_cuff_force_world_n=b['interface'].measured_force_world_n,physical_cuff_moment_world_nm=b['interface'].measured_moment_world_nm)]
 return arrays([r['time_s'] for r in rows],[r.get('estimated_human_state_rad_rad_s',r.get('estimated_state')) for r in rows],[r.get('physical_cuff_force_world_n',r.get('cuff_force_world_n')) for r in rows],[r.get('physical_cuff_moment_world_nm',r.get('cuff_moment_world_nm')) for r in rows],now,b['task_state'].phase.value)
