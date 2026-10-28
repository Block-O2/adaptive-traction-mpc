from pathlib import Path
import os,sys,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg');sys.dont_write_bytecode=True
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');e=json.loads((P/'analysis/extended/BRANCH02_C19.json').read_text());center=e['guard']['crossing_records'][0]['time_s'];fig,ax=plt.subplots(3,1,figsize=(10,8),sharex=True)
for tag,label,color in [('C19','Original C19 (motion FAIL)','#b14242'),('ANTC19','Branch selector (= blind negative shift)','#225c8b'),('BLINDPC19','Blind positive shift','#218576')]:
 ident='BRANCH02_'+tag
 with np.load(P/'runtime/motion_series'/(ident+'_NATIVE_WRENCH.npz')) as z:
  t=(z['time_s']-center)*1000;k=abs(t)<=60;ax[0].plot(t[k],np.linalg.norm(z['force_world_n'][k],axis=1),label=label,color=color);ax[1].plot(t[k],np.linalg.norm(z['moment_world_nm'][k],axis=1),color=color)
 with np.load(P/'runtime/motion_series'/(ident+'.npz')) as z:
  t=(z['time_s']-center)*1000;k=abs(t)<=60;ax[2].plot(t[k],np.degrees(z['jerk_rad_s3'][k,0]),color=color)
for a in ax:a.grid(alpha=.2);a.axvline(0,color='#777',lw=.8,ls=':')
ax[0].legend(fontsize=8);ax[0].set_ylabel('Actual cuff force norm (N)');ax[1].set_ylabel('Actual cuff moment norm (Nm)');ax[2].set_ylabel('Unfiltered native hip jerk (deg/s³)');ax[2].set_xlabel('Time relative to original C19 guard event (ms)')
fig.suptitle('Actual 0.25 ms simulation stream around the original guard correction\nAll curves retain their common physical clock; no filtering or per-curve peak alignment',fontsize=12);fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(P/'figures/05_BRANCH_ACTUAL_FORCE_PULSE.png',dpi=180);fig.savefig(P/'figures/05_BRANCH_ACTUAL_FORCE_PULSE.pdf');plt.close(fig);print('BRANCH_FIGURE_WRITTEN','EVENT_PHYSICAL_S',center)
