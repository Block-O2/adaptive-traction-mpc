from common import *
p=O/'diagnostic_seed_20261004/episode_00001'
d=json.loads((p/'runtime_artifacts.json').read_text());print('KEYS',[(k,type(v).__name__,len(v) if hasattr(v,'__len__') else 0) for k,v in d.items()],flush=True)
for k,v in d.items():
    if isinstance(v,list) and v and isinstance(v[0],dict):print(k,list(v[0].keys()),flush=True)
summary=json.loads((p/'summary.json').read_text());print('SUMMARY',summary['status'],summary.get('abort_reason'),summary['task']['phase_transitions'],flush=True)
