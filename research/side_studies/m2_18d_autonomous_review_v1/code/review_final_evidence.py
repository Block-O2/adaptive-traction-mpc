from task_bootstrap import *
def main():
 names=['HOST_QUALIFICATION_SUMMARY','ADMISSION_HEADROOM_AUDIT','NATIVE_COUNT_AUTHORITY_AUDIT','FROZEN_SELECTION_INTEGRITY','SUFFIX_LABEL_AUDIT','SOURCE_CLOSURE_AUDIT','ACTIVATION_CHAIN_COMPONENTS','BASELINE_RUNTIME_ROUTE_EQUIVALENCE','AUDIT_COMPUTE_RECONCILIATION']
 for name in names:
  d=json.loads((STUDY/'reports'/(name+'.json')).read_text());small={k:v for k,v in d.items() if not isinstance(v,(list,dict))};small['collection_sizes']={k:len(v) for k,v in d.items() if isinstance(v,(list,dict))}
  for k in ['aggregate','aggregates','groups','summary']:
   if k in d and len(json.dumps(d[k]))<12000:small[k]=d[k]
  if name=='HOST_QUALIFICATION_SUMMARY':small['new_B_route_rows']=[{k:v for k,v in r.items() if k in ('id','status','error','abort_reason','pre_task_requests','task_requests','task_activated','task_over55')} for r in d['rows'] if r['id'].startswith(('321_','322_','323_','324_'))]
  print(name+': '+json.dumps(small,ensure_ascii=False))
 d=json.loads((STUDY/'delivery/ACTOR_SOURCE_RETENTION_MANIFEST.json').read_text());print('RETENTION: '+json.dumps(dict(files=len(d['files']),references=len(d['attempt_references']),bytes=d['total_bytes'])))
 host=json.loads((STUDY/'reports/HOST_QUALIFICATION_SUMMARY.json').read_text())
 for run in host['rows']:
  for request in run['full_timelines']:
   if request['stage']=='TASK' and request.get('outcome')=='ACTIVATED' and request.get('activation_age_ms',100)<55:
    p=STUDY/'output'/(run['id']+'_SELECTIONS.json');sels=json.loads(p.read_text()).get('rows',[]) if p.exists() else [];matches=[s for s in sels if s['request_id']==request['request_id']]
    print('UNDER55: '+json.dumps(dict(id=run['id'],method=run['method'],request=request,selection=[{k:s.get(k) for k in ('request_id','count_before','late_discard','selected_source','plan_changed','applied_plan','applied_action')} for s in matches]),ensure_ascii=False))
if __name__=='__main__':main()
