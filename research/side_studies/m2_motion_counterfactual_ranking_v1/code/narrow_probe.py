from common import *
j=load(OLD/'BRANCH_LABELS.json')
print('counts', {k:len(v) for k,v in j.items()})
r=j['rows'][0]; print('label keys',list(r['labels']));print('smalllabels',{k:v for k,v in r['labels'].items() if 'native' not in k and 'sampled_' not in k})
d=load(r['source_file']); print('metric keys',list(d['metric']));print('child',d['child']);print('context',d['branch_start']['context']);print('counts',d['branch_start']['counts']);print('table',d['table'])
p=Path(r['labels']['trace']).parent/'runtime_artifacts.json.gz'
for key in ['native_states_evaluation_only','command_receipts']:
 first=next(array_items(p,key),None);print('first',key,first)
print('first decision',load(MATRIX/'output'/(r['id']+'_DECISIONS.json'))['rows'][0])
print('failed ids',[(r.get('id'),list(r)) for r in j['failed_rows']]);print('excluded',[(r.get('id'),list(r)) for r in j['excluded_rows']])
