"""Install only new study files and run non-physical gates before source freeze."""
from pathlib import Path
import os,sys,json,shutil,time,hashlib,ast,traceback,types,copy
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent;P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',STUDY_GROUP='P00',STUDY_MODE='history')
for stage in ['stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning']:sys.path.insert(0,str(P/'source/stages'/stage/'src'))
sys.path[:0]=[str(P),str(P/'control'),str(P/'code')]
def put(n,x):
    f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
for f in R.iterdir():
    if f.suffix in ['.py','.md'] and f.name!='bootstrap.py':
        if f.suffix=='.py':ast.parse(f.read_text(encoding='utf-8'))
        shutil.copy2(f,P/f.name)
from patient_models import model_static_audit,digest
records=[]
for row in json.loads((P/'COHORT.json').read_text())['patients']:
    case=json.loads((P/row['case_path']).read_text());target=P/'patients'/row['patient_id']/'static'
    if (target/'MODEL_STATIC_AUDIT.json').exists():
        result=json.loads((target/'MODEL_STATIC_AUDIT.json').read_text());assert result['case_sha256']==digest(case)
    else:result=model_static_audit(case,target,verify_robot=True,patient_id=row['patient_id'])
    records.append(result);print('STATIC',row['patient_id'],result['model_static_valid'],flush=True)
put('STATIC_PATIENT_AUDIT.json',dict(records=records,native_steps=0))
assert all(r['model_static_valid'] for r in records)
assert len({r['invariant_robot_contact_interface_sections_sha256'] for r in records})==1
import streaming_reuse
rt=types.SimpleNamespace(persist_runtime_artifacts=lambda:None)
# Modules, unlike SimpleNamespace, are hashable like the actual runtime module.
rt=types.ModuleType('serializer_probe');rt.persist_runtime_artifacts=lambda:None
def install(module):module.persist_runtime_artifacts=lambda:None
memory=types.SimpleNamespace(install=install)
original=rt.persist_runtime_artifacts;streaming_reuse.ensure(rt,memory)
rt.persist_runtime_artifacts=original
old_failure=False
try:streaming_reuse.ensure(rt,memory)
except AssertionError:old_failure=True
assert old_failure
streaming_reuse.restore(rt)
for _ in range(2):
    streaming_reuse.ensure(rt,memory);rt.persist_runtime_artifacts=lambda:None;streaming_reuse.restore(rt)
put('tests/SERIALIZER_OWNER_PROBE.json',dict(status='PASS',old_failure_reproduced=True,two_corrected_calls=True,native_steps=0))
import numpy as np
import history_features as hf
rows=[]
for i in range(601):
    p='OUTBOUND' if i<200 else 'HOLD' if i<400 else 'RETURN';s=i*.005
    rows.append(dict(physical_s=s,phase=p,estimated_q_dq=[0.,-.01,0.,0.],reference_q_dq=[0.,0.,0.,0.],
        reference_progress=.4,force_world_N=[10. if p=='OUTBOUND' else 5.,0.,0.],moment_world_Nm=[0.,1.,0.],source_age_s=0.))
meta=dict(complete_task_observed=True,commissioned_belief={})
h=hf.summarize(rows,meta);a=hf.ilc(h);off=hf.ilc(h,False)
assert a['action']['knee_delta_deg']<0 and a['action']['phase']=='OUTBOUND' and off['action']['knee_delta_deg']==0
assert len(h['features'])==len(hf.FEATURE_NAMES)
poisoned=copy.deepcopy(rows)
for row in poisoned:row['native_truth_injected_for_negative_test']=[999999.,-999999.]
h2=hf.summarize(poisoned,meta);assert h2['features']==h['features']
put('tests/HISTORY_CAUSAL_PROBE.json',dict(status='PASS',full_integral_expected_N_s=20.,computed_N_s=h['JF_N_s'],
    poison_truth_does_not_change_features=True,ilc_changes_with_history=True,disabled_is_A0=True,native_steps=0))
files={}
for d in ['source','code','deps','control']:
    for f in sorted((P/d).rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and 'results' not in f.relative_to(P).parts:files[str(f.relative_to(P))]=sha(f)
for n in ['continuous_runner.py','bounded_planner.py','history_features.py','cross_analysis.py','patient_models.py','FROZEN_18D.json','ACTION_SET.json','MOTION_ACCEPTANCE_PROTOCOL.json']:
    files[n]=sha(P/n)
put('EXECUTION_CODE_MANIFEST.json',dict(files=files,frozen_unix=time.time(),source_copy_only=True,new_isolated_planner='bounded_planner.py',controller_or_safety_source_edits=False))
# campaign_v6 reads this historical-named manifest at import; it is an explicit same-byte alias, not a stale identity.
shutil.copy2(P/'EXECUTION_CODE_MANIFEST.json',P/'EXECUTION_CODE_MANIFEST_v6.json')
put('PREPHYSICAL_CHECKS.json',dict(status='PASS',unix=time.time(),static_patients=len(records),serializer_owner_probe=True,causal_history_probe=True,
    source_manifest_sha256=sha(P/'EXECUTION_CODE_MANIFEST.json'),new_physics_starts=0,remaining_gate='real full-state repeated action equivalence'))
for n in ['PREPHYSICAL_CHECKS.json','STATIC_PATIENT_AUDIT.json','EXECUTION_CODE_MANIFEST.json']:shutil.copy2(P/n,R/n)
print('PREPHYSICAL_PASS',flush=True)
