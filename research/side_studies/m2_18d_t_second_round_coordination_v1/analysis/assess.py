"""Independent observed trajectory statistics; no controller or physics imports."""
from pathlib import Path
import os,json,sys,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def measure(ident):
 z=np.load(P/'motion_series'/(ident+'.npz'));tr=np.load(P/'source/results'/ident/'trace.npz');m=tr['stage']=='TASK';origin=tr['time_s'][m][0];tf=tr['time_s'][m]-origin;t=z['time_s']-origin
 f=np.linalg.norm(tr['physical_cuff_force_world_n'][m],axis=1);mm=np.linalg.norm(tr['physical_cuff_moment_world_nm'][m],axis=1);v=z['true_dq_rad_s'];a=z['acceleration_rad_s2'];j=z['jerk_rad_s3'];q=z['true_q_rad']
 raw=read('reports/'+ident+'_MEASURED.json');su=read('source/results/'+ident+'/summary.json');transition={r['to']:r['time_s']-origin for r in su['task']['phase_transitions']}
 def window(lo,hi):
  sel=(t>=lo-1e-9)&(t<=hi+1e-9);w=np.maximum(0,np.minimum(tf[1:],hi)-np.maximum(tf[:-1],lo));ix=(tf>=lo-1e-9)&(tf<=hi+1e-9)
  return dict(J_F=float(f[:-1]@w),force_peak_N=float(f[ix].max()),force_RMS_N=float(np.sqrt(f[:-1]**2@w/(hi-lo))),moment_integral_Nm_s=float(mm[:-1]@w),TV_v=float(np.linalg.norm(np.diff(v[sel],axis=0),axis=1).sum()),TV_a=float(np.linalg.norm(np.diff(a[sel],axis=0),axis=1).sum()),jerk_RMS=float(np.sqrt(np.mean(np.sum(j[sel]**2,axis=1)))),TV_v_joint=np.abs(np.diff(v[sel],axis=0)).sum(axis=0).tolist(),TV_a_joint=np.abs(np.diff(a[sel],axis=0)).sum(axis=0).tolist(),velocity_rms_deg=np.rad2deg(np.sqrt(np.mean(v[sel]**2,axis=0))).tolist(),acceleration_rms_deg=np.rad2deg(np.sqrt(np.mean(a[sel]**2,axis=0))).tolist(),amax_deg=np.rad2deg(abs(a[sel]).max(axis=0)).tolist(),jmax_deg=np.rad2deg(abs(j[sel]).max(axis=0)).tolist(),excursion_deg=np.rad2deg(np.ptp(q[sel],axis=0)).tolist(),travel_deg=np.rad2deg(np.abs(np.diff(q[sel],axis=0)).sum(axis=0)).tolist())
 windows={'full':window(0,float(tf[-1]))}
 for ph,lo,hi in [('OUTBOUND',0,transition['HOLD']),('HOLD',transition['HOLD'],transition['RETURN']),('RETURN',transition['RETURN'],transition['COMPLETE'])]:windows[ph]=window(lo,hi)
 for lo,hi in [(1.5,3.2),(2.8,3.2),(4,6),(6.8,7.4),(13.8,16.6),(15,16),(16.5,17.3)]:windows[f'{lo:g}-{hi:g}']=window(lo,hi)
 assert abs(windows['full']['J_F']-raw['J_F_N_s'])<1e-8
 posture=[];terminal=[]
 for lr in su['learning_records']:
  screen=lr['selected_plan']['execution_screen']
  if 'second_round_posture' in screen:posture.append(dict(decision_index=lr['decision_index'],request_task_s=lr['request_time_s']-origin,**screen['second_round_posture']))
  if 'terminal_duration_intervention' in screen:terminal.append(dict(decision_index=lr['decision_index'],request_task_s=lr['request_time_s']-origin,**screen['terminal_duration_intervention']))
 return dict(id=ident,windows=windows,tracking_RMS_deg=raw['tracking_RMS_deg'],clearance=raw['clearance'],force_peak_N=raw['force_peak_N'],moment_peak_Nm=raw['moment_peak_Nm'],native_audit=raw['native_physical_audit'],axes=raw['axes'],dose=raw['dose'],posture_interventions=posture,T_interventions=terminal),dict(t=t,tf=tf,f=f,cf=np.r_[0,np.cumsum(f[:-1]*np.diff(tf))],q=q,v=v,a=a,j=j,refq=tr['reference_q_rad'][m],refv=tr['reference_dq_rad_s'][m])
