"""Postprocess every complete arm; retain failures; no physics."""
from pathlib import Path
import os,sys,json,hashlib,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/force_mechanism_waypoint_v3');sys.path.insert(0,str(P/'code'));sys.path.insert(0,str(P/'control'))
import numpy as np
import matplotlib.pyplot as plt
from analyze_mechanism import clean,put,integ,metrics
from stream_runtime_evidence import array_items
def encode(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(encode(x).encode()).hexdigest()
def polynomial(c,T,t):
 u=np.clip(t/T,0,1);c=np.asarray(c,float)
 return [np.asarray([np.polynomial.polynomial.polyval(u,np.polynomial.polynomial.polyder(row,m=k)) for row in c])/T**k for k in range(3)]
def sample(r,t):
 if r['canonical_zero_identity_evaluation']:
  a=r['identity_payload']['original'];return polynomial(a['values'],a['duration_s'],t)
 i=min(len(r['segments'])-1,max(0,int(np.searchsorted(r['knots_s'],t,side='right')-1)));a=r['segments'][i];return polynomial(a['immutable_coefficients'],a['duration_s'],t-r['knots_s'][i])
def load(ident):
 run=P/'source/results'/ident;tr=np.load(run/'trace.npz');m=tr['stage']=='TASK';mo=np.load(P/'motion_series'/(ident+'.npz'));t0=mo['time_s'][0];tf=tr['time_s'][m]-t0;t=mo['time_s']-t0;q=mo['true_q_rad'];v=mo['true_dq_rad_s'];a=mo['acceleration_rad_s2'];j=mo['jerk_rad_s3'];force=np.linalg.norm(tr['physical_cuff_force_world_n'][m],axis=1)
 z={k:tr[k][m] for k in tr.files if len(tr[k])==len(m)};z.update(t=t,tf=tf,q=q,v=v,a=a,j=j,f=force,cf=np.r_[0,np.cumsum(force[:-1]*np.diff(tf))],refq=tr['reference_q_rad'][m],refv=tr['reference_dq_rad_s'][m],verr=v[::20]-tr['reference_dq_rad_s'][m],torque=tr['cr12_actuator_command_nm'][m])
 assert np.max(abs(q[::20]-tr['evaluation_only_human_state_rad_rad_s'][m,:2]))<1e-12
 assert np.max(abs(v[::20]-tr['evaluation_only_human_state_rad_rad_s'][m,2:]))<1e-12
 su=json.loads((run/'summary.json').read_text());ev=[]
 for d in su['decisions']:
  for kind,key in [('request','decision_request_time_s'),('activation','actual_schedule_start_physics_s')]:
   if d.get(key) is not None:ev.append(dict(kind=kind,task_s=d[key]-t0,request_id=d['timing_request_id'],phase=d['phase']))
 for e in array_items(run/'runtime_artifacts.json.gz','rolling_splice_events'):
  if e.get('actual_splice_physics_s') is not None:ev.append(dict(kind='splice',task_s=e['actual_splice_physics_s']-t0,request_id=e.get('request_id')))
 z['events']=ev;z['su']=su;z['beta']=tr['task_beta'];z['weights']=tr['task_residual_weights_nm']
 return z
def audit(ident,z):
 run=P/'source/results'/ident;receipts=list(array_items(run/'runtime_artifacts.json.gz','command_receipts'));multi=[r for r in receipts if r.get('applied') and r.get('native_steps',0)>0 and 'multisegment_reference' in r];objects=json.loads((P/'output'/(ident+'_REFERENCE_OBJECTS.json')).read_text())['references'];errors=[];mx=0
 for key,obj in objects.items():
  assert digest(obj['identity_payload'])==key==obj['reference_id'];assert digest([key,encode(obj['path_certificate'])])==obj['certificate_id'];assert obj['path_certificate']['feasible']
 for r in multi:
  a=r['multisegment_reference'];obj=objects[a['reference_id']];expected=sample(obj,a['selected_local_progress_s'])
  mx=max(mx,max(float(np.max(abs(x-np.asarray(a[k])))) for x,k in zip(expected,['q_rad','dq_rad_s','ddq_rad_s2'])))
  assert a['q_rad']==r['q_ref_rad'] and a['dq_rad_s']==r['dq_ref_rad_s'];assert a['worker_certificate_id']==obj['certificate_id'];assert a['current_full_path_certificate']['feasible'];assert digest([a['reference_id'],a['current_full_path_certificate']])==a['current_certificate_id'];assert a['source_sample_time_s']==obj['binding']['source_sample_time_s'];assert a['source_capture_ns']==obj['binding']['sensor_capture_ns']
 assert mx<1e-10
 if objects:assert multi,'Proposed multisegment object with no positive-step receipt'
 comp=sum(z['robot_torque_component_'+k+'_nm'][:-1] for k in ['base','position','velocity','allocator','clipping']);assert np.max(abs(comp-z['torque'][:-1]))<1e-9
 measure=json.loads((P/'reports'/(ident+'_MEASURED.json')).read_text());assert abs(z['cf'][-1]-measure['J_F_N_s'])<1e-8
 out=dict(id=ident,status='PASS',reference_objects=len(objects),positive_multisegment_receipts=len(multi),multisegment_native_steps=sum(r['native_steps'] for r in multi),reference_reconstruction_max_error=mx,identity_worker_certificate_and_current_certificate_reconstructed=True,native_ownership_original_gate=measure['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID'],native_rows_original_gate=measure['native_steps'],torque_component_sum_error=float(np.max(abs(comp-z['torque'][:-1]))),request_count=len(z['su']['decisions']),first_multisegment_task_s=None if not multi else multi[0]['start_physics_s']-10.05,last_multisegment_task_s=None if not multi else multi[-1]['end_physics_s']-10.05,source_age_scope='original scientific mode evaluator only; not host qualification')
 put('audit/'+ident+'_REFERENCE_RECEIPT_AUDIT.json',out);put('evidence/'+ident+'_MULTISEGMENT_RECEIPTS.json',dict(rows=multi));return out
def save(fig,name):
 from plot_local_scale import visible_y_limits
 for ax in fig.axes:visible_y_limits(ax)
 fig.savefig(P/'figures'/(name+'.png'),dpi=160);fig.savefig(P/'figures'/(name+'.svg'));plt.close(fig)
def main():
 assert (P/'PHYSICAL_DONE.json').exists(),'Wait for campaign final completion'
 rows=[json.loads(l) for l in (P/'CANDIDATE_RESULTS.jsonl').read_text().splitlines()];complete=[r for r in rows if r['status']=='COMPLETE'];B=load('targeted2_B0');cases={};audits=[]
 for r in complete:
  ident=r['id'];z=load(ident);cases[ident]=z;audits.append(audit(ident,z));windows=[(0,z['tf'][-1]),(4,6),(15,16)]
  if r['candidate'].get('local_window_task_s'):windows.append(tuple(r['candidate']['local_window_task_s']))
  mm={f'{lo:.6f}-{hi:.6f}':metrics(z,lo,hi) for lo,hi in windows};r['detailed_metrics']=mm
  # Pre-first-applied interval is an exact negative control for changed arms.
  if audits[-1]['first_multisegment_task_s'] is not None:
   before=z['tf']<audits[-1]['first_multisegment_task_s']-1e-8
   r['pre_intervention_exact']={k:bool(np.array_equal(z[k][before],B[k][before],equal_nan=True)) for k in ['f','refq','refv','torque','evaluation_only_human_state_rad_rad_s','cr12_q_rad','physical_cuff_moment_world_nm']};assert all(r['pre_intervention_exact'].values())
  put('derived/'+ident+'_METRICS.json',r)
  np.savez_compressed(P/'series'/(ident+'.npz'),**{k:v for k,v in z.items() if isinstance(v,np.ndarray)})
 put('TARGETED_RESULTS.json',dict(rows=rows,audits=audits))
 for tag in ['O','R']:
  rs=[r for r in complete if r['candidate']['id'].startswith(tag+'_')];lo,hi=rs[0]['candidate']['local_window_task_s'];fig,axs=plt.subplots(11,2,figsize=(19,23),sharex=True,layout='constrained');colormap={'zero':'#2166ac','smooth':'#b2182b','opposite_quarter':'#4d9221','half':'#e08214','repeat':'#762a83'}
  for r in rs:
   z=cases[r['id']];name=r['candidate']['id'];kind=name[2:];col=colormap.get(kind,'gray');style='--' if kind=='repeat' else '-'
   for c in [0,1]:
    axs[0,c].plot(z['tf'],z['f'] if c==0 else z['cf']-np.interp(lo,z['tf'],z['cf']),c=col,ls=style,label=name+(' FAIL' if not r['motion_pass'] else ''))
    axs[1,c].plot(z['tf'],z['f']-B['f'] if c==0 else z['cf']-B['cf'],c=col,ls=style)
    axs[2,c].plot(z['t'],np.degrees(z['v'][:,c]),c=col,ls=style)
    axs[3,c].plot(z['tf'],np.degrees(z['refv'][:,c]-B['refv'][:,c]),c=col,ls=style)
    axs[4,c].plot(z['t'],np.degrees(z['a'][:,c]),c=col,ls=style)
    axs[5,c].plot(z['t'][::4],z['j'][::4,c],c=col,ls=style)
    axs[6,c].plot(z['tf'],np.degrees(z['q'][::20,c]-z['refq'][:,c]),c=col,ls=style)
    axs[7,c].plot(z['tf'],np.linalg.norm(z['physical_cuff_moment_world_nm'] if c==0 else z['torque']-B['torque'],axis=1),c=col,ls=style)
    key='allocated_wrench_world';axs[8,c].plot(z['tf'],np.linalg.norm(z[key][:,:3] if c==0 else z[key][:,3:],axis=1),c=col,ls=style)
    axs[9,c].plot(z['tf'],np.linalg.norm(z['robot_torque_component_'+('allocator' if c==0 else 'velocity')+'_nm']-B['robot_torque_component_'+('allocator' if c==0 else 'velocity')+'_nm'],axis=1),c=col,ls=style)
    for ki,mark in [('request','|'),('activation','o'),('splice','x')]:
     ev=[e['task_s'] for e in z['events'] if e['kind']==ki];axs[10,c].scatter(ev,np.full(len(ev),list(colormap).index(kind)),marker=mark,c=col,s=25)
  labels=[['Force [N]','Local cumulative J_F [N s]'],['Force − B [N]','Cumulative J_F − B [N s]'],['Hip actual v [deg/s]','Knee actual v [deg/s]'],['Hip reference Δv [deg/s]','Knee reference Δv [deg/s]'],['Hip acceleration [deg/s²]','Knee acceleration [deg/s²]'],['Hip raw jerk [rad/s³]','Knee raw jerk [rad/s³]'],['Hip tracking [deg]','Knee tracking [deg]'],['Cuff moment norm [Nm]','Robot torque Δnorm [Nm]'],['Total command force [N]','Total command moment [Nm]'],['Allocator torque Δnorm [Nm]','Velocity-feedback torque Δnorm [Nm]'],['Lifecycle row by arm','Lifecycle row by arm']]
  for row in range(11):
   for c in [0,1]:
    ax=axs[row,c];ax.set_ylabel(labels[row][c]);ax.set_xlim(lo-.15,hi+.5);ax.axvspan(lo,hi,color='#238b45',alpha=.06);ax.grid(alpha=.2)
  axs[0,0].legend(ncol=3,fontsize=8);axs[-1,0].set_xlabel('Task elapsed [s]');axs[-1,1].set_xlabel('Task elapsed [s]');fig.suptitle(tag+' targeted shape intervention | original ±0.05° bound / quarter-scale opposite | all outcomes retained');save(fig,'06_'+tag+'_targeted_intervention')
 # Compact exact metric contrasts, separating local and full-task effect.
 table=[]
 for r in complete:
  if 'local' not in r:continue
  z=cases[r['id']];lo,hi=r['candidate']['local_window_task_s'];mm=metrics(z,lo,hi);bm=metrics(B,lo,hi)
  deltaf=z['f']-B['f'];fi=(z['tf']>=lo)&(z['tf']<=hi);schedule_diff=[]
  for i,(a,b) in enumerate(zip(z['su']['decisions'],B['su']['decisions'])):
   if a['decision_request_time_s']!=b['decision_request_time_s'] or a['executed_label']!=b['executed_label']:schedule_diff.append(dict(index=i,request_task_s=a['decision_request_time_s']-10.05,B_request_task_s=b['decision_request_time_s']-10.05,label=a['executed_label'],B_label=b['executed_label']))
  table.append(dict(id=r['id'],motion_pass=r['motion_pass'],full_J_F=r['J_F'],full_delta_J_F=r['J_F']-B['cf'][-1],local_window=[lo,hi],local_delta_J_F=mm['J_F']-bm['J_F'],local_positive_force_area=integ(z['tf'],np.maximum(deltaf,0),lo,hi),local_negative_force_area=integ(z['tf'],np.minimum(deltaf,0),lo,hi),local_force_lower_time_fraction=integ(z['tf'],(deltaf<0).astype(float),lo,hi)/(hi-lo),local_force_delta_extrema=[deltaf[fi].min(),deltaf[fi].max()],local_TV_v_percent=100*(mm['TV_v']/bm['TV_v']-1),local_TV_refv_percent=100*(mm['TV_refv']/bm['TV_refv']-1),local_TV_a_percent=100*(mm['TV_a']/bm['TV_a']-1),local_jerk_RMS_percent=100*(mm['combined_jerk_RMS']/bm['combined_jerk_RMS']-1),local_moment_delta=mm['moment_J']-bm['moment_J'],tracking_RMS_deg=mm['q_tracking_RMS_deg'],schedule_event_changes=schedule_diff,full_duration_s=z['tf'][-1],actual_end_q_delta_deg=np.degrees(z['q'][-1]-B['q'][-1]),actual_max_q_delta_deg=np.max(abs(np.degrees(z['q']-B['q'])),axis=0)))
 put('derived/TARGETED_CONTRASTS.json',dict(rows=table));print(json.dumps(clean(table),indent=2))
if __name__=='__main__':main()
