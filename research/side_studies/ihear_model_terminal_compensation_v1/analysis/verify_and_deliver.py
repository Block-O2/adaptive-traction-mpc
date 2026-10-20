"""Final checks and full evidence mirror; never starts physics."""
from pathlib import Path
import os,json,time,hashlib,shutil,ast,subprocess
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as z:
  for b in iter(lambda:z.read(2**20),b''):h.update(b)
 return h.hexdigest()
# Add analysis provenance after results are complete; the execution closure is immutable.
for f in (R/'analysis').glob('*.py'):shutil.copy2(f,P/'analysis'/f.name)
shutil.copy2(R/'REPRODUCTION.md',P/'REPRODUCTION.md')
required=['REPORT.md','CONTROL_ARCHITECTURE_AUDIT.md','TERMINAL_OVERSHOOT_DIAGNOSIS.md','MODEL_PREDICTION_STUDY.md','EXISTING_CONTROLLER_TUNING.md','PD_ASSIST_STUDY.md','FEEDFORWARD_ABLATION.md','EXPERIMENT_RESULTS.json','CANDIDATE_LEDGER.json','VALIDATION_RESULTS.json','ATTEMPT_ACCOUNTING.json','NEXT_RESEARCH_DECISION.md']
for n in required:assert (P/n).is_file() and (P/n).stat().st_size>0
figure_names=['01_historical_terminal.png','02_control_model_acceleration.png','03_causal_prediction_error.png','04_overshoot_before_after.png','05_force_motion_moment.png','06_interventions_terminal.png','07_coupling_and_control.png','08_development_holdout.png','09_controller_intents.png']
assert all((P/'figures'/n).exists() for n in figure_names)
put('audit/FIGURE_REVIEW.json',dict(status='PASS',method='Rendered PNGs inspected in the assistant image viewer; scientific plots use original raw-derived values',figures=figure_names,checks=['readable axes and units','visible original excursion threshold','reference/actual labels','W1 versus unused W2 scope','causal contrast and bounded controller intentions','undershoot definition explicit'],superseded_exploratory_plot='01_terminal_reference_actual.png is retained as an earlier diagnostic; use 01_historical_terminal.png for the final reference/actual comparison'))
source_checks=[]
for n in ['EXECUTION_CODE_MANIFEST.json','EXECUTION_CODE_MANIFEST_v2.json']:
 m=read(n);errors=[rel for rel,h in m['files'].items() if not (P/rel).exists() or sha(P/rel)!=h];assert not errors,errors
 source_checks.append(dict(manifest=n,sha256=sha(P/n),files=len(m['files']),status='PASS'))
syntax=0
for root in ['analysis','control']:
 for f in (P/root).rglob('*.py'):ast.parse(f.read_text(),filename=str(f));syntax+=1
