from pathlib import Path
import os,sys,json,pickle,time,hashlib,dataclasses,numpy as np
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');O=S.parent/'b_fast_runtime_completion_v1';sys.path.insert(0,str(S/'code'));sys.dont_write_bytecode=True
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc,full_controller_replay
from traction_mpc_stage4 import estimator_v2 as ma
before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
cfg=json.loads((S/'queue/035_C13_science_nominal.json').read_text());cfg.update(attribution=False,capture_controller_full=False,hold_mapping_reuse=False)
import fast_runtime;fast_runtime.install(cfg)
p=O/'inputs/030_N5_V3_A1_C1c_science_nominal_FULL_CONTROLLER_CAUSAL.pkl';rows=[r for r in pickle.loads(p.read_bytes()) if r['phase']=='TASK_HOLD']
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1 as C
original=C.prepare;sys.path.insert(0,str(Path(__file__).parent));import hold_static_geometry as cache;cache.install();records=[]
for row in rows:
 runtime,kw,public=pickle.loads(row['inputs']);contract=runtime['contract'];candidate=kw['candidate'];cache.reset();base=[];reuse=[]
 for repeat in range(30):
  # Preserve tiny varying original velocities; never collapse HOLD to zero.
  cand=dataclasses.replace(candidate,label='actual_'+str(repeat),dq_waypoint_rad_s=np.array([repeat*1e-31,-repeat*2e-31]))
  begin=time.monotonic_ns();wanted=original(contract,cand);base.append((time.monotonic_ns()-begin)/1e6)
  begin=time.monotonic_ns();actual=contract.prepare(cand);reuse.append((time.monotonic_ns()-begin)/1e6)
  assert actual.candidate is cand and sc.clean(actual)==sc.clean(wanted)
  if repeat==0:actual.human_cuff_position_world_m[0]+=1.;actual=contract.prepare(cand);assert sc.clean(actual)==sc.clean(wanted)
 changed=dataclasses.replace(candidate,q_waypoint_rad=candidate.q_waypoint_rad+np.array([-1e-8,0.]));assert sc.clean(original(contract,changed))==sc.clean(contract.prepare(changed))
 import copy
 clone=copy.copy(contract);clone.human_model=copy.deepcopy(contract.human_model);clone.human_model.beta[0]+=1e-8
 assert sc.clean(original(clone,candidate))==sc.clean(clone.prepare(candidate))
 invalid=dataclasses.replace(candidate,phase_goal_rad=candidate.phase_goal_rad+np.array([1e-6,0.]))
 try:contract.prepare(invalid)
 except ValueError:pass
 else:raise AssertionError('original invalid-goal rejection missing')
 ev=cache.evidence();print(json.dumps(dict(geometry_type=str(type(contract.human_model.geometry)),model_type=str(type(contract.human_model)),allocator_type=str(type(contract.cuff_allocator)),evidence=ev)),flush=True);assert ev['counters'].get('pose_hit',0)>0 and ev['counters'].get('allocator_factors_hit',0)>0
 records.append(dict(source_sample_s=row['source_sample_time_s'],mapped_bit_exact=True,tiny_nonzero_velocity_preserved=True,candidate_identity=True,mutation_isolated=True,changed_reference_model_recomputed=True,invalid_goal_rejected=True,original_ms=float(np.median(base)),reused_ms=float(np.median(reuse[1:])),cache=ev))
out=dict(status='PASS',rows=records,input_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_sha256=hashlib.sha256((Path(__file__).parent/'hold_static_geometry.py').read_bytes()).hexdigest(),model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,physics_steps=0)
target=S/'output/C16b_LOCAL_EQUIVALENCE.json';assert not target.exists();target.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
