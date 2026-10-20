from pathlib import Path
import sys,json,gzip,pickle
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_w1_d_qualification_v1')
sys.dont_write_bytecode=True;sys.path.insert(0,str(S/'code'))
def main():
 mode=sys.argv[1]
 if mode=='attempt':
  ident=sys.argv[2]
  for rel in ['output/'+ident+'_HOST_COORDINATOR.json','source/results/'+ident+'/summary.json']:
   p=S/rel
   if not p.exists():continue
   x=json.loads(p.read_text())
   if 'HOST_COORDINATOR' in rel:
    print('COORD',len(x['rows']),len(x['hints']))
    for e in x['rows']:
     s=e.get('selection_row');print('SELECT',e['request_id'],e['worker_elapsed_ms'],e['source_age_at_worker_return_ms'],e['admission'],None if s is None else [s['selected_source'],s['selected_index'],s['count_before'],s['late_discard']])
   else:
    print('SUMMARY',x.get('status'),x.get('abort_reason'),'DECISIONS',len(x.get('decisions',[])),'LEARNING',len(x.get('learning_records',[])))
    for r in x.get('decisions',[])[:2]:print('DEC',list(r),{k:r[k] for k in r if 'screen' in k or 'coord' in k or k in ['phase','timing_request_id']})
    for r in x.get('learning_records',[])[:2]:print('LEARN',list(r),{k:r[k] for k in r if k!='selected_plan'})
 elif mode=='history_compact':
  x=json.loads((S/'reports/HISTORICAL_JITTER_ATTRIBUTION.json').read_text())
  print('SOURCE_DIFF',x['source_nonrelocation_differences']);print('CONFIG_DIFF',x['config_differences']);print('BINARY_EQUAL',x['native_binary_old']==x['native_binary_new'])
  for r in x['rows']:print(r['id'],'phase',r['phase_condition_gap_ms'])
 elif mode=='schemas':
  for folder,ident in [(S.parent/'b_hold_return_critical_path_v1','047_C13_host_nominal_quiet'),(S.parent/'b_runtime_qualification_decoupling_v1','005_B_quiet_retest_deviation')]:
   ev=json.loads((folder/'output'/(ident+'_MULTIRATE.json')).read_text())
   print(ident,'TOP',list(ev),'ROW',list(ev['rows']))
   for key in ev['rows']:
    rows=ev['rows'][key];print(key,len(rows),rows[:1])
   print('REQ',ev['native_requests'][:1])
   artifact=folder/'source/results'/ident/'runtime_artifacts.json.gz'
   from stream_runtime_evidence import array_items
   for key in ['command_receipts','native_states_evaluation_only']:
    print(key,next(array_items(artifact,key)))
 elif mode=='saved':
  old=S.parent/'b_native_q_realtime_integration_v1'
  for p in sorted((old/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))[:3]:
   x=pickle.loads(p.read_bytes());print(p,list(x));print('CONTEXT',x.get('context'));print('COUNT',x.get('count'))
  for rel in ('queue/100_E5_NATIVE_WORKER_science_B.json','queue/101_E5_NATIVE_WORKER_science_M2.json'):
   print(rel,(old/rel).read_text())
 elif mode=='routing':
  import lean_instrumentation;lean_instrumentation.prime()
  import study_common as sc,multirate,fast_runtime,host_adapter as ha,async_native_main as am
  cfg=json.loads((S/'queue/003_M2_guard_off_smoke.json').read_text());cfg['durable_config_path']=str(S/'queue/003_M2_guard_off_smoke.json')
  multirate.install('R3',cfg['execution_mode']);fast_runtime.install(cfg)
  import deferred_evaluation,admission_certificates,fast_task_owner,fast_task_ipc,commissioning_owner
  commissioning_owner.install('R3',cfg['execution_mode'])
  deferred_evaluation.install();admission_certificates.install();fast_task_owner.install_parent();fast_task_ipc.install()
  interface=ha.make_interface(cfg)
  print('same module',sc.rt is am.rt,'same namespaces',sc.rt._run_executed_case.__globals__ is sc.rt.__dict__,'snapshot',sc.rt.snapshot_task_call,sc.rt._run_executed_case.__globals__['snapshot_task_call'])
  x=next((S.parent/'b_native_q_realtime_integration_v1/output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'));row=pickle.loads(x.read_bytes());planner,args=pickle.loads(row['payload'])
  from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
  import numpy as np
  req=op.PlanRequest(row['request_id'],'TASK',0.,row['sensor_capture_ns'],row['request_ns'],True)
  b=dict(adaptive_planner=planner,planner=planner.planner,arguments=args,request=req,belief=args['belief'],spec=planner.planner.spec,task_state=sc.types.SimpleNamespace(phase=args['phase'],phase_elapsed_s=args['phase_elapsed_s'],hold_elapsed_s=0.),sac_hooks=sc.types.SimpleNamespace(force_integral=0.,moment_integral=0.),physical_now=row['context']['task_s'],task_start_time=0.,observation=sc.types.SimpleNamespace(as_array=lambda:np.zeros(4)),reference_acceleration=np.zeros(2),interface=sc.types.SimpleNamespace(measured_force_world_n=np.zeros(3),measured_moment_world_nm=np.zeros(3)))
  interface.decision_boundary(b);print('pending',interface.pending is not None)
  raw=sc.rt._run_executed_case.__globals__['snapshot_task_call'](planner,args);print('payload len',len(pickle.loads(raw)),'hints',len(interface.hints),'pending remains',interface.pending is not None)
 elif mode=='preflight':
  import study_common as sc,native_core,representation
  import mujoco,numpy,scipy
  case,options=sc.load_case_options()
  from interfaces import TableInterface
  table=TableInterface();contract=S/'output/SHARED_COORDINATION_ACTION_CONTRACT.json'
  assert contract.exists() and table.K==3 and representation.TIMINGS[3]==[.1,.4,.7]
  result=dict(status='PASS',python=sys.version,mujoco=mujoco.__version__,numpy=numpy.__version__,scipy=scipy.__version__,case=case,K3=representation.TIMINGS[3],contract_file=str(contract),contract_sha256=sc.sha(contract),Q_sha256=sc.sha(S/'weights/frozen_Q_v1/weights.npz'),no_physics=True)
  (S/'reports/PREFLIGHT.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
