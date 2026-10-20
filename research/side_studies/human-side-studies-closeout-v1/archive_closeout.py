"""Closeout archive only. Never import scientific controller/plant code."""
from pathlib import Path
import json,os,hashlib,gzip,zipfile,shutil,time,subprocess
from datetime import datetime,timezone
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');W=P/'human-side-studies-closeout-v1'
ROOT=Path('/mnt/d/CodexResearchEvidence/adaptive-traction-mpc-learning')
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha_stream(stream):
 h=hashlib.sha256()
 while True:
  b=stream.read(4*1024*1024)
  if not b:break
  h.update(b)
 return h.hexdigest()
def sha(p):
 with p.open('rb') as f:return sha_stream(f)
def content(p):
 if p.suffix=='.gz':
  with gzip.open(p,'rb') as f:return dict(kind='gzip_decompressed_content',sha256=sha_stream(f))
 if p.suffix=='.npz':
  with zipfile.ZipFile(p) as z:
   assert z.testzip() is None
   return dict(kind='npz_uncompressed_members',members=[dict(name=n,bytes=z.getinfo(n).file_size,sha256=sha_stream(z.open(n))) for n in sorted(z.namelist())])
 raise ValueError('Unsupported archive content')
if os.getpriority(os.PRIO_PROCESS,0)<19:os.nice(19-os.getpriority(os.PRIO_PROCESS,0))
start=time.monotonic();plan=json.loads((W/'ARCHIVE_PLAN.json').read_text());dest=Path(plan['destination'])
assert dest.parent==ROOT and not dest.exists() and ROOT.resolve()==ROOT
assert shutil.disk_usage(ROOT).free>sum(x['bytes'] for x in plan['files'])+10*1024**3
inventory=json.loads((W/'PRE_CLOSEOUT_INVENTORY.json').read_text());lookup={r['path']:r for r in inventory['files']}
extras=['lab-human-adaptation-contrast-v1/runs_R2/C0__commissioning_only/trace.npz','lab-human-adaptation-contrast-v1/runs_R2/C5__commissioning_only/trace.npz','lab-human-adaptation-contrast-v1/diagnostics_R2/D1_C5_TRUE_MODEL_FROM_START/runs/C5__fixed_population/trace.npz']
records=[dict(r,action='REPLACE_REDUNDANT_LOCAL_RAW_WITH_ARCHIVE_SYMLINK') for r in plan['files']]+[dict(lookup[p],category='restore_drill_key_trace_backup',action='KEEP_LOCAL_PLUS_D_KEY_BACKUP') for p in extras]
dest.mkdir();save(W/'ARCHIVE_SCOPE_AMENDMENT.json',dict(original_plan_sha256=sha(W/'ARCHIVE_PLAN.json'),addition='Three already-existing key traces backed up directly on D solely to test recovery of actual key trajectories; these remain local and will not be deleted.',added_files=extras))
rows=[];last=start
for i,r in enumerate(records):
 p=Path(r['absolute_path']);assert p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(P.resolve())
 st=p.stat();assert st.st_size==r['bytes'] and st.st_mtime_ns==r['mtime_ns'];assert sha(p)==r['sha256']
 target=dest/r['path'];assert target.resolve().is_relative_to(dest);target.parent.mkdir(parents=True,exist_ok=True)
 with p.open('rb') as a,target.open('xb') as b:
  shutil.copyfileobj(a,b,4*1024*1024);b.flush();os.fsync(b.fileno())
 assert sha(target)==r['sha256'] and target.stat().st_size==r['bytes']
 original_content=content(p);archived_content=content(target);assert original_content==archived_content
 row=dict(r,archive_path=str(target),archive_windows_path='D:/CodexResearchEvidence/adaptive-traction-mpc-learning/'+str(target.relative_to(ROOT)),file_hash_verified=True,decompressed_content=original_content,decompressed_hash_verified=True,restore_method='python restore_archive.py --original-path ORIGINAL --destination NEW_FILE; verifies original bytes and decompressed content; default no overwrite.')
 rows.append(row)
 if time.monotonic()-last>35:print('ARCHIVE_VERIFIED',i+1,'/',len(records),flush=True);last=time.monotonic()
