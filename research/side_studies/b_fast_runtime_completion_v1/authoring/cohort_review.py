from pathlib import Path
import sys,json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import host_review
group=sys.argv[1];dispatch=json.loads((S/'reports'/(group+'_DISPATCH.json')).read_text());out=[]
for row in dispatch['rows']:
 ident=row['id'];sys.argv=[host_review.__file__,ident];host_review.main()
 r=json.loads((S/'reports'/(ident+'_FUNCTIONAL.json')).read_text());l=r.get('legacy_result',{})
 out.append(dict(id=ident,seed=row['config']['seed'],pid=row['interpreter_pid'],ordinal=row['interpreter_ordinal'],worker_status=row['worker_status'],functional=r['functional'],strict=r.get('legacy_strict'),checks=r.get('functional_checks'),phase_durations=l.get('phase_durations'),activation_age_ms=l.get('activation_age_ms'),meaningful_plans=l.get('physically_executed_meaningful_count'),service_gap_ms=r.get('service_gap_ms'),rolling_1s_mean_ms=r.get('rolling_1s_mean_ms'),wall_physics=r.get('wall_physics'),steps=r.get('actual_native_steps'),expired_writes=r.get('expired_actual_write_receipts'),causal_violations=r.get('causal_violations'),compute=row['compute']))
result=dict(id=group,status='REVIEWED',registered_runs=len(dispatch['rows']),same_interpreter=dispatch['same_interpreter'],physical_session_continuous=False,rows=out,all_functional=bool(len(out)==4 and all(x['functional']=='PASS' for x in out)),M2_eligible=False,unix=time.time(),scope='Frozen full B engineering repetitions; original failures preserved, no qualification from timing alone.')
(S/'reports'/(group+'_REVIEW.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
