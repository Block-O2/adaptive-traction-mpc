"""Prospective development addendum after a useful signed posture response."""
from pathlib import Path
import os,sys,json,time,ast,hashlib
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
assert not (P/'refine_PLAN.json').exists()
assessment=json.loads((P/'derived/ASSESSMENT_dev.json').read_text());r=next(r for r in assessment['rows'] if r['id']=='dev_P_more')
assert r['qualified'] and r['delta_J_F_vs_T']<-.2 and max(r['delta_vs_T'].values())<0
sys.dont_write_bytecode=True;os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
# Reuse only the already frozen causal mathematical fixture, skipping its authoring loop/main.
tree=ast.parse((P/'control/register.py').read_text());nodes=[]
for n in tree.body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='design' for t in n.targets):break
 if isinstance(n,ast.For):continue
 nodes.append(n)
ns={'__file__':str(P/'control/register.py')};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(P/'control/register.py'),'exec'),ns)
np=ns['np'];fixture=ns['fixture'];FixedDuration=ns['FixedDuration'];checks=[]
for index in [10,11]:
 fx=fixture(index);args=fx['evaluate_args'].copy();args['action']=args['action']+np.radians([.3,-.3]);planner=fx['planner'];native=planner.scheduler
 planner.scheduler=FixedDuration(native,fx['schedule'].duration_s);planner.round_forced_velocity=np.array(fx['archived']['target_dq_rad_s'])
 try:x=planner._evaluate(**args)
 finally:planner.scheduler=native;planner.round_forced_velocity=None
 checks.append(dict(index=index,status='PASS' if x.feasible else 'REJECTED',reason=x.rejection_reason,scope='each archived causal fixture separately; actual corridor receives fresh complete runtime checks'))
assert all(x['status']=='PASS' for x in checks),checks
candidate=dict(id='P_corridor',base='T',posture=[dict(phase='RETURN',slot=k,delta_deg=[.3,-.3]) for k in [2,3]],changes=[],purpose='sustain the beneficial spatial separation over adjacent RETURN targets, testing whether a corridor avoids isolated-target compensation',expected_force_window=[12.8,16.6],expected_motion='full TV_v/TV_a/jerk no worse than T; less pulse compensation than single-slot P_more',unchanged='same 0.3deg amplitude; all 18D parameters/plateau/T1.5; each live selected segment duration/pass velocity; task endpoints/duration/safety',success='unchanged SELECTION_RULE.json; not merely crossing a force threshold; mechanism and magnitude separately reported',failure='any original qualification fail, either posture intent rejected/not actually executed, or no full-task gain',offline_checks=checks)
addendum=dict(frozen_unix=time.time(),stage='prospective development, before candidate physics; no validation data available',evidence_trigger={k:r[k] for k in ['id','delta_J_F_vs_T','delta_vs_T','qualified']},original_protocol_boundary='Initial rule allowed a half-size refinement. This explicit prospective addendum substitutes one support-extension mechanism test; original rule and all initial results remain immutable. No amplitude scan and no selection-threshold change.',rationale='The single target reduced force and all three full motion variations but fell short of primary criteria. Test sustained coordination instead of tuning amplitude to pass the threshold. Current code already supports multiple registered slots, so code/selection/safety contracts are unchanged.',max_additional_development_candidates=1,no_joint_smoothing_unless_individual_signals=True,candidate=candidate,selection_rule_sha256=hashlib.sha256((P/'SELECTION_RULE.json').read_bytes()).hexdigest(),execution_manifest_sha256=hashlib.sha256((P/'EXECUTION_CODE_MANIFEST.json').read_bytes()).hexdigest())
(P/'REFINEMENT_PROTOCOL.json').write_text(json.dumps(addendum,indent=2,ensure_ascii=False)+'\n')
config=dict(frozen_unix=time.time(),condition=dict(name='refine',seed=2026101901,prefix={'OUTBOUND':[[-.045,-.075,-.055]]}),fork_after_prefix=1,archive_condition='V1',arms=[dict(id=a,base=a,posture=[],changes=[]) for a in ['B','T']]+[candidate])
(P/'refine_PLAN.json').write_text(json.dumps(config,indent=2)+'\n')
print(json.dumps(dict(status='PASS',checks=checks,candidate=candidate)),flush=True)
