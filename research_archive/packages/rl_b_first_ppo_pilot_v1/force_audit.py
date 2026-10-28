"""Independent raw left integration; no runtime or reward functions imported."""
from pathlib import Path
import json,math
from stream_json import array_items,object_value
from common import put

def audit(ep):
 raw=ep/'runtime_artifacts.json';rows=[x for x in array_items(raw,'trace') if x['stage']=='TASK'];end=object_value(raw,'last_boundary')['time_s'];totals={};jf=jm=0.;mismatch=[];zero=[]
 for i,a in enumerate(rows):
  right=rows[i+1]['time_s'] if i+1<len(rows) else end;dt=right-a['time_s'];assert dt>=0
  f=math.sqrt(sum(v*v for v in a['cuff_force_world_n']));m=math.sqrt(sum(v*v for v in a['cuff_moment_world_nm']));v=totals.setdefault(a['task_phase'],{'duration_s':0.,'J_F_N_s':0.,'J_M_Nm_s':0.});v['duration_s']+=dt;v['J_F_N_s']+=f*dt;v['J_M_Nm_s']+=m*dt;jf+=f*dt;jm+=m*dt
  if abs(a['interval_force_cost_n_s']-f*dt)>1e-7:mismatch.append({'row':i,'dt':dt,'stored':a['interval_force_cost_n_s'],'raw_left':f*dt})
  if dt==0:zero.append({'row':i,'time_s':a['time_s'],'phase':a['task_phase'],'cost':a['interval_force_cost_n_s'],'rejected_before_apply':a.get('execution_rejected_before_apply',False),'terminal_boundary':a.get('terminal_boundary_node',False)})
 summary=json.loads((ep/'summary.json').read_text());wrapper=json.loads((ep/'episode_summary.json').read_text());ticks=[json.loads(l) for l in (ep/'online_tick_evidence.jsonl').read_text().splitlines()]
 tick_jf=sum(math.sqrt(sum(x*x for x in a['measured_force_world_n']))*(b['task_s']-a['task_s']) for a,b in zip(ticks,ticks[1:]));tick_jm=sum(math.sqrt(sum(x*x for x in a['measured_moment_world_nm']))*(b['task_s']-a['task_s']) for a,b in zip(ticks,ticks[1:]))
 diffs={'summary_force':summary['task']['force_integral_n_s']-jf,'wrapper_force':wrapper['force_integral_N_s']-jf,'tick_force':tick_jf-jf,'summary_moment':summary['qualification']['physical_interval_moment_integral_nm_s']-jm,'wrapper_moment':wrapper['moment_integral_Nm_s']-jm,'tick_moment':tick_jm-jm,'reward_force':wrapper['reward_totals']['force']+.02*jf/100.}
 r={'category':'INDEPENDENT_RAW_5MS_LEFT_INTEGRATION','episode':str(ep),'task_duration_s':end-rows[0]['time_s'],'independent_J_F_N_s':jf,'independent_J_M_Nm_s':jm,'phases':totals,'summary_force':summary['task']['force_integral_n_s'],'wrapper_reward':wrapper['reward_totals'],'differences':diffs,'mismatching_rows':mismatch,'zero_duration_rows':zero,'pass':not mismatch and max(abs(x) for x in diffs.values())<1e-7,'integration_definition':'original measured force norm, interval-start left integral over executed TASK time; zero duration owns zero cost'}
 put(ep/'FORCE_INDEPENDENT_AUDIT.json',r);return r
if __name__=='__main__':
 import sys
 r=audit(Path(sys.argv[1]));print(json.dumps(r,indent=2))
