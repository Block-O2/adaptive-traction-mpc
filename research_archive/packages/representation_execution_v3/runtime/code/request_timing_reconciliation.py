"""Disjoint native monotonic event intervals, no CPU-time substitution."""
from task_bootstrap import *
from analyze_timing import header_requests
from causal_timing_report import quantile
from collections import defaultdict,Counter
def main():
 rows=[];groups=defaultdict(list);issues=[]
 for p in sorted((STUDY/'output').glob('*_RESULT.json')):
  r=json.loads(p.read_text());cfg=r.get('inputs',{});id=r['id']
  if cfg.get('execution_mode')!='REALTIME_CHARACTERIZATION':continue
  folder=STUDY/'source/results'/id;summary_path=folder/'summary.json';s=json.loads(summary_path.read_text()) if summary_path.exists() else {};artifact=folder/'runtime_artifacts.json.gz';qs=s.get('timing',{}).get('requests',[]) or (header_requests(artifact) if artifact.exists() else [])
  for q in qs:
   names=['sensor_capture_ns','request_ns','snapshot_finish_ns','enqueue_ns','worker_start_ns','compute_finish_ns','result_collected_ns','validation_start_ns','validation_finish_ns','activation_ns']
   events=[(n,q[n]) for n in names if q.get(n) is not None];terminal='ACTIVATION' if q.get('activation_ns') is not None else 'DISPOSITION'
   if terminal=='DISPOSITION':
    terminal_ns=q.get('disposition_ns');events=[e for e in events if terminal_ns is None or e[1]<=terminal_ns]
    if terminal_ns is not None:events.append(('disposition_ns',terminal_ns))
   segments=[]
   for (a,t0),(b,t1) in zip(events,events[1:]):
    dt=(t1-t0)/1e6;segments.append(dict(start=a,end=b,ms=dt))
    if dt<0:issues.append(dict(id=id,request=q['request_id'],start=a,end=b,ms=dt))
   extra=0.
   if terminal=='ACTIVATION':extra=(max(q['activation_ns'],q.get('effective_activation_ns',q['activation_ns']))-q['activation_ns'])/1e6
   age=q.get('activation_age_ms') if terminal=='ACTIVATION' else q.get('disposition_age_ms');summed=sum(x['ms'] for x in segments)+extra
   error=None if age is None else abs(summed-age)
   if error is not None and error>1e-8:issues.append(dict(id=id,request=q['request_id'],age_reconstruction_error_ms=error))
   row=dict(id=id,method=cfg.get('method'),timing_version=cfg.get('timing_version'),host_series=cfg.get('host_series','cold'),request_id=q['request_id'],stage=q['stage'],first_TASK_request=(q['stage']=='TASK' and q['request_id']==min(z['request_id'] for z in qs if z['stage']=='TASK')),outcome=q.get('outcome'),reason=q.get('reason'),terminal=terminal,age_ms=age,event_intervals=segments,effective_activation_extra_ms=extra,reconstruction_error_ms=error,source_capture_ns=q['sensor_capture_ns'],request_ns=q['request_ns'],source_sample_time_s=q['source_sample_time_s'],legacy_fields={k:q.get(k) for k in ('snapshot_ms','queue_ms','compute_ms','validation_and_command_construction_ms','worker_to_main_scheduling_ms')})
   available_age=(q['request_ns']-q['sensor_capture_ns'])/1e6
   row.update(immutable_source_to_request_available_ms=available_age,request_available_to_actual_terminal_ms=None if age is None else age-available_age,source_stamp_role='Original fixed wall epoch mapping of physical sensor sample; actual host materialization is separately retained in original artifact')
   rows.append(row);key='/'.join((str(cfg.get('method')),str(cfg.get('timing_version')),q['stage'],'firstTASK' if row['first_TASK_request'] else 'later_or_preTASK'));groups[key].append(row)
 compact={}
 for key,rs in groups.items():
  labels=set((v['start'],v['end']) for row in rs for v in row['event_intervals']);compact[key]=dict(n=len(rs),outcomes=dict(Counter(row['outcome'] for row in rs)),age_ms=quantile([row['age_ms'] for row in rs if row['age_ms'] is not None]),intervals={a+'__'+b:quantile([x['ms'] for row in rs for x in row['event_intervals'] if (x['start'],x['end'])==(a,b)]) for a,b in sorted(labels)})
 out=dict(status='PASS' if not issues else 'TIMESTAMP_ORDER_DIAGNOSTIC',request_count=len(rows),groups=compact,rows=rows,issues=issues,deadline_contract=dict(bridge_ms=40,strict_evaluator_ms=55,generic_expiry_ms=100),physics_added=0,interpretation='Each row uses consecutive immutable native events; sums exactly reconstruct conservative activation or disposition age. Nested profiling is excluded. Snapshot interval includes any research decision performed before snapshot_finish, so cannot be described as pure serialization. Failed request workers may finish after disposition; late work is excluded from the disposition path and retained in native raw records. First TASK request runs in an already prewarmed native process; this is first causal snapshot transport, not cold interpreter import.')
 save(STUDY/'reports/REQUEST_TIMING_RECONCILIATION.json',out);print(json.dumps(dict(status=out['status'],request_count=len(rows),issues=issues,groups=compact)))
if __name__=='__main__':main()
