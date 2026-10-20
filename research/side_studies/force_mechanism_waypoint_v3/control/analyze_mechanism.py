"""Read-only archive analysis; no plant/controller imports or physics calls."""
from pathlib import Path
import os, json, hashlib, subprocess, shutil, sys
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MPLBACKEND='Agg')
import numpy as np
from scipy.signal import savgol_filter
import matplotlib.pyplot as plt
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
P=S/'force_mechanism_waypoint_v3'; D=S/'force_motion_coupling_diagnosis_v2'
LOCAL=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with open(f,'rb') as st:
  for b in iter(lambda:st.read(2**20),b''):h.update(b)
 return h.hexdigest()
def snapshot():
 g={}
 for k,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('staged',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]:
  b=subprocess.check_output(['git','-C',str(MAIN),*args]);g[k]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
  if k in ['head','branch']:g[k]['value']=b.decode().strip()
  (P/'audit'/('git_'+k+'_before.txt')).write_bytes(b)
 g['index']=sha(MAIN/'.git/index')
 return {'git':g,'files':{str(f.relative_to(MAIN)):[f.stat().st_size,f.stat().st_mtime_ns] for f in MAIN.rglob('*') if f.is_file() and '.git' not in f.relative_to(MAIN).parts}}
def integ(t,x,lo,hi):return np.tensordot(np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo)),x[:-1],axes=(0,0))
def rms(x):return np.sqrt(np.mean(x*x,axis=0))
def load(label):
 r=next(x for x in json.loads((D/'RAW_DERIVED_METRICS.json').read_text())['cases'] if x['label']==label)
 z=dict(np.load(D/'series'/f'{label}.npz')); root=Path(r['source_root']);run=root/'source/results'/r['archive_case']
 tr=np.load(run/'trace.npz');m=tr['stage']=='TASK';z.update({k:tr[k][m] for k in tr.files if len(tr[k])==len(m)})
 z['beta']=tr['task_beta'];z['weights']=tr['task_residual_weights_nm'];z['events']=json.loads((D/'events'/f'{label}.json').read_text())['events']
 z['rec']=r;z['su']=json.loads((run/'summary.json').read_text());return z
