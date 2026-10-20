from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1');F=S/'figures';F.mkdir(exist_ok=True)
sel=json.loads((S/'FROZEN_SELECTION.json').read_text());rows=[json.loads(l) for l in (S/'EVALUATIONS.jsonl').read_text().splitlines()];best=sel['discovery_results'][0];brow=next(r for r in rows if r['id']==best)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':160})
colors={'baseline_B0_repeat_1':'#65758a','baseline_NATIVE_SCALAR_18':'#dc9943',best:'#147b83'}
fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
labels={'baseline_B0_repeat_1':'B0','baseline_NATIVE_SCALAR_18':'NATIVE_SCALAR_18',best:'Best known'}
task0=0.
for ident in dict.fromkeys(['baseline_B0_repeat_1','baseline_NATIVE_SCALAR_18',best]):
 with np.load(S/'source/results'/ident/'trace.npz') as z:
  j=z['stage']=='TASK';t=z['time_s'][j];force=np.linalg.norm(z['physical_cuff_force_world_n'][j],axis=1);cum=np.r_[0,np.cumsum(force[:-1]*np.diff(t))];task0=t[0];axes[0,0].plot(t-task0,cum,label=labels[ident],color=colors[ident],lw=1.6)
 with np.load(S/'motion_series'/(ident+'.npz')) as z:
  t=z['time_s']-task0;q=np.rad2deg(z['true_q_rad']);stride=20
  axes[0,1].plot(t[::stride],q[::stride,0],label=labels[ident],color=colors[ident],lw=1.4)
  axes[1,0].plot(t[::stride],q[::stride,1],label=labels[ident],color=colors[ident],lw=1.4)
for r in brow['actual_execution']:
 if not r['physically_executed_nonzero']:continue
 delta=r['native_coordination_metadata'][0]['delta'];t=r['first_execution_physics_s']-task0;axes[1,1].vlines(t,0,delta,color='#147b83' if r['phase']=='OUTBOUND' else '#dc9943');axes[1,1].scatter([t],[delta],s=38,color='#147b83' if r['phase']=='OUTBOUND' else '#dc9943');axes[1,1].annotate(r['phase'],(t,delta),xytext=(3,5),textcoords='offset points',fontsize=8)
titles=['Accumulated cuff force','Actual hip motion','Actual knee motion','Physically executed native coordination'];units=['J_F (N s)','Hip angle (deg)','Knee angle (deg)','Accepted delta (progress)']
for ax,title,unit in zip(axes.flat,titles,units):ax.set(title=title,xlabel='Task time (s)',ylabel=unit);ax.grid(alpha=.15)
axes[0,0].legend(loc='upper left');axes[1,1].axhline(0,color='#65758a',lw=.8)
fig.suptitle(f"Full task, unchanged motion gates | best known gain {brow['comparison']['gain_percent']:.3f}%",fontsize=14);fig.savefig(F/'FULL_TASK_COORDINATION.png');plt.close(fig)
fig,ax=plt.subplots(figsize=(9,5),constrained_layout=True)
for r in rows:
 if r['id'].startswith(('V','verify')):continue
 passed=r['comparison']['acceptance_pass'];ax.scatter(r['continuous_constraints']['worst_ratio'],r['comparison']['gain_percent'],color='#147b83' if passed else '#ce6e61',s=32 if passed else 20,alpha=.7)
ax.axvline(1,color='#65758a',ls='--',lw=1);ax.axhline(2,color='#dc9943',ls=':',lw=1);ax.axhline(5,color='#dc9943',ls=':',lw=1);ax.scatter([brow['continuous_constraints']['worst_ratio']],[brow['comparison']['gain_percent']],marker='*',s=190,color='#17383e');ax.set(xlabel='Worst normalized research constraint (pass <= 1)',ylabel='Full-task force reduction (%)',title='Feasible motion and strong low-force tradeoff');ax.grid(alpha=.15);fig.savefig(F/'FORCE_MOTION_FRONTIER.png');plt.close(fig)
print(str(F))
