"""Keep SCI coordinator and fast-prefix timings separate from actual activation."""
from task_bootstrap import *
from causal_timing_report import quantile
import numpy as np
def summarize(id):
 p=STUDY/'output'/(id+'_SELECTIONS.json')
 if not p.exists():return None
 s=json.loads(p.read_text()).get('rows',[])
 if not s:return None
 full=[r['end_to_end_s']*1000 for r in s];fast=[r.get('fast_coordinator_s',r['end_to_end_s'])*1000 for r in s];q=[r['Q_inference_s']*1000 for r in s]
 return dict(id=id,selection_rows=len(s),coordinator_ms=quantile(full),coordinator_mean_ms=float(np.mean(full)),fast_prefix_ms=quantile(fast),fast_prefix_mean_ms=float(np.mean(fast)),Q_inference_ms=quantile(q),selection_source_sha256=sha(p),scope='SCI coordinator elapsed includes full validation shadow where enabled; fast_prefix ends before proposal submission and excludes shadow. Neither is command activation latency.')
def main():
 rows=[]
 for p in sorted((STUDY/'versions').glob('*_FULL_NATIVE_EQUIVALENCE_GATE.json')):
  gate=json.loads(p.read_text())
  if gate['status']!='PASS':continue
  for case in gate['rows']:
   result=json.loads((STUDY/'output'/(case['optimized']+'_RESULT.json')).read_text())
   if result['inputs'].get('method')!='M2' or result['inputs'].get('prefix'):continue
   baseline=summarize(case['baseline']);optimized=summarize(case['optimized'])
   if baseline and optimized:rows.append(dict(version=gate['version'],gate_sha256=sha(p),scientific_native_signature_exact=case['full_native_step_signature_exact'],baseline=baseline,optimized=optimized))
 host=json.loads((STUDY/'reports/HOST_QUALIFICATION_SUMMARY.json').read_text());actual=[r for r in host['rows'] if r['id']=='117_host_cold_pair3_accelerated'];assert len(actual)==1
 out=dict(status='SCI_SCOPE_AND_ACTUAL_SCOPE_SEPARATED',rows=rows,actual_E5=dict(id=actual[0]['id'],coordinator_ms=actual[0]['coordinator_ms'],actual_activation_age_ms=actual[0]['TASK_timing']['activation_age_ms'],actual_learning_execution_proven=actual[0]['learning_execution_proven'],task_activated=actual[0]['task_activated'],late_discard=actual[0]['late_discard']),physics_added=0,interpretation='Scientific trajectories are paired by exact gate; host timing epochs differ and E6 SCI overlaps the recorded offline sweep. Ratios are descriptive observations, not randomized causal speedup estimates. Exact SCI acceleration is not actual qualification; the displayed E5 activations execute original zero carry after late proposals.')
 save(STUDY/'reports/ACCELERATION_LATENCY_SUMMARY.json',out);print(json.dumps(dict(status=out['status'],rows=[dict(version=r['version'],baseline_p50_ms=r['baseline']['coordinator_ms']['p50'],optimized_p50_ms=r['optimized']['coordinator_ms']['p50'],fast_prefix_p50_ms=r['optimized']['fast_prefix_ms']['p50']) for r in rows],actual_E5=out['actual_E5'])))
if __name__=='__main__':main()
