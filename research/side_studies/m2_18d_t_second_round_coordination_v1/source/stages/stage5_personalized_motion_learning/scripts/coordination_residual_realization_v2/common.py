from pathlib import Path
import sys, os, json, time, hashlib, importlib.util, shutil, gzip
from dataclasses import is_dataclass,asdict
import numpy as np
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';sys.dont_write_bytecode=True
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_t_second_round_coordination_v1/source');S=R/'stages/stage5_personalized_motion_learning'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/coordination_residual_realization_v2')
P=S/'scripts/coordination_residual_realization_v2';D=S/'docs/coordination_residual_realization_v2';O=S/'results/coordination_residual_realization_v2';L=W/'output'
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):sys.path.insert(0,str(R/'stages'/stage/'src'))
sys.path.insert(0,str(S/'scripts/single_human_sac_expert_v1'))
sys.path.insert(0,str(S/'scripts/single_human_sac_expert_v1_r2'))
import sac_env
from sac_env import SACExpertEnv,load_case_options
import campaign_r2 as r2
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_sac_expert_v1 as original_rt
from traction_mpc_stage5.task import TaskPhase
def clean(x):
 if is_dataclass(x):return clean(asdict(x))
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 return original_rt._jsonable(x)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(clean(x),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def save(name,x):
 for d in (L,D):
  d.mkdir(parents=True,exist_ok=True);(d/name).write_text(json.dumps(clean(x),indent=2,sort_keys=True,allow_nan=False)+'\n')
def read(name):return json.loads((L/name).read_text())
def registered_task_endpoints():
 case,_=load_case_options();t=case['task']
 return dict(start_return_target_rad=np.radians(t['start_deg']).tolist(),outbound_goal_target_rad=np.radians(t['goal_deg']).tolist())
def load_runtime():
 # A normal versioned package module is required by the existing spawned
 # planner. Existing production modules remain byte-for-byte protected.
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_coordination_residual_v2
 return runtime_coordination_residual_v2
def guard():
 assert time.time()<read('CONTRACT.json')['hard_cutoff_unix'],'8H_HARD_CAP'
def compact(folder):
 p=folder/'runtime_artifacts.json'
 if p.exists():
  h=sha(p);out=Path(str(p)+'.gz')
  with p.open('rb') as src,gzip.open(out,'wb',compresslevel=3) as dst:shutil.copyfileobj(src,dst)
  with gzip.open(out,'rb') as f:assert hashlib.sha256(f.read()).hexdigest()==h
  p.unlink()
def run(name,interface=None,original=False):
 guard();case,options=load_case_options();folder=O/name;folder.mkdir(parents=True,exist_ok=False)
 env=SACExpertEnv(folder,case,options,.02,'MATCHED',True);env.episode_dir=folder;env.host_start=time.monotonic()
 rt=original_rt if original else load_runtime()
 kw={} if original else dict(coordination_interface=interface)
 try:
  env.summary=rt.run_executed_case(folder,qualification_case=case,qualification_arm='commissioning_only',simulate_planning_latency=True,formal_qualification=False,dev_a_recovery=True,dev_c_bumpless_transfer=False,dev_d_rigid_table_reference=True,autonomous_recovery_options=options,task_timeout_s=30.,runtime_capture=env.capture,execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_s=0.,session_context={},sac_hooks=env,**kw)
  effective_name=name if interface is None or getattr(interface,'child',None) is None else interface.child['label']+'_'+interface.child['kind']
  metric=r2.metric(env,effective_name,'MATCHED');metric.pop('raw_actions',None)
  save(effective_name+'.json',metric)
  if interface is not None:interface.finish(env,metric)
  print(json.dumps({k:metric.get(k) for k in ('name','status','valid','J_F','phase_durations','host_s')}),flush=True)
  return metric
 finally:compact(folder);env.close()

