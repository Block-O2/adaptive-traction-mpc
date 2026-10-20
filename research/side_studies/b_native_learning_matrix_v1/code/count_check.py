from task_bootstrap import *
for name in ['smoke_OUTBOUND_2_candidate0_DATA.json','parent_dev_0_OUTBOUND_4_candidate0_DATA.json']:
 r=json.loads((STUDY/'output'/name).read_text());print(json.dumps(dict(id=r['id'],child=r['child'],counts={k:v for k,v in r['metric'].items() if 'api_calls' in k or 'native_physics' in k or 'simulation_seconds' in k})))
