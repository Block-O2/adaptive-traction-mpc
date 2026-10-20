from pathlib import Path
import sys,json,shutil,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_control_learning_transition_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_jitter_m2_host_v1')
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
if sys.argv[1]=='diagnostic':
 shutil.copy2(W/'low_overhead_timing.py',S/'code/low_overhead_timing.py')
 p=S/'code/run_one.py';text=p.read_text();assert 'low_overhead_timing' not in text
 text=text.replace(" from native_method import PrefixBInterface"," if cfg.get('low_overhead_diagnostic'):\n  import low_overhead_timing\n  low_overhead_timing.install()\n from native_method import PrefixBInterface",1)
 text=text.replace("  fast_runtime.finish(ident)","  if cfg.get('low_overhead_diagnostic'):low_overhead_timing.finish(ident)\n  fast_runtime.finish(ident)",1);p.write_text(text)
 for idx,condition in [(6,'nominal'),(7,'deviation')]:
  cfg=json.loads((S/'queue/001_zero_residual_smoke.json').read_text());cfg.update(id=f'{idx:03d}_B_threadCPU_{condition}',low_overhead_diagnostic=True,attribution=True)
  # fast_attribution adds nested instrumentation if attribution=True; keep
  # its toggle false and identify this separate low-cost diagnostic explicitly.
  cfg['attribution']=False;cfg['attribution_only']=True
  cfg['prefix']={} if condition=='nominal' else dict(OUTBOUND=[[.2,.1,-.1],[.05,.15,.25]])
  save(S/'queue'/(cfg['id']+'.json'),cfg)
 save(S/'reports/DIAGNOSTIC_REGISTRATION.json',dict(unix=time.time(),max_extra_B_host_controls=2,per_service_thread_CPU=True,GC_callbacks=True,formal_FAST_benchmark=False,no_cProfile=True,controller_math_changes=False))
elif sys.argv[1]=='pairs':
 receipt=json.loads((S/'reports/017_M2_guard_off_export_retry_AXES.json').read_text())
 assert receipt['PHYSICAL_TASK_VALID']=='PASS' and receipt['HOST_EXECUTION_CAUSAL_VALID']=='PASS' and receipt['nonzero_execution_count']>0,'nonzero safe smoke required'
 base=json.loads((S/'queue/017_M2_guard_off_export_retry.json').read_text());pairs=[]
 for j,(condition,rep,order) in enumerate([('nominal',1,['M0','M2']),('nominal',2,['M2','M0']),('deviation',1,['M0','M2']),('deviation',2,['M2','M0'])]):
  names=[]
  for k,method in enumerate(order):
   ident=f'{8+2*j+k:03d}_{condition}_pair{rep}_{"B" if method=="M0" else "M2"}'
   cfg={**base,'id':ident,'method':method,'host_coordinator':True,'seed':2026100800+rep,'prefix':{} if condition=='nominal' else dict(OUTBOUND=[[.2,.1,-.1],[.05,.15,.25]]),'pair_id':condition+'_pair'+str(rep),'pair_condition':condition,'pair_replicate':rep,'low_overhead_diagnostic':False,'candidate_budget':6,'strict55_guard':False,'qualification_group':'PAIRED_HOST_RESEARCH'}
   save(S/'queue'/(ident+'.json'),cfg);names.append(ident)
  pairs.append(dict(pair_id=condition+'_pair'+str(rep),ids=names,seed=2026100800+rep))
 save(S/'reports/PAIR_REGISTRATION.json',dict(unix=time.time(),pairs=pairs,same_B_C13=True,matched_instrumentation=True,both_strict55_guard=False,physical_bridge_guard_ms=40,all_failures_retained=True,scope='matched development timing repeats; no independent Human/generalized claim'))
 print(json.dumps(pairs))
