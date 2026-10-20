from pathlib import Path
import json,sys,gzip,re
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');i=sys.argv[1]
summary=json.loads((S/'source/results'/i/'summary.json').read_text());print('SUMMARY_KEYS',list(summary));print('TASK_KEYS',list(summary.get('task',{})))
print('REFERENCE_RECORDS',json.dumps(summary.get('online_reference_records',[])[:2],indent=2)[:4500]);print('COMMISSION_KEYS',list(summary.get('commissioning',{})))
for d in summary.get('decisions',[])[:2]:
 print('DECISION_KEYS',list(d));print('SCALARS',{k:v for k,v in d.items() if not isinstance(v,(dict,list))});print('DICT_KEYS',{k:list(v) for k,v in d.items() if isinstance(v,dict)})
 chosen=next((v for v in d.get('evaluations',[]) if v.get('label')==d.get('executed_label')),None)
 if chosen:print('SCHEDULE_FIELDS',{k:v for k,v in chosen.get('schedule',{}).items() if not isinstance(v,(dict,list))})
m=json.loads((S/'output'/(i+'_MULTIRATE.json')).read_text());print('REQ3',next((r for r in m['native_requests'] if r['request_id']==3),None))
with gzip.open(S/'source/results'/i/'runtime_artifacts.json.gz','rt') as f:
 chunk=f.read(3000);print('ARTIFACT_INITIAL',chunk[:1000])
