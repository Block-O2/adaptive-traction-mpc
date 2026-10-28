from pathlib import Path
import os,json
os.environ.update(OPENBLAS_NUM_THREADS='1',MPLBACKEND='Agg',MPLCONFIGDIR='/tmp/ihear_v5_mpl')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');fig,ax=plt.subplots(3,2,figsize=(13,10),constrained_layout=True)
labels=[('CORE01_BEST','Strong fixed','#20252c'),('SMOOTH01_REF_MINJ_0p25','Reference min-jerk (motion FAIL)','#bb7744'),('SMOOTH01_PASS_SLOW','Bounded slow passing (motion PASS)','#147d92')]
for ident,label,color in labels:
 with np.load(P/'runtime/source/results'/ident/'trace.npz') as z:
  use=z['stage']=='TASK';t=z['time_s'][use];t=t-t[0];f=np.linalg.norm(z['physical_cuff_force_world_n'][use],axis=1);ref=np.degrees(z['reference_dq_rad_s'][use]);ax[0,0].plot(t,ref[:,0],label=label,color=color,lw=.9);ax[2,0].plot(t,f,label=label,color=color,lw=.9)
 with np.load(P/'runtime/motion_series'/(ident+'.npz')) as z:
  t=z['time_s'];t=t-t[0];j=np.degrees(z['jerk_rad_s3']);window=(t>=3.09)&(t<=3.2)
  ax[0,1].plot(t[window],j[window,0],label=label,color=color,lw=.8);ax[1,0].plot(t,j[:,0],label=label,color=color,lw=.6);ax[1,1].plot(t,j[:,1],label=label,color=color,lw=.6)
 d=json.loads((P/'analysis/extended'/(ident+'.json')).read_text());ax[2,1].scatter(d['JF'],np.linalg.norm(d['native_motion']['jerk_deg_s3']['rms']),color=color,s=65,label=label)
ax[0,0].set_ylabel('Issued hip reference velocity (deg/s)');ax[0,1].set_ylabel('Native hip jerk (deg/s^3)');ax[0,1].set_title('Fixed actual-time handoff window; no peak alignment')
ax[1,0].set_ylabel('Native hip jerk (deg/s^3)');ax[1,1].set_ylabel('Native knee jerk (deg/s^3)');ax[2,0].set_ylabel('Measured cuff force norm (N), 200 Hz');ax[2,1].set_ylabel('Combined native jerk RMS (deg/s^3)');ax[2,1].set_xlabel('Full original JF (N s); failed motion never ranked')
for a in ax.ravel():a.grid(alpha=.2)
for a in [ax[0,0],ax[0,1],ax[1,0],ax[1,1],ax[2,0]]:a.set_xlabel('Task physical time (s)')
ax[0,0].legend(fontsize=8);ax[2,1].legend(fontsize=8);fig.suptitle('Reference smoothness, actual Human jerk and force burden are separate outcomes',fontsize=14)
fig.savefig(P/'figures/01_INITIAL_REAL_SMOOTHNESS.png',dpi=180);plt.close(fig)
print('FIGURE_SAVED')
