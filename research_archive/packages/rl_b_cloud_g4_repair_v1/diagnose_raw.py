from pathlib import Path
import json,math
from stream_json import array_items,object_value
from common import put
OLD=Path('/home/hank/ihear-lab/rl_b_cloud_v1')
def run(case):
 ep=OLD/'runs'/case/'physics/env/episode_0001';raw=ep/'runtime_artifacts.json';rows=[r for r in array_items(raw,'trace') if r['stage']=='TASK'];boundary=object_value(raw,'last_boundary')
 jf=0.;phase={};duplicates=[]
 for i,r in enumerate(rows):
  end=rows[i+1]['time_s'] if i+1<len(rows) else boundary['time_s']
  dt=end-r['time_s'];f=math.sqrt(sum(x*x for x in r['cuff_force_world_n']));cost=f*dt;jf+=cost
  v=phase.setdefault(r['task_phase'],{'dt':0.,'J_F':0.,'recorded_J_F':0.});v['dt']+=dt;v['J_F']+=cost;v['recorded_J_F']+=r['interval_force_cost_n_s']
  if abs(cost-r['interval_force_cost_n_s'])>1e-7:duplicates.append({'row_index':i,'time_s':r['time_s'],'task_s':r.get('task_elapsed_s'),'next_time_s':end,'dt':dt,'force_N':f,'raw_cost':r['interval_force_cost_n_s'],'independent_cost':cost,'difference':r['interval_force_cost_n_s']-cost,'fields':r})
 ticks=[json.loads(l) for l in (ep/'online_tick_evidence.jsonl').read_text().splitlines()];tj=sum(math.sqrt(sum(v*v for v in a['measured_force_world_n']))*(b['task_s']-a['task_s']) for a,b in zip(ticks,ticks[1:]));summary=json.loads((ep/'summary.json').read_text());metrics=json.loads((ep/'episode_summary.json').read_text())
 requests=[r for r in array_items(raw,'requests') if r['stage']=='TASK'];fallback=list(array_items(raw,'safe_fallback_events'))
 return {'case':case,'independent_trace_JF':jf,'online_tick_JF':tj,'recorded_cost_sum':sum(r['interval_force_cost_n_s'] for r in rows),'native_summary':summary['task'],'wrapper_summary':metrics,'phases':phase,'mismatches':duplicates,'first_tick':ticks[0],'last_tick':ticks[-1],'last_boundary':boundary,'requests':requests,'fallback':fallback,'governor_count':None}
res=[run(c) for c in ['g4_slow_01','qual_maximal_01','qual_random_01']];put('audit/HISTORICAL_RAW_DIAGNOSIS.json',res)
for r in res:
 print(r['case'],r['independent_trace_JF'],r['online_tick_JF'],r['recorded_cost_sum']);print('phases',r['phases']);print('mismatches', [{k:v for k,v in d.items() if k!='fields'} for d in r['mismatches']]);print('transitions',r['native_summary']['phase_transitions']);print('request outcomes',[(x['request_id'],x['source_sample_time_s'],x['outcome'],x.get('reason')) for x in r['requests']]);print('fallback events',[(x.get('event'),x.get('time_s'),x.get('reason')) for x in r['fallback']])
