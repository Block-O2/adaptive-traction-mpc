"""Offline phase dose and native Human motion comparison; zero new physics."""
from pathlib import Path
import os,sys,json,csv,math
R=Path(__file__).resolve().parents[1];os.environ['IHEAR_RESEARCH_ROOT']=str(R);sys.path.insert(0,str(R/'scripts'))
from research_common import atomic,read,sha,now
import numpy as np
PHASES=['OUTBOUND','HOLD','RETURN']

def build():
 rows=[json.loads(s) for s in (R/'ALL_ATTEMPTS.jsonl').read_text().splitlines()] if (R/'ALL_ATTEMPTS.jsonl').exists() else []
 means=[r for r in rows if r['mode']=='evaluation' and r['policy_mode']=='deterministic' and r['branch'].startswith('REWARD_')]
 root=R/'FROZEN_COMPARISON_FIGURES';root.mkdir(exist_ok=True);records=[];series={};pairs=[]
 for row in means:
  run=Path(row['run']);force=read(run/'env/episode_0001/FORCE_INDEPENDENT_AUDIT.json');summary=read(run/'env/episode_0001/summary.json')
  label='R4' if row['branch'].startswith('REWARD_R4_') else 'R1';key=(row['seed'],label)
  metrics_path=R/'audit/independent_all_attempts'/row['job_id']/run.name/'COMMON_MOTION_METRICS.json'
  if not metrics_path.exists():metrics_path=run/'COMMON_MOTION_METRICS.json'
  motion=read(metrics_path);source=metrics_path.parent/'ACTUAL_HUMAN_TASK_SERIES.npz'
  if not source.exists():continue
  with np.load(source) as z:loaded={k:z[k].copy() for k in ['time_s','q_rad','dq_rad_s','ddq_rad_s2','jerk_rad_s3']}
  series[key]=loaded;begin=row['native_steps']*.00025-row['task_s'];transitions=summary['task']['phase_transitions'];bounds=[0.]
  for phase in ['HOLD','RETURN']:
   found=[x['time_s']-begin for x in transitions if x['to']==phase]
   if found:bounds.append(found[0])
  bounds.append(row['task_s']);phases={}
  for phase,lo,hi in zip(PHASES,bounds[:-1],bounds[1:]):
   select=(loaded['time_s']>lo+1e-9)&(loaded['time_s']<=hi+1e-9)
   if not select.any():continue
   p=dict(force['phases'].get(phase,{}));p['native_window_count']=int(select.sum())
   for kind,name in [('dq_rad_s','velocity_RMS_deg_s'),('ddq_rad_s2','acceleration_RMS_deg_s2'),('jerk_rad_s3','jerk_RMS_deg_s3')]:p[name]=np.degrees(np.sqrt((loaded[kind][select]**2).mean(0))).tolist()
   phases[phase]=p
  records.append(dict(seed=row['seed'],reward=label,run=str(run),success=row['success'],task_s=row['task_s'],integral_scope=row['integral_scope'],phases=phases,force_source_sha256=sha(run/'env/episode_0001/FORCE_INDEPENDENT_AUDIT.json'),native_series_sha256=sha(source),native_derivative_phase_definition='Backward derivative ending strictly after phase start and at/before transition; pre-TASK anchors retained; phase RMS diagnostic only'))
 for seed in [1495656323,1630784693]:
  a=next((x for x in records if x['seed']==seed and x['reward']=='R1'),None);b=next((x for x in records if x['seed']==seed and x['reward']=='R4'),None)
  if not (a and b):continue
  for phase in PHASES:
   aa=a['phases'].get(phase);bb=b['phases'].get(phase)
   eligible=bool(a['success'] and b['success'] and aa and bb and abs(a['task_s']-b['task_s'])<1e-7 and abs(aa['duration_s']-bb['duration_s'])<1e-7)
   pairs.append(dict(seed=seed,phase=phase,qualified_full_equal_phase_duration=eligible,JF_delta=bb['J_F_N_s']-aa['J_F_N_s'] if eligible else None,JM_delta=bb['J_M_Nm_s']-aa['J_M_Nm_s'] if eligible else None,phase_knee_jerk_delta=bb['jerk_RMS_deg_s3'][1]-aa['jerk_RMS_deg_s3'][1] if eligible else None))
 atomic(root/'PHASE_RESULTS.json',dict(time_utc=now(),records=records,pairs=pairs,new_native_steps=0,new_optimizer_updates=0,source_sha256=sha(Path(__file__)),scope='Saved nominal mean trajectories; phase differences require both full and matching whole/phase durations; no causal component attribution'))
 with (root/'phase_comparisons.csv').open('w',newline='') as f:
  names=['seed','phase','qualified_full_equal_phase_duration','JF_delta','JM_delta','phase_knee_jerk_delta'];w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(pairs)
 os.environ['MPLCONFIGDIR']=str(R/'analysis_tools/mpl-cache');import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 plt.rcParams['agg.path.chunksize']=10000
 fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
 for row_index,seed in enumerate([1495656323,1630784693]):
  rr=[x for x in records if x['seed']==seed]
  valid=len(rr)==2 and all(x['success'] for x in rr) and abs(rr[0]['task_s']-rr[1]['task_s'])<1e-7
  for col,(metric,title) in enumerate([('J_F_N_s','JF [N s]'),('J_M_Nm_s','JM [Nm s]')]):
   ax=axes[row_index,col];ax.set_title(f'{seed}: {title}')
   if valid:
    x=np.arange(3)
    for offset,label in [(-.18,'R1'),(.18,'R4')]:
     r=next(x for x in rr if x['reward']==label);ax.bar(x+offset,[r['phases'].get(p,{}).get(metric,0.) for p in PHASES],width=.34,label=label)
    ax.set_xticks(x,PHASES,fontsize=8);ax.legend();ax.grid(axis='y',alpha=.2)
   else:ax.text(.5,.5,'Both complete equal-duration trajectories required',ha='center',va='center',transform=ax.transAxes)
 fig.savefig(root/'R1_R4_phase_dose.png',dpi=160);fig.savefig(root/'R1_R4_phase_dose.pdf');plt.close(fig)
 for seed in [1495656323,1630784693]:
  rr=[x for x in records if x['seed']==seed]
  if len(rr)!=2 or not all(x['success'] for x in rr) or abs(rr[0]['task_s']-rr[1]['task_s'])>=1e-7:continue
  fig,axes=plt.subplots(4,1,figsize=(12,11),sharex=True,layout='constrained')
  for label,style in [('R1','--'),('R4','-')]:
   z=series[(seed,label)]
   for ax,kind,unit in zip(axes,['q_rad','dq_rad_s','ddq_rad_s2','jerk_rad_s3'],['q [deg]','dq [deg/s]','ddq [deg/s2]','jerk [deg/s3]']):
    for joint,color in [(0,'#2878B5'),(1,'#D95319')]:ax.plot(z['time_s'],np.degrees(z[kind][:,joint]),style,color=color,lw=.65,alpha=.8,label=f'{label} '+('hip' if joint==0 else 'knee'))
    ax.set_ylabel(unit);ax.grid(alpha=.2)
  axes[0].legend(ncol=4,fontsize=8);axes[0].set_title(f'Actual native Human motion, parent {seed}; complete TASK only');axes[-1].set_xlabel('TASK time [s]')
  fig.savefig(root/f'R1_R4_native_motion_seed{seed}.png',dpi=160);fig.savefig(root/f'R1_R4_native_motion_seed{seed}.pdf');plt.close(fig)
 (root/'README.md').write_text('# 冻结 R1/R4 的阶段剂量和真实运动\n\n只读已保存 nominal mean 轨迹，零新物理/Adam。阶段 JF/JM 来自独立原5ms左积分；native速度、加速度、jerk来自完整4kHz序列和pre-TASK anchors。相位RMS仅作诊断，不创造新的jerk合格阈值。\n\n只有两者完整且整体/相位分别等时时才列直接阶段剂量差；失败partial原样列入JSON，不以低剂量比较性能。运动图只为两条完整等时轨迹生成，图内展示全部native序列。\n\n相位差能定位变化阶段，不能据此唯一归因于力臂、旋转阻尼或某一个Reward项。正式B/H150 live matched与G4资格仍未获得。\n')
 return dict(cases=len(records),phase_pairs=len(pairs))
if __name__=='__main__':print(json.dumps(build()))
