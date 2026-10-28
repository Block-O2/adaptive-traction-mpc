"""Terminal package manifest and verification. Invoke after every owned job exits."""
from pathlib import Path
import json,hashlib,datetime,os,ast
P=Path(__file__).resolve().parents[1]
REQUIRED=['REPORT.md','RESEARCH_MILESTONE_REFLECTION.md','RESEARCH_DECISION_LOG.jsonl','EXPERIMENT_CONTRACT.md','PHYSICS_MECHANISM_AUDIT.md','FORWARD_PROXY_VALIDATION.md','PROXY_MODEL_RESULTS.json','OPTIMIZATION_PLAN.md','THREE_ARM_RESULTS.json','BASELINE_AND_CANDIDATE_COMPARISON.md','MODEL_RESIDUAL_STUDY.md','MOTION_AND_WRENCH_TRADEOFF.md','CROSS_CYCLE_INTERFACE_PROPOSAL.md','ATTEMPT_ACCOUNTING.json','RESOURCE_USAGE.json','SOURCE_RETURN_PLAN.md','NEXT_RESEARCH_DECISION.md']
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for x in iter(lambda:s.read(4*2**20),b''):h.update(x)
 return h.hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def main():
 checks={};errors=[]
 for name in REQUIRED:
  f=P/name;checks[name]=f.is_file() and f.stat().st_size>0
  if not checks[name]:errors.append('MISSING_OR_EMPTY:'+name)
 for name in ['audit/HISTORY_END.json','audit/PROCESS_EXIT_AUDIT.json','ATTEMPT_ACCOUNTING.json','RESOURCE_USAGE.json','audit/INDEPENDENT_RAW_AUDIT.json']:
  d=json.loads((P/name).read_text());checks[name]=d['status']=='PASS'
  if not checks[name]:errors.append('AUDIT_NOT_PASS:'+name)
 for name in ['CAMPAIGN_SOURCE_MANIFEST.json','VALIDATION_SOURCE_MANIFEST.json']:
  for rel,h in json.loads((P/name).read_text())['files'].items():
   if sha(P/rel)!=h:errors.append('FROZEN_SOURCE_CHANGED:'+rel)
 journal=P.parent/'RESEARCH_DECISION_JOURNAL.md';jfinal=json.loads((P/'audit/JOURNAL_FINAL_RECORDING.json').read_text());checks['long_term_journal_final_sha']=sha(journal)==jfinal['final_sha256'];checks['long_term_original_reflection_preserved']=journal.read_bytes().startswith((P/'history/RESEARCH_DECISION_JOURNAL_START.md').read_bytes())
 for k in ['long_term_journal_final_sha','long_term_original_reflection_preserved']:
  if not checks[k]:errors.append(k)
 for f in (P/'source').glob('*.py'):ast.parse(f.read_text(),filename=str(f))
 current=json.loads((P/'WORK_STATE.json').read_text());current.update(active_phase='STOP',terminal_status='COMPLETE_BOUNDED_STUDY',owned_physics_running=False,remaining_work=[],next=[]);put('WORK_STATE.json',current)
 (P/'STOP_REQUESTED').write_text('FINITE_STUDY_COMPLETE_NO_AUTO_RESTART\n');now=datetime.datetime.now(datetime.timezone.utc);start=json.loads((P/'START.json').read_text());t0=datetime.datetime.fromisoformat(start['T0_utc']);deadline=datetime.datetime.fromisoformat(start['deadline_utc']);checks['within_original_7h']=now<=deadline
 if not checks['within_original_7h']:errors.append('HARD_DEADLINE_EXCEEDED')
 put('END.json',{'status':'STOP','time_utc':now.isoformat(),'original_T0_utc':start['T0_utc'],'actual_autonomous_elapsed_hours':(now-t0).total_seconds()/3600,'hard_deadline_utc':start['deadline_utc'],'clock_never_reset':True,'all_owned_processes_exited':checks['audit/PROCESS_EXIT_AUDIT.json'],'no_auto_next_package_Stage2_campaign_Git_changes':True})
 models=[]
 for f in sorted((P/'models').glob('C_*.json')):
  d=json.loads(f.read_text());models.append({'path':str(f.relative_to(P)),'model_id':d.get('id'),'role':'PRODUCTION_PREQUENTIAL' if 'public_baseline_anchor' in d else 'SYNTHETIC_ZERO_PHYSICS_PREFLIGHT_ONLY','sha256':sha(f),'training_attempt_ids':d.get('training_attempt_ids')})
 put('audit/MODEL_ARTIFACT_SCOPE_FINAL.json',{'rows':models,'preflight_not_patient_data':True})
 files={str(f.relative_to(P)):{'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(P.rglob('*')) if f.is_file() and f not in [P/'OUTPUT_MANIFEST.json',P/'PACKAGE_VERIFICATION.json'] and '__pycache__' not in f.parts}
 put('OUTPUT_MANIFEST.json',{'schema':'lgmi.package.v1','files':files,'scope':'all retained inputs/new source/models/raw/results/reports except manifest and verification themselves','seal_utc':now.isoformat()})
 # Re-read every manifest entry, not merely the in-memory hashes.
 manifest=json.loads((P/'OUTPUT_MANIFEST.json').read_text());verified=0
 for rel,r in manifest['files'].items():
  if (P/rel).stat().st_size!=r['bytes'] or sha(P/rel)!=r['sha256']:errors.append('OUTPUT_HASH_MISMATCH:'+rel)
  verified+=1
 checks['all_output_sha256_rechecked']=not any(e.startswith('OUTPUT_HASH') for e in errors)
 verification={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors,'verified_output_files':verified,'output_manifest_sha256':sha(P/'OUTPUT_MANIFEST.json'),'required_deliverables':REQUIRED+['PACKAGE_VERIFICATION.json'],'report_sha256':sha(P/'REPORT.md'),'final_journal_sha256':sha(journal),'all_owned_jobs_joined':checks['audit/PROCESS_EXIT_AUDIT.json'],'source_sha256':sha(Path(__file__)),'interpretation':'package integrity, not blanket PASS for scientific/clinical/hardware claims; see FINAL_STATUS.json','utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 put('PACKAGE_VERIFICATION.json',verification);print(json.dumps({'status':verification['status'],'errors':errors,'files_verified':verified,'elapsed_hours':(now-t0).total_seconds()/3600}),flush=True)
if __name__=='__main__':main()
