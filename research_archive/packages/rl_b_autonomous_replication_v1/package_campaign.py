"""Seal a completed/stopped package; no training, physics or Git actions."""
from pathlib import Path
import json,time,hashlib,zipfile,os
R=Path(__file__).resolve().parent
required=['REPORT.md','RESEARCH_PLAN_AND_DECISIONS.md','MULTISEED_PPO_RESULTS.json','PPO_LEARNING_CURVES.md','MATCHED_EVALUATOR_AUDIT.md','BASELINE_REPRODUCTION.json','STAGE2_PERFORMANCE_STUDY.md','STAGE2_RESULTS.json','VALIDATION_RESULTS.json','RESOURCE_USAGE.json','ATTEMPT_ACCOUNTING.json','PACKAGE_VERIFICATION.json','FINAL_CAMPAIGN_READINESS.md','NEXT_RESEARCH_DECISION.md']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024**2),b''):h.update(x)
 return h.hexdigest()
def put(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def main():
 validation=json.loads((R/'VALIDATION_RESULTS.json').read_text());exit_audit=json.loads((R/'PROCESS_EXIT_AUDIT.json').read_text())
 if not validation['pass'] or not exit_audit['pass']:raise RuntimeError('FINAL_VERIFICATION_OR_PROCESS_EXIT_FAILED')
 if not (R/'STOP.json').exists():raise RuntimeError('EXPLICIT_STOP_RECORD_REQUIRED')
 missing=[n for n in required if n!='PACKAGE_VERIFICATION.json' and not (R/n).is_file()]
 if missing:raise RuntimeError('MISSING_REQUIRED_DELIVERABLES:'+repr(missing))
 # These two verification files are explicitly excluded to avoid self-hashing.
 files={str(p.relative_to(R)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(R.rglob('*')) if p.is_file() and p.name not in ['OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json'] and '__pycache__' not in p.parts}
 manifest={'schema':'ihear_replication_payload_sha256_v1','created_unix':time.time(),'files':files,'self_exclusions':['OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json'],'pycache_excluded_as_generated_non_evidence':True}
 put(R/'OUTPUT_MANIFEST.json',manifest)
 checked={k:sha(R/k)==m['sha256'] and (R/k).stat().st_size==m['bytes'] for k,m in files.items()}
 verification={'unix':time.time(),'status':'PASS' if all(checked.values()) else 'FAIL','payload_files':len(files),'payload_bytes':sum(m['bytes'] for m in files.values()),'manifest_hashes_all_match':all(checked.values()),'manifest_sha256':sha(R/'OUTPUT_MANIFEST.json'),'required_deliverables':required,'all_required_deliverables_present':True,'history_source_checkpoints_unchanged':validation['checks']['historical_4827_files_and_original_archives_unchanged'],'native_and_raw_independent_verification':validation['checks']['evaluation_final_native_receipt_recomputation'],'START_END_closed':validation['checks']['START_END_all_closed'],'owned_processes_exited':exit_audit['pass'],'validation_pass':validation['pass'],'final_campaign_started':False,'final_decision':'NOT_READY_FOR_FINAL_CAMPAIGN','hash_scope_exclusions':manifest['self_exclusions'],'archive_verification_is_external':True}
 put(R/'PACKAGE_VERIFICATION.json',verification)
 archive=R.parent/(R.name+'_verified.zip')
 if archive.exists():raise RuntimeError('ARCHIVE_ALREADY_EXISTS')
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True) as z:
  for name in sorted([*files,'OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json']):z.write(R/name,str(Path(R.name)/name))
 with zipfile.ZipFile(archive) as z:
  bad=z.testzip();payload_ok=True
  for name,m in files.items():
   h=hashlib.sha256()
   with z.open(str(Path(R.name)/name)) as f:
    for b in iter(lambda:f.read(1024**2),b''):h.update(b)
   if h.hexdigest()!=m['sha256']:payload_ok=False
 external={'unix':time.time(),'archive':str(archive),'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'crc_ok':bad is None,'all_manifest_payload_hashes_match':payload_ok,'manifest_sha256':sha(R/'OUTPUT_MANIFEST.json'),'package_verification_sha256':sha(R/'PACKAGE_VERIFICATION.json'),'members':len(files)+2,'pass':bad is None and payload_ok}
 put(R.parent/(R.name+'_ARCHIVE_VERIFICATION.json'),external)
 assert external['pass']
 print(json.dumps(external))
if __name__=='__main__':main()
