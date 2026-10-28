"""Export scientific figures/tables from saved results only."""
from pathlib import Path
import os,csv,json,sys
from research_common import ROOT,read
os.environ['MPLCONFIGDIR']=str(ROOT/'runtime/cache/matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def export_csv(path,rows):
 if not rows:return
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 data=read(ROOT/'STD_ABLATION_RESULTS.json');assert data['status']=='COMPLETE';out=ROOT/'figures';out.mkdir(exist_ok=True);tables=ROOT/'tables';tables.mkdir(exist_ok=True)
 cases=data['cases'];seeds=[1495656323,1630784693];colors={'A':'#b65e35','B':'#197b83','C':'#252525'}
 rows=[];action_rows=[]
 for x in cases:
  m=x['motion'];rows.append(dict(seed=x['seed'],arm=x['arm'],stream=x['rng'],split=x['split'],status=x['status'],integral_scope=x['integral_scope'],task_s=x['task_s'],JF_N_s=x['JF'],JM_Nm_s=x['JM'],clip_fraction=x['clip_fraction'],hip_tracking_RMS_deg=m['tracking_RMS_deg'][0],knee_tracking_RMS_deg=m['tracking_RMS_deg'][1],hip_jerk_RMS_deg_s3=m['jerk_RMS_deg_s3'][0],knee_jerk_RMS_deg_s3=m['jerk_RMS_deg_s3'][1],hip_RETURN_overshoot_deg=m['RETURN_overshoot_below_goal_deg'][0] if m['RETURN_overshoot_below_goal_deg'] else None,knee_RETURN_overshoot_deg=m['RETURN_overshoot_below_goal_deg'][1] if m['RETURN_overshoot_below_goal_deg'] else None,receipt_physics_source_age_max_s=x['source_age_TASK_s']['maximum'] if x['source_age_TASK_s'] else None,receipt_host_age_max_ms=x['receipt_host_sensor_age_at_apply_ms_profile']['maximum'] if x['receipt_host_sensor_age_at_apply_ms_profile'] else None,request_host_activation_age_max_ms=x['request_host_activation_age_ms']['maximum'] if x['request_host_activation_age_ms'] else None,native_steps=x['native_steps'],wall_s=x['wall_s']))
  ts=read(Path(x['run'])/'RESEARCH_TRANSITIONS.json')
  for i,t in enumerate(ts):
   link=x['native_actions'][i]
   action_rows.append(dict(seed=x['seed'],arm=x['arm'],stream=x['rng'],split=x['split'],noise_index=i,mean_0=t['mean'][0],mean_1=t['mean'][1],checkpoint_std_0=t['std'][0],checkpoint_std_1=t['std'][1],sampling_std_0=t['effective_std'][0] if x['arm']!='C' else None,sampling_std_1=t['effective_std'][1] if x['arm']!='C' else None,z_0=t['noise'][0] if x['arm']!='C' else None,z_1=t['noise'][1] if x['arm']!='C' else None,raw_0=t['raw_action'][0],raw_1=t['raw_action'][1],clipped_0=t['action'][0],clipped_1=t['action'][1],request_id=link['request_id'],planner_outcome=link['outcome'],planner_activated=link['plan_activated'],proposal_is_applied_torque=False))
 export_csv(tables/'std_attempts.csv',rows);export_csv(tables/'policy_actions.csv',action_rows)
 export_csv(tables/'paired_outcomes.csv',[{k:x[k] for k in ['seed','rng','A_success','B_success','A_task_s','B_task_s','complete_equal_duration','JF_difference_B_minus_A','JM_difference_B_minus_A']} for x in data['pairs']])
 fig,axes=plt.subplots(1,3,figsize=(13,3.8));fig.suptitle('Frozen exploration-scale ablation | nominal action streams, n=6 per parent')
 for j,seed in enumerate(seeds):
  p=next(x['arms'] for x in data['per_parent'] if x['seed']==seed)
  for k,arm in enumerate(['A','B']):
   pos=j*3+k;axes[0].bar(pos,p[arm]['complete'],color=colors[arm],width=.8);axes[0].text(pos,p[arm]['complete']+.08,f'{p[arm]["complete"]}/{p[arm]["attempts"]}',ha='center',fontsize=9)
   axes[1].bar(pos,100*(p[arm]['clip_fraction'] or 0),color=colors[arm],width=.8)
 axes[0].set(ylim=(0,7),ylabel='Complete tasks',xticks=[.5,3.5],xticklabels=['parent 149…','parent 163…']);axes[1].set(ylabel='Clipped action components (%)',xticks=[.5,3.5],xticklabels=['parent 149…','parent 163…'])
 for x in cases:
  if x['split'] not in ['preregistered','identity'] or not x['success']:continue
  axes[2].scatter(x['JF'],x['JM'],c=colors[x['arm']],marker='x' if x['arm']=='C' else ('o' if x['seed']==seeds[0] else '^'),s=38,alpha=.8)
 for p in data['pairs']:
  if not p['complete_equal_duration']:continue
  ab=[next(x for x in cases if x['seed']==p['seed'] and x['rng']==p['rng'] and x['arm']==arm) for arm in ['A','B']]
  axes[2].plot([x['JF'] for x in ab],[x['JM'] for x in ab],c='#aaaaaa',lw=.7,zorder=0)
 axes[2].set(xlabel='Complete JF (N s)',ylabel='Complete JM (Nm s)',title='Complete tasks only; duration varies\nCircle: parent 149… | Triangle: parent 163…')
 for ax in axes:ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15)
 from matplotlib.lines import Line2D
 fig.legend(handles=[Line2D([0],[0],color=colors[a],marker='x' if a=='C' else 'o',ls='',label=l) for a,l in [('A','A: checkpoint STD'),('B','B: evaluation STD=0.2'),('C','C: mean regression')]],loc='lower center',ncol=3,frameon=False,bbox_to_anchor=(.5,-.025))
 fig.tight_layout(rect=(0,.06,1,.94));fig.savefig(out/'std_ablation_summary.png',dpi=180,bbox_inches='tight');fig.savefig(out/'std_ablation_summary.pdf',bbox_inches='tight');plt.close(fig)
 # Predeclared first new stream, shown without choosing a favorable trajectory.
 fig,axes=plt.subplots(2,2,figsize=(11,6),sharex=True)
 for j,seed in enumerate(seeds):
  for arm in ['A','B']:
   x=next((x for x in cases if x['seed']==seed and x['arm']==arm and x['rng']==202610213101),None)
   if not x:continue
   series=np.load(Path(x['run'])/'ACTUAL_HUMAN_TASK_SERIES.npz');stride=20
   for joint in range(2):axes[j,joint].plot(series['time_s'][::stride],np.degrees(series['q_rad'][::stride,joint]),color=colors[arm],lw=1,label=arm)
  axes[j,0].set_ylabel(f'parent {str(seed)[:3]}…\nActual angle (deg)')
 axes[0,0].set_title('Hip');axes[0,1].set_title('Knee')
 for ax in axes.ravel():ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
 for ax in axes[1]:ax.set_xlabel('Executed TASK time (s)')
 axes[0,0].legend(frameon=False);fig.suptitle('Actual Human native state | preregistered stream 202610213101');fig.tight_layout();fig.savefig(out/'human_first_stream.png',dpi=180);fig.savefig(out/'human_first_stream.pdf');plt.close(fig)
 print('saved CSVs and PNG/PDF figures; no physics or learning')
if __name__=='__main__':main()
