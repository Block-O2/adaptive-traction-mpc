from pathlib import Path
import os,json
r=Path(__file__).resolve().parents[1];os.environ['MPLCONFIGDIR']=str(r/'audit/mpl-cache');os.environ['MPLBACKEND']='Agg'
import numpy as np,matplotlib.pyplot as plt
x=json.loads((r/'CHECKPOINT_050_080_COMPARISON.json').read_text());a=json.loads((r/'stability/TRAINING_OPTIMIZATION_AUDIT.json').read_text());seeds=sorted({d['seed'] for d in x['policy_drift_timeline']});colors=['#4C72B0','#DD8452','#55A868']
fig,axs=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
for s,col in zip(seeds,colors):
 d=[q for q in x['policy_drift_timeline'] if q['seed']==s];ep=[q['episode'] for q in d]
 for j,ax in enumerate(axs[0]):ax.plot(ep,[q['mean_on_common_obs'][j] for q in d],color=col,marker='o',ms=3,label=str(s));ax.set(title=['Hip raw mean on fixed causal observations','Knee raw mean on fixed causal observations'][j],xlabel='Training episodes',ylabel='Gaussian mean (action units)');ax.axvspan(50,80,alpha=.05,color='black');ax.grid(alpha=.2)
 q=[q for q in a['episodes'] if q['seed']==s];epochs=[q['episode'] for q in q];succ=[q['success'] for q in q];roll=np.convolve(succ,np.ones(10)/10,mode='valid');axs[1,0].plot(range(10,81),roll,color=col,label=str(s));axs[1,1].plot(epochs,[max(q['losses']['train/approx_kl'],1e-8) for q in q],color=col,alpha=.75,label=str(s))
axs[1,0].set(title='Observed stochastic training completion (10 episodes)',xlabel='Training episodes',ylabel='Completion fraction',ylim=(-.02,1.02));axs[1,1].set(title='Recorded SB3 approximate KL (last epoch only)',xlabel='Training episodes',ylabel='Approximate KL',yscale='log')
for ax in axs.flat:ax.legend(fontsize=7);ax.grid(alpha=.2)
fig.suptitle('Existing 240 episodes / 51 checkpoints; no reconstructed training updates',fontsize=12);fig.savefig(r/'stability/PPO_STABILITY.png',dpi=180);fig.savefig(r/'stability/PPO_STABILITY.pdf');plt.close(fig)
fig,axs=plt.subplots(2,2,figsize=(10,6),constrained_layout=True)
for i,s in enumerate([1495656323,1630784693]):
 for ck,col in [('checkpoint050_first','#4C72B0'),('checkpoint080_first','#C44E52')]:
  p=r/'stability'/f'seed{s}_{ck}_APPLIED_SERIES.npz';z=np.load(p);t=z['trace_t']-10.05
  for j in [0,1]:axs[i,j].plot(t,np.degrees(z['trace_truth'][:,j]),label=ck.replace('_first',''),color=col,lw=1.4)
 for j in [0,1]:axs[i,j].set(title=f'Seed {s}: '+['hip','knee'][j],xlabel='TASK seconds',ylabel='Actual human angle (deg)');axs[i,j].axvline(10.025,ls=':',color='gray',lw=.8);axs[i,j].grid(alpha=.2);axs[i,j].legend(fontsize=8)
fig.suptitle('Saved deterministic native boundary motion: complete 050 vs partial 080');fig.savefig(r/'stability/RETURN_REGRESSION.png',dpi=180);fig.savefig(r/'stability/RETURN_REGRESSION.pdf')
