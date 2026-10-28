"""Evaluation-only actual native Human motion; no truth flows to actor/controller."""
from pathlib import Path
import math,json,argparse
from collections import deque
from common import put
from stream_json import array_items

def audit(run,episode=1):
 run=Path(run);ep=run/f'env/episode_{episode:04d}';m=json.loads((ep/'episode_summary.json').read_text());s=json.loads((ep/'summary.json').read_text());raw=ep/'runtime_artifacts.json'
 task_start=m['native_steps_total']*.00025-m['task_s'];qi=m['physical_evaluation_only']['human_qpos_indices'];vi=m['physical_evaluation_only']['human_dof_indices']
 hist=deque(maxlen=81);limits=[45.,75.];acc_limits=[300.,600.];peaks={'native':[0.,0.],'5ms':[0.,0.],'20ms':[0.,0.]};exceeds={k:[0,0] for k in peaks};vel_peak=[0.,0.];vel_exceeds=[0,0];qlo=[math.inf]*2;qhi=[-math.inf]*2;steps=0;bad=0
 for row in array_items(raw,'native_states_evaluation_only'):
  t=row['time_s']
  if t<=task_start+1e-9:continue
  q=[math.degrees(row['qpos_evaluation_only'][i]) for i in qi];v=[math.degrees(row['qvel_evaluation_only'][i]) for i in vi];steps+=1
  bad+=int(not all(math.isfinite(x) for x in q+v))
  for i in range(2):
   qlo[i]=min(qlo[i],q[i]);qhi[i]=max(qhi[i],q[i]);vel_peak[i]=max(vel_peak[i],abs(v[i]));vel_exceeds[i]+=int(abs(v[i])>limits[i]+1e-7)
  for name,n in [('native',1),('5ms',20),('20ms',80)]:
   if len(hist)<n:continue
   oldt,oldv=hist[-n];dt=t-oldt
   for i in range(2):
    a=abs((v[i]-oldv[i])/dt);peaks[name][i]=max(peaks[name][i],a);exceeds[name][i]+=int(a>acc_limits[i]+1e-6)
  hist.append((t,v))
 truth=s['qualification']['true_physics'];task=s['task']
 checks={'finite_actual_human':bad==0,'ROM_original_0_125':all(0.-1e-7<=qlo[i] and qhi[i]<=125.+1e-7 for i in range(2)),'velocity_original_45_75':not any(vel_exceeds),'native_acceleration_original_300_600':not any(exceeds['native']),'5ms_acceleration_original_300_600':not any(exceeds['5ms']),'20ms_acceleration_original_300_600':not any(exceeds['20ms']),'torque_fraction_below_1':task['peak_robot_torque_fraction']<=1.+1e-9,'native_force_below_200':truth['maximum_interface_force_n']['TASK']<=200.+1e-9,'native_moment_below_60':truth['maximum_interface_moment_nm']['TASK']<=60.+1e-9,'positive_true_clearance':truth['minimum_clearance_m']['TASK']>=0.,'no_true_bed_contact':truth['shank_bed_contact_steps']['TASK']==0,'no_mujoco_warnings':not task['mujoco_warning_counts']}
 result={'category':'REAL_NATIVE_PHYSICS_EVALUATION_ONLY','pass':all(checks.values()),'checks':checks,'task_native_steps':steps,'q_min_deg':qlo,'q_max_deg':qhi,'abs_dq_max_deg_s':vel_peak,'velocity_exceedance_steps':vel_exceeds,'abs_ddq_max_deg_s2':peaks,'acceleration_exceedance_windows':exceeds,'original_motion_limits':{'velocity_deg_s':limits,'acceleration_deg_s2':acc_limits},'native_true_physics':truth,'task_torque_fraction':task['peak_robot_torque_fraction'],'qualification_scope':'observed episode only; finite-difference actual Human acceleration is independent of reference certificate; not all-action or host realtime safety'}
 put(ep/'ACTUAL_HUMAN_MOTION_AUDIT.json',result);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('run');p.add_argument('--episode',type=int,default=1);a=p.parse_args();print(json.dumps(audit(a.run,a.episode)))
