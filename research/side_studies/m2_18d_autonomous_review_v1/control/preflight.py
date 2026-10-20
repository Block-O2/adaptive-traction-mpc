from pathlib import Path
import os,sys,json,time,hashlib,ast,types
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path.insert(0,str(P/'code'))
import study_common as sc,matched_harness as mh,analyze_matched as am
from rich_planner import RichFreePlanner
from traction_mpc_stage5.full3d_adaptive_integration_v1.coordination_residual_v2 import NativeResidualPlannerV2
from traction_mpc_stage5.task import TaskPhase
import numpy as np
def read(n):return json.loads((P/n).read_text())
def put(n,x):mh.put(P/n,sc.clean(x))
assert sc.STUDY==P and mh.PACKAGE==P and am.S==P
imports=[]
for name,m in list(sys.modules.items()):
 f=getattr(m,'__file__',None)
 if f and '/home/hank/coding/' in f:
  assert Path(f).resolve().is_relative_to(P),(name,f)
  imports.append(dict(module=name,path=f))
old=read('FROZEN_18D.json');new=read('CANDIDATE.json');repair=read('BOUNDED_REPAIR.json')
assert old==json.loads((P.parent/'m2_18d_baseline_qualification_v1/FROZEN_18D.json').read_text())
assert sc.sha(P/'MOTION_ACCEPTANCE_PROTOCOL.json')==sc.sha(P.parent/'m2_18d_baseline_qualification_v1/MOTION_ACCEPTANCE_PROTOCOL.json')
assert new['phases']==old['phases']==repair['phases']
assert np.array_equal(np.flatnonzero(np.asarray(old['free_parameters'])!=new['free_parameters']),[3,4,13])
for i in range(18):
 assert new['free_parameters'][i]==(0 if i in [3,4,13] else old['free_parameters'][i])
 assert repair['free_parameters'][i]==old['free_parameters'][i]*(.5 if i in [0,1,2,3,4,10,11,12,13] else 1)
# Exercise production formula with a native-velocity test double; no physical integration.
original=NativeResidualPlannerV2._waypoint_terminal_velocity
NativeResidualPlannerV2._waypoint_terminal_velocity=lambda self,**kw:np.array([.2,.3])
obj=RichFreePlanner.__new__(RichFreePlanner)
obj.spec=types.SimpleNamespace(start_return_target_rad=np.deg2rad([5,10]),outbound_goal_target_rad=np.deg2rad([120,120]),joint_angle_completion_tolerance_rad=np.deg2rad([.5,.5]))
obj.reference_phase_goal=lambda ph:obj.spec.start_return_target_rad if ph is TaskPhase.RETURN else obj.spec.outbound_goal_target_rad
rows=[]
try:
 for ph in [TaskPhase.OUTBOUND,TaskPhase.RETURN,TaskPhase.HOLD]:
  for m in [0,.1,.3,.5,.8,1]:
   start=obj.spec.start_return_target_rad if ph is not TaskPhase.RETURN else obj.spec.outbound_goal_target_rad
   goal=obj.reference_phase_goal(ph);target=start+m*(goal-start)
   values={}
   for name,x in [('E',old['free_parameters']),('C',new['free_parameters']),('zero',[0.]*18)]:
    obj.free_parameters=np.array(x);values[name]=obj._waypoint_terminal_velocity(phase=ph,reference_state=np.zeros(6),target_q_rad=target)
   assert np.array_equal(values['zero'],[.2,.3])
   if ph in [TaskPhase.HOLD,TaskPhase.OUTBOUND]: assert np.array_equal(values['C'],[.2,.3])
   if ph is TaskPhase.RETURN: assert np.array_equal(values['E'],values['C'])
   rows.append(dict(phase=ph.value,m=m,values=values))
finally:NativeResidualPlannerV2._waypoint_terminal_velocity=original
for d in ['source','code','deps','control']:
 for f in (P/d).rglob('*.py'):ast.parse(f.read_text(),filename=str(f))
for n in ['code/rich_planner.py','code/matched_harness.py','code/analyze_matched.py','code/explore_common.py']:
 oldbytes=(P.parent/'m2_18d_baseline_qualification_v1'/n).read_bytes().replace(str(P.parent/'m2_18d_baseline_qualification_v1').encode(),str(P).encode())
 assert (P/n).read_bytes()==oldbytes,n
manifest={str(f.relative_to(P)):sc.sha(f) for d in ['source','code','deps','weights','control'] for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in f.parts and 'results' not in f.parts}
for n in ['RUN_PLAN.json','FROZEN_18D.json','CANDIDATE.json','BOUNDED_REPAIR.json','MOTION_ACCEPTANCE_PROTOCOL.json','output/SHARED_COORDINATION_ACTION_CONTRACT.json']:manifest[n]=sc.sha(P/n)
put('EXECUTION_CODE_MANIFEST.json',dict(files=manifest,frozen_unix=time.time(),imports=imports))
put('PREPHYSICAL_CHECKS.json',dict(status='PASS',unix=time.time(),no_physics_started=not (P/'ATTEMPTS.jsonl').exists(),frozen_parameter_identity=True,return_and_plateau_identity=True,motion_protocol_byte_identity=True,original_controller_and_safety_unchanged=True,imports_within_closure=True,velocity_formula_tests=rows,production_math_invoked=True,source_ast_pass=True,scope='Mathematics and code contracts only; physical qualification still required'))
print(json.dumps(dict(status='PASS',files=len(manifest),formula_cases=len(rows))))
