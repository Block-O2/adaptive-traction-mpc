from pathlib import Path
import os,sys,json,ast,shutil,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;A=P.parent/'ihear_autonomous_multitrack_v1'
sys.dont_write_bytecode=True;sys.path[:0]=[str(P/'code'),str(P/'control')]
import study_common as sc
import numpy as np
import matplotlib.pyplot as plt
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import StateResidualHumanModel
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(sc.clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
src=(A/'analysis/historical_audit.py').read_text();tree=ast.parse(src)
for name in ['load','terminal','variations']:exec(ast.get_source_segment(src,next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==name)))
def metrics(e):
 e=np.asarray(e);return dict(rmse=np.sqrt(np.mean(e*e,axis=0)).tolist(),p95_abs=np.quantile(abs(e),.95,axis=0).tolist(),max_abs=np.max(abs(e),axis=0).tolist(),bias=np.mean(e,axis=0).tolist())
data={k:load(A,'Adev_'+k) for k in ['B','T','D','ER']}
put('derived/HISTORICAL_TERMINAL.json',{k:dict(terminal=terminal(v),excursion=v['metric']['dose']['excursion_deg'],delta_B=np.array(v['metric']['dose']['excursion_deg'])-data['B']['metric']['dose']['excursion_deg'],events=v['events']) for k,v in data.items()})
allresults=[];predrows=[];inst=[]
for arm in ['B','ER']:
 p=A/'source/results'/('Adev_'+arm);z=np.load(p/'trace.npz');ix=z['stage']=='TASK';t=z['time_s'][ix];x=z['estimated_human_state_rad_rad_s'][ix];truth=z['evaluation_only_human_state_rad_rad_s'][ix]
 qref=z['reference_q_rad'][ix];vref=z['reference_dq_rad_s'][ix];aref=z['reference_ddq_rad_s2'][ix];acc=z['actual_human_acceleration_rad_s2'][ix];u=z['applied_generalized_action_nm'][ix]
 force=z['physical_cuff_force_world_n'][ix];moment=z['physical_cuff_moment_world_nm'][ix];beta=z['task_beta'];weights=z['task_residual_weights_nm'];su=read(p/'summary.json')
 lr=su['learning_records'][0];geo=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in lr['adaptive_state']['effective_geometry'].items()})
 origins=np.arange(20,len(t)-41,10);hs=[.005,.020,.040,.100,.200];errs={}
 for i in origins:
  m=StateResidualHumanModel(geometry=geo,beta=beta[i],rom_human=sc.rt.high_rom_deployable_prior(),residual_weights_nm=weights[i],residual_limit_nm=12.)
  tau_meas=geo.generalized_input_from_wrench(x[i,:2],force[i],moment[i]);am=m.continuous_dynamics(x[i],tau_meas)[2:];au=m.continuous_dynamics(x[i],u[i])[2:]
  nt=data[arm]['t'];a_true=np.array([np.interp(t[i]-t[0],nt,data[arm]['a'][:,j]) for j in range(2)])
  inst.append(dict(arm=arm,time_s=t[i]-t[0],model_measured_accel_deg_s2=np.rad2deg(am),model_requested_action_accel_deg_s2=np.rad2deg(au),causal_observed_accel_deg_s2=np.rad2deg(acc[i]),native_accel_deg_s2=a_true,PD_request_deg_s2=np.rad2deg(np.array([180,140])*(qref[i]-x[i,:2])+np.array([28,22])*(vref[i]-x[i,2:])),reference_accel_deg_s2=np.rad2deg(aref[i])))
  states={key:x[i].copy() for key in ['model_held_measured_wrench','model_held_requested_action']}
  for step in range(1,41):
   for key,state in states.items():
    # All model parameters and force/command inputs frozen at the prediction origin.
    # No future reference, future wrench, future estimate, or future truth is read.
    action=(geo.generalized_input_from_wrench(state[:2],force[i],moment[i]) if key=='model_held_measured_wrench' else u[i])
    states[key]=m.step_dynamics(state,action,.005)
   h=step*.005
   if step not in [1,4,8,20,40]:continue
   predicts={**states,'constant_velocity':x[i]+np.r_[h*x[i,2:],np.zeros(2)],'causal_constant_acceleration':x[i]+np.r_[h*x[i,2:]+.5*h*h*acc[i],h*acc[i]]}
   target=truth[i+step]
   region='terminal' if 15.3<=t[i]-t[0]<=17.6 else 'other'
   for key,pred in predicts.items():
    error=np.rad2deg(pred-target)
    for area in ['full',region]:errs.setdefault((key,h,area),[]).append(error)
    if region=='terminal':predrows.append(dict(arm=arm,method=key,horizon_s=h,origin_task_s=t[i]-t[0],prediction_deg_deg_s=np.rad2deg(pred),truth_deg_deg_s=np.rad2deg(target),error_deg_deg_s=error))
 for (method,horizon,region),e in errs.items():allresults.append(dict(arm=arm,method=method,horizon_s=horizon,region=region,n=len(e),**metrics(e)))
 print('PREDICTION_ARM_COMPLETE',arm,flush=True)
