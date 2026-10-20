"""Reconstruct held schedule completion from saved causal SCI boundaries."""
from task_bootstrap import *
import numpy as np
def main():
 import study_common as sc
 case,options=sc.load_case_options();rows=[]
 for prefix in ('210','211','212','213','220','221','222','223'):
  p=next((STUDY/'output').glob(prefix+'*_RESULT.json'));result=json.loads(p.read_text());id=result['id'];folder=STUDY/'source/results'/id;s=json.loads((folder/'summary.json').read_text());m=result['metric']
  with np.load(folder/'trace.npz') as z:
   times=z['time_s'];phase=z['task_phase'];stage=z['stage'];task_indices=np.flatnonzero(stage=='TASK');assert len(task_indices)
   ds=[d for d in s['decisions'] if d['phase']=='HOLD'];holds=[]
   for j,d in enumerate(ds):
    start=d['actual_schedule_start_physics_s'];duration=.5
    # 0.5 is the original selected HOLD schedule duration, checked below
    # against every matching recorded candidate schedule, not a new deadline.
    duration_records=[]
    def visit(x,path=''):
     if isinstance(x,dict):
      if 'duration_s' in x:duration_records.append(dict(path=path,duration_s=x['duration_s']))
      for k,v in x.items():visit(v,path+'/'+k)
     elif isinstance(x,list):
      for n,v in enumerate(x):visit(v,path+'/'+str(n))
    visit(d)
    selected=[x for x in duration_records if x['path'].startswith('/evaluations/')]
    assert selected and all(x['duration_s']==duration for x in selected),'HOLD_DURATION_NOT_FROZEN_HALF_SECOND'
    candidate_times=times[(times>=start-1e-10)&(times<start+duration+.02)]
    exact_tick=round(duration/.005);origin_tick=round(start/.00025)
    nominal_index=np.argmin(np.abs(candidate_times-(start+duration)));nominal=float(candidate_times[nominal_index]);elapsed=nominal-start;first_ready=next(float(t) for t in candidate_times if t-start>=duration-1e-12)
    after=s['task']['phase_transitions'][1]['time_s'] if j==len(ds)-1 else ds[j+1]['decision_request_time_s']
    holds.append(dict(index=j,start_physics_s=start,registered_duration_s=duration,selected_schedule_duration_evidence=selected,nominal_100_control_intervals_end_s=nominal,nominal_elapsed_s=elapsed,nominal_deficit_s=duration-elapsed,original_1e_12_completion_pass=elapsed>=duration-1e-12,first_clock_ready_s=first_ready,extra_control_intervals=round((first_ready-nominal)/.005),actual_next_request_or_phase_boundary_s=after,expected_one_extra_boundary_after_ready_s=first_ready+.005,actual_matches_ready_plus_one_tick=abs(after-(first_ready+.005))<1e-9))
  rows.append(dict(id=id,valid=m['valid'],HOLD_s=m['phase_durations']['HOLD'],recorded_keys=list(ds[0]),holds=holds,source_sha256=sha(folder/'summary.json')))
 out=dict(status='READ_ONLY_CAUSAL_CLOCK_RECONSTRUCTION',rows=rows,recovery_options=options,physics_attempts_added=0,no_clock_reset=True,no_threshold_changes=True,diagnostic_scope='Saved trace plus original 1e-12 completion arithmetic. This reconstructs boundary readiness; it does not counterfactually re-run the controller or certify a repair.')
 save(STUDY/'reports/R2_CLOCK_RECONSTRUCTION.json',out)
 print(json.dumps(dict(rows=[dict(id=r['id'],HOLD_s=r['HOLD_s'],holds=[{k:x[k] for k in ('nominal_deficit_s','original_1e_12_completion_pass','extra_control_intervals','actual_matches_ready_plus_one_tick')} for x in r['holds']]) for r in rows],receipt_reference_governor=options.get('receipt_reference_governor'),status=out['status'])))
if __name__=='__main__':main()
