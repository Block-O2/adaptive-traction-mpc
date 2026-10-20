from pathlib import Path
import os,json
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg',MPLCONFIGDIR=str(P/'tmp/mpl'))
import numpy as np
import matplotlib.pyplot as plt
def read(n):return json.loads((P/n).read_text())
bm=read('reports/W1_B_MEASURED.json');diag=read('audit/VALIDATION_BASELINE_FAILURE_DIAGNOSIS.json');limitv=bm['motion']['raw']['full']['velocity_deg_s']['p95_abs'][1]*1.1;limita=bm['motion']['raw']['full']['acceleration_deg_s2']['p95_abs'][1]*1.1
Z={}
for name in ['B','E','T']:
 ident='W1_'+name;z=np.load(P/'motion_series'/(ident+'.npz'));tr=np.load(P/'source/results'/ident/'trace.npz');m=tr['stage']=='TASK';origin=tr['time_s'][m][0];t=z['time_s']-origin;tf=tr['time_s'][m]-origin;force=np.linalg.norm(tr['physical_cuff_force_world_n'][m],axis=1)
 q=np.rad2deg(z['true_q_rad']);Z[name]=dict(t=t,tf=tf,f=force,cf=np.r_[0,np.cumsum(force[:-1]*np.diff(tf))],v=np.abs(np.rad2deg(z['true_dq_rad_s'][:,1])),a=np.abs(np.rad2deg(z['acceleration_rad_s2'][:,1])),exc=np.maximum.accumulate(q,axis=0)-np.minimum.accumulate(q,axis=0))
fig,axs=plt.subplots(6,1,figsize=(14,17),sharex=True,layout='constrained')
for name,co in [('B','#666666'),('E','#d95f02'),('T','#0072b2')]:
 z=Z[name];axs[0].plot(z['tf'],z['f'],c=co,label=name);axs[1].plot(z['tf'],z['cf']-Z['B']['cf'],c=co);axs[2].plot(z['t'],z['v'],c=co);axs[3].plot(z['t'],z['a'],c=co)
 axs[4].plot(z['t'],np.cumsum(z['v']>limitv),c=co,label=name+' velocity');axs[4].plot(z['t'],np.cumsum(z['a']>limita),c=co,ls='--',label=name+' acceleration')
for j,co in enumerate(['#0072b2','#d95f02']):axs[5].plot(Z['T']['t'],Z['T']['exc'][:,j]-Z['B']['exc'][:,j],c=co,label=['Hip','Knee'][j])
axs[2].axhline(limitv,c='#d73027',ls=':',label='Original full-B p95 x 1.10');axs[3].axhline(limita,c='#d73027',ls=':')
axs[4].axhline(.05*len(Z['T']['t']),c='#d73027',ls=':',label='5% of full task samples');axs[5].axhline(.5,c='#d73027',ls=':',label='Tolerance at task end only');axs[5].axhline(-.5,c='#d73027',ls=':')
cut=diag['first_planned_D_request_task_s']
for ax,label in zip(axs,['Force N','Cumulative delta J_F vs B, N s','Absolute knee velocity deg/s','Absolute knee acceleration deg/s2','Cumulative samples over full-B limits','T minus B cumulative excursion deg']):
 ax.set_ylabel(label);ax.grid(alpha=.2);ax.axvline(cut,c='#6a3d9a',ls='--',lw=.8);ax.set_xlim(0,19.03)
 for boundary in [9.005,10.025]:ax.axvline(boundary,c='.6',lw=.6)
axs[0].legend(ncol=3);axs[2].legend(loc='upper left');axs[4].legend(ncol=4,fontsize=8);axs[5].legend();axs[-1].set_xlabel('Task time s | purple line: first planned D decision, D NOT executed')
fig.suptitle('W1 frozen baseline domain failure | force gain retained, original motion gate FAIL\nFull task/safety/causal PASS; no D result and no W2 physics')
fig.savefig(P/'figures/W1_motion_failure_timeline.png',dpi=150);plt.close(fig)
print('W1_FAILURE_FIGURE_SAVED',flush=True)
