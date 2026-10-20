from pathlib import Path
import os,json,ast,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;A=P.parent/'ihear_autonomous_multitrack_v1'
def read(p):return json.loads(p.read_text())
src=(A/'analysis/historical_audit.py').read_text();tree=ast.parse(src)
exec(ast.get_source_segment(src,next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='load')))
rows=read(P/'EXPERIMENT_RESULTS.json')['rows'];by={r['id']:r for r in rows}
Z={i:load(P,i) for i in by}
colors={'B':'#555555','T':'#cc79a7','D':'#888800','ER':'#d55e00','H150':'#0072b2','KD120':'#009e73','PD':'#e69f00','FF':'#56b4e9','PDFF':'#882255'}
def save(fig,name):
 fig.savefig(P/'figures'/name,dpi=160);plt.close(fig)
def style(ax,label):ax.set_ylabel(label);ax.grid(alpha=.22)
z=Z['Dev_ER'];b=Z['Dev_B'];fig,axs=plt.subplots(3,2,figsize=(13,10),sharex=True,layout='constrained')
for joint,name in enumerate(['Hip','Knee']):
 for lab,zz in [('B',b),('ER',z)]:
  wn=(zz['t']>=15.8)&(zz['t']<=18.3);wf=(zz['tf']>=15.8)&(zz['tf']<=18.3)
  axs[0,joint].plot(zz['t'][wn],zz['q'][wn,joint],c=colors[lab],label=lab+' actual')
  axs[0,joint].plot(zz['tf'][wf],zz['rq'][wf,joint],c=colors[lab],ls='--',label=lab+' reference')
  axs[1,joint].plot(zz['t'][wn],zz['v'][wn,joint],c=colors[lab]);axs[1,joint].plot(zz['tf'][wf],zz['rv'][wf,joint],c=colors[lab],ls='--')
  axs[2,joint].plot(zz['tf'][wf],zz['truth'][wf,joint]-zz['rq'][wf,joint],c=colors[lab])
 for ax,label in zip(axs[:,joint],[name+' angle (deg)',name+' velocity (deg/s)','Actual - reference (deg)']):style(ax,label);ax.set_xlim(15.8,18.3)
 axs[0,joint].legend(fontsize=8);axs[-1,joint].set_xlabel('Task time (s)')
fig.suptitle('Historical W1: issued reference and actual Human response');save(fig,'01_historical_terminal.png')

rr=[by['Dev_'+a] if a=='D' else by['Ctrl_'+a] for a in ['B','T','D','ER','H150','KD120','PD','FF','PDFF'] if ('Dev_'+a if a=='D' else 'Ctrl_'+a) in by]
labs=[r['candidate']['id'] for r in rr];xx=np.arange(len(rr));fig,axs=plt.subplots(2,2,figsize=(14,10),layout='constrained')
series=[('J_F_N_s','Full force integral (N s)'),('overshoot','Knee overshoot below issued goal (deg)'),('excursion','Knee excursion minus matched B (deg)'),('moment_integral_Nm_s','Full moment integral (Nm s)')]
for ax,(key,label) in zip(axs.flat,series):
 vals=[r['terminal'][1]['return_overshoot_below_goal_deg'] if key=='overshoot' else r['excursion_delta_B_deg'][1] if key=='excursion' else r[key] for r in rr]
 ax.bar(xx,vals,color=[colors[l] for l in labs]);ax.set_xticks(xx,labs);style(ax,label)
 for i,(v,r) in enumerate(zip(vals,rr)):ax.annotate(f'{v:.3f}'+(' *' if r['fully_qualified'] else ''),(i,v),xytext=(0,4),textcoords='offset points',ha='center',fontsize=8)
 if key=='excursion':ax.axhline(.5,c='black',ls=':',label='Original +0.5 deg gate');ax.legend()
 if key=='J_F_N_s':ax.set_ylim(min(vals)-2,max(vals)+6)
 elif key=='moment_integral_Nm_s':ax.set_ylim(min(vals)-2,max(vals)+2)
 else:ax.set_ylim(0,max(vals)*1.15)
fig.suptitle('W1 full physical comparisons; * = all original qualifications pass\nD from Dev; other arms from Ctrl, with identical matched B/T/ER');save(fig,'05_force_motion_moment.png')

fig,axs=plt.subplots(4,1,figsize=(13,12),sharex=True,layout='constrained')
for r in rr:
 lab=r['candidate']['id']
 if lab in ['T','D']:continue
 zz=Z[r['id']];wn=(zz['t']>=16.2)&(zz['t']<=18.1);wf=(zz['tf']>=16.2)&(zz['tf']<=18.1)
 for ax,key,j in [(axs[0],'q',1),(axs[1],'v',0)]:ax.plot(zz['t'][wn],zz[key][wn,j],c=colors[lab],label=lab,lw=1.1)
 for ax,key in [(axs[2],'f'),(axs[3],'moment')]:ax.plot(zz['tf'][wf],zz[key][wf],c=colors[lab],label=lab,lw=1.1)
for ax,label in zip(axs,['Knee angle (deg)','Hip velocity (deg/s)','Cuff force (N)','Cuff moment (Nm)']):style(ax,label);ax.set_xlim(16.2,18.1)
axs[0].axhline(9.5,c='black',ls=':',lw=.8);axs[0].legend(ncol=7,fontsize=9);axs[-1].set_xlabel('Task time (s)');fig.suptitle('Terminal responses under the frozen interventions');save(fig,'06_interventions_terminal.png')

