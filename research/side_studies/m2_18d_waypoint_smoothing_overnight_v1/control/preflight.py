from pathlib import Path
import os,sys,json,hashlib,shutil,time,subprocess,ast
P=Path(__file__).resolve().parents[1];L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
for n in ['campaign.py','history_design.py','preflight.py']:
 if (L/'control'/n).resolve()!=(P/'control'/n).resolve():shutil.copy2(L/'control'/n,P/'control'/n)
sys.path[:0]=[str(P/'code'),str(P/'control'),str(P/'tests')]
import study_common as sc
import analyze_mechanism as hist
assert sc.STUDY==P and hist.P==P,'HELPER_OUTPUT_ISOLATION'
def put(n,x):(P/n).write_text(json.dumps(sc.clean(x),indent=2,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
OLD=P.parent/'force_mechanism_waypoint_v3';man=json.loads((OLD/'EXECUTION_CODE_MANIFEST.json').read_text())
assert sha(OLD/'CANDIDATE_PLAN.json')==man['original_plan_sha256'];assert sha(OLD/'EXECUTABLE_PLAN.json')==man['executable_plan_sha256']
put('audit/ENGINEERING_ERRORS.json',dict(rows=[dict(stage='offline historical analysis',error='numpy bool in console JSON',impact='all files already saved; no physics'),dict(stage='analysis output isolation',error='literal historical package name in helper',recovery='old CANDIDATE_PLAN and EXECUTABLE_PLAN restored byte-exact against original execution manifest; newly created analysis JSON moved to intended package',physics_starts=0)],acknowledge_temporary_historical_write=True))
assert (P/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes()==(OLD/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes()
for d in ['source','deps']:
 for f in (P/d).rglob('*.py'):
  original=OLD/f.relative_to(P)
  assert ast.dump(ast.parse(f.read_text().replace(str(P),str(OLD))))==ast.dump(ast.parse(original.read_text())),'SOURCE_SEMANTIC_CHANGE:'+str(f)
cp=subprocess.run([sys.executable,'-B',str(P/'tests/test_certification.py')],capture_output=True,text=True)
(P/'logs/prephysical_contract_tests.log').write_text(cp.stdout+cp.stderr);assert cp.returncode==0,cp.stdout+cp.stderr
import targeted_fixture as fx
import numpy as np
from rich_planner import RichFreePlanner
from traction_mpc_stage5.full3d_adaptive_integration_v1.multisegment_reference import adapt_decision
source=(P/'tests/targeted_fixture.py').read_text().split("if __name__")[0]
source=source[source.index('def fixture'):]
source=source.replace('def fixture(index=1):',"def make_fixture(index=1,base='B'):")
source=source.replace("P/'key_traces/historical_B/summary.json'","(P/'key_traces/historical_B/summary.json' if base=='B' else P.parent/'ihear_overnight_research_retrospective_v1/source/results/development_repair2_quality_NATIVE_SCALAR_18_063/summary.json')")
source=source.replace('planner=NativeResidualPlannerV2','planner=RichFreePlanner')
source=source.replace('planner.residual_spec={}',"planner.residual_spec={};planner.free_parameters=np.asarray(OLD_PARAMETERS['free_parameters'] if base=='E' else np.zeros(18))")
ns=dict(fx.__dict__);ns.update(RichFreePlanner=RichFreePlanner,OLD_PARAMETERS=json.loads((P/'HISTORICAL_18D_PARAMETERS.json').read_text()));exec(source,ns)
registered=json.loads((P/'CANDIDATE_PLAN.json').read_text());rows=[];feasible=[]
for c in registered['coarse']:
 ok=True
 for change in c['changes']:
  f=ns['make_fixture'](change['decision_index'],c['base']);old=f['decision'].executed.schedule;stored=change['archived_schedule']
  err=max(abs(old.duration_s-stored['duration_s']),float(np.max(abs(old.sample(0).q_rad-np.asarray(stored['start_q_rad'])))),float(np.max(abs(old.sample(old.duration_s).q_rad-np.asarray(stored['target_q_rad'])))))
  try:
   new=adapt_decision(f['decision'],f['planner'],f['belief'],{**f['context'],'study_spec':change['spec']}).executed.schedule
   assert new.certificate['feasible'];new.assert_integrity()
   endpoint=max(np.max(abs(getattr(new.sample(t),k)-getattr(old.sample(t),k))) for t in [0,old.duration_s] for k in ['q_rad','dq_rad_s','ddq_rad_s2']);assert endpoint<1e-10
   dev=max(np.max(abs(new.sample(t).q_rad-old.sample(t).q_rad)) for t in np.linspace(0,old.duration_s,1001));assert dev<=np.radians(.05)+1e-10
   rows.append(dict(id=c['id'],change=change['id'],feasible=True,fixture_schedule_error=err,endpoint_error=endpoint,reference_id=new.sealed_digest,certificate_id=new.sealed_certificate_id,max_deviation_deg=np.degrees(dev)))
  except ValueError as e:ok=False;rows.append(dict(id=c['id'],change=change['id'],feasible=False,rejection=str(e),fixture_schedule_error=err))
 if ok:feasible.append(c)
put('TARGETED_MATH_TESTS.json',dict(status='PASS',rows=rows,physics_starts=0,scope='offline causal fixtures; fresh runtime certification still mandatory'))
assert all(any(c['id']==n for c in feasible) for n in ['B0','E0','B_zero','E_zero']),'BASELINE_ZERO_OFFLINE_GATE'
put('EXECUTABLE_PLAN.json',dict(coarse=feasible,omitted=[c['id'] for c in registered['coarse'] if c not in feasible],registered_unix=time.time(),original_plan_sha256=sha(P/'CANDIDATE_PLAN.json')))
manifest={str(f.relative_to(P)):sha(f) for d in ['source','code','deps','weights','tests','control'] for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in f.parts}
put('EXECUTION_CODE_MANIFEST.json',dict(files=manifest,executable_plan_sha256=sha(P/'EXECUTABLE_PLAN.json'),run_plan_sha256=sha(P/'RUN_PLAN.json'),motion_protocol_sha256=sha(P/'MOTION_ACCEPTANCE_PROTOCOL.json')))
import importlib.util,matched_harness,analyze_matched
spec=importlib.util.spec_from_file_location('smoothing_campaign',P/'control/campaign.py');campaign=importlib.util.module_from_spec(spec);spec.loader.exec_module(campaign)
assert campaign.P==P and matched_harness.PACKAGE==P and analyze_matched.S==P
assert all(str(P) in getattr(m,'__file__','') for m in [sc,hist,campaign,matched_harness,analyze_matched])
put('PREPHYSICAL_CHECKS.json',dict(status='PASS',contract_tests=json.loads((P/'CERTIFICATION_TEST_RESULTS.json').read_text())['test_count'],source_semantics='source/deps unchanged except absolute path relocation',motion_protocol_unchanged=True,historical_plan_hash_restoration_verified=True,helper_output_isolation=True,executable_candidates=len(feasible),physics_starts=0))
print(json.dumps(dict(rows=rows,candidates=len(feasible)),indent=2))
