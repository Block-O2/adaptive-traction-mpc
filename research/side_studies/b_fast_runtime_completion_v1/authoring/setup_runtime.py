from pathlib import Path
import os,sys,json,time,hashlib,shutil,subprocess,importlib,re
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
def save(p,x):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
def main():
 for p in (S/'code').glob('*.py'):
  text=p.read_text();new=text.replace("'b_multirate_realtime_v1'","'b_fast_runtime_completion_v1'")
  if text!=new:p.write_text(new)
 for n in ('fast_dispatch.py','fast_attribution.py','fast_runtime.py','causal_clock.py','clock_regression.py','offline_controller_replay.py','plant_cost.py','native_interface_adapter.py','native_local_regression.py','scientific_gate.py','same_tick_reuse.py','native_vectors.py','so3_vector_regression.py','numerical_reuse.py','numerical_reuse_regression.py','host_review.py','full_controller_replay.py','native_soft_limits.py','soft_limit_regression.py','service_clock.py','service_clock_regression.py','task_input_replay.py','fast_task_owner.py','fast_task_ipc.py','ipc_local_regression.py','resource_guard.py'):
  p=W/n
  if p.exists():shutil.copy2(p,S/'code'/n)
 p=S/'code/run_one.py';text=p.read_text()
 shutil.copy2(W/'loaded_context_reuse.py',S/'code/loaded_context_reuse.py')
 shutil.copy2(W/'worker_numeric_reuse.py',S/'code/worker_numeric_reuse.py')
 shutil.copy2(W/'native_small_kernels.py',S/'code/native_small_kernels.py')
 shutil.copy2(W/'admission_key.py',S/'code/admission_key.py')
 shutil.copy2(W/'causal_metadata.py',S/'code/causal_metadata.py')
 shutil.copy2(W/'admission_replay.py',S/'code/admission_replay.py')
 shutil.copy2(W/'geometry_transaction_reuse.py',S/'code/geometry_transaction_reuse.py')
 shutil.copy2(W/'native_geometry.py',S/'code/native_geometry.py')
 shutil.copy2(W/'native_value_tree.py',S/'code/native_value_tree.py')
 shutil.copy2(W/'native_quintic.py',S/'code/native_quintic.py')
 shutil.copy2(W/'deferred_receipt_prepare.py',S/'code/deferred_receipt_prepare.py')
 shutil.copy2(W/'native_single_step.py',S/'code/native_single_step.py')
 shutil.copy2(W/'single_step_regression.py',S/'code/single_step_regression.py')
 shutil.copy2(W/'native_intervals.py',S/'code/native_intervals.py')
 shutil.copy2(W/'native_bool_reductions.py',S/'code/native_bool_reductions.py')
 shutil.copy2(W/'completed_result_service.py',S/'code/completed_result_service.py')
 shutil.copy2(W/'streaming_reuse.py',S/'code/streaming_reuse.py')
 shutil.copy2(W/'fault_injection.py',S/'code/fault_injection.py')
 shutil.copy2(W/'readiness_service.py',S/'code/readiness_service.py')
 shutil.copy2(W/'committed_endpoint_service.py',S/'code/committed_endpoint_service.py')
 common=S/'code/study_common.py';common_text=common.read_text()
 if 'streaming_reuse.ensure' not in common_text:
  shutil.copy2(common,S/'versions/REUSE_SERIALIZER_NEGATIVE_study_common.py')
  anchor=" memory.phase('PHYSICS');memory.install(rt)"
  assert common_text.count(anchor)==1
  common_text=common_text.replace(anchor," memory.phase('PHYSICS')\n import streaming_reuse\n streaming_reuse.ensure(rt,memory)")
  anchor=" finally:\n  folder=env.episode_dir"
  assert common_text.count(anchor)==1
  common_text=common_text.replace(anchor," finally:\n  streaming_reuse.restore(rt)\n  folder=env.episode_dir")
  common.write_text(common_text)
 if 'import fast_runtime' not in text:
  text=text.replace(" from native_method import PrefixBInterface", " import fast_runtime\n fast_runtime.install(cfg)\n from native_method import PrefixBInterface")
  text=text.replace("  sc.save(ident+'_MULTIRATE.json',multirate.evidence())", "  fast_runtime.finish(ident)\n  sc.save(ident+'_MULTIRATE.json',multirate.evidence())")
  p.write_text(text)
 text=p.read_text()
 text=re.sub(r'(?: import fast_runtime\n fast_runtime.install\(cfg\)\n)+','',text)
 anchor=" if cfg['revision'] in ('R2','R3'):\n  import commissioning_owner"
 text=text.replace(anchor," import fast_runtime\n fast_runtime.install(cfg)\n"+anchor)
 text=text.replace("  result=dict(id=ident,status='COMPLETE',metric=metric,", "  metric['actual_new_main_model_inverse_dynamics_api_calls']=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-model_before\n  result=dict(id=ident,status='COMPLETE',metric=metric,") if "metric['actual_new_main_model_inverse_dynamics_api_calls']=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-model_before" not in text else text
 text=text.replace(" from native_method import PrefixBInterface", " if cfg.get('fast_task_owner'):\n  import fast_task_owner\n  fast_task_owner.install_parent()\n from native_method import PrefixBInterface") if "fast_task_owner.install_parent()" not in text else text
 text=text.replace(" from native_method import PrefixBInterface", " if cfg.get('task_transport')=='DIRECT_D1':\n  import fast_task_ipc\n  fast_task_ipc.install(fast=cfg.get('fast_task_owner',False))\n from native_method import PrefixBInterface") if "fast_task_ipc.install(" not in text else text
 text=text.replace("fast_task_ipc.install(fast=cfg.get('fast_task_owner',False))","fast_task_ipc.install(fast=cfg.get('fast_task_owner',False),scientific=cfg['execution_mode']=='SCIENTIFIC_SIMULATION')")
 text=text.replace("fast_task_ipc.install(fast=cfg.get('fast_task_owner',False),scientific=cfg['execution_mode']=='SCIENTIFIC_SIMULATION')","fast_task_ipc.install(fast=cfg.get('fast_task_owner',False),scientific=cfg['execution_mode']=='SCIENTIFIC_SIMULATION',transport_warm=cfg.get('bidirectional_transport_warm',False))")
 if "fault_injection.install(cfg)" not in text:
  anchor=" from native_method import PrefixBInterface"
  assert text.count(anchor)==1
  text=text.replace(anchor," if cfg.get('fault_injection'):\n  assert not reuse,'Registered fault diagnostics use independent fresh owners'\n  import fault_injection\n  fault_injection.install(cfg)\n"+anchor)
 p.write_text(text)
 if (S/'PREFLIGHT.json').exists():
  print('UPDATED_ADAPTERS_ONLY');return
 if not (S/'versions/RUNTIME_FUNCTIONAL_CHECKS.json').exists():
  save(S/'versions/RUNTIME_FUNCTIONAL_CHECKS.json',dict(schema='prospective_runtime_functional_v1',registered_unix=time.time(),population='all actual service opportunities in full host episode, including commissioning/model publish; extra same-period services reported separately',required=dict(full_OUT_HOLD_RETURN=True,original_physical_safety=True,original_R2=True,original_current_state_admission=True,source_expiry_ns=100000000,meaningful_plans_min=2,causal_substep_command_ownership=True,quantization_delay_ns_max=250000,service_gap_p50_ms_max=5.5,service_gap_p95_ms_max=7.5,service_gap_p99_ms_max=10.,service_gap_over_10ms_fraction_max=.05,missed_grid_fraction_max=.15,rolling_1s_service_mean_ms_max=6.,max_unresolved_backlog_s=.100,expired_write_count_max=0),legacy_strict='Original strict55, miss/receipt, safety and R2 labels preserved independently. No old FAIL relabeling.',engineering_only=True,not_hard_realtime_guarantee=True,injection_protocol=[dict(kind='worker_delay',delay_ms=30,requests=[3]),dict(kind='expired_result',delay_ms=120,requests=[3]),dict(kind='model_version_mismatch',requests=[3]),dict(kind='explicit_native_rejection',requests=[3])],M2_gate='Full B physical/R2/causal/functional plus independent retest and multiple nontrivial executed plans; legacy strict55 alone is not a veto.'))
 sys.path.insert(0,str(S/'code'));import lean_instrumentation;lean_instrumentation.prime();import study_common as sc
 versions={n:dict(version=importlib.import_module(n).__version__,file=importlib.import_module(n).__file__) for n in ('numpy','mujoco','scipy','gymnasium','setuptools')}
 from native_method import PrefixBInterface
 PrefixBInterface(dict(method='M0',prefix={},execution_mode='SCIENTIFIC_SIMULATION'))
 case,options=sc.load_case_options()
 import runner
 resource=runner.sample(owner='FAST_PREFLIGHT');resource['cpu_load']=os.getloadavg()
 save(S/'PREFLIGHT.json',dict(status='PASS',unix=time.time(),python=sys.version,executable=sys.executable,dependencies=versions,compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],shared_action_sha256=sc.sha(S/'output/SHARED_COORDINATION_ACTION_CONTRACT.json'),entry=str(S/'code/run_one.py'),entry_imported=True,native_physics_dispatched=False,source=str(sc.R),options=options,writable_test=(S/'checkpoints/PREFLIGHT_WRITABLE.txt').exists(),resource=resource))
 print('PREFLIGHT_PASS',time.time()-json.loads((S/'RUN_PLAN.json').read_text())['t0_unix'])
if __name__=='__main__':main()
