from task_bootstrap import *
rows=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()]
started=[x for x in rows if x['event']=='START'];ended=[x for x in rows if x['event']=='END']
print(json.dumps(dict(elapsed_h=(time.time()-json.loads((STUDY/'RUN_PLAN.json').read_text())['start_unix'])/3600,attempts=len(started),ended=len(ended),current=[x['id'] for x in started if x['id'] not in {y['id'] for y in ended}],last=ended[-2:])))
data=[]
for p in sorted((STUDY/'output').glob('*_DATA.json')):
 r=json.loads(p.read_text());data.append(dict(id=r['id'],valid=r['metric']['valid'],J_F=r['metric']['J_F'],remaining=r['remaining_J_F'],moment=r['metric']['moment_integral'],phase=r['metric']['phase_durations']))
print(json.dumps(dict(data_count=len(data),latest_data=data[-4:])))
for name in ('PIPELINE_STATE.json','PIPELINE_ATTENTION.json','RESOURCE_STATE.json'):
 p=STUDY/name
 if p.exists():print(name,p.read_text()[:2000])
p=STUDY/'output/RESOURCES_ALL_PROCESS_TREES.jsonl'
if p.exists():
 r=json.loads(p.read_text().splitlines()[-1]);print(json.dumps({k:r[k] for k in ('unix','mem_available','swap_used','PSS','owned_count','windows','psi')}))
if len(sys.argv)>1 and sys.argv[1]=='keys':
 r=json.loads((STUDY/'output/002_original_B_retry1_RESULT.json').read_text())['metric'];print(json.dumps({k:v for k,v in r.items() if not isinstance(v,dict) or k=='phase_durations'}))
