from pathlib import Path
import os,sys,json,pickle,time,hashlib,copy,dataclasses,numpy as np
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');O=S.parent/'b_fast_runtime_completion_v1';sys.path.insert(0,str(S/'code'));sys.dont_write_bytecode=True
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc,full_controller_replay
from traction_mpc_stage4 import estimator_v2 as ma
before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
cfg=json.loads((S/'queue/035_C13_science_nominal.json').read_text());cfg.update(attribution=False,capture_controller_full=False)
import fast_runtime;fast_runtime.install(cfg)
p=O/'inputs/030_N5_V3_A1_C1c_science_nominal_FULL_CONTROLLER_CAUSAL.pkl'
rows=[r for r in pickle.loads(p.read_bytes()) if r['phase']=='TASK_HOLD'];assert rows
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1 as C
original=C.prepare
import hold_mapping_reuse as cache;cache.install();records=[]
for row in rows:
 runtime,kw,public=pickle.loads(row['inputs']);contract=runtime['contract'];candidate=kw['candidate']
 cache.reset();base=[];reuse=[]
 for repeat in range(20):
  start=time.monotonic_ns();wanted=original(contract,candidate);base.append((time.monotonic_ns()-start)/1e6)
  start=time.monotonic_ns();actual=contract.prepare(candidate);reuse.append((time.monotonic_ns()-start)/1e6)
  assert actual.candidate is candidate and sc.clean(actual)==sc.clean(wanted)
  # A consumer mutation of one returned buffer cannot pollute future output.
  if repeat==0:actual.human_cuff_position_world_m[0]+=1.;actual=contract.prepare(candidate);assert sc.clean(actual)==sc.clean(wanted)
 k=cache.key(contract,candidate);assert k is not None
 changed=dataclasses.replace(candidate,q_waypoint_rad=candidate.q_waypoint_rad+np.array([1e-8,0.]));assert k!=cache.key(contract,changed)
 model=copy.deepcopy(contract.human_model);model.beta[0]+=1e-8;clone=copy.copy(contract);clone.human_model=model;assert k!=cache.key(clone,candidate)
 invalid=dataclasses.replace(candidate,phase_goal_rad=candidate.phase_goal_rad+np.array([1e-6,0.]))
 try:contract.prepare(invalid)
 except ValueError:rejected=True
 else:rejected=False
 assert rejected
 records.append(dict(source_sample_s=row['source_sample_time_s'],mapped_bit_exact=True,candidate_identity_preserved=True,output_mutation_isolated=True,model_reference_misses=True,invalid_original_goal_rejected=True,original_prepare_ms=np.median(base),cached_prepare_ms=np.median(reuse[1:]),cache=cache.evidence(),allocator_type=str(type(contract.cuff_allocator))))
out=dict(status='PASS',input_path=str(p),input_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=records,model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,physics_steps=0,source_sha256=hashlib.sha256((S/'code/hold_mapping_reuse.py').read_bytes()).hexdigest(),scope='Original pure HOLD mapping only; no live coupled plant, no feedback/admission skipped')
target=S/'output/C14_LOCAL_EQUIVALENCE.json';assert not target.exists();target.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
