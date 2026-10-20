"""Independent stored-trace audit of the intended local intervention."""
from pathlib import Path
import json,os,sys,gzip
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
LOCAL=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/LOCAL.name
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def put(n,x):(LOCAL/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
rows=[]
for g in sys.argv[1:] or ['N2']:
 rr=json.loads((P/(g+'_RESULTS.json')).read_text())['rows'];by={r['arm']:r for r in rr};su={a:json.loads((P/'source/results'/(g+'_'+a)/'summary.json').read_text()) for a in ['B','E','T']}
 before={};e=su['E'];tt=su['T'];events=[]
 for i,(el,tl) in enumerate(zip(e['learning_records'],tt['learning_records'])):
  ed=e['decisions'][el['decision_index']];td=tt['decisions'][tl['decision_index']];es=el['selected_plan']['schedule'];ts=tl['selected_plan']['schedule'];meta=tl['selected_plan']['execution_screen'].get('terminal_duration_intervention')
  if meta:
   assert meta['status']=='ACCEPTED' and tl['selected_plan_activated']
   assert abs(ts['duration_s']-np.ceil(es['duration_s']*1.5/.005-1e-10)*.005)<1e-12
   for k in ['start_q_rad','start_dq_rad_s','target_q_rad','target_dq_rad_s']:assert np.max(abs(np.asarray(ts[k])-es[k]))<1e-12
   assert abs(ed['decision_request_time_s']-td['decision_request_time_s'])<1e-10
   assert abs(ed['actual_schedule_start_physics_s']-td['actual_schedule_start_physics_s'])<1e-10
   composite=td['rolling_composite'];assert abs(composite['splice_elapsed_s']-.04)<1e-12
   events.append(dict(index=i,meta=meta,E_schedule=es,T_schedule=ts,E_request=ed['decision_request_time_s'],T_request=td['decision_request_time_s'],activation=td['actual_schedule_start_physics_s'],splice=td['actual_schedule_start_physics_s']+.04))
  elif not events:
   assert es==ts,(g,i,'UPSTREAM_SCHEDULE_CHANGED')
 assert len(events)==1,'Expected exactly one final OUTBOUND intervention'
 ev=events[0];z=np.load(P/'source/results'/(g+'_E')/'trace.npz');y=np.load(P/'source/results'/(g+'_T')/'trace.npz');t0=z['time_s'][z['stage']=='TASK'][0];cut=ev['splice'];first={};upstream={}
 for k in ['reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','evaluation_only_human_state_rad_rad_s','cr12_actuator_command_nm','physical_cuff_force_world_n']:
  d=np.max(abs(y[k]-z[k]),axis=1);ix=np.flatnonzero(d>1e-10);first[k]=None if not len(ix) else z['time_s'][ix[0]]-t0
  pre=z['time_s']<=cut+1e-10;upstream[k]=float(np.nanmax(d[pre]));assert upstream[k]<1e-10,(g,k,'PHYSICAL_OR_REFERENCE_CHANGE_BEFORE_SPLICE')
 measures={}
 for a in ['B','E','T']:
  m=json.loads((P/'reports'/(g+'_'+a+'_MEASURED.json')).read_text());ms=np.load(P/'motion_series'/(g+'_'+a+'.npz'));nt=ms['time_s']-t0;acc=np.rad2deg(ms['acceleration_rad_s2']);j=np.argmax(abs(acc[:,1]));mask=(nt>=ev['E_request']-t0)&(nt<8)
  measures[a]=dict(J_F_N_s=m['J_F_N_s'],motion=by[a]['motion'],native_full=m['motion']['raw']['full'],phase_motion=m['motion']['raw']['phases'],dose=m['dose'],tracking_RMS_deg=m['tracking_RMS_deg'],moment_integral_Nm_s=m['moment_integral_Nm_s'],clearance=m['clearance'],knee_peak=dict(task_s=nt[j],signed_deg_s2=acc[j,1]),terminal_knee_max_abs_acceleration_deg_s2=np.max(abs(acc[mask,1])),absolute_safety=by[a]['absolute_safety'],task=by[a]['task'],receipt=by[a]['receipt'])
 fullE=np.array(measures['E']['native_full']['acceleration_deg_s2']['max_abs']);fullT=np.array(measures['T']['native_full']['acceleration_deg_s2']['max_abs'])
 row=dict(group=g,status='PASS',one_accepted_final_intervention=True,original_selected_target_and_pass_velocity_preserved=True,unchanged_all_upstream_schedules=True,reference_and_physical_before_splice_max_abs_error=upstream,first_5ms_difference_task_s=first,events=events,measures=measures,delta_J_F_T_minus_E=by['T']['J_F_N_s']-by['E']['J_F_N_s'],delta_J_F_T_minus_B=by['T']['J_F_N_s']-by['B']['J_F_N_s'],knee_max_reduction_percent_vs_E=100*(fullE[1]-fullT[1])/fullE[1],interpretation='Paired local reference timing total effect. Does not uniquely identify allocator/contact/feedback mediators.')
 rows.append(row);print(g,'T',by['T']['J_F_N_s'],'knee amax',fullT[1],'ratio',by['T']['motion']['burden_ratios']['acceleration_deg_s2/max_abs'][1],flush=True)
put('audit/INTERVENTION_EXECUTION_AUDIT.json',dict(status='PASS',rows=rows,no_physics=True,no_controller_imports=True))
