"""Non-physical static preflight and frozen source manifest."""
from pathlib import Path
import os,sys,json,shutil,time,hashlib,traceback,ast
sys.dont_write_bytecode=True
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
R=Path(__file__).resolve().parent
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
for stage in ['stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning']:sys.path.insert(0,str(P/'source/stages'/stage/'src'))
def put(n,x):
    f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for name in ['cross_runner.py','cross_analysis.py','prepare_execution.py','register_study.py','serial_campaign.py','verify_reference.py']:
    shutil.copy2(R/name,P/name);ast.parse((P/name).read_text())
shutil.copy2(R/'audit_human/patient_models.py',P/'patient_models.py')
for rel in ['audit_human/HUMAN_MODEL_AUDIT.md','audit_protocol/PATIENT_VARIATION_CONTRACT.md','audit_protocol/P1_PROTOCOL.md','audit_protocol/LEARNING_DATA_SCHEMA.json','audit_execution/FROZEN_B_H150_CONTRACT.md']:
    shutil.copy2(R/rel,P/Path(rel).name)
sys.path.insert(0,str(P))
from patient_models import model_static_audit,digest
cohort=json.loads((P/'VIRTUAL_PATIENT_COHORT.json').read_text())
records=[]
for patient in cohort['patients']:
    pid=patient['patient_id'];case=json.loads((P/patient['case_path']).read_text())
    target=P/'patients'/pid/'static'
    if (target/'MODEL_STATIC_AUDIT.json').exists():
        result=json.loads((target/'MODEL_STATIC_AUDIT.json').read_text())
        assert result['case_sha256']==digest(case),'STALE_STATIC_CASE:'+pid
        assert json.loads((target/'qualification_case.json').read_text())==case,'STALE_STATIC_MODEL_INPUT:'+pid
        assert sha(target/'model.xml')==result['xml_sha256'],'STALE_STATIC_XML:'+pid
    else:
        try:result=model_static_audit(case,output_dir=target,verify_robot=True,patient_id=pid)
        except Exception as error:
            result=dict(patient_id=pid,model_static_valid=False,status='STATIC_AUDIT_ERROR',error=str(error),traceback=traceback.format_exc(),native_steps=0,physics_starts=0)
            put('patients/'+pid+'/STATIC_ERROR.json',result)
    records.append(result)
    print('STATIC',pid,result.get('model_static_valid'),result.get('error',result.get('static_assembly',{}).get('category')),flush=True)
put('STATIC_PATIENT_AUDIT.json',dict(registered_patients=len(records),records=records,physics_starts=0))
valid=[r for r in records if r.get('model_static_valid')]
invariants={r['invariant_robot_contact_interface_sections_sha256'] for r in valid}
assert len(invariants)<=1,'ROBOT_CONTACT_CHANGED_BETWEEN_PATIENTS'
baseline=records[0]
assert baseline.get('model_static_valid'),'REFERENCE_STATIC_PREFLIGHT_FAILED'
original=P.parent/'ihear_overnight_control_learning_transition_v1'
original_case=json.loads((original/'source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_nominal_sync_120_v1.json').read_text())
assert original_case==json.loads((P/'patients/P00/case.json').read_text()),'REFERENCE_CASE_NOT_EXACT'
files={}
for sub in ['source','code','deps','control']:
    for f in sorted((P/sub).rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and 'results' not in f.relative_to(P).parts:files[str(f.relative_to(P))]=sha(f)
for n in ['cross_runner.py','cross_analysis.py','patient_models.py','serial_campaign.py','verify_reference.py','FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','ACTION_SET.json']:files[n]=sha(P/n)
manifest=dict(files=files,registered_unix=time.time(),historical_algorithms_unchanged_except_package_path_relocation=True,patient_generation='existing qualification_case plant-only argument',new_orchestration=['cross_runner.py','cross_analysis.py','patient_models.py'])
put('EXECUTION_CODE_MANIFEST.json',manifest)
put('PREPHYSICAL_CHECKS.json',dict(status='PASS',unix=time.time(),reference_exact_case=True,static_valid=len(valid),static_total=len(records),invariant_robot_contact=True,cohort_hash=sha(P/'VIRTUAL_PATIENT_COHORT.json'),source_hash=sha(P/'EXECUTION_CODE_MANIFEST.json'),physics_starts=0,full_admissibility_requires_patient_commissioning=True))
for n in ['STATIC_PATIENT_AUDIT.json','PREPHYSICAL_CHECKS.json','EXECUTION_CODE_MANIFEST.json']:shutil.copy2(P/n,R/n)
print('PREPHYSICAL_PASS',len(valid),'/',len(records),flush=True)