expected={r['archive_path'] for r in rows};actual={str(p) for p in dest.rglob('*') if p.is_file()}
assert expected==actual,'archive exact file list mismatch'
# Trial recovery onto D, not C; genuine npz member integrity and exact byte hash.
drill=dest/'restore-drill';drill.mkdir();recovered=[]
for rel in extras:
 r=next(r for r in rows if r['path']==rel);p=drill/rel;p.parent.mkdir(parents=True,exist_ok=True)
 with Path(r['archive_path']).open('rb') as a,p.open('xb') as b:shutil.copyfileobj(a,b,4*1024*1024)
 assert sha(p)==r['sha256'];assert content(p)==r['decompressed_content']
 recovered.append(dict(original_path=r['absolute_path'],archive_path=r['archive_path'],restored_path=str(p),bytes=p.stat().st_size,sha256=sha(p),exact_original_content_hash_verified=True,npz_members_verified=True))
verification=dict(status='PASS_BEFORE_ANY_LOCAL_DELETE',created_utc=datetime.now(timezone.utc).isoformat(),archive_destination=str(dest),verified_files=len(rows),verified_bytes=sum(r['bytes'] for r in rows),all_file_hashes_verified=True,all_decompressed_content_hashes_verified=True,exact_archive_file_list_verified=True,restore_drill=recovered,C_staging_bytes=0,trial_restore_volume='D',elapsed_seconds=time.monotonic()-start)
save(W/'ARCHIVE_VERIFICATION.json',verification)
save(W/'RESTORE_INDEX.json',dict(status='VERIFIED_ARCHIVE_AND_RECOVERY_INDEX',archive_destination=str(dest),archive_verification_sha256=sha(W/'ARCHIVE_VERIFICATION.json'),historical_manifest_policy='Original manifests unchanged; this migration overlay provides original path -> archive path -> original bytes SHA256 -> decompressed SHA/member hashes -> restore method.',files=rows))
# Save equivalent evidence next to D archive before local cleanup.
save(dest/'ARCHIVE_MANIFEST.json',dict(verification=verification,files=rows))
save(dest/'RESTORE_INDEX.json',dict(files=rows,original_source_root=str(P),method='Restore exact archive bytes without overwriting; validate sha256 plus decompressed payload.'))
deleted=[]
for r in rows:
 if r['action']!='REPLACE_REDUNDANT_LOCAL_RAW_WITH_ARCHIVE_SYMLINK':continue
 src=Path(r['absolute_path']);target=Path(r['archive_path'])
 assert src.is_file() and not src.is_symlink() and src.resolve().is_relative_to(P.resolve())
 assert sha(src)==r['sha256'] and sha(target)==r['sha256']
 link=src.with_name(src.name+'.archive_link_pending');assert not link.exists();link.symlink_to(target)
 assert sha(link)==r['sha256']
 # Atomic replacement removes precisely this verified redundant local file.
 os.replace(link,src)
 assert src.is_symlink() and src.resolve()==target and sha(src)==r['sha256']
 deleted.append(dict(original_path=str(src),archive_path=str(target),bytes=r['bytes'],sha256=r['sha256'],outcome='REDUNDANT_LOCAL_BYTES_REMOVED_ORIGINAL_PATH_RESOLVES_TO_VERIFIED_ARCHIVE',time_utc=datetime.now(timezone.utc).isoformat()))
 save(W/'CLEANUP_LEDGER.json',dict(status='IN_PROGRESS',files=deleted,deleted_local_bytes=sum(r['bytes'] for r in deleted),explicit_temporary_files_deleted=0))
# Every historical file's original bytes and original manifest hash still readable.
checks=[]
for r in inventory['files']:
 p=Path(r['absolute_path']);assert p.exists() and sha(p)==r['sha256'];checks.append(r['path'])
verification.update(status='PASS_ARCHIVE_RESTORE_AND_POST_CLEANUP',deleted_redundant_local_files=len(deleted),deleted_redundant_local_bytes=sum(r['bytes'] for r in deleted),all_original_inventory_file_hashes_still_accessible=len(checks),elapsed_seconds=time.monotonic()-start)
save(W/'ARCHIVE_VERIFICATION.json',verification)
save(W/'CLEANUP_LEDGER.json',dict(status='COMPLETE',files=deleted,deleted_local_files=len(deleted),deleted_local_bytes=sum(r['bytes'] for r in deleted),explicit_temporary_files_deleted=0,other_files_deleted=0,SAC_shared_main_history_deletions=0))
save(dest/'ARCHIVE_VERIFICATION_FINAL.json',verification)
print('ARCHIVE_COMPLETE',len(rows),'ARCHIVED_BYTES',sum(r['bytes'] for r in rows),'LOCAL_REDUNDANT_FILES_REMOVED',len(deleted),'LOCAL_BYTES_FREED',sum(r['bytes'] for r in deleted),'HISTORICAL_HASHES_PASS',len(checks),'RESTORE_DRILL_PASS',len(recovered),flush=True)