put('derived/CAUSAL_PREDICTION_RESULTS.json',dict(fitted_to_this_trajectory=False,calibration='existing online causal beta/residual; no posterior fit',origins_spacing_s=.05,horizons_s=hs,methods=['constant_velocity','causal_constant_acceleration','model_held_measured_wrench','model_held_requested_action'],reference_preview='not used; no claimed closed-loop coupled predictor',uncertainty='empirical development absolute-error p95/max only, not coverage guarantee',truth_role='evaluation after predictions only',rows=allresults))
put('derived/PREDICTION_TERMINAL_ROWS.json',predrows);put('derived/ACCELERATION_ALIGNMENT.json',inst)
fig,axs=plt.subplots(4,1,figsize=(12,12),sharex=True,layout='constrained')
for arm in ['B','ER']:
 d=data[arm];axs[0].plot(d['t'],d['q'][:,1],label=arm+' actual');axs[0].plot(d['tf'],d['rq'][:,1],ls='--',label=arm+' reference');axs[1].plot(d['tf'],d['estimated'][:,1]-d['rq'][:,1],label=arm+' estimated error');axs[1].plot(d['t'],d['q'][:,1]-d['rq'][-1,1],ls=':',label=arm+' actual minus goal');axs[2].plot(d['t'],d['v'][:,0],label=arm+' hip');axs[2].plot(d['t'],d['v'][:,1],ls='--',label=arm+' knee');axs[3].plot(d['tf'],d['f'],label=arm)
for ax,l in zip(axs,['Knee angle (deg)','Error (deg)','Actual velocity (deg/s)','Cuff force (N)']):ax.set_ylabel(l);ax.grid(alpha=.2);ax.legend(ncol=2);ax.set_xlim(15.3,18.)
for ax in axs:ax.axvline(terminal(data['ER'])[1]['reference_stably_stopped_task_s'],color='grey',ls=':')
axs[-1].set_xlabel('Task time (s); grey: ER knee reference stable stop');fig.savefig(P/'figures/01_terminal_reference_actual.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(3,1,figsize=(12,10),sharex=True,layout='constrained');r=[v for v in inst if v['arm']=='ER'];tt=[v['time_s'] for v in r]
for key,label in [('model_measured_accel_deg_s2','Model: held sensed wrench'),('model_requested_action_accel_deg_s2','Model: requested action'),('causal_observed_accel_deg_s2','Causal observed acceleration'),('native_accel_deg_s2','Native truth'),('PD_request_deg_s2','Unprojected PD request')]:axs[0].plot(tt,[v[key][1] for v in r],label=label)
d=data['ER']
for key in ['position','velocity','allocator','base']:
 z=np.load(A/'source/results/Adev_ER/trace.npz');ix=z['stage']=='TASK';axs[1].plot(d['tf'],np.linalg.norm(z['robot_torque_component_'+key+'_nm'][ix],axis=1),label=key)
axs[2].plot(d['tf'],d['moment'],label='Cuff moment norm')
for ax,l in zip(axs,['Knee acceleration (deg/s2)','Robot torque component norm (Nm)','Moment (Nm)']):ax.set_ylabel(l);ax.legend(ncol=2);ax.grid(alpha=.2);ax.set_xlim(15.3,18.)
axs[-1].set_xlabel('Task time (s)');fig.savefig(P/'figures/02_control_model_acceleration.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
for method in ['constant_velocity','causal_constant_acceleration','model_held_measured_wrench','model_held_requested_action']:
 rr=sorted([r for r in allresults if r['arm']=='ER' and r['region']=='terminal' and r['method']==method],key=lambda r:r['horizon_s'])
 for ax,metric in zip(axs,['rmse','p95_abs']):ax.plot([r['horizon_s']*1000 for r in rr],[r[metric][1] for r in rr],marker='o',label=method);ax.set_ylabel('Knee q '+metric+' (deg)');ax.set_xlabel('Horizon (ms)');ax.grid(alpha=.2);ax.set_yscale('log')
axs[0].legend(fontsize=7);fig.savefig(P/'figures/03_causal_prediction_error.png',dpi=150);plt.close(fig)
_,options=sc.load_case_options();put('audit/ACTIVE_OPTIONS.json',options)
sources={}
for f in [A/'source/results/Adev_ER/trace.npz',A/'source/results/Adev_ER/summary.json',A/'motion_series/Adev_ER.npz',A/'source/results/Adev_B/trace.npz',A/'motion_series/Adev_B.npz']:sources[str(f)]=sc.sha(f)
put('audit/HISTORICAL_ANALYSIS_SOURCES.json',sources)
for f in [*list((P/'derived').glob('*.json')),*list((P/'figures').glob('*.png'))]:
 dst=R/f.relative_to(P);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
print(json.dumps(sc.clean(dict(status='PASS',terminal=terminal(data['ER'])[1],prediction_ER_terminal=[r for r in allresults if r['arm']=='ER' and r['region']=='terminal' and r['horizon_s']==.1],options=options))),flush=True)
