from pathlib import Path
import os,sys,json,time,hashlib,gzip,shutil,types,importlib
from dataclasses import asdict,is_dataclass
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
sys.dont_write_bytecode=True
STUDY=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_interface_v1');W=STUDY/'code';L=STUDY/'output';D=L;R=STUDY/'source';S=R/'stages/stage5_personalized_motion_learning';O=R/'results'
for p in (L,O):p.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(STUDY/'deps'))
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):sys.path.insert(0,str(R/'stages'/stage/'src'))
for name in ('single_human_sac_expert_v1','single_human_sac_expert_v1_r2'):sys.path.insert(0,str(S/'scripts'/name))
import numpy as np
import sac_env
from sac_env import SACExpertEnv,load_case_options
import campaign_r2 as r2
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_coordination_residual_v2 as rt
from traction_mpc_stage5.task import TaskPhase
def clean(x):
 if is_dataclass(x):return clean(asdict(x))
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 return rt._jsonable(x)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def digest(x):return hashlib.sha256(json.dumps(clean(x),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def save(name,x):
 p=L/name;temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(clean(x),indent=2,sort_keys=True,allow_nan=False)+'\n');temp.replace(p)
def read(name):return json.loads((L/name).read_text())
def guard():
 cfg=json.loads((STUDY/'RUN_PLAN.json').read_text());assert time.time()<cfg['dispatch_cutoff_unix'],'WALL_CLOSEOUT'
def native_model_calls(root):
 counts=set()
 def walk(x):
  if isinstance(x,dict):
   if 'research_model_invocations' in x:counts.add((x.get('request_id'),x.get('worker_start_ns'),x['research_model_invocations']))
   for value in x.values():walk(value)
  elif isinstance(x,(list,tuple)):
   for value in x:walk(value)
 walk(root);return sum(row[2] for row in counts)
class Interface:
 def __init__(self,action=None):self.action=action or {};self.child=None;self.rows=[]
 def decision_boundary(self,b):pass
 def boundary(self,b):
  r=b['reference'];self.rows.append([b['task_state'].phase.value,float(b['physical_now']-b['task_start_time']),*r.q_rad,*r.dq_rad_s,*r.ddq_rad_s2])
 def finish(self,env,metric):
  np.savez_compressed(env.episode_dir/'native_reference.npz',phase=[r[0] for r in self.rows],data=np.asarray([r[1:] for r in self.rows]))
gates=types.SimpleNamespace(Interface=Interface)
v2=sys.modules[__name__]
def run(name,interface,original=False,execution_mode='SCIENTIFIC_SIMULATION'):
 guard();case,options=load_case_options();folder=O/name;folder.mkdir(parents=True,exist_ok=False)
 env=SACExpertEnv(folder,case,options,.02,'MATCHED',True);env.episode_dir=folder;env.host_start=time.monotonic()
 import operational_memory_v3 as memory
 memory.phase('PHYSICS')
 import streaming_reuse
 streaming_reuse.ensure(rt,memory)
 original_persist=rt.persist_runtime_artifacts
 def persist_branch_artifacts(output_dir,capture):
  # Forked native runtime retains its parent's output_dir argument. Route
  # logging through the active environment's unique branch directory.
  return original_persist(env.episode_dir,capture)
 rt.persist_runtime_artifacts=persist_branch_artifacts
 try:
  if original:
   from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_sac_expert_v1 as execute_rt
   memory.install(execute_rt)
  else:execute_rt=rt
  kwargs={} if original else dict(coordination_interface=interface)
  env.summary=execute_rt.run_executed_case(folder,qualification_case=case,qualification_arm='commissioning_only',simulate_planning_latency=True,formal_qualification=False,dev_a_recovery=True,dev_c_bumpless_transfer=False,dev_d_rigid_table_reference=True,autonomous_recovery_options=options,task_timeout_s=30.,runtime_capture=env.capture,execution_mode=execution_mode,scientific_host_delay_s=0.,session_context={} if execution_mode=='SCIENTIFIC_SIMULATION' else None,sac_hooks=env,**kwargs)
  effective=name if interface.child is None else interface.child['label']+'_'+interface.child['kind']
  import mode_metadata
  mode_metadata.install()
  metric=r2.metric(env,effective,'MATCHED');metric.pop('raw_actions',None)
  from traction_mpc_stage4 import estimator_v2 as model_accounting
  metric['main_model_inverse_dynamics_api_calls']=getattr(model_accounting,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',None)
  metric['native_worker_model_inverse_dynamics_api_calls']=native_model_calls(env.summary)
  metric['actual_new_main_model_inverse_dynamics_api_calls']=metric['main_model_inverse_dynamics_api_calls']-(0 if interface.child is None else interface.child.get('main_api_counter_at_fork',0)) if metric['main_model_inverse_dynamics_api_calls'] is not None else None
  metric['actual_new_native_worker_model_inverse_dynamics_api_calls']=metric['native_worker_model_inverse_dynamics_api_calls']-(0 if interface.child is None else interface.child.get('native_api_counter_at_fork',0))
  metric['tick_integral_vs_evaluation_J_F_error']=float(env.force_integral-metric['J_F'])
  with np.load(env.episode_dir/'trace.npz') as z:
   metric['native_control_samples']=len(z['time_s']);metric['simulation_seconds']=float(z['time_s'][-1]);metric['native_physics_steps']=int(z['physics_steps'][-1]);metric['native_physics_dt_s']=float(rt.NOMINAL_PHYSICS_DT_S)
   metric['actual_new_simulation_seconds']=metric['simulation_seconds'];metric['actual_new_native_physics_steps']=metric['native_physics_steps']
  save(effective+'.json',metric);interface.finish(env,metric)
  return metric
 except BaseException:
  # Preserve actual computation on an exceptional attempt. A failed prefix
  # is never promoted to a successful low-cost sample.
  from traction_mpc_stage4 import estimator_v2 as ma
  runtime=env.capture.get('runtime',{});plant=runtime.get('plant')
  physical=float(plant.data.time) if plant is not None else None
  effective=name if interface.child is None else interface.child['label']+'_'+interface.child['kind']
  calls=getattr(ma,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',None)
  save(effective+'_PARTIAL_COMPUTE.json',dict(status='FAILED_UNRANKED',simulation_seconds=physical,native_physics_steps=None if physical is None else round(physical/rt.NOMINAL_PHYSICS_DT_S),actual_new_simulation_seconds=None if physical is None else physical-(0 if interface.child is None else interface.child['physical_time_at_fork']),actual_new_native_physics_steps=None if physical is None else round(physical/rt.NOMINAL_PHYSICS_DT_S)-(0 if interface.child is None else interface.child['physics_step_at_fork']),main_model_inverse_dynamics_api_calls=calls,actual_new_main_model_inverse_dynamics_api_calls=None if calls is None else calls-(0 if interface.child is None else interface.child['main_api_counter_at_fork']),observed_tick_force_integral=env.force_integral,observed_tick_moment_integral=env.moment_integral,valid=False))
  if hasattr(interface,'search_rows'):
   network=interface.network
   save(effective+'_SELECTIONS.json',dict(method=interface.method,rows=interface.search_rows,network_Q_calls=0 if network is None else network.Q_calls,network_G_calls=0 if network is None else network.G_calls,P_performance_calls=0,delay_replay=interface.request.get('delay_replay',False),incomplete=True,execution_mode=execution_mode))
  if hasattr(interface,'labels'):save(effective+'_FAILED_DECISIONS.json',dict(rows=interface.labels,skipped=interface.skips,execution_mode=execution_mode,status='FAILED_UNRANKED'))
  raise
 finally:
  streaming_reuse.restore(rt)
  folder=env.episode_dir
  path=folder/'runtime_artifacts.json'
  if path.exists():
   h=sha(path)
   with path.open('rb') as src,gzip.open(str(path)+'.gz','wb',compresslevel=3) as dst:shutil.copyfileobj(src,dst)
   hh=hashlib.sha256()
   with gzip.open(str(path)+'.gz','rb') as f:
    for part in iter(lambda:f.read(2**20),b''):hh.update(part)
   assert hh.hexdigest()==h;path.unlink()
  env.close()
