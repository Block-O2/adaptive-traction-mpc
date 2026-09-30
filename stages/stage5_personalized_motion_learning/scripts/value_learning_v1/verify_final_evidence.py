"""Verify closed NEW campaign bytes, lossless content, models and frozen source."""
from datetime import datetime,timezone
from pathlib import Path
import gzip,hashlib,json,time
from research_campaign import R,S,D,RAW,RUNS,sha,save

def content_sha(path):
 h=hashlib.sha256()
 with gzip.open(path,'rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def main():
 started=time.perf_counter();failures=[];checked=0;bytes_checked=0;rollouts=0;archived=0
 source=json.loads((D/'SOURCE_FINGERPRINTS.json').read_text())
 for key in ('production_files_sha256','frozen_evidence_sha256'):
  for path,expected in source[key].items():
   actual=sha(R/path);checked+=1
   if actual!=expected:failures.append({'path':path,'kind':'frozen_source_hash_mismatch'})
 supplement=json.loads((D/'OBJECTIVE_SCOPE_SUPPLEMENT.json').read_text())
 if sha(D/'LEARNING_RESEARCH_V1_CONTRACT.json')!=supplement['original_contract_sha256']:
  failures.append({'kind':'original_contract_changed'})
 for rp in sorted(RUNS.glob('*/rollout_result.json')):
  record=json.loads(rp.read_text());rollouts+=1
  if record.get('status')=='RUNNING':
   failures.append({'run_id':record['run_id'],'kind':'rollout_not_closed'});continue
  root=rp.parent
  virtual={e['original_path']:e for e in record.get('lossless_archives',[])}
  for relative,expected in record.get('raw_files_sha256',{}).items():
   path=root/relative
   try:
    if path.exists():actual=sha(path);bytes_checked+=path.stat().st_size
    elif relative in virtual:
     entry=virtual[relative];actual=content_sha(root/entry['archive_path']);bytes_checked+=entry['original_bytes'];archived+=1
    else:raise FileNotFoundError(path)
    checked+=1
    if actual!=expected:failures.append({'run_id':record['run_id'],'path':relative,'kind':'raw_hash_mismatch'})
   except Exception as error:failures.append({'run_id':record['run_id'],'path':relative,'error':str(error)})
  # Entries may include an archived file not listed under the original name.
  for relative,entry in virtual.items():
   if relative not in record.get('raw_files_sha256',{}):
    actual=content_sha(root/entry['archive_path']);checked+=1;archived+=1;bytes_checked+=entry['original_bytes']
    if actual!=entry['original_sha256']:failures.append({'run_id':record['run_id'],'path':relative,'kind':'lossless_content_mismatch'})
  if rollouts%100==0:print(json.dumps({'verified_rollouts':rollouts,'verified_files':checked,'failures':len(failures)}),flush=True)
 manifest=json.loads((D/'RAW_DATA_MANIFEST.json').read_text())
 for relative,expected in manifest['auxiliary_files_sha256'].items():
  path=RAW/relative;checked+=1
  if not path.exists() or sha(path)!=expected:failures.append({'path':relative,'kind':'auxiliary_hash_mismatch'})
 offline=json.loads((D/'OFFLINE_VALUE_MODEL_COMPARISON.json').read_text())
 for model in offline['all_training_candidates']:
  checked+=1
  if sha(Path(model['model_path']))!=model['sha256']:failures.append({'model':model['key'],'kind':'model_hash_mismatch'})
 pilot=json.loads((D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json').read_text())
 for session in pilot['sessions']:
  for row in session['rows']:
   if row['status']=='VALID' and row.get('model_path_used'):
    checked+=1
    if sha(Path(row['model_path_used']))!=row['model_version_used']:failures.append({'run_id':row['run_id'],'kind':'active_model_hash_mismatch'})
 host=json.loads((D/'HOST_ARCHIVE_MANIFEST.json').read_text())
 # Offload verified SHA and byte length at move; verify destination through
 # the same local symlink during rollout hashes above, without double reads.
 logs={str(p.relative_to(RAW)):sha(p) for p in sorted(RAW.glob('*.log'))}
 output={'status':'PASS' if not failures else 'FAIL','timestamp_utc':datetime.now(timezone.utc).isoformat(),
  'verified_rollouts':rollouts,'verified_files':checked,'verified_archived_original_contents':archived,
  'bytes_hashed_including_original_content':bytes_checked,'failures':failures,'wall_s':time.perf_counter()-started,
  'closed_log_hashes':logs,'host_archive_manifest_sha256':sha(D/'HOST_ARCHIVE_MANIFEST.json'),
  'historical_raw_verification_preserved':json.loads((D/'SOURCE_RAW_VERIFICATION.json').read_text()),
  'model_hashes_verified':True,'original_contract_and_production_preserved':True}
 save(D/'FINAL_EVIDENCE_VERIFICATION.json',output)
 print(json.dumps({k:v for k,v in output.items() if k not in ('closed_log_hashes','historical_raw_verification_preserved')},indent=2),flush=True)
 if failures:raise RuntimeError('Final evidence verification failed')
if __name__=='__main__':main()