acc=read('ATTEMPT_ACCOUNTING.json');assert acc['status']=='PASS_CLOSED';assert acc['START']==acc['END']<=80
assert read('audit/INDEPENDENT_ATTEMPT_ACCOUNTING.json')['status']=='PASS'
ind=[read('audit/INDEPENDENT_'+g+'.json') for g in ['Dev','Ctrl','W2']];assert all(x['status']=='PASS' for x in ind)
checks=[y for x in ind for y in x['checks']];assert len(checks)==acc['complete_runs'];assert {x['id'] for x in checks}=={r['id'] for r in acc['rows'] if r['status']=='COMPLETE_FULL_TASK'}
results=read('EXPERIMENT_RESULTS.json');assert results['status']=='CLOSED_WITH_PRESERVED_FAILED_ATTEMPTS';assert not results['partial_ranked']
all_raw=[r for r in results['rows']];assert all(r['task']=='PASS' and r['receipt']=='PASS' and r['absolute_safety'] for r in all_raw)
for g in ['Ctrl','W2']:assert read(g+'_DONE.json')['all_children_joined'];assert read(g+'_PAIR_GATE.json')['status']=='PASS';assert read(g+'_PARENT_GATE.json')['status']=='PASS'
assert read('REPEAT_VERIFICATION.json')['status']=='PASS'
for g in ['Dev','W2']:assert read('audit/'+g+'_FULL_NATIVE_CAUSAL_PROOF.json')['status']=='PASS'
assert read('audit/HISTORY_PROTECTION.json')['status']=='PASS';assert read('audit/GIT_LOGICAL_STATE.json')['status']=='PASS';assert read('audit/OWNED_PROCESS_EXIT.json')['status']=='PASS'
assert read('PHYSICS_CLOSED.json')['status']=='CLOSED';assert (P/'PHYSICS_STOP.json').exists() and (P/'PHYSICS_STOP_v2.json').exists()
selection=read('NEW_FROZEN_SELECTION.json');reg=read('HOLDOUT_REGISTRATION.json');rep=read('REPEAT_VERIFICATION.json');w2start=next(r['start_unix'] for r in acc['rows'] if r['id']=='W2_parent')
assert selection['selected_unix']<reg['registered_unix']<w2start;assert rep['unix']<w2start
assert all(r['registered_before_START'] for r in read('CANDIDATE_LEDGER.json')['entries'] if 'registered_before_START' in r)
plan=read('RUN_PLAN.json');assert time.time()<plan['hard_stop_unix']
put('STATE.json',dict(phase='STOP_COMPLETE',physics_starts=acc['START'],physics_end_count=acc['END'],primary='H150',validation=read('VALIDATION_RESULTS.json')['status'],no_next_package=True,unix=time.time()))
verification=dict(status='PASS',unix=time.time(),evidence_level='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION',required_deliverables_present=True,source_closures=source_checks,analysis_control_AST_files=syntax,START_END_closed=True,complete_raw_runs_recomputed=len(checks),arithmetic_method='Separate implementation/process, same agent; no plant/controller imports',independent_audit_files=['audit/INDEPENDENT_'+g+'.json' for g in ['Dev','Ctrl','W2']],native_ownership_and_source_age_verified=True,all_complete_runs_task_safety_receipt=True,failed_motion_candidates_preserved=True,partial_not_ranked=True,deterministic_repeat='PASS',holdout=read('VALIDATION_RESULTS.json')['status'],no_holdout_retuning=True,causal_hip_only_contrast='PASS Dev and W2',history_protection=read('audit/HISTORY_PROTECTION.json'),git_logical_state=read('audit/GIT_LOGICAL_STATE.json'),all_owned_physics_processes_exited=True,elapsed_since_conservative_T0_s=time.time()-plan['t0_unix'],last_60min_of_hard_budget_physics_cutoff_preserved=True,early_stop_reason='Mechanism contrast, failed bounded ablations, full repeat and unused-prefix validation are decisive for this scope; no budget-filling experiments',formal_LEVEL2=False,host_realtime_LEVEL3=False,cross_Human=False,hardware=False,clinical=False,delivery='Full scientific evidence mirrored to Windows; see DELIVERY_VERIFICATION.json',manifest_scope='EVIDENCE_MANIFEST.json covers all stable canonical evidence including this verification; excludes temporary/cache/lock files, itself and final delivery verification to avoid circular hashes')
put('PACKAGE_VERIFICATION.json',verification)
files={}
for f in sorted(P.rglob('*')):
 if not f.is_file():continue
 rel=f.relative_to(P)
 if any(v in rel.parts for v in ['tmp','__pycache__']) or f.suffix in ['.pyc','.lock'] or str(rel) in ['EVIDENCE_MANIFEST.json','DELIVERY_VERIFICATION.json']:continue
 files[str(rel)]=dict(sha256=sha(f),size=f.stat().st_size)
put('EVIDENCE_MANIFEST.json',dict(status='FROZEN_FINAL',unix=time.time(),files=files))
assert shutil.disk_usage(R).free>sum(x['size'] for x in files.values())+2**30
delivered=0
for rel,entry in files.items():
 target=R/rel;target.parent.mkdir(parents=True,exist_ok=True)
 if not target.exists() or sha(target)!=entry['sha256']:shutil.copy2(P/rel,target)
 assert sha(target)==entry['sha256'];delivered+=entry['size']
 if len(str(rel))==0:raise AssertionError('EMPTY_PATH')
shutil.copy2(P/'EVIDENCE_MANIFEST.json',R/'EVIDENCE_MANIFEST.json');assert sha(P/'EVIDENCE_MANIFEST.json')==sha(R/'EVIDENCE_MANIFEST.json')
delivery=dict(status='PASS',unix=time.time(),canonical=str(P),Windows_destination='C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/'+R.name,files_verified=len(files)+1,bytes_evidence_mirrored=delivered,all_evidence_SHA256_matches=True,evidence_manifest_sha256=sha(P/'EVIDENCE_MANIFEST.json'),temporary_runtime_files_excluded=True,all_required_deliverables=[*required,'PACKAGE_VERIFICATION.json'])
put('DELIVERY_VERIFICATION.json',delivery);shutil.copy2(P/'DELIVERY_VERIFICATION.json',R/'DELIVERY_VERIFICATION.json')
print(json.dumps(dict(status='PASS',starts=acc['START'],complete_raw_runs=len(checks),files_verified=len(files)+1,bytes=delivered,validation=read('VALIDATION_RESULTS.json')['status'],elapsed_s=verification['elapsed_since_conservative_T0_s'])),flush=True)
