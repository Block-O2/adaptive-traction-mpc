from pathlib import Path
import sys,json,time,hashlib,gzip
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_t_second_round_coordination_v1')
sys.path.insert(0,str(S/'code'))
import numpy as np
def quantile(xs):
 xs=[x for x in xs if x is not None]
 return dict(n=len(xs),**{k:float(np.quantile(xs,q)) if xs else None for k,q in [('p50',.5),('p90',.9),('p95',.95),('p99',.99),('max',1.)]})
def summarize(ident):
 p=S/'output'/(ident+'_RESULT.json');result=json.loads(p.read_text());e=S/'output'/(ident+'_MULTIRATE.json')
 ev=json.loads(e.read_text()) if e.exists() else {};rows=ev.get('rows',{});fast=rows.get('fast',[])
 starts=[r['service_start_ns'] for r in fast];gaps=[(y-x)/1e6 for x,y in zip(starts,starts[1:])];compute=[(r['service_finish_ns']-r['service_start_ns'])/1e6 for r in fast if r['service_finish_ns'] is not None]
 skipped=sum(r['skipped_periods'] for r in fast);requests=ev.get('native_requests',[]);task=[r for r in requests if r['stage']=='TASK']
 out=dict(id=ident,status=result['status'],error=result.get('error'),execution_mode=result['inputs']['execution_mode'],host_qualification_applicable=result['inputs']['execution_mode']=='REALTIME_CHARACTERIZATION',metric=result.get('metric'),service_gap_ms=quantile(gaps),service_compute_ms=quantile(compute),lateness_ms=quantile([r['lateness_ns']/1e6 for r in fast]),skipped_periods=skipped,miss_rate=skipped/(len(fast)+skipped) if fast else None,compute_over_5ms_rate=sum(x>5 for x in compute)/len(compute) if compute else None,planner_compute_ms=quantile([r.get('compute_ms') for r in task]),planner_queue_ms=quantile([r.get('queue_ms') for r in task]),activation_age_ms=quantile([r.get('activation_age_ms') for r in task if r['outcome']=='ACTIVATED']),request_outcomes={k:sum(r['outcome']==k for r in task) for k in set(r['outcome'] for r in task)},task_requests=len(task),admission_ms=quantile([(r['revalidation_finish_ns']-r['revalidation_start_ns'])/1e6 for r in rows.get('admission',[])]),commissioning_ms=quantile([(r['estimate_ready_ns']-r['data_available_ns'])/1e6 for r in rows.get('commissioning',[])]))
 summary=S/'source/results'/ident/'summary.json'
 if summary.exists():
  native=json.loads(summary.read_text());out['native_execution_mode']=native.get('execution_mode');out['native_qualification']=native.get('qualification');out['task']=native.get('task');out['safety_mode_counts']=native.get('safety_mode_counts')
  decisions=native.get('decisions',[]);out['meaningful_executed']=int(sum(bool(r.get('plan_activated')) and r.get('phase') in ('OUTBOUND','RETURN') and np.any(np.abs(r.get('executed_action_delta_q_rad',[0,0]))>1e-12) for r in decisions))
 groups={}
 for stage in set(r['phase'] for r in fast):
  rs=[r for r in fast if r['phase']==stage];ss=[r['service_start_ns'] for r in rs];sk=sum(r['skipped_periods'] for r in rs)
  groups[stage]=dict(service_gap_ms=quantile([(y-x)/1e6 for x,y in zip(ss,ss[1:])]),n=len(rs),skipped_periods=sk,miss_rate=sk/(len(rs)+sk))
 out['stages']=groups
 (S/'reports'/(ident+'_AUDIT.json')).write_text(json.dumps(out,indent=2)+'\n')
 return {k:out[k] for k in ('id','status','error','service_gap_ms','service_compute_ms','miss_rate','task_requests','planner_compute_ms','activation_age_ms')}
def gate(version,nominal,deviation):
 from full_native_equivalence import full_compare
 rows=[full_compare(a,b) for a,b in [('012_BASE_nominal',nominal),('013_BASE_deviation',deviation)]]
 out=dict(revision=version,status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',rows=rows,tolerance=1e-10,pre_registered=True,scope='Full 0.25ms native physics arrays/contact, 5ms trace, references, metrics, selected native decisions/fallback/phase/safety')
 (S/'versions'/(version+'_SCIENTIFIC_GATE.json')).write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps(dict(revision=version,status=out['status'],rows=[dict(status=r['status'],issues=r['issues'],physical_exact=r['full_native_step_signature_exact']) for r in rows])),flush=True)
if __name__=='__main__':
 if sys.argv[1]=='gate':gate(*sys.argv[2:])
 else:
  for ident in sys.argv[1:]:print(json.dumps(summarize(ident)),flush=True)
