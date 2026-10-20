from pathlib import Path
import sys,json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');ident=sys.argv[1]
r=json.loads((S/'output'/(ident+'_RESULT.json')).read_text());m=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text());i=json.loads((S/'output'/(ident+'_DIRECT_IPC.json')).read_text())['rows']
print('RESULT',json.dumps({k:v for k,v in r.items() if k not in ('metric','inputs')}));print('REQUESTS_LAST',json.dumps(m['native_requests'][-4:]));print('CACHE_LAST',json.dumps(next((x['hold_static_mechanics'] for x in reversed(i) if 'hold_static_mechanics' in x),None)));print('FAST_LAST',json.dumps(m['rows']['fast'][-3:]));print('SENSOR_LAST',json.dumps(m['rows']['sensor_capture'][-2:]))
