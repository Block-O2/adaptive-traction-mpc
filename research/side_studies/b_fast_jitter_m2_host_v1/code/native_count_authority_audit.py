"""Read-only attempted-boundary counter vs actual native admission evidence."""
from task_bootstrap import *
from collections import Counter
def main():
 host=json.loads((STUDY/'reports/HOST_QUALIFICATION_SUMMARY.json').read_text());rows=[]
 for run in host['rows']:
  if run['method']!='M2':continue
  id=run['id'];path=STUDY/'output'/(id+'_SELECTIONS.json')
  if not path.exists():continue
  selections=json.loads(path.read_text()).get('rows',[]);requests=sorted([q for q in run['full_timelines'] if q['stage']=='TASK'],key=lambda q:q['request_ns']);by_id={q['request_id']:q for q in requests};local=[]
  for selection in selections:
   q=by_id.get(selection['request_id'],{});prior=[r for r in requests if r['request_ns']<q.get('request_ns',0)];phase=selection['context']['phase'];count=selection['count_before'][phase]
   local.append(dict(request_id=selection['request_id'],phase=phase,coordinator_count_before=count,registered_phase_slots=5,current_action_zero_by_count_mask=count>=5,prior_TASK_request_outcomes=dict(Counter(r['outcome'] for r in prior)),current_native_outcome=q.get('outcome'),late_discard=bool(selection.get('late_discard')),current_action_commit_not_inferred_from_count=True))
  rows.append(dict(id=id,timing_version=run['timing_version'],rows=local))
 source=STUDY/'code/native_method.py';text=source.read_text();worker=STUDY/'code/async_native_worker.py';wtext=worker.read_text();assert 'self.count[phase]+=1' in text and 'prior_counts=COORD.count.copy()' in wtext and 'COORD.carry=prior_carry.copy()' in wtext
 out=dict(status='ATTEMPTED_BOUNDARY_COUNTER_LIMITATION_IDENTIFIED',rows=rows,source_sha256=sha(source),worker_source_sha256=sha(worker),physics_added=0,Q_updates=0,authority_modified=False,source_contract='Frozen TableInterface/NativeInterface increments the coordinator per-phase count when choose/apply constructs a proposal, before original native activation. E5 saves prior_counts for the current carry action and restores prior carry on late guard, but does not transactionally roll back the count. A request cancelled/expired later can therefore consume a coordinator counter position. These are attempted modifiable-boundary counters in actual failed prefixes; they are not proof of physically executed graph slots.',interpretation='The SCI exact gates retain the original frozen feature/selection definition and original candidate authority. No count, mask, target, source timestamp or failed-prefix metric is rewritten. This limitation is reported separately from verified Q feature reconstruction. Transactional admission/accepted-action counter semantics would require an explicit design and new equivalence/authority review; it is not silently changed tonight. Count>=5 proves current action maps to zero, not that five learned actions executed.')
 save(STUDY/'reports/NATIVE_COUNT_AUTHORITY_AUDIT.json',out);print(json.dumps(dict(status=out['status'],M2_runs_with_selection_records=len(rows),selections=sum(len(r['rows']) for r in rows),zero_current_by_counter=sum(q['current_action_zero_by_count_mask'] for r in rows for q in r['rows']),authority_modified=False)))
if __name__=='__main__':main()
