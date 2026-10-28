from task_bootstrap import *
import numpy as np,gzip
def header_requests(path):
 from stream_runtime_evidence import array_items
 return list(array_items(path,'requests'))
def main():
 prefix=sys.argv[1] if len(sys.argv)>1 else '';rows=[]
 for p in sorted((STUDY/'output').glob(prefix+'*_RESULT.json')):
  r=json.loads(p.read_text());id=r['id'];m=r.get('metric',{});profile=STUDY/'output'/(id+'_TIMING_PROFILE.json');prof=json.loads(profile.read_text()) if profile.exists() else {}
  folder=STUDY/'source/results'/id;sp=folder/'summary.json';summary=json.loads(sp.read_text()) if sp.exists() else {}
  requests=summary.get('timing',{}).get('requests',[])
  if not requests and (folder/'runtime_artifacts.json.gz').exists():requests=header_requests(folder/'runtime_artifacts.json.gz')
  task=[q for q in requests if q.get('stage')=='TASK'];sel=STUDY/'output'/(id+'_SELECTIONS.json');selections=json.loads(sel.read_text()).get('rows',[]) if sel.exists() else []
  lat=[s['end_to_end_s']*1000 for s in selections];ages=[q['activation_age_ms'] for q in task if q.get('activation_age_ms') is not None]
  row=dict(id=id,mode=r['inputs'].get('execution_mode'),method=r['inputs'].get('method'),timing_version=r['inputs'].get('timing_version'),status=r['status'],valid=m.get('valid'),task_status=m.get('status'),abort_reason=summary.get('abort_reason'),J_F_unranked=m.get('J_F'),task_requests=task,profile_summary=prof.get('summary'),coordinator_ms=dict(p50=float(np.quantile(lat,.5)),p90=float(np.quantile(lat,.9)),p95=float(np.quantile(lat,.95)),max=max(lat)) if lat else None,activation_age_ms=ages,selection_late_discard=sum(s['late_discard'] for s in selections),learning_selected_plan_changes=sum(s['plan_changed'] and not s['late_discard'] for s in selections),full_request_activation_source='original write-once lifecycle timestamps; actual conservative receipt activation; no restamping',error=r.get('error'))
  rows.append(row)
 save(STUDY/('TIMING_PROFILE'+('_'+prefix if prefix else '')+'.json'),dict(rows=rows,bridge_ms=40,evaluator_activation_ms=55,generic_expiration_ms=100,nested_profile_not_additive=True))
 for r in rows:
  print(json.dumps({k:r[k] for k in ('id','valid','abort_reason','coordinator_ms','activation_age_ms','selection_late_discard')}))
  for q in r['task_requests']:print(json.dumps({k:q.get(k) for k in ('request_id','acquisition_to_request_ms','snapshot_ms','queue_ms','compute_ms','worker_to_main_scheduling_ms','validation_and_command_construction_ms','activation_age_ms','disposition_age_ms','outcome','reason')}))
if __name__=='__main__':main()
