"""Independent raw native timing reconstruction; evaluation only."""
from pathlib import Path
from stream_json import array_items,object_value
from common import put
import json,collections
out={}
for label,path in [('maximal','runs/repair_reset_maximal_01'),('random','runs/repair_random_01')]:
 ep=Path(path)/'physics/env/episode_0001';raw=ep/'runtime_artifacts.json';summary=json.loads((ep/'summary.json').read_text());metrics=json.loads((ep/'episode_summary.json').read_text());gov=list(array_items(raw,'reference_governor_records'));requests=[r for r in array_items(raw,'requests') if r['stage']=='TASK'];events=list(array_items(raw,'safe_fallback_events'));start=metrics['native_steps_total']*.00025-metrics['task_s']
 print(label,'governor first',str(gov[0])[:1400] if gov else None)
 out[label]={'task_start_native_s':start,'task_end_native_s':start+metrics['task_s'],'task_s':metrics['task_s'],'native_total_s':metrics['native_steps_total']*.00025,'phase_transitions':summary['task']['phase_transitions'],'requests':[{'request_id':r['request_id'],'source_task_s':r['source_sample_time_s']-start,'outcome':r['outcome'],'reason':r.get('reason'),'activation_age_ms':r.get('activation_age_ms')} for r in requests],'fallback_events':[{'event':r['event'],'task_s':r['physics_s']-start,'request_id':r.get('request_id'),'reason':r.get('reason')} for r in events],'event_counts':dict(collections.Counter(r['event'] for r in events)),'governor_records':gov,'native_return_commit':object_value(raw,'return_commit_attempts')}
put('audit/TASK_TIMING_RAW_EVIDENCE.json',out)
