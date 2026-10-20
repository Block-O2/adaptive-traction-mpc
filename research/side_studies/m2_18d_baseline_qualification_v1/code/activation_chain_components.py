"""Non-additive original profile events joined to native validation windows."""
from task_bootstrap import *
from causal_timing_report import quantile
from collections import defaultdict

def union_length(intervals):
 total=0;right=None
 for left,end in sorted(intervals):
  if right is None or left>right:total+=end-left;right=end
  elif end>right:total+=end-right;right=end
 return total

def main():
 host=json.loads((STUDY/'reports/HOST_QUALIFICATION_SUMMARY.json').read_text());rows=[];missing=[]
 categories=[('CURRENT_MODEL_REVALIDATION',{'rolling_revalidation','activation_revalidation'}),('PREPARED_RECEIPT_CATCHUP',{'receipt_prepare'}),('OTHER_NATIVE_CATCHUP',{'physics_catch_up'}),('ACTUAL_COMMAND_WRITE',{'actual_command_apply'})]
 for run in host['rows']:
  id=run['id'];path=STUDY/'output'/(id+'_TIMING_PROFILE.json')
  if not path.exists():missing.append(id);continue
  profile=json.loads(path.read_text());events=profile.get('events',[])
  if not events:missing.append(id);continue
  for q in run['full_timelines']:
   left=q.get('validation_start_ns');right=q.get('activation_ns') or q.get('validation_finish_ns') or q.get('disposition_ns')
   if left is None or right is None or right<left:continue
   clips=defaultdict(list);matched=[]
   for event in events:
    a=max(left,event['start_ns']);b=min(right,event['finish_ns'])
    if b<=a:continue
    matched.append(dict(name=event['name'],parent=event.get('parent'),clipped_elapsed_ms=(b-a)/1e6,original_event_start_ns=event['start_ns'],original_event_finish_ns=event['finish_ns'],thread=event.get('thread'),error=event.get('error')))
    for label,names in categories:
     if event['name'] in names:clips[label].append((a,b))
   boundaries=sorted({left,right,*[v for values in clips.values() for pair in values for v in pair]});exclusive=defaultdict(int)
   for a,b in zip(boundaries,boundaries[1:]):
    label=next((label for label,_ in categories if any(x<=a and b<=y for x,y in clips[label])),'UNPROFILED_NATIVE_COMMAND_CHECKS_AND_CONSTRUCTION')
    exclusive[label]+=b-a
   total=(right-left)/1e6;pieces={label:ns/1e6 for label,ns in exclusive.items()};assert abs(sum(pieces.values())-total)<1e-10
   mechanics=union_length([(max(left,e['start_ns']),min(right,e['finish_ns'])) for e in events if e['name']=='mechanics' and min(right,e['finish_ns'])>max(left,e['start_ns'])])/1e6
   rows.append(dict(id=id,method=run['method'],timing_version=run['timing_version'],public_version=run['public_version'],series=run['host_series'],request_id=q['request_id'],stage=q['stage'],outcome=q['outcome'],window_start_ns=left,window_end_ns=right,window_elapsed_ms=total,exclusive_ms=pieces,inclusive_mechanics_inside_window_ms=mechanics,inclusive_mechanics_not_added_to_exclusive_total=True,profile_sha256=sha(path),matched_events=matched))
 groups=defaultdict(list)
 for row in rows:groups[row['method']+'/'+row['timing_version']+'/'+str(row['public_version'])+'/'+row['stage']].append(row)
 compact={key:dict(n=len(v),window_elapsed_ms=quantile([r['window_elapsed_ms'] for r in v]),exclusive_components_ms={label:quantile([r['exclusive_ms'].get(label,0.) for r in v]) for label in [x[0] for x in categories]+['UNPROFILED_NATIVE_COMMAND_CHECKS_AND_CONSTRUCTION']},inclusive_mechanics_ms=quantile([r['inclusive_mechanics_inside_window_ms'] for r in v])) for key,v in groups.items()}
 out=dict(status='ORIGINAL_PROFILE_WINDOW_RECONCILED',rows=rows,groups=compact,unprofiled_or_disabled_run_ids=missing,physics_added=0,no_control_edits=True,interpretation='Validation_start through real activation (or actual failure disposition) is one disjoint event window. Wrapper intervals are clipped, unioned and partitioned with explicit precedence; nested rolling/activation/mechanics durations are never summed twice. Unprofiled time retains command construction/checks, host interruptions and instrumentation overhead. E6/E7 deliberately disabled these research wrappers, so missing profiles are censored, not zero latency. Failed disposition windows include original error handling and are not successful deployment latency.')
 save(STUDY/'reports/ACTIVATION_CHAIN_COMPONENTS.json',out);print(json.dumps(dict(status=out['status'],windows=len(rows),unprofiled_runs=len(missing),selected_groups={k:v for k,v in compact.items() if k in ('M0/T0/None/TASK','M0/T0/None/COMMISSIONING','M2/E5_HOST_v1/None/TASK')})))
if __name__=='__main__':main()
