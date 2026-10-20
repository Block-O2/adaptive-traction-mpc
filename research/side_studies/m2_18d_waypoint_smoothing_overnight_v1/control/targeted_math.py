from pathlib import Path
import sys,json,hashlib,shutil
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
for f in (L/'control').glob('*.py'):shutil.copy2(f,P/'control'/f.name)
sys.path.insert(0,str(P/'tests'))
src=(P/'tests/fixture.py').read_text().replace("snapshot=s['learning_records'][index]", "snapshot=next(r for r in s['learning_records'] if r['decision_index']==index)")
(P/'tests/targeted_fixture.py').write_text(src)
from targeted_fixture import *
from traction_mpc_stage5.full3d_adaptive_integration_v1.multisegment_reference import *
plan=json.loads((P/'CANDIDATE_PLAN.json').read_text());rows=[];executable=[plan['coarse'][0]]
for c in plan['coarse'][1:]:
 f=fixture(index=3 if c['phase']=='OUTBOUND' else 11)
 intent={**f['context'],'study_spec':c['spec'],'perturbation_deg':[0,0]}
 try:s=adapt_decision(f['decision'],f['planner'],f['belief'],intent).executed.schedule
 except ValueError as e:
  rows.append(dict(id=c['id'],feasible=False,rejected_reason=str(e)))
  if 'opposite' not in c['id']:raise
  c={**c,'id':c['id']+'_quarter','spec':{**c['spec'],'deltas_deg':(np.asarray(c['spec']['deltas_deg'])*.25).tolist()}}
  try:s=adapt_decision(f['decision'],f['planner'],f['belief'],{**intent,'study_spec':c['spec']}).executed.schedule
  except ValueError as e:
   rows.append(dict(id=c['id'],feasible=False,rejected_reason=str(e)));continue
 assert s.certificate['feasible'];s.assert_integrity();assert len(s.segments)==4
 for t in [0,s.duration_s]:
  for key in ['q_rad','dq_rad_s','ddq_rad_s2']:assert np.max(abs(getattr(s.sample(t),key)-getattr(s.original.sample(t),key)))<1e-10
 dev=max(np.max(abs(s.sample(t).q_rad-s.original.sample(t).q_rad)) for t in np.linspace(0,s.duration_s,1001));assert dev<=np.radians(.05)+1e-10
 rows.append(dict(id=c['id'],feasible=True,endpoint_C2_preserved=True,max_q_deviation_deg=float(np.degrees(dev)),certificate=s.sealed_certificate_id,reference=s.sealed_digest))
 executable.append(c)
out=dict(status='PASS',cases=rows,physics_starts=0,original_protocol_unchanged=(P/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes()==(P.parent/'adaptive_continuous_coordination_optimization_v1/MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes())
assert all(r['feasible'] for r in rows if 'opposite' not in r['id']),'Primary or zero must pass offline certificate'
assert out['original_protocol_unchanged'];(P/'TARGETED_MATH_TESTS.json').write_text(json.dumps(out,indent=2))
(P/'EXECUTABLE_PLAN.json').write_text(json.dumps(dict(coarse=executable,amendment='Before any physics: full opposite rejected by unchanged velocity gate, one quarter-scale attempt is retained if certified; otherwise use zero control. Original plan preserved.',original_plan_sha256=hashlib.sha256((P/'CANDIDATE_PLAN.json').read_bytes()).hexdigest()),indent=2))
manifest={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for d in ['source','code','deps','weights','control','tests'] for p in (P/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(P/'EXECUTION_CODE_MANIFEST.json').write_text(json.dumps(dict(files=manifest,plan_sha256=hashlib.sha256((P/'CANDIDATE_PLAN.json').read_bytes()).hexdigest(),motion_protocol_sha256=hashlib.sha256((P/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes()).hexdigest()),indent=2))
print(json.dumps(out,indent=2))
