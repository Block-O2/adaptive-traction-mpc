from pathlib import Path
import json,sys
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');ident=sys.argv[1]
s=json.loads((S/'source/results'/ident/'summary.json').read_text());m=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text());h=json.loads((S/'output'/(ident+'_CRITICAL_TRACE.json')).read_text())['rows'];e=json.loads((S/'output'/(ident+'_HOLD_ENDPOINT_HANDOFF.json')).read_text())['rows']
t=s['task']['phase_transitions'];start=next(r['time_s'] for r in t if r['to']=='HOLD');end=next(r['time_s'] for r in t if r['from']=='HOLD')
ds=[d for d in s['decisions'] if d.get('phase')=='HOLD'];ds.append(next(d for d in s['decisions'] if d.get('phase')=='RETURN'))
requests=[r for r in m['native_requests'] if r['request_id'] in {d['timing_request_id'] for d in ds}]
firstdwell=next(r for r in h if r['event']=='ACTUAL_SENSOR_DWELL_CHECK' and r['proposed_phase']=='RETURN');allowed=next(r for r in h if r['event']=='ACTUAL_SHARED_MINIMUM_CHECK' and r['allowed'])
postmin=[r for r in h if r['event']=='ACTUAL_GUARDED_HOLD_RETURN_CHECK' and r['before_phase_elapsed_s']>=1.-1e-10]
out=dict(id=ident,HOLD_s=end-start,HOLD_entry=start,HOLD_exit=end,first_dwell=firstdwell,first_actual_minimum_allow=allowed,post_minimum_guard_checks=postmin,endpoint_services=e,decisions=[{k:d.get(k) for k in ('phase','timing_request_id','decision_request_time_s','actual_schedule_start_physics_s','phase_elapsed_s')} for d in ds],requests=requests)
(S/'reports'/(ident+'_EXACT_TRANSITION.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