fig,axs=plt.subplots(5,2,figsize=(15,15),sharex=True,layout='constrained')
for lab in ['ER','H150']:
 zz=Z['Ctrl_'+lab];wn=(zz['t']>=16.5)&(zz['t']<=18);wf=(zz['tf']>=16.5)&(zz['tf']<=18)
 for j in range(2):
  for k,key in enumerate(['q','v','a']):axs[k,j].plot(zz['t'][wn],zz[key][wn,j],c=colors[lab],label=lab)
  axs[0,j].plot(zz['tf'][wf],zz['rq'][wf,j],c=colors[lab],ls='--',lw=.9)
 axs[3,0].plot(zz['tf'][wf],zz['command'][wf,1],c=colors[lab]);axs[3,1].plot(zz['tf'][wf],zz['command'][wf,2],c=colors[lab])
 axs[4,0].plot(zz['tf'][wf],zz['f'][wf],c=colors[lab]);axs[4,1].plot(zz['tf'][wf],zz['moment'][wf],c=colors[lab])
for j,joint in enumerate(['Hip','Knee']):
 for k,label in enumerate([joint+' q (deg)',joint+' dq (deg/s)',joint+' ddq (deg/s2)']):style(axs[k,j],label)
for ax,label in zip(axs[3],['Actual robot command J2 (Nm)','Actual robot command J3 (Nm)']):style(ax,label)
for ax,label in zip(axs[4],['Cuff force (N)','Cuff moment (Nm)']):style(ax,label);ax.set_xlabel('Task time (s)')
for ax in axs.flat:ax.axvline(16.945,c='#777777',ls=':',lw=.8);ax.set_xlim(16.5,18)
axs[0,0].legend();fig.suptitle('Hip-only timing contrast: Human coupling and actual robot output\nDashed = issued q reference; vertical line = RETURN5 splice; mediation is not uniquely identified');save(fig,'07_coupling_and_control.png')

if 'W2_H150' in by:
 fig,axs=plt.subplots(2,3,figsize=(15,9),layout='constrained')
 for k,g in enumerate(['Ctrl','W2']):
  for lab in ['B','ER','H150']:
   r=by[g+'_'+lab];zz=Z[r['id']];wn=(zz['t']>=15.8)&(zz['t']<=18.3)
   axs[k,0].plot(zz['t'][wn],np.maximum(0,9.5-zz['q'][wn,1]),c=colors[lab],label=lab)
   i=['B','ER','H150'].index(lab);axs[k,1].bar(i,r['excursion_delta_B_deg'][1],color=colors[lab]);axs[k,1].annotate(f"{r['excursion_delta_B_deg'][1]:.4f}",(i,r['excursion_delta_B_deg'][1]),xytext=(0,4),textcoords='offset points',ha='center')
   axs[k,2].bar(i,r['motion']['gain_percent'],color=colors[lab]);axs[k,2].annotate(f"{r['motion']['gain_percent']:.4f}%",(i,r['motion']['gain_percent']),xytext=(0,4),textcoords='offset points',ha='center')
  axs[k,0].set_title('W1 development / exact repeat' if k==0 else 'W2 previously unused prefix');axs[k,0].legend();axs[k,0].set_xlabel('Task time (s)');axs[k,0].set_ylim(0,1.5);style(axs[k,0],'Knee undershoot: max(0, 9.5 - q), deg')
  for ax,label in zip(axs[k,1:],['Knee excursion minus own B (deg)','Force reduction vs own B (%)']):style(ax,label);ax.set_xticks([0,1,2],['B','ER','H150'])
  axs[k,1].axhline(.5,c='black',ls=':');axs[k,1].set_ylim(0,max(.65,axs[k,1].get_ylim()[1]*1.1));axs[k,2].set_ylim(0,3)
 fig.suptitle('Frozen H150 paired validation: same Human, a new legal prefix');save(fig,'08_development_holdout.png')

fig,axs=plt.subplots(2,2,figsize=(13,8),sharex=True,layout='constrained')
for ax,lab in zip(axs.flat,['KD120','PD','FF','PDFF']):
 f=P/'output'/('Ctrl_'+lab+'_CONTROL_INTENT.json')
 if not f.exists():continue
 ir=read(f)['rows'];tt=np.array([r['sample_s'] for r in ir])-Z['Ctrl_'+lab]['origin'];dd=np.array([r['delta_rad_s2'] for r in ir]);w=(tt>=14)&(tt<=19.03)
 ax.plot(tt[w],dd[w,0],label='Hip');ax.plot(tt[w],dd[w,1],label='Knee');ax.axhline(.2,c='black',ls=':');ax.axhline(-.2,c='black',ls=':');ax.set_title(lab);style(ax,'Added acceleration intent (rad/s2)');ax.legend();ax.set_xlabel('Task time (s)')
fig.suptitle('Bounded controller interventions before the original output filter');save(fig,'09_controller_intents.png')
for f in (P/'figures').glob('*.png'):shutil.copy2(f,R/'figures'/f.name)
print('FIGURES_COMPLETE')
