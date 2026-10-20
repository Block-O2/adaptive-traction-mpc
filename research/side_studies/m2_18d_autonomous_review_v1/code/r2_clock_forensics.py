"""Read-only reconstruction of persistent SCI schedule boundary arithmetic."""
from task_bootstrap import *
import numpy as np
def main():
 rows=[]
 for prefix in ('210','211','212','213','220','221','222','223'):
  path=next((STUDY/'output').glob(prefix+'*_RESULT.json'));r=json.loads(path.read_text());id=r['id'];folder=STUDY/'source/results'/id;s=json.loads((folder/'summary.json').read_text());m=r['metric']
  with np.load(folder/'trace.npz') as z:
   fields={k:dict(shape=z[k].shape,dtype=str(z[k].dtype),first=z[k][:2].tolist()) for k in z.files}
   times=z['time_s'] if 'time_s' in z else z['time'];ticks=np.diff(times)
   phases=z['task_phase']
   changes=[]
   if phases is not None:
    for i in range(1,len(times)):
     if phases[i]!=phases[i-1]:changes.append(dict(index=i,time=float(times[i]),previous_time=float(times[i-1]),before=str(phases[i-1]),after=str(phases[i])))
  decisions=[]
  for d in s['decisions']:
   decisions.append({k:v for k,v in d.items() if k in ('phase','decision_request_time_s','activation_timestamp_s','proposed_activation_timestamp_s','executed_label','actual_schedule_start_physics_s','executed_duration_s') or 'duration' in k})
  rows.append(dict(id=id,summary_sha256=sha(folder/'summary.json'),trace_sha256=sha(folder/'trace.npz'),task=s['task'],durations=m['phase_durations'],valid=m['valid'],trace_fields=fields,trace_phase_changes=changes,tick_min=float(ticks.min()),tick_max=float(ticks.max()),decisions=decisions))
 save(STUDY/'reports/R2_CLOCK_FORENSICS_RAW.json',dict(status='READ_ONLY_DIAGNOSTIC',rows=rows,physics_added=0,control_changes=0))
 print(json.dumps(dict(rows=[dict(id=r['id'],durations=r['durations'],transitions=r['task']['phase_transitions'],hold_decisions=[d for d in r['decisions'] if d['phase']=='HOLD'],decision_count=len(r['decisions'])) for r in rows])))
if __name__=='__main__':main()
