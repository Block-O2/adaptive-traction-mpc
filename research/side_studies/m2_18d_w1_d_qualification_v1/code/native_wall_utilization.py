"""Original native-step/catch-up timing attribution; no forward computation."""
from task_bootstrap import *
from stream_runtime_evidence import array_items
from causal_timing_report import quantile
from collections import defaultdict
def main():
 import runner
 host=json.loads((STUDY/'reports/HOST_QUALIFICATION_SUMMARY.json').read_text());rows=[];start=time.time();next_resource=start
 for run in host['rows']:
  id=run['id'];p=STUDY/'source/results'/id/'runtime_artifacts.json.gz';assert p.exists()
  intervals=list(array_items(p,'catchup_intervals'));intervals.sort(key=lambda r:r['host_start_ns']);inside=[0.]*len(intervals);counts=[0]*len(intervals);native=[];k=0
  assert all(a['host_end_ns']<=b['host_start_ns'] for a,b in zip(intervals,intervals[1:])),id+':OVERLAPPING_CATCHUP_SCOPES'
  for state in array_items(p,'native_states_evaluation_only'):
   if time.time()>=next_resource:runner.sample(filename='OFFLINE_RESOURCE_LOG.jsonl');next_resource=time.time()+45
   hs=state.get('host_step_start_ns');hf=state.get('host_step_finish_ns')
   if hs is None or hf is None:continue
   assert hf>=hs;elapsed=(hf-hs)/1e6;native.append(elapsed)
   while k<len(intervals) and hs>=intervals[k]['host_end_ns']:k+=1
   if k<len(intervals) and intervals[k]['host_start_ns']<=hs and hf<=intervals[k]['host_end_ns']:inside[k]+=elapsed;counts[k]+=1
  scopes=[]
  for j,r in enumerate(intervals):
   wall=(r['host_end_ns']-r['host_start_ns'])/1e6;residual=wall-inside[j];assert residual>=-1e-8
   scopes.append(dict(reason=r['reason'],native_steps=r['native_steps'],matched_native_timed_steps=counts[j],host_ms=wall,recorded_plant_step_and_small_receipt_bookkeeping_ms=inside[j],outside_recorded_step_ms=max(0.,residual),step_and_loop_budget_fraction=None if not r['native_steps'] else wall/(r['native_steps']*.25),remaining_backlog_ms=r['quantization_or_backlog_ns']/1e6,exception=r.get('exception')))
  active=[r for r in scopes if r['native_steps']>0];total_steps=sum(r['native_steps'] for r in active);total_wall=sum(r['host_ms'] for r in active);native_sum=sum(native)
  rows.append(dict(id=id,method=run['method'],timing_version=run['timing_version'],series=run['host_series'],actual_native_steps=len(native),recorded_native_step_ms=quantile(native),recorded_native_step_mean_ms=native_sum/len(native) if native else None,recorded_native_steps_over250us=sum(v>.25 for v in native),catchup_calls=len(scopes),nonempty_catchup_calls=len(active),catchup_integrated_steps=total_steps,steps_outside_catchup_scopes=len(native)-sum(counts),nonempty_catchup_host_ms=total_wall,matched_plant_step_ms=sum(inside),catchup_outside_recorded_step_ms=sum(r['outside_recorded_step_ms'] for r in active),catchup_compute_to_physical_duration_ratio=None if not total_steps else total_wall/(total_steps*.25),catchup_loop_fraction=quantile([r['step_and_loop_budget_fraction'] for r in active]),catchup_backlog_ms=quantile([r['remaining_backlog_ms'] for r in active]),full_task_valid=run['full_task_valid'],scopes=scopes))
  rows[-1]['public_version']=run.get('public_version') or 'unspecified'
  assert time.time()-start<900 and time.time()<START+8.25*3600,'BOUNDED_READ_ONLY_WALL_ATTRIBUTION'
 groups=defaultdict(list)
 for r in rows:groups[r['method']+'/'+r['timing_version']+'/'+r.get('public_version','unspecified')+'/'+r['series']].append(r)
 compact={key:dict(attempts=len(v),native_steps=sum(r['actual_native_steps'] for r in v),run_mean_native_step_ms=quantile([r['recorded_native_step_mean_ms'] for r in v if r['recorded_native_step_mean_ms'] is not None]),run_catchup_compute_ratio=quantile([r['catchup_compute_to_physical_duration_ratio'] for r in v if r['catchup_compute_to_physical_duration_ratio'] is not None])) for key,v in groups.items()}
 out=dict(status='READ_ONLY_ACTUAL_WALL_BUDGET_ATTRIBUTION',rows=rows,groups=compact,wall_seconds=time.time()-start,physics_added=0,new_model_predictions=0,registered_native_dt_ms=.25,registered_feedback_period_ms=5,scope='Original host_step_start/finish brackets plant.step_native and small receipt bookkeeping only. Catch-up residual includes original observer, state/contact copies after finish stamp, sensor capture, loop, stop checks and host interruption; it is not all evaluator-only logging. prepare_apply native steps outside catch_up are counted separately.',interpretation='All cohorts retain failed prefixes and different states/seeds. Ratios describe observed host resources; no causal speedup is asserted between unequal epochs, and zero denominator is N/A. No free physics pause or rewritten timestamp is introduced.')
 save(STUDY/'reports/NATIVE_WALL_UTILIZATION.json',out);print(json.dumps(dict(status=out['status'],attempts=len(rows),wall_seconds=out['wall_seconds'],groups=compact)))
if __name__=='__main__':main()
