from audit_common import *
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np,importlib.util
spec=importlib.util.spec_from_file_location('frozen_clock_networks',OLD/'code/inference.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def main():
 rows=[]
 for case in read(STUDY/'AUDIT_CONTRACT.json')['cases']:
  pool=STUDY/'output'/(case['state']+'_POOL.json')
  if not pool.exists():continue
  net=mod.Networks(case['weights'])
  for item in read(pool)['rows']:
   source=item['item']['committed_source']
   if not source:continue
   data=read(source);terminal=item['KNOWN']['prediction']['terminal'];x=np.asarray(terminal['feature'],np.float32)
   matches=[r for r in data['value_rows'] if 'input' in r and r['count']==terminal['count'] and r['context']['phase']==terminal['phase']]
   if not matches:rows.append(dict(identity=item['item']['identity'],event_match_available=False,model_terminal=terminal));continue
   actual=min(matches,key=lambda r:float(np.mean((np.asarray(r['input'])[4:8]-x[4:8])**2))+abs(r['context']['task_s']-terminal['task_s'])*1e-6)
   y=np.asarray(actual['input'],np.float32).copy()
   for i,phase in enumerate(('OUTBOUND','RETURN')):y[58:88].reshape(2,5,3)[i,:actual['count'][phase]]=0.
   rows.append(dict(identity=item['item']['identity'],event_match_available=True,matching_rule='same phase and counts, closest reference; event boundary is a receipt/prefetch request, not guaranteed same physical clock/state as analytic terminal',model_task_s=terminal['task_s'],actual_native_boundary_task_s=actual['context']['task_s'],clock_difference_s=terminal['task_s']-actual['context']['task_s'],model_terminal=terminal,actual_context=actual['context'],normalized_state_difference=(x[:4]-y[:4]).tolist(),normalized_reference_difference=(x[4:8]-y[4:8]).tolist(),normalized_wrench_difference=(x[31:37]-y[31:37]).tolist(),synthetic_deltaV=net.value(x),actual_native_deltaV=net.value(y),actual_native_deltaV_target=actual['deltaV_label'],actual_native_V_base=actual['V_base'],original_model_terminal_V_base=item['KNOWN']['V_base'],actual_node_inference_error_Ns=net.value(y)-actual['deltaV_label'],do_not_treat_event_matching_as_exact_state_target_equality=True))
 save(STUDY/'EVENT_CLOCK_ALIGNMENT.json',dict(rows=rows,verdict='analytic clocks and native request event clocks are separate; labels use exact actual request clock; model terminal is a synthetic state. This source-level approximation is not by itself a label off-by-one proof'))
 print(json.dumps(dict(event_matches=sum(r['event_match_available'] for r in rows),clock_differences_s=[r['clock_difference_s'] for r in rows if r['event_match_available']])))
if __name__=='__main__':main()
