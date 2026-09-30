"""Lossless archive ONLY this campaign's new large JSON, verify before unlink."""
from pathlib import Path
from datetime import datetime,timezone
import gzip,hashlib,json,subprocess,time
R=Path('/home/hank/coding/adaptive-traction-mpc-learning');S=R/'stages/stage5_personalized_motion_learning'
RAW=(S/'results/value_learning_research_v1').resolve();D=S/'docs/value_learning_research_v1'
def hash_stream(f):
 h=hashlib.sha256()
 for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
rows=[]
for p in sorted(RAW.glob('runs/*/rep_*/runtime_artifacts.json')):
 resolved=p.resolve()
 if RAW not in resolved.parents:raise RuntimeError('archive target escaped current campaign')
 result=p.parent.parent/'rollout_result.json'
 record=json.loads(result.read_text())
 if record['status']=='RUNNING':
  backup=result.with_name('rollout_result_before_storage_failure_v2.json')
  if not backup.exists():backup.write_bytes(result.read_bytes())
  record.update(status='INTERRUPTED_HOST_RESOURCE',failure_reason='Host C disk exhausted (<300 MB); WSL terminated with swap-device read errors.',retry_run_id=record['run_id']+'_retry2',original_record_sha256=hashlib.sha256(backup.read_bytes()).hexdigest())
  result.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
 if p.stat().st_size<10*1024*1024:continue
 dest=p.with_suffix(p.suffix+'.gz');before_bytes=p.stat().st_size
 with p.open('rb') as f:original_sha=hash_stream(f)
 if not dest.exists():
  with p.open('rb') as source,gzip.open(dest,'wb',compresslevel=1) as output:
   for b in iter(lambda:source.read(1024*1024),b''):output.write(b)
 with gzip.open(dest,'rb') as f:recovered_sha=hash_stream(f)
 if recovered_sha!=original_sha:raise RuntimeError('lossless archive verification failed:'+str(p))
 with dest.open('rb') as f:archive_sha=hash_stream(f)
 entry={'original_path':str(p.relative_to(R)),'archive_path':str(dest.relative_to(R)),'original_sha256':original_sha,'gzip_sha256':archive_sha,'original_bytes':before_bytes,'gzip_bytes':dest.stat().st_size,'lossless_verified':True}
 rows.append(entry)
 # Exact scope/path checked above; only the verified redundant uncompressed
 # NEW campaign file is removed. Old exploration/baseline directories untouched.
 p.unlink()
 record.setdefault('lossless_archives',[]).append(entry)
 if record.get('raw_files_sha256'):
  record['raw_files_sha256'][str(dest.relative_to(result.parent))]=archive_sha
 result.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'archived':entry['original_path'],'bytes_logically_released':before_bytes-entry['gzip_bytes']}),flush=True)
log={'schema':'new_campaign_lossless_storage_recovery_v1','timestamp_utc':datetime.now(timezone.utc).isoformat(),'files':rows,'uncompressed_bytes':sum(x['original_bytes'] for x in rows),'compressed_bytes':sum(x['gzip_bytes'] for x in rows),'all_original_content_SHA256_verified_after_decompression':True,'prior_exploration_or_baseline_touched':False,'host_C_free_bytes':subprocess.check_output(['df','-B1','/mnt/c'],text=True)}
(D/'STORAGE_RECOVERY_V2.json').write_text(json.dumps(log,indent=2,sort_keys=True)+'\n')
state=json.loads((D/'STATE.json').read_text());state.update(phase='STORAGE_RECOVERY',repair_cycles_used=2,next_action='reclaim virtual disk freed blocks; verify host capacity before further rollouts')
(D/'STATE.json').write_text(json.dumps(state,indent=2,sort_keys=True)+'\n')
print(json.dumps({'recovery_complete':True,'bytes_logically_released':log['uncompressed_bytes']-log['compressed_bytes']}),flush=True)
