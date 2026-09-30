"""Verified byte-identical offload of this campaign's immutable gzip evidence.

The research root, run ids, original-content hashes and gzip hashes stay intact.
Only completed NEW gzip files move to the spacious host D volume; symlinks keep
the existing scientific evidence paths readable. Historical evidence untouched.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,os,time,shutil
from evidence_io import file_sha
R=Path(__file__).resolve().parents[4]
RAW=R/'stages/stage5_personalized_motion_learning/results/value_learning_research_v1'
D=R/'stages/stage5_personalized_motion_learning/docs/value_learning_research_v1'
DEST=Path('/mnt/d/CodexResearchEvidence/adaptive-traction-mpc-learning/value_learning_research_v1_20260930_140700Z')

def offload():
 DEST.mkdir(parents=True,exist_ok=True)
 rows=[]
 for rp in sorted((RAW/'runs').glob('*/rollout_result.json')):
  record=json.loads(rp.read_text())
  if record['status']=='RUNNING':continue
  for entry in record.get('lossless_archives',[]):
   relative=Path(entry['archive_path'])
   source=(R/relative) if relative.parts[0]=='stages' else rp.parent/relative
   expected=entry['gzip_sha256']
   target=DEST/source.relative_to(RAW)
   if source.is_symlink():
    if source.resolve()!=target.resolve():raise RuntimeError('unexpected evidence symlink destination')
    rows.append({'source':str(source.relative_to(R)),'destination':str(target),'sha256':expected,'bytes':target.stat().st_size});continue
   if RAW.resolve() not in source.resolve().parents:raise RuntimeError('source escaped NEW campaign root')
   if source.suffix!='.gz' or not source.is_file():continue
   if file_sha(source)!=expected:raise RuntimeError('source gzip hash mismatch')
   target.parent.mkdir(parents=True,exist_ok=True)
   if DEST.resolve() not in target.resolve().parents:raise RuntimeError('destination escaped dedicated campaign directory')
   if not target.exists():
    with source.open('rb') as src,target.open('xb') as dst:
     shutil.copyfileobj(src,dst,1024*1024);dst.flush();os.fsync(dst.fileno())
   if file_sha(target)!=expected:raise RuntimeError('destination gzip hash mismatch; source retained')
   source.unlink() # redundant NEW gzip only, verified identical dedicated copy
   source.symlink_to(target)
   rows.append({'source':str(source.relative_to(R)),'destination':str(target),'sha256':expected,'bytes':target.stat().st_size})
 manifest={'schema':'new_campaign_lossless_host_archive_v1','status':'PASS','timestamp_utc':datetime.now(timezone.utc).isoformat(),
  'destination':str(DEST),'scope':'completed NEW campaign gzip only; history untouched; source paths remain symlinks',
  'byte_identical_gzip_verified_before_local_unlink':True,'files':rows,'total_bytes':sum(x['bytes'] for x in rows)}
 temp=D/'HOST_ARCHIVE_MANIFEST.json.tmp';temp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');temp.replace(D/'HOST_ARCHIVE_MANIFEST.json')
 print(json.dumps({'archive_files':len(rows),'bytes':manifest['total_bytes'],'host_C_free_bytes':shutil.disk_usage('/mnt/c').free}),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');a=p.parse_args()
 while True:
  offload()
  if not a.watch or datetime.now(timezone.utc)>=datetime.fromisoformat('2026-09-30T23:10:00+00:00'):break
  time.sleep(60)
