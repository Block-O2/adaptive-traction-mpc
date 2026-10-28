from pathlib import Path
import json,sys
O=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8/runtime')
ident=sys.argv[1] if len(sys.argv)>1 else '099_N13_S2_D2_C6_host_nominal'
s=json.loads((O/'source/results'/ident/'summary.json').read_text());m=json.loads((O/'output'/(ident+'_MULTIRATE.json')).read_text())
print('SUMMARY_KEYS',list(s));print('TASK',json.dumps(s['task'])[:5000]);print('TIMING_KEYS',list(s.get('timing',{})))
for d in s['decisions']:
 if d.get('phase')=='HOLD' or d.get('phase')=='RETURN':
  print('DECISION',json.dumps(d)[:7000])
  if d.get('phase')=='RETURN':break
ids={d['timing_request_id'] for d in s['decisions'] if d.get('phase')=='HOLD'}
ids.add(next(d['timing_request_id'] for d in s['decisions'] if d.get('phase')=='RETURN'))
for r in m['native_requests']:
 if r['request_id'] in ids:print('REQUEST',json.dumps(r))
for kind in ('COMMITTED_ENDPOINT_SERVICE','DIRECT_IPC'):
 p=O/'output'/(ident+'_'+kind+'.json')
 if p.exists():
  x=json.loads(p.read_text());print(kind,'KEYS',list(x))
  print(json.dumps([r for r in x.get('rows',[]) if r.get('request_id') in ids])[:16000])
