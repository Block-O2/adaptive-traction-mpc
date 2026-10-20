"""Static native acceleration comparison from completed validated raw."""
from pathlib import Path
import os,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
L=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/L.name;(P/'figures').mkdir(exist_ok=True)
audit=json.loads((P/'audit/EXPANDED_EXECUTION_TIME_AUDIT.json').read_text());fig,axs=plt.subplots(2,2,figsize=(13,7.5),layout='constrained');colors={'B':'#666666','E':'#c34242','T':'#177952'}
for row,g in enumerate(['V1','V2']):
 b=json.loads((P/'reports'/(g+'_B_MEASURED.json')).read_text());limit=b['motion']['raw']['full']['acceleration_deg_s2']['max_abs'][1]*1.1
 for a in ['B','E','T']:
  z=np.load(P/'motion_series'/(g+'_'+a+'.npz'));nt=z['time_s']-z['time_s'][0];acc=np.rad2deg(z['acceleration_rad_s2'][:,1]);peak=int(np.argmax(abs(acc)));color=colors[a]
  axs[row,0].plot(nt[::4],acc[::4],color=color,lw=.75,label=a+' actual');axs[row,0].scatter([nt[peak]],[acc[peak]],s=16,color=color,zorder=4)
  axs[row,1].plot(nt,acc,color=color,lw=1.,label=a+' actual')
  f=P/'source/results'/(g+'_'+a);r=np.load(f/'native_reference.npz')['data'];axs[row,1].plot(r[:,0],np.rad2deg(r[:,6]),'--',color=color,lw=.9,label=a+' issued')
 for col in [0,1]:
  ax=axs[row,col];ax.axhline(limit,color='#222222',lw=.75,ls=':');ax.axhline(-limit,color='#222222',lw=.75,ls=':');ax.grid(alpha=.18);ax.set_xlabel('Task clock (s)');ax.set_ylabel(g+' knee acceleration (deg/s²)')
 axs[row,0].set_xlim(0,19.03);axs[row,0].legend(ncol=3,fontsize=8,loc='upper right');axs[row,1].set_xlim(6.65,7.55);axs[row,1].legend(ncol=3,fontsize=8,loc='upper right')
 for a,ls in [('E','--'),('T','-')]:
  ev=next(x for x in audit['new_rows'] if x['id']==g+'_'+a);axs[row,1].axvline(ev['suffix_end_task_s'],color=colors[a],ls=ls,lw=.9);axs[row,1].text(ev['suffix_end_task_s']+.005,-145 if a=='E' else -125,a+' suffix end',color=colors[a],fontsize=8)
 axs[row,1].set_ylim(-170,90)
axs[0,0].set_title('Full task: native response; dots mark exact absolute peaks');axs[0,1].set_title('Terminal segment: issued reference and actual native response');fig.suptitle('Frozen T=1.5 | Two new lawful prefixes | B / frozen 18D (E) / T\nDotted horizontal lines: each condition\'s original ±1.10 × B full-task maximum',fontsize=12)
f=P/'figures/expanded_native_motion.png';fig.savefig(f,dpi=160);plt.close(fig)
print(f,flush=True)
