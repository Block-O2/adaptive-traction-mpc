from pathlib import Path
import json,sys,os
os.environ['MPLBACKEND']='Agg'
import numpy as np
import matplotlib.pyplot as plt
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1')
load=lambda p:json.loads(Path(p).read_text())
rows=load(S/'FREE_TRAJECTORY_SEARCH_RESULTS.json')['rows'];sel=load(S/'FROZEN_SELECTION.json');best=sel['best'];strong=sel['diagnostic'];base=best['base_id']
(S/'figures').mkdir(exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.25,'figure.dpi':160})
fig,ax=plt.subplots(figsize=(8.6,5.2))
for passed,color,label in [(False,'#cc653d','Motion / compensation FAIL'),(True,'#187e68','All frozen gates PASS')]:
    subset=[r for r in rows if r['comparison']['acceptance_pass']==passed]
    ax.scatter([r['comparison']['gain_percent'] for r in subset],[r['constraints']['worst_ratio'] for r in subset],c=color,s=28,label=label,alpha=.8)
ax.axhline(1,color='#333',ls='--',lw=1);ax.axvline(2,color='#557',ls=':',lw=1);ax.axvline(5,color='#557',ls=':',lw=1)
ax.scatter([best['comparison']['gain_percent']],[best['constraints']['worst_ratio']],marker='*',s=160,c='#172b4d',label='Frozen best')
ax.set(xlabel='Full TASK cuff-force reduction vs matched B (%)',ylabel='Worst normalized frozen requirement (<=1 passes)',title='Forward dynamics search: force and actual motion')
ax.legend(loc='best');fig.tight_layout();fig.savefig(S/'figures/FORCE_MOTION_SEARCH.png');fig.savefig(S/'figures/FORCE_MOTION_SEARCH.svg');plt.close(fig)
ids=list(dict.fromkeys([base,best['id'],strong['id']]))
colors=['#536079','#087f8c','#bc603e'];labels=['Matched B','Frozen best','Low-force diagnostic']
fig,axs=plt.subplots(3,2,figsize=(12,10))
for ident,color,label in zip(ids,colors,labels):
    with np.load(S/'source/results'/ident/'trace.npz') as z:
        mask=z['stage']=='TASK';t=z['time_s'][mask];f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);jf=np.r_[0,np.cumsum(f[:-1]*np.diff(t))]
        t-=t[0];axs[0,0].plot(t,f,color=color,label=label,lw=1);axs[0,1].plot(t,jf,color=color,label=label,lw=1.3)
    with np.load(S/'motion_series'/(ident+'.npz')) as z:
        # Native arrays drive acceptance. Stride only reduces exported figure size.
        t=z['time_s']-z['time_s'][0];ix=np.r_[np.arange(0,len(t),20),len(t)-1]
        q=np.rad2deg(z['true_q_rad']);v=np.rad2deg(z['true_dq_rad_s']);acc=np.rad2deg(z['acceleration_rad_s2'])
        for joint in [0,1]:
            axs[1,joint].plot(t[ix],q[ix,joint],color=color,label=label,lw=1)
            axs[2,joint].plot(t[ix],v[ix,joint],color=color,label=label,lw=1)
for ax,title,y in zip(axs.ravel(),['Actual cuff force','Complete-task force integral','Actual hip angle','Actual knee angle','Actual hip velocity','Actual knee velocity'],['N','N s','deg','deg','deg/s','deg/s']):
    ax.set(title=title,xlabel='Actual TASK time (s)',ylabel=y)
axs[0,0].legend();fig.suptitle('Original plant, robot actuators and contact; raw motion metrics',fontsize=13);fig.tight_layout();fig.savefig(S/'figures/PHYSICAL_TRAJECTORIES.png');plt.close(fig)
m=load(best['metrics_path']);b=load(S/'reports'/(base+'_MEASURED.json'))
names=[];ratios=[]
for signal,stats in [('velocity_deg_s',['max_abs','p95_abs','rms']),('acceleration_deg_s2',['max_abs','p95_abs','rms']),('jerk_deg_s3',['p95_abs','rms'])]:
    for stat in stats:
        names.append({'velocity_deg_s':'Velocity','acceleration_deg_s2':'Acceleration','jerk_deg_s3':'Jerk'}[signal]+' '+{'max_abs':'max','p95_abs':'p95','rms':'RMS'}[stat]);ratios.append(np.array(m['motion']['raw']['full'][signal][stat])/np.array(b['motion']['raw']['full'][signal][stat]))
ratios=np.array(ratios);fig,ax=plt.subplots(figsize=(10,5));x=np.arange(len(names));ax.bar(x-.18,ratios[:,0],width=.35,color='#067c87',label='Hip');ax.bar(x+.18,ratios[:,1],width=.35,color='#ae6e39',label='Knee');ax.axhline(1.1,color='#b24235',ls='--',label='Frozen 10% noninferiority');ax.set_xticks(x,names,rotation=22,ha='right');ax.set_ylabel('Actual native-motion statistic / matched B');ax.set_title('Frozen best: unfiltered velocity, acceleration and jerk',pad=43);ax.legend(loc='lower center',bbox_to_anchor=(.5,1.02),ncol=3,frameon=False);fig.tight_layout();fig.savefig(S/'figures/BEST_MOTION_CONSTRAINTS.png');plt.close(fig)
(S/'FIGURES.md').write_text('# 物理结果图\n\n![Force versus motion](figures/FORCE_MOTION_SEARCH.png)\n\n![Physical traces](figures/PHYSICAL_TRAJECTORIES.png)\n\n![Motion constraints](figures/BEST_MOTION_CONSTRAINTS.png)\n\n资格使用全部0.25ms原生人体样本的raw导数。图中仅为文件大小采样，不平滑验收信号。\n')
print('PLOTS_CREATED')
