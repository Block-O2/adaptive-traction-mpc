from pathlib import Path
import os,sys,json,csv
os.environ.update(MPLBACKEND='Agg')
import numpy as np,matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/force_mechanism_waypoint_v3');sys.path.insert(0,str(P/'control'))
from postprocess_targeted import load,save
from analyze_mechanism import put,integ
rows=json.loads((P/'derived/TARGETED_CONTRASTS.json').read_text())['rows'];B=load('targeted2_B0');fig,axs=plt.subplots(3,2,figsize=(17,12),sharex=True,layout='constrained');colors={'zero':'#2166ac','smooth':'#b2182b','opposite_quarter':'#4d9221','half':'#e08214','repeat':'#762a83'}
for col,tag in enumerate(['O','R']):
 for r in rows:
  if not r['id'].startswith('targeted2_'+tag+'_'):continue
  z=load(r['id']);kind=r['id'].removeprefix('targeted2_'+tag+'_');style='--' if kind=='repeat' else '-';co=colors[kind]
  axs[0,col].plot(z['tf'],z['f'],c=co,ls=style,label=kind);axs[1,col].plot(z['tf'],z['f']-B['f'],c=co,ls=style);axs[2,col].plot(z['tf'],z['cf']-B['cf'],c=co,ls=style)
  for ax in axs[:,col]:ax.axvspan(*r['local_window'],color='#238b45',alpha=.015)
 axs[0,col].legend(ncol=3,fontsize=8);axs[0,col].set_title(tag+' interventions | full task');axs[0,col].set_ylabel('Force [N]');axs[1,col].set_ylabel('Instantaneous F − B [N]');axs[2,col].set_ylabel('Cumulative J_F − B [N s]');axs[2,col].set_xlabel('Task elapsed [s]')
 for ax in axs[:,col]:
  ax.set_xlim(0,19.03);ax.grid(alpha=.2)
  for t in [9.005,10.025]:ax.axvline(t,c='.4',lw=.7)
 axs[1,col].axhline(0,c='.4',lw=.7);axs[2,col].axhline(0,c='.4',lw=.7)
fig.suptitle('Targeted shape interventions | full force and cumulative curves | exact repeats overlap originals');save(fig,'07_targeted_full_task')
fig,axs=plt.subplots(1,2,figsize=(13,5),layout='constrained')
for ax,tag in zip(axs,['O','R']):
 for r in rows:
  if not r['id'].startswith('targeted2_'+tag+'_'):continue
  kind=r['id'].removeprefix('targeted2_'+tag+'_');x=r['local_TV_v_percent'];y=r['local_delta_J_F'];ax.scatter(x,y,c=colors[kind],marker='x' if kind=='repeat' else 'o',s=70,label=kind)
  if kind!='repeat':ax.annotate(kind,(x,y),xytext=(-6,5) if x>0 else (6,5),ha='right' if x>0 else 'left',textcoords='offset points',fontsize=8)
 ax.axhline(0,c='.5');ax.axvline(0,c='.5');ax.grid(alpha=.2);ax.set_xlabel('Actual velocity TV change in support [%]');ax.set_ylabel('Support J_F − B [N s]');ax.set_title(tag+' local contrast; dependent same-state observations')
fig.suptitle('Smooth / opposite / half / repeat | small local effects, no universal force surrogate');save(fig,'08_local_motion_force_contrast')
with (P/'derived/TARGETED_CONTRASTS.csv').open('w',newline='') as f:
 fields=['id','motion_pass','full_J_F','full_delta_J_F','local_delta_J_F','local_TV_v_percent','local_TV_refv_percent','local_TV_a_percent','local_jerk_RMS_percent','local_moment_delta','local_positive_force_area','local_negative_force_area','local_force_lower_time_fraction','full_duration_s'];w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
# Cumulative snapshots reveal downstream changes without attributing them to local smoothness.
extra=[]
for r in rows:
 if not r['id'].endswith(('_smooth','_half','_opposite_quarter')):continue
 z=load(r['id']);end=r['local_window'][1];times=sorted(set([end,min(19.03,end+.5),16.58,16.585,19.03]));extra.append(dict(id=r['id'],cumulative_delta_at_time={str(t):float(np.interp(t,z['tf'],z['cf']-B['cf'])) for t in times}))
put('derived/DOWNSTREAM_CUMULATIVE_SNAPSHOTS.json',dict(rows=extra))
print('COMPACT_FIGURES_AND_CSV_DONE')
