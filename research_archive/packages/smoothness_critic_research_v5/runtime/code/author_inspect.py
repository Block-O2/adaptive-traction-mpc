from pathlib import Path
import json,sys,os
S=Path('/home/hank/ihear-lab/smoothness_critic_research_v5/runtime');OLD=S.parent/'b_hold_return_critical_path_v1'
if sys.argv[1]=='old':
 ledger=json.loads((OLD/'TASK_LEDGER.json').read_text())
 for ident in ('047_C13_host_nominal_quiet','048_C13_host_deviation_quiet'):
  r=ledger[ident];res=json.loads((OLD/'output'/(ident+'_RESULT.json')).read_text());print(json.dumps(dict(id=ident,wall=r.get('wall_seconds'),metric_keys=list(res['metric']),physical=res['metric']['physical_audit'],prefix=res['inputs']['prefix']),indent=2))
elif sys.argv[1]=='sources':
 for name in ('online_planning.py','activation_validation.py'):
  p=S/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1'/name
  for i,line in enumerate(p.read_text().splitlines(),1):
   if any(x in line for x in ('55','100','expire','fallback','_warm_planner_process')):print(name,i,line)
elif sys.argv[1]=='progress':
 print((S/'STATE.json').read_text())
 for p in sorted((S/'logs').glob('*.log')):print(p.name,p.stat().st_size,p.read_text()[-1800:])
elif sys.argv[1]=='performance':
 for ident in sys.argv[2:]:
  f=json.loads((S/'reports'/(ident+'_FUNCTIONAL.json')).read_text());a=json.loads((S/'reports'/(ident+'_AUDIT.json')).read_text())
  print(json.dumps(dict(id=ident,rolling=f.get('rolling_1s_mean_ms'),gap_fraction=f.get('gap_over_10_fraction'),miss=a['miss_rate'],service_compute=a['service_compute_ms'],stages=a['stages']),indent=2))
 p=S/'RESOURCE.jsonl'
 print('resource_files',[str(p) for p in S.glob('*RESOURCE*')])
elif sys.argv[1]=='close_schema':
 import numpy as np
 ident='005_B_quiet_retest_deviation'
 z=np.load(S/'source/results'/ident/'trace.npz');print('TRACE',[(k,z[k].shape) for k in z.files if any(x in k for x in ('phase','time','force','moment','tracking','error','stage'))])
 s=json.loads((S/'source/results'/ident/'summary.json').read_text());print('SUMMARY',list(s));print('TASK',s['task'].get('phase_transitions'));print('FALLBACK',s.get('fallback_events',[])[:2])
 d=json.loads((S/'output'/(ident+'_DIRECT_IPC.json')).read_text());print('IPC',list(d));print('JOIN',str(d)[-600:])
 for p in sorted((S/'reports').glob('*_RUNTIME_QUALIFICATION.json')):
  r=json.loads(p.read_text());f=json.loads((S/'reports'/(r['id']+'_FUNCTIONAL.json')).read_text());print('AGE',r['id'],f['legacy_result']['activation_age_ms'])
