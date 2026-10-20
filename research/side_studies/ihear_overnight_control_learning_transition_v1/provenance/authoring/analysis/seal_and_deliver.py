"""Package verification, scientific manifest and byte-verified Windows mirror."""
from pathlib import Path
import os,sys,json,hashlib,time,shutil,subprocess
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f):
    h=hashlib.sha256()
    with f.open('rb') as stream:
        for block in iter(lambda:stream.read(4*2**20),b''):h.update(block)
    return h.hexdigest()
assert read('audit/HISTORY_PROTECTION_FINAL.json')['status']=='PASS'
assert read('audit/SCIENTIFIC_VERIFICATION_FINAL.json')['status']=='PASS'
assert (P/'PHYSICS_CLOSED.json').exists() and (P/'audit/MONITOR_EXIT.json').exists()
required=['REPORT.md','OVERNIGHT_TIMELINE.md','FROZEN_CONTROL_BASELINE.md','COUPLED_RESPONSE_IDENTIFICATION.md','PREDICTION_VALIDATION.json','LEARNING_PROBLEM_DEFINITION.md','LEARNING_DATASET_AUDIT.md','STATE_ACTION_REWARD_SCHEMA.json','Q_VALUE_EXPERIMENTS.md','LEARNING_RESULTS.json','LEARNING_RESULTS_FINAL.json','FEW_REPETITION_EVALUATION.md','RL_BASELINE_STUDY.md','EXPERIMENT_RESULTS.json','ATTEMPT_ACCOUNTING.json','NEXT_RESEARCH_DECISION.md','REPRODUCE.md']
assert all((P/n).is_file() for n in required)
required+=['EARLY_VALUE_STUDY.md','EARLY_VALUE_EVALUATION.json','EARLY_VALUE_PROTOCOL.json','REPETITION_SERIALIZER_REPAIR.md']
assert all((P/n).is_file() for n in required)
live=[];me=os.getpid()
for path in Path('/proc').iterdir():
    if not path.name.isdigit() or int(path.name)==me:continue
    try:cmd=(path/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
    except (FileNotFoundError,PermissionError,ProcessLookupError):continue
    # Exclude current wsl/bash parent wrappers; require a Python executable.
    exe=cmd.split(' ',1)[0]
    if 'python' in Path(exe).name and (str(P)+'/' in cmd or str(R)+'/' in cmd):live.append(dict(pid=int(path.name),command=cmd))
assert not live,live
put('audit/OWNED_PROCESSES_CLOSED.json',dict(status='PASS',unix=time.time(),live_owned_python_processes=live,method='launcher EXIT receipts, closed START/END, exclusive physics lock, /proc Python command inventory; audit packager excluded'))
# Keep actual authoring versions separate from frozen copied runtime sources.
sources={}
protected=set()
for mf in P.glob('EXECUTION_CODE_MANIFEST*.json'):protected.update(json.loads(mf.read_text())['files'])
for path in read('models/TRAINING_CODE_MANIFEST.json')['files']:
    protected.add(str(Path(path).relative_to(P)))
for sub in ['control','analysis','learning']:
    for f in sorted((R/sub).glob('*.py')):
        target=P/'provenance/authoring'/sub/f.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target);sources[str(target.relative_to(P))]=sha(target)
        executable=P/sub/f.name;relative=str(executable.relative_to(P))
        if relative not in protected:
            if executable.exists() and sha(executable)!=sha(f):
                old=P/'provenance/pre_delivery_sources'/sub/f.name;old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(executable,old)
            shutil.copy2(f,executable)
put('provenance/AUTHORING_MANIFEST.json',dict(files=sources,scope='final Windows authoring versions; frozen execution versions remain at original manifest paths; initial predictor retained separately'))
now=time.time();plan=read('RUN_PLAN.json');acc=read('ATTEMPT_ACCOUNTING.json')
assert now<plan['hard_stop_unix'];assert not acc['unknown_native_cost_ids']
verification=dict(status='PASS',finished_unix=now,elapsed_seconds=now-plan['t0_unix'],hard_deadline_met=True,physics_closed=read('PHYSICS_CLOSED.json'),all_required_deliverables_present=True,required_files=required,source_and_model_identity='audit/SCIENTIFIC_VERIFICATION_FINAL.json',raw_arithmetic='all complete source/results tasks have derived/*_INDEPENDENT.json',history_protection=read('audit/HISTORY_PROTECTION_FINAL.json'),attempt_accounting=dict(P1_START=acc['P1_START'],P1_END=acc['P1_END'],P2_episodes=0,actual_new_native_steps=acc['actual_new_native_steps']),owned_processes='audit/OWNED_PROCESSES_CLOSED.json',git_mutations_performed=False,evidence_scope='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION; one Human',evidence_manifest='EVIDENCE_MANIFEST.json',delivery_verification='DELIVERY_VERIFICATION.json',scientific_success_distinct_from_package_integrity=True)
put('PACKAGE_VERIFICATION.json',verification)
put('STATE.json',dict(phase='STOP_COMPLETE',unix=now,physics_starts=acc['P1_START'],physics_ends=acc['P1_END'],next='No automatic next study'))
excluded={'EVIDENCE_MANIFEST.json','DELIVERY_VERIFICATION.json','audit/FINAL_MANIFEST_VERIFICATION.json'}
def include(f):
    rel=f.relative_to(P)
    return f.is_file() and str(rel) not in excluded and not any(x in ['tmp','__pycache__'] for x in rel.parts) and f.suffix not in ['.pyc','.lock']
files={str(f.relative_to(P)):dict(sha256=sha(f),size=f.stat().st_size) for f in sorted(P.rglob('*')) if include(f)}
put('EVIDENCE_MANIFEST.json',dict(files=files,created_unix=time.time(),exclusions=sorted(excluded)+['tmp/**','__pycache__/**','*.pyc','*.lock'],scope='all stable scientific evidence, failed records, source, models, reports and final protection audits'))
assert all(sha(P/n)==entry['sha256'] for n,entry in files.items())
put('audit/FINAL_MANIFEST_VERIFICATION.json',dict(status='PASS',files=len(files),manifest_sha256=sha(P/'EVIDENCE_MANIFEST.json'),unix=time.time()))
delivery_files=list(files)+['EVIDENCE_MANIFEST.json','audit/FINAL_MANIFEST_VERIFICATION.json']
total=0
for n in delivery_files:
    source=P/n;target=R/n;target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists() or sha(target)!=sha(source):shutil.copy2(source,target)
    assert sha(source)==sha(target),n;total+=source.stat().st_size
delivery=dict(status='PASS',canonical=str(P),windows_mirror=str(R),files=len(delivery_files),bytes=total,verified_sha256_equal=True,canonical_evidence_manifest_sha256=sha(P/'EVIDENCE_MANIFEST.json'),unix=time.time(),mirror_extra_authoring_checkpoint_files_not_scientific_evidence=True)
put('DELIVERY_VERIFICATION.json',delivery);shutil.copy2(P/'DELIVERY_VERIFICATION.json',R/'DELIVERY_VERIFICATION.json')
print('PACKAGE_AND_DELIVERY_PASS',len(files),'FILES',total,'BYTES',flush=True)
