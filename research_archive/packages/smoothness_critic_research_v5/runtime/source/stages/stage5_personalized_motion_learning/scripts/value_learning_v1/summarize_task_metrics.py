"""Expose secondary task metrics separately; none enter the scalar value target."""
import json
from research_campaign import D,RUNS,OLD,save,sha

KEYS=('J_F_task_n_s','mean_force_n','rms_force_n','peak_force_n','moment_integral_nm_s','moment_peak_nm','duration_s','minimum_clearance_m','dq_rms_rad_s','ddq_rms_rad_s2')
def main():
 selected=[]
 for name in ('BEST_KNOWN_REFERENCE_TABLE.json','NATIVE_BEST_KNOWN_REFERENCE_TABLE.json'):
  table=json.loads((D/name).read_text())
  selected += [(row['best_run_id'],name) for row in table['rows']]
 pilot=json.loads((D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json').read_text())
 selected += [(row['run_id'],session['mode']) for session in pilot['sessions'] for row in session['rows']]
 rows=[]
 for run_id,role in selected:
  path=RUNS/run_id/'rollout_result.json'
  if not path.exists():path=OLD/run_id/'rollout_result.json'
  record=json.loads(path.read_text());valid=record['status']=='VALID'
  rows.append({'run_id':run_id,'role':role,'condition':record['condition_id'],'status':record['status'],
   'result_sha256':sha(path),'metrics':{key:record.get(key) if valid else None for key in KEYS},
   'invalid_task_does_not_receive_a_good_truncated_metric':not valid})
 save(D/'SUPPLEMENTARY_TASK_METRICS.json',{'status':'COMPLETE','rows':rows,
  'primary_target':'only measured TASK cuff force-norm integral, existing registered5ms left endpoint accounting',
  'secondary_metrics_not_weighted_into_reward':True,
  'smoothness_proxy':'per-joint RMS actual Human dq and ddq over TASK samples, existing trace_metrics definition; acceleration RMS is a descriptive smoothness proxy, not a jerk certificate or safety guarantee',
  'physical_acceleration_is_evaluation_only_not_value_input':True})

if __name__=='__main__':main()
