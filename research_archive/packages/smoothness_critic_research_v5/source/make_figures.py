from pathlib import Path
import os,sys,json
os.environ.update(OPENBLAS_NUM_THREADS='1',MPLBACKEND='Agg',MPLCONFIGDIR='/home/hank/ihear-lab/smoothness_critic_research_v5/runtime/tmp/mpl');sys.dont_write_bytecode=True
import numpy as np
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parents[1];(P/'figures').mkdir(exist_ok=True)
pred=json.loads((P/'predictions/DEV_PREREGISTERED_PREDICTIONS.json').read_text());rows=[]
for a in pred['actions']:
 if a['tag']!='C19' and 'local_delta' not in a:continue
 f=P/'analysis/branches'/('DEV_'+a['tag']+'.json')
 if not f.exists():continue
 r=json.loads(f.read_text());rows.append((a.get('local_delta',0),r,a['prediction']))
rows.sort(key=lambda t:t[0]);x=np.array([r[0] for r in rows])*1e3;c=['#157a6e' if r[1]['qualified'] else '#c44536' for r in rows];fig,axs=plt.subplots(3,1,figsize=(10,9),sharex=True,constrained_layout=True)
axs[0].plot(x,[r[2]['predicted_curvature_spike'] for r in rows],'--',color='#59697b',label='Frozen analytic-response prediction');axs[0].scatter(x,[r[1]['minimum_curvature_event']['guard']['model_curvature_m_s2'] for r in rows],c=c,zorder=3,label='Original guard, real closed-loop input');axs[0].set_ylabel('Model curvature (m/s²)');axs[0].legend(fontsize=9)
for j,label in enumerate(['Hip','Knee']):axs[1].plot(x,[r[1]['native_motion']['jerk_deg_s3']['rms'][j] for r in rows],marker=['o','s'][j],label=label)
axs[1].set_ylabel('Unfiltered native jerk RMS (°/s³)');axs[1].legend()
axs[2].scatter(x,[r[1]['JF'] for r in rows],c=c,label='JF; green qualified, red motion fail');axs[2].set_ylabel('Full-task JF (N·s)');axs[2].ticklabel_format(axis='y',style='plain',useOffset=False);axs[2].set_xlabel('C19 x[3] perturbation × 10³');axs[2].legend(fontsize=9)
for ax in axs:ax.grid(alpha=.2)
fig.suptitle('Frozen local predictions vs unchanged-guard physical runs\nNo replacement guard was executed',fontsize=12)
for ext in ['png','svg']:fig.savefig(P/'figures'/('LOCAL_BRANCH_VALIDATION.'+ext),dpi=180)
plt.close(fig)
# Visualize the exact endpoint inequality counterexample independently of plant runs.
t=np.linspace(0,.08,801);g=2e-5-.02*t+t*t;fig,ax=plt.subplots(figsize=(8,3.8),constrained_layout=True);ax.plot(t*1000,g*1e6,label='Exact scalar constant-acceleration path');ax.axhline(10,color='#c44536',ls='--',label='Unchanged 10 µm threshold');ax.axvline(5,color='#59697b',ls=':',label='5 ms sampling');ax.set(xlabel='Time (ms)',ylabel='Gap (µm)',title='Horizon endpoint inequality alone does not certify the interval');ax.legend(fontsize=8);ax.grid(alpha=.2)
for ext in ['png','svg']:fig.savefig(P/'figures'/('HORIZON_COUNTEREXAMPLE.'+ext),dpi=180)
print('FIGURES',len(rows),'local rows; unfiltered native metrics')
