from pathlib import Path
import os,json,ast,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
src=(R/'analysis/historical_audit.py').read_text();tree=ast.parse(src)
for name in ['load','terminal','variations']:exec(ast.get_source_segment(src,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)))
base=load(P,'Adev_ER');rows=[];ZS={}
windows=[('before_R3',0.,14.085),('R3_and_bridge',14.085,15.38),('R4_and_bridge',15.38,16.945),('R5_and_final_carry',16.945,19.0300001)]
def integral(z,key,lo,hi):return float(z[key][:-1]@np.maximum(0,np.minimum(z['tf'][1:],hi)-np.maximum(z['tf'][:-1],lo)))
for ident in ['Adev_AV090','Adev_AV080']:
 if not (P/'reports'/(ident+'_MEASURED.json')).exists():continue
 z=load(P,ident);ZS[ident]=z;parts=[]
 for label,lo,hi in windows:
  ix=(z['t']>=lo-1e-8)&(z['t']<hi-1e-8);it=(z['tf']>=lo-1e-8)&(z['tf']<hi-1e-8)
  parts.append(dict(window=label,lo=lo,hi=hi,J_F_delta_N_s=integral(z,'f',lo,hi)-integral(base,'f',lo,hi),moment_delta_Nm_s=integral(z,'moment',lo,hi)-integral(base,'moment',lo,hi),max_actual_q_difference_deg=np.max(abs(z['q'][ix]-base['q'][ix]),axis=0).tolist(),actual_knee_vmax_deg_s=float(abs(z['v'][ix,1]).max()),parent_actual_knee_vmax_deg_s=float(abs(base['v'][ix,1]).max()),issued_reference_knee_vmax_deg_s=float(abs(z['rv'][it,1]).max()),parent_reference_knee_vmax_deg_s=float(abs(base['rv'][it,1]).max())))
 err=sum(a['J_F_delta_N_s'] for a in parts)-(z['metric']['J_F_N_s']-base['metric']['J_F_N_s']);assert abs(err)<1e-8
 bsu=read(P/'source/results/Adev_ER/summary.json');su=read(P/'source/results'/ident/'summary.json');sch=[]
 for idx in [11,12,13]:
  a=next(r for r in su['learning_records'] if r['decision_index']==idx)['selected_plan']['schedule'];b=next(r for r in bsu['learning_records'] if r['decision_index']==idx)['selected_plan']['schedule'];sch.append(dict(decision=idx,slot=idx-8,duration_s=a['duration_s'],parent_duration_s=b['duration_s'],target_delta_deg=np.rad2deg(np.array(a['target_q_rad'])-b['target_q_rad']).tolist(),pass_velocity_delta_deg_s=np.rad2deg(np.array(a['target_dq_rad_s'])-b['target_dq_rad_s']).tolist(),certified_reference_vmax_deg_s=np.rad2deg(a['maximum_reference_velocity_rad_s']).tolist(),parent_certified_reference_vmax_deg_s=np.rad2deg(b['maximum_reference_velocity_rad_s']).tolist()))
 rows.append(dict(id=ident,windows=parts,JF_partition_error=err,schedule_changes=sch,scope='Mechanism accounting only; window integrals never used as full-task ranking'))
put('derived/TRACK_A_WINDOW_RESPONSE.json',dict(rows=rows,observation='R3 reference velocity peak decreases while actual Human R3 peak increases. Fixed endpoints/duration redistribute motion, and later R4/R5 durations remain equal while R4 hip target responds slightly.'))
fig,axs=plt.subplots(4,1,figsize=(12,12),sharex=True,layout='constrained')
for ident,c in zip(ZS,['#cc79a7','#e69f00']):
 z=ZS[ident];axs[0].plot(z['t'],z['q'][:,1]-base['q'][:,1],c=c,label=ident);axs[1].plot(z['t'],z['v'][:,1]-base['v'][:,1],c=c);axs[2].plot(z['tf'],z['rv'][:,1],c=c);axs[3].plot(z['tf'],np.r_[0,np.cumsum((z['f'][:-1]-base['f'][:-1])*np.diff(z['tf']))],c=c)
axs[2].plot(base['tf'],base['rv'][:,1],c='#009e73',ls='--',label='ER reference');axs[0].legend();axs[2].legend()
for ax,label in zip(axs,['Actual knee q difference (deg)','Actual knee dq difference (deg/s)','Issued knee dq (deg/s)','Cumulative delta J_F vs ER (N s)']):
 ax.set_ylabel(label);ax.set_xlim(13.8,18.2);ax.grid(alpha=.2)
 for t in [14.085,15.38,16.945]:ax.axvline(t,c='.5',ls=':',lw=.8)
axs[-1].set_xlabel('Task time (s); differences vanish before new R3 splice; complete-task totals remain authoritative');fig.suptitle('New velocity intent: strong local response but small final undershoot change');fig.savefig(P/'figures/Track_A_local_and_downstream.png',dpi=150);plt.close(fig)
for f in [P/'derived/TRACK_A_WINDOW_RESPONSE.json',P/'figures/Track_A_local_and_downstream.png']:
 dest=R/f.relative_to(P);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
print(json.dumps(dict(status='PASS',rows=rows)),flush=True)
