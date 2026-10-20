from analyze import *
for label in ['B0','legacy005','18D']:
    m=next(x for x in json.loads((P/'RAW_DERIVED_METRICS.json').read_text())['cases'] if x['label']==label)
    su=json.loads((Path(m['source_root'])/'source/results'/m['archive_case']/'summary.json').read_text())
    for x in su['learning_records'][:2]:
        print(label,'learning_keys',list(x));print('small',str({k:v for k,v in x.items() if k!='selected_plan' and not isinstance(v,(list,dict))})[:1500]);print('selectedplan_keys',list(x['selected_plan']));print('schedule_keys',list(x['selected_plan']['schedule']))
    print('decisions',[(i,d['timing_request_id'],d['executed_label'],d['actual_schedule_start_physics_s']) for i,d in enumerate(su['decisions'][:3])])
