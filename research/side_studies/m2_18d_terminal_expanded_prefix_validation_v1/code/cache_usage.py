from pathlib import Path
import json,sys
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_expanded_prefix_validation_v1');ident=sys.argv[1]
raw=json.loads((S/'output'/(ident+'_DIRECT_IPC.json')).read_text())['rows'];m=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text());s=json.loads((S/'source/results'/ident/'summary.json').read_text());holdids={r['timing_request_id'] for r in s['decisions'] if r.get('phase')=='HOLD'}
last=next((r['hold_static_mechanics'] for r in reversed(raw) if 'hold_static_mechanics' in r),None)
schedule=next((r['hold_static_schedule'] for r in reversed(raw) if 'hold_static_schedule' in r),None)
out=dict(id=ident,status='OBSERVED' if last else 'NOT_ENABLED',pure_cache=last,hold_requests=[{k:r.get(k) for k in ('request_id','compute_ms','worker_to_main_scheduling_ms','validation_and_command_construction_ms','acquisition_to_request_ms','activation_age_ms')} for r in m['native_requests'] if r['request_id'] in holdids],background_model_API_calls=0 if last is None else sum(r['model_API_calls'] for r in last['rows']),no_live_plant_owner_in_worker=True)
out['original_schedule_cache']=schedule
(S/'reports'/(ident+'_CACHE_USAGE.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