def metrics(z,lo,hi):
 t=z['t'];tf=z['tf'];m=(t>=lo-1e-8)&(t<=hi+1e-8);f=(tf>=lo-1e-8)&(tf<hi-1e-8);v=z['v'][m];a=z['a'][m];j=z['j'][m]
 qerr=np.degrees(z['q'][::20]-z['refq']);verr=np.degrees(z['v'][::20]-z['refv']);mom=np.linalg.norm(z['physical_cuff_moment_world_nm'],axis=1)
 out={'J_F':integ(tf,z['f'],lo,hi),'mean_F':integ(tf,z['f'],lo,hi)/(hi-lo),'peak_F':z['f'][f].max(),'TV_v':np.linalg.norm(np.diff(v,axis=0),axis=1).sum(),'TV_v_joint':abs(np.diff(v,axis=0)).sum(axis=0),'TV_refv':np.linalg.norm(np.diff(z['refv'][f],axis=0),axis=1).sum(),'TV_verr':np.linalg.norm(np.diff(z['verr'][f],axis=0),axis=1).sum(),'TV_a':np.linalg.norm(np.diff(a,axis=0),axis=1).sum(),'a_RMS':rms(a),'jerk_RMS':rms(j),'combined_jerk_RMS':np.sqrt(np.mean(np.sum(j*j,axis=1))),'q_mean_deg':np.degrees(z['q'][m]).mean(axis=0),'hip_minus_knee_mean_deg':np.degrees(z['q'][m,0]-z['q'][m,1]).mean(),'q_tracking_RMS_deg':rms(qerr[f]),'v_tracking_RMS_deg_s':rms(verr[f]),'moment_J':integ(tf,mom,lo,hi),'force_vector_mean':z['physical_cuff_force_world_n'][f].mean(axis=0),'allocated_wrench_mean':z['allocated_wrench_world'][f].mean(axis=0),'allocated_force_mean_norm':np.linalg.norm(z['allocated_wrench_world'][f,:3],axis=1).mean(),'allocated_moment_mean_norm':np.linalg.norm(z['allocated_wrench_world'][f,3:],axis=1).mean(),'generalized_action_mean':z['applied_generalized_action_nm'][f].mean(axis=0),'robot_torque_RMS':rms(z['torque'][f]),'components_RMS':{k:rms(z['robot_torque_component_'+k+'_nm'][f]) for k in ['base','position','velocity','allocator','clipping']}}
 # Oscillatory residual: descriptive finite-band diagnostic, not clinical smoothness.
 out['velocity_residual_RMS_deg_s']={str(w):rms(np.degrees(z['v']-savgol_filter(z['v'],int(round(w/.00025))//2*2+1,3,axis=0))[m]) for w in [.25,.5,1.]}
 out['events']=[e for e in z['events'] if lo<=e['task_s']<=hi and e['kind'] in ['request','activation','splice']]
 return out
def save(fig,name):
 fig.savefig(P/'figures'/f'{name}.png',dpi=170);fig.savefig(P/'figures'/f'{name}.svg');plt.close(fig)
def annotate(axs,bounds,window=None):
 for ax in axs:
  for x in bounds[1:-1]:ax.axvline(x,color='.4',lw=.8)
  for lo,hi in [(4,6),(15,16)]:ax.axvspan(lo,hi,color='#2ca25f',alpha=.09)
  for lo,hi in [(1,2.5),(15,15.5)]:ax.axvspan(lo,hi,color='#d95f02',alpha=.07)
  ax.grid(alpha=.18)
  if window:ax.set_xlim(*window)
def main():
 assert not P.exists(),'New version must not overwrite existing work'
 for d in ['audit','control','figures','derived','series','logs','reports','output','tmp']:(P/d).mkdir(parents=True,exist_ok=True)
 for f in (LOCAL/'control').glob('*.py'):shutil.copy2(f,P/'control'/f.name)
 put('audit/PROTECTION_BEFORE.json',snapshot())
 files={}
 oldman=json.loads((D/'SOURCE_MANIFEST.json').read_text())['files']
 for label in ['B0','18D']:
  r=next(x for x in json.loads((D/'RAW_DERIVED_METRICS.json').read_text())['cases'] if x['label']==label)
  run=Path(r['source_root'])/'source/results'/r['archive_case']
  for f in [D/'REPORT.md',D/'series'/f'{label}.npz',D/'events'/f'{label}.json',run/'trace.npz',run/'summary.json',run/'runtime_artifacts.json.gz',run/'config_snapshot.json',Path(r['source_root'])/'reports'/(r['archive_case']+'_MEASURED.json')]:
   h=sha(f);files[str(f)]={'size':f.stat().st_size,'sha256':h}
   if str(f) in oldman:assert h==oldman[str(f)]['sha256']
 put('audit/ARCHIVE_INPUTS.json',files)
 B=load('B0');E=load('18D');bounds=B['rec']['task_bounds_s'];assert np.allclose(B['tf'],E['tf'],atol=1e-8,rtol=0)
 windows=[(0,bounds[-1]),(0,9.005),(9.005,10.025),(10.025,bounds[-1]),(4,6),(4,4.5),(4.5,5),(5,5.5),(5.5,6),(15,16),(15,15.5),(15.5,16),(1,2.5)]
 out={f'{lo:g}-{hi:g}':{'B':metrics(B,lo,hi),'18D':metrics(E,lo,hi)} for lo,hi in windows}
 put('derived/MECHANISM_WINDOWS.json',out)
 diff={}
 for lo,hi in [(4,6),(15,16),(0,bounds[-1])]:
  f=(B['tf']>=lo)&(B['tf']<hi)
  diff[f'{lo}-{hi}']={k:{'max_norm':np.max(np.linalg.norm(E[k][f]-B[k][f],axis=1)),'rms_norm':np.sqrt(np.mean(np.sum((E[k][f]-B[k][f])**2,axis=1)))} for k in ['allocated_wrench_world','cr12_actuator_command_nm','physical_cuff_force_world_n',*[f'robot_torque_component_{n}_nm' for n in ['base','position','velocity','allocator','clipping']]]}
 put('derived/PAIRED_COMPONENT_CHANGES.json',diff)
 for label,z in [('B',B),('18D',E)]:
  err=sum(z['robot_torque_component_'+k+'_nm'][:-1] for k in ['base','position','velocity','allocator','clipping'])-z['torque'][:-1]
  assert np.max(abs(err))<1e-9
  np.savez_compressed(P/'series'/f'{label}.npz',**{k:v for k,v in z.items() if isinstance(v,np.ndarray)})
 fig,axs=plt.subplots(9,1,figsize=(17,21),sharex=True,layout='constrained')
 cols=['#2166ac','#b2182b']
 for z,col,lab in [(B,cols[0],'B'),(E,cols[1],'18D')]:
  axs[0].plot(z['tf'],z['f'],c=col,label=lab);axs[1].plot(z['tf'],z['cf'],c=col)
  for i in [0,1]:
   axs[3+i].plot(z['t'],np.degrees(z['v'][:,i]),c=col,label=lab+' actual');axs[3+i].plot(z['tf'],np.degrees(z['refv'][:,i]),c=col,ls='--',alpha=.65,label=lab+' reference')
  axs[5].plot(z['t'][::10],np.linalg.norm(z['a'][::10],axis=1),c=col)
  axs[6].plot(z['t'][::10],np.linalg.norm(z['j'][::10],axis=1),c=col)
  axs[7].plot(z['tf'],np.linalg.norm(z['q'][::20]-z['refq'],axis=1)*180/np.pi,c=col)
  for k,mark in [('request','|'),('activation','o'),('splice','x')]:
   ev=[e['task_s'] for e in z['events'] if e['kind']==k];axs[8].scatter(ev,np.full(len(ev),0 if lab=='B' else 1),marker=mark,s=45,c=col,label=lab+' '+k)
 gain=B['f']-E['f'];axs[2].plot(B['tf'],gain,color='#238b45',label='B minus 18D instantaneous force');ax2=axs[2].twinx();ax2.plot(B['tf'],B['cf']-E['cf'],color='#762a83',ls='--',label='accumulated benefit');ax2.set_ylabel('B − 18D J_F [N s]');axs[2].axhline(0,color='.4',lw=.6)
 for ax,y in zip(axs,['Force [N]','Cumulative J_F [N s]','B − 18D F [N]','Hip velocity [deg/s]','Knee velocity [deg/s]','||acceleration|| [rad/s²]','||raw jerk|| [rad/s³]','||q tracking error|| [deg]','Lifecycle events']):ax.set_ylabel(y)
 annotate(axs,bounds,(0,bounds[-1]));axs[0].legend(loc='upper right');axs[3].legend(ncol=4,fontsize=8);axs[8].legend(ncol=6,fontsize=8);axs[8].set_yticks([0,1],['B','18D']);axs[-1].set_xlabel('Task elapsed time [s]')
 top=axs[0].secondary_xaxis('top',functions=(lambda x:x+10.05,lambda x:x-10.05));top.set_xlabel('Absolute physics time [s]')
 for lo,hi,name in zip(bounds,bounds[1:],['OUTBOUND','HOLD','RETURN']):axs[0].text((lo+hi)/2,1.06,name,transform=axs[0].get_xaxis_transform(),ha='center',fontsize=9)
 fig.suptitle('B vs frozen 18D | common task / absolute time | force is the slope of cumulative J_F\nGreen: main benefit windows; orange: B high-load intervals; raw derivatives retain native rate',fontsize=13);save(fig,'01_core_common_timeline')
 for lo,hi,tag in [(3.7,6.2,'02_outbound_mechanism'),(14.7,16.3,'03_return_mechanism')]:
  fig,axs=plt.subplots(10,2,figsize=(19,23),sharex=True,layout='constrained')
  for z,col,lab in [(B,cols[0],'B'),(E,cols[1],'18D')]:
   for c in [0,1]:
    axs[0,c].plot(z['tf'],z['f'] if c==0 else z['cf']-np.interp(lo,z['tf'],z['cf']),c=col,label=lab)
    axs[1,c].plot(z['t'],np.degrees(z['q'][:,c]),c=col);axs[1,c].plot(z['tf'],np.degrees(z['refq'][:,c]),c=col,ls='--',alpha=.6)
    axs[2,c].plot(z['t'],np.degrees(z['v'][:,c]),c=col);axs[2,c].plot(z['tf'],np.degrees(z['refv'][:,c]),c=col,ls='--',alpha=.6)
    axs[3,c].plot(z['t'],np.degrees(z['a'][:,c]),c=col);axs[4,c].plot(z['t'][::4],z['j'][::4,c],c=col)
    axs[5,c].plot(z['tf'],np.degrees(z['q'][::20,c]-z['refq'][:,c]),c=col)
    axs[6,c].plot(z['tf'],np.linalg.norm(z['allocated_wrench_world'][:,:3] if c==0 else z['allocated_wrench_world'][:,3:],axis=1),c=col)
    axs[7,c].plot(z['tf'],np.linalg.norm(z['robot_torque_component_'+('allocator' if c==0 else 'velocity')+'_nm'],axis=1),c=col)
    axs[8,c].plot(z['tf'],np.linalg.norm(z['physical_cuff_moment_world_nm'] if c else z['torque'],axis=1),c=col)
    for k,mark in [('request','|'),('activation','o'),('splice','x')]:
     ev=[e['task_s'] for e in z['events'] if e['kind']==k];axs[9,c].scatter(ev,np.full(len(ev),0 if lab=='B' else 1),marker=mark,c=col,label=lab+' '+k,s=40)
  labels=[['Instantaneous F [N]','Local cumulative J_F [N s]'],['Hip q [deg]','Knee q [deg]'],['Hip velocity [deg/s]','Knee velocity [deg/s]'],['Hip acceleration [deg/s²]','Knee acceleration [deg/s²]'],['Hip raw jerk [rad/s³]','Knee raw jerk [rad/s³]'],['Hip tracking [deg]','Knee tracking [deg]'],['Allocated force norm [N]','Allocated moment norm [Nm]'],['Allocator torque norm [Nm]','Velocity feedback torque norm [Nm]'],['Robot command norm [Nm]','Measured cuff moment norm [Nm]'],['Lifecycle','Lifecycle']]
  for row in range(10):
   for c in [0,1]:axs[row,c].set_ylabel(labels[row][c]);annotate([axs[row,c]],bounds,(lo,hi))
  axs[0,0].legend();axs[9,0].legend(ncol=3,fontsize=8);axs[-1,0].set_xlabel('Task elapsed [s]');axs[-1,1].set_xlabel('Task elapsed [s]')
  for c in [0,1]:axs[0,c].secondary_xaxis('top',functions=(lambda x:x+10.05,lambda x:x-10.05)).set_xlabel('Absolute physics [s]')
  fig.suptitle('B / 18D local mechanism | solid actual, dashed issued reference | paired colors across rows');save(fig,tag)
 print('ARCHIVE_ANALYSIS_COMPLETE',P)
 for k in ['4-6','15-16','15-15.5','15.5-16']:
  print(k,{n:{f:clean(out[k][n][f]) for f in ['J_F','TV_v','TV_refv','TV_a','combined_jerk_RMS','q_mean_deg','q_tracking_RMS_deg','v_tracking_RMS_deg_s','moment_J','allocated_force_mean_norm','allocated_moment_mean_norm']} for n in ['B','18D']})
if __name__=='__main__':main()
