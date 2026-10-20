from task_bootstrap import *
def main():
 for id in ('parent_dev_0_RETURN_1_candidate2_retry1','030_zero_context_repair','040_v1_0_nominal_a_M0'):
  paths=[STUDY/'output'/(id+'_RESULT.json'),STUDY/'output'/(id+'_DATA.json')]
  p=next((p for p in paths if p.exists()),None)
  if p is None:continue
  r=json.loads(p.read_text());m=r.get('metric',{});audit=m.get('physical_audit',{}).get('unchanged_evaluator',{})
  print(json.dumps(dict(id=id,status=r.get('status'),valid=m.get('valid'),J_F=m.get('J_F'),moment=m.get('moment_integral'),phase=m.get('phase_durations'),physical_result=audit.get('physical_task_result',{}).get('status'),scientific_result=audit.get('scientific_validity',{}).get('status'),scientific_reasons=audit.get('scientific_validity',{}).get('reasons'),Q_P_calls=r.get('P_full_performance_calls',r.get('P_full_performance_calls')),wall=r.get('wall_seconds'))))
 weights=json.loads((STUDY/'LATEST_WEIGHTS.json').read_text());t=json.loads((Path(weights['path'])/'TRAINING.json').read_text());parity=json.loads((Path(weights['path'])/'DEPLOYMENT_PARITY.json').read_text())
 out={k:t[k] for k in ('selected_Q','Q_counts','G_counts','wall_s','peak_host_RSS_bytes','cuda_peak_allocated_bytes')};out['parity']=parity;out['weights_sha256']=t['weights_sha256']
 print(json.dumps(out))
if __name__=='__main__':main()