def main():
 groups=sys.argv[1:] or ['dev'];allrows=[];series={};metrics={}
 for g in groups:
  for r in read(g+'_RESULTS.json')['rows']:
   ident=r['id'];m,z=measure(ident);metrics[ident]=m;series[ident]=z
   base=metrics.get(g+'_T')
   if base:
    b=base['windows']['full'];x=m['windows']['full'];d=x['J_F']-b['J_F'];changes={k:x[k]/b[k]-1 for k in ['TV_v','TV_a','jerk_RMS']}
    qualified=bool(r['motion']['acceptance_pass'] and r['task']=='PASS' and r['receipt']=='PASS' and r['absolute_safety'])
    force_signal=d<=-.5 and max(changes.values())<=.002
    motion_signal=min(changes.values())<=-.005 and max(changes.values())<=.002 and d<=.2
    actual_change={k:float(np.max(abs(z[k]-series[g+'_T'][k]))) for k in ['q','v','a']}
    row=dict(id=ident,candidate=r['candidate'],qualified=qualified,J_F=x['J_F'],delta_J_F_vs_T=d,delta_vs_T=changes,force_signal=force_signal,motion_signal=motion_signal,eligible=qualified and (force_signal or motion_signal),actual_change=actual_change,full=x,windows=m['windows'],posture_interventions=m['posture_interventions'])
    allrows.append(row)
 put('derived/COMPLETE_METRICS_'+('_'.join(groups))+'.json',metrics);put('derived/ASSESSMENT_'+('_'.join(groups))+'.json',dict(rows=allrows,thresholds_from='SELECTION_RULE.json',created_unix=time.time()))
 for r in allrows:print(json.dumps({k:r[k] for k in ['id','qualified','delta_J_F_vs_T','delta_vs_T','eligible','actual_change']},ensure_ascii=False),flush=True)
 # Parallel tradeoff objectives remain separate, including unqualified results.
 fig,axs=plt.subplots(1,3,figsize=(15,4.8),layout='constrained')
 for r in allrows:
  if r['candidate']['id'] in ['B','E','T','T_zero']:continue
  for ax,key in zip(axs,['TV_v','TV_a','jerk_RMS']):
   label={'dev_P_more':'One target','dev_S_O':'Local O','dev_S_R':'Local R','refine_P_corridor':'Two targets'}.get(r['id'],r['id'])
   offset=(6,-13) if r['candidate']['id']=='S_O' else (6,7)
   ax.scatter(r['delta_J_F_vs_T'],100*r['delta_vs_T'][key],c='#0072b2' if r['qualified'] else '#d73027',marker='o' if r['eligible'] else 'x',s=65);ax.annotate(label,(r['delta_J_F_vs_T'],100*r['delta_vs_T'][key]),fontsize=8,xytext=offset,textcoords='offset points')
 for ax,key in zip(axs,['velocity TV','acceleration TV','jerk RMS']):ax.axhline(0,c='.5',lw=.7);ax.axvline(0,c='.5',lw=.7);ax.set_xlabel('Full delta J_F vs matched frozen T [N s]');ax.set_ylabel('Full '+key+' change [%]');ax.grid(alpha=.2);ax.set_xlim(-1.4,.35);ax.margins(y=.18)
 fig.suptitle('Development force–motion trade-off vs matched T\nShown arms pass original development gates; circle meets the additional selection criterion')
 fig.savefig(P/'figures/force_motion_tradeoff.png',dpi=150);plt.close(fig)
 # Preserve a common full/local time axis for each development intervention.
 if 'dev_T' in series:
  base=series['dev_T'];candidates=[r for r in allrows if r['id'].startswith('dev_') and r['candidate']['id'] not in ['B','E','T','T_zero']]
  fig,axs=plt.subplots(4,1,figsize=(13,13),sharex=True,layout='constrained')
  for r in candidates:
   z=series[r['id']];label=r['candidate']['id'];axs[0].plot(z['tf'],z['f']-base['f'],label=label);axs[1].plot(z['tf'],z['cf']-base['cf']);axs[2].plot(z['t'][::10],np.rad2deg(z['v'][::10,0]-base['v'][::10,0]));axs[3].plot(z['t'][::10],np.rad2deg(z['v'][::10,1]-base['v'][::10,1]))
  for ax,label in zip(axs,['Delta force N','Delta cumulative J_F N s','Delta actual hip v deg/s','Delta actual knee v deg/s']):ax.set_ylabel(label);ax.axhline(0,c='.5',lw=.6);ax.grid(alpha=.2)
  axs[0].legend();axs[-1].set_xlabel('Task s');fig.suptitle('Intervention response vs frozen T | full task including downstream effects');fig.savefig(P/'figures/intervention_full_response.png',dpi=150);plt.close(fig)
if __name__=='__main__':main()
