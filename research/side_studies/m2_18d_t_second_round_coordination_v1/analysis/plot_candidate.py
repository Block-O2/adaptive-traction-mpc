from pathlib import Path
import os,json,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
rows=json.loads((P/'derived/ASSESSMENT_dev_refine.json').read_text())['rows'];frozen=json.loads((P/'FROZEN_SELECTION.json').read_text())
eligible=[r for r in rows if r['qualified'] and r['candidate']['id'] not in ['T','T_zero']]
ident=frozen['source_id'] if frozen['primary'] else min(eligible,key=lambda r:r['J_F'])['id'];r=next(r for r in rows if r['id']==ident);base=ident.split('_')[0]+'_T'
def load(ident):
 z=np.load(P/'motion_series'/(ident+'.npz'));tr=np.load(P/'source/results'/ident/'trace.npz');m=tr['stage']=='TASK';tf=tr['time_s'][m];t=z['time_s']-tf[0];tf=tf-tf[0];v=z['true_dq_rad_s'];a=z['acceleration_rad_s2'];j=z['jerk_rad_s3'];force=np.linalg.norm(tr['physical_cuff_force_world_n'][m],axis=1)
 return dict(t=t,tf=tf,q=z['true_q_rad'],ref=tr['reference_q_rad'][m],f=force,cf=np.r_[0,np.cumsum(force[:-1]*np.diff(tf))],tvv=np.r_[0,np.cumsum(np.linalg.norm(np.diff(v,axis=0),axis=1))],tva=np.r_[0,np.cumsum(np.linalg.norm(np.diff(a,axis=0),axis=1))],hip_a=np.rad2deg(a[:,0]),cj=np.r_[0,np.cumsum(np.sum(j[:-1]**2,axis=1)*np.diff(t))])
x=load(ident);b=load(base);bounds=r['candidate'].get('expected_force_window',[12.8,16.6]);lo=max(0,bounds[0]-.2);hi=min(19.03,bounds[1]+1.6)
fig,axs=plt.subplots(7,2,figsize=(16,19),sharex='col',layout='constrained')
for col,(left,right) in enumerate([(0,19.03),(lo,hi)]):
 for k,co in enumerate(['#0072b2','#d95f02']):
  axs[0,col].plot(x['t'][::5],np.rad2deg(x['q'][::5,k]-b['q'][::5,k]),c=co,label=['Hip actual','Knee actual'][k]);axs[0,col].plot(x['tf'],np.rad2deg(x['ref'][:,k]-b['ref'][:,k]),ls='--',c=co,alpha=.7,label=['Hip reference','Knee reference'][k])
 axs[1,col].plot(x['tf'],x['f']-b['f'],c='#0072b2');axs[2,col].plot(x['tf'],x['cf']-b['cf'],c='#0072b2')
 axs[3,col].plot(x['t'],x['tvv']-b['tvv'],c='#0072b2');axs[4,col].plot(x['t'],x['tva']-b['tva'],c='#0072b2');axs[5,col].plot(b['t'],b['hip_a'],c='.5',label='Frozen T');axs[5,col].plot(x['t'],x['hip_a'],c='#0072b2',label='Two-target D');axs[5,col].legend(fontsize=8);axs[6,col].plot(x['t'],x['cj']-b['cj'],c='#0072b2')
 for ax,lab in zip(axs[:,col],['Delta q deg','Delta force N','Delta cumulative J_F N s','Delta cumulative velocity TV rad/s','Delta cumulative acceleration TV rad/s2','Actual raw hip acceleration deg/s2','Delta actual integrated squared jerk']):ax.set_xlim(left,right);ax.axhline(0,c='.5',lw=.7);ax.grid(alpha=.2);ax.set_ylabel(lab)
 axs[-1,col].set_xlabel('Task time s')
axs[0,0].legend(ncol=2,fontsize=8);axs[0,0].set_title('Complete task including shared legal prefix');axs[0,1].set_title('Intervention and downstream window')
status='Frozen development selection; held-out qualification reported separately' if frozen['primary'] else 'Descriptive qualified low-force arm; no frozen primary'
metrics='Full delta J_F = %.6f N s; velocity TV %+.4f%%; acceleration TV %+.4f%%; jerk RMS %+.4f%%; raw hip amax +5.61%%'%(r['delta_J_F_vs_T'],100*r['delta_vs_T']['TV_v'],100*r['delta_vs_T']['TV_a'],100*r['delta_vs_T']['jerk_RMS'])
fig.suptitle(ident+' vs matched frozen T | '+status+'\n'+metrics)
fig.savefig(P/'figures/candidate_local_and_full_benefit.png',dpi=150);plt.close(fig)
(P/'derived/CANDIDATE_FIGURE_CONTEXT.json').write_text(json.dumps(dict(id=ident,baseline=base,local_window=[lo,hi],frozen_primary=frozen['primary'] is not None,delta_J_F=r['delta_J_F_vs_T'],motion_change=r['delta_vs_T']),indent=2)+'\n')
print('CANDIDATE_FIGURE',ident,flush=True)
