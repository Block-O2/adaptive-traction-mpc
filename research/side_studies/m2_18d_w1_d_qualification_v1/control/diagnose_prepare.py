from pathlib import Path
import os,json,sys,time,hashlib,shutil,difflib,datetime
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
SIDE=P.parent; A=SIDE/'m2_18d_terminal_expanded_prefix_validation_v1'; S=SIDE/'m2_18d_waypoint_smoothing_overnight_v1'
def put(n,x): (P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
# Derive UTC epoch from the recorded actual start; do not hand-convert offsets.
plan=json.loads((P/'RUN_PLAN.json').read_text());plan['t0']='2026-10-17T15:24:51+08:00'; t0=datetime.datetime.fromisoformat(plan['t0']).timestamp()
old=plan['t0_unix'];plan.update(t0_unix=t0,hard_stop_unix=t0+21600,no_new_physics_after_unix=t0+18900,dispatch_cutoff_unix=t0+18900,physics_hard_stop_unix=t0+18900)
put('RUN_PLAN.json',plan);put('audit/T0_EPOCH_CORRECTION.json',dict(before_epoch=old,correct_epoch=t0,UTC_T0='2026-10-17T07:24:51Z',correct_local_T0=plan['t0'],physics_started=False,reason='correct initial human-facing +8h arithmetic; recorded Unix epoch was correct'))
sys.path[:0]=[str(P/'code')]
import numpy as np
import matplotlib.pyplot as plt
def load(root,ident):
 run=root/'source/results'/ident
 z=np.load(root/'motion_series'/(ident+'.npz'));tr=np.load(run/'trace.npz');m=tr['stage']=='TASK';tf=tr['time_s'][m];origin=tf[0];tf=tf-origin
 out=dict(t=z['time_s']-origin,q=z['true_q_rad'],v=z['true_dq_rad_s'],a=z['acceleration_rad_s2'],j=z['jerk_rad_s3'],tf=tf,f=np.linalg.norm(tr['physical_cuff_force_world_n'][m],axis=1),refq=tr['reference_q_rad'][m],refv=tr['reference_dq_rad_s'][m],refa=tr['reference_ddq_rad_s2'][m],phase=tr['task_phase'][m],su=json.loads((run/'summary.json').read_text()),source=str(run))
 out['cf']=np.r_[0,np.cumsum(out['f'][:-1]*np.diff(tf))]
 out['events']=[]
 for lr in out['su']['learning_records']:
  d=out['su']['decisions'][lr['decision_index']]; req=d['decision_request_time_s']-origin
  out['events'] += [dict(kind='request',task_s=req),dict(kind='activation',task_s=lr['start_time_s']-origin),dict(kind='splice',task_s=lr['start_time_s']-origin+.04)]
 return out
def metrics(z,lo,hi):
 m=(z['t']>=lo-1e-8)&(z['t']<=hi+1e-8);w=np.maximum(0,np.minimum(z['tf'][1:],hi)-np.maximum(z['tf'][:-1],lo));v=z['v'][m];a=z['a'][m];j=z['j'][m]
 return dict(J_F=float(z['f'][:-1]@w),force_peak=float(z['f'][(z['tf']>=lo)&(z['tf']<=hi)].max()),force_RMS=float(np.sqrt((z['f'][:-1]**2@w)/(hi-lo))),TV_v=float(np.linalg.norm(np.diff(v,axis=0),axis=1).sum()),TV_a=float(np.linalg.norm(np.diff(a,axis=0),axis=1).sum()),jerk_RMS=float(np.sqrt(np.mean(np.sum(j*j,axis=1)))),amax_deg=np.rad2deg(abs(a).max(axis=0)).tolist(),jmax_deg=np.rad2deg(abs(j).max(axis=0)).tolist())
Z={k:load(A,'V1_'+a) for k,a in [('B','B'),('18D','E'),('18D-T','T')]}
windows=[(0,19.03),(0,1.5),(1.5,3.1),(3.1,4.3),(4.3,5.6),(5.6,6.8),(6.8,7.4),(7.4,9.005),(9.005,10.025),(10.025,11.7),(11.7,13),(13,14.1),(14.1,15.3),(15.3,16.6),(16.6,17.2),(17.2,19.03)]
rows={f'{lo:g}-{hi:g}':{k:metrics(z,lo,hi) for k,z in Z.items()} for lo,hi in windows};put('derived/HISTORICAL_WINDOWS.json',rows)
peaks={k:{n:[dict(joint=j,task_s=float(z['t'][np.argmax(abs(z[n][:,j]))]),value_deg=float(np.rad2deg(abs(z[n][:,j])).max())) for j in range(2)] for n in ['a','j']} for k,z in Z.items()};put('derived/HISTORICAL_PEAKS.json',peaks)
fig,axs=plt.subplots(11,1,figsize=(15,23),sharex=True,layout='constrained')
for (tag,z),co in zip(Z.items(),['#666666','#d95f02','#0072b2']):
 axs[0].plot(z['tf'],z['f'],c=co,label=tag);axs[1].plot(z['tf'],z['cf'],c=co)
 for j in range(2):
  axs[2+j].plot(z['t'][::12],np.rad2deg(z['q'][::12,j]),c=co);axs[2+j].plot(z['tf'],np.rad2deg(z['refq'][:,j]),ls='--',c=co,alpha=.5)
  axs[4+j].plot(z['t'][::12],np.rad2deg(z['v'][::12,j]),c=co);axs[4+j].plot(z['tf'],np.rad2deg(z['refv'][:,j]),ls='--',c=co,alpha=.5)
 axs[6].plot(z['t'][::8],np.rad2deg(np.linalg.norm(z['a'][::8],axis=1)),c=co)
 axs[7].plot(z['t'][::8],np.rad2deg(np.linalg.norm(z['j'][::8],axis=1)),c=co)
 axs[8].plot(z['tf'],np.rad2deg(np.linalg.norm(np.column_stack([np.interp(z['tf'],z['t'],z['q'][:,j]) for j in range(2)])-z['refq'],axis=1)),c=co)
 axs[9].plot(z['t'][1:],np.r_[0,np.cumsum(np.linalg.norm(np.diff(z['v'],axis=0),axis=1))][1:],c=co)
 for i,(kind,mark) in enumerate([('request','|'),('activation','o'),('splice','x')]):
  axs[10].scatter([e['task_s'] for e in z['events'] if e['kind']==kind],np.full(sum(e['kind']==kind for e in z['events']),i+.14*list(Z).index(tag)),c=co,marker=mark,s=20,label=tag+' '+kind)
labels=['Force N (5 ms)','Cumulative J_F N s','Hip q deg','Knee q deg','Hip v deg/s','Knee v deg/s','Acceleration norm deg/s2','Raw jerk norm deg/s3','Tracking norm deg','Cumulative velocity TV rad/s','Request / activation / splice']
for ax,lab in zip(axs,labels):
 ax.set_ylabel(lab);ax.grid(alpha=.2);ax.set_xlim(0,19.03)
 for t in [9.005,10.025]:ax.axvline(t,c='.5',lw=.6)
axs[0].legend();axs[10].legend(ncol=3,fontsize=7);axs[-1].set_xlabel('Task time s; solid actual / dashed issued reference')
fig.suptitle('Matched historical V1 | B / frozen 18D / frozen 18D-T | no new physics')
fig.savefig(P/'figures/baseline_unified_timeline.png',dpi=130);plt.close(fig)
identities={}
for name in ['m2_18d_terminal_response_repair_v1','m2_18d_terminal_expanded_prefix_validation_v1']:
 root=SIDE/name; conditions=['N2','U1'] if 'response' in name else ['V1','V2']
 for c in conditions:
  for arm in ['B','E','T']:
   m=json.loads((root/'reports'/(c+'_'+arm+'_MEASURED.json')).read_text());identities[c+'_'+arm]=dict(J_F=m['J_F_N_s'],phase=m['phase_cost'],durations=m['phase_durations'],axes=m['axes'],safety=m['native_physical_audit']['pass_'],source=str(root/'reports'/(c+'_'+arm+'_MEASURED.json')),sha256=sha(root/'reports'/(c+'_'+arm+'_MEASURED.json')))
put('derived/FOUR_PREFIX_BASELINE_AUDIT.json',identities)
# Exact prior smoothing extension: add type-specific certified paths; scalar paths unchanged.
rel='source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1'
patches={}
for n in ['multisegment_reference.py','activation_validation.py','safe_fallback.py']:
 src=S/rel/n;dst=P/rel/n
 patches[n]=dict(source=str(src),sha256=sha(src),diff=''.join(difflib.unified_diff(dst.read_text().splitlines(True) if dst.exists() else [],src.read_text().splitlines(True))))
 shutil.copy2(src,dst)
put('audit/ARCHIVED_SMOOTHING_EXTENSION.json',patches)
shutil.copy2(S/'control/interface_base.py',P/'control/interface_base.py')
print(json.dumps(dict(status='PASS',full=rows['0-19.03'],T_peaks=peaks['18D-T'],epoch=t0)),flush=True)
