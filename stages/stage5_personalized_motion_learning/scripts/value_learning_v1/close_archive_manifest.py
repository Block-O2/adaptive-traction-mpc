"""Close an all-offloaded archive manifest without repeated host path resolution."""
import argparse,json,os,signal
from datetime import datetime,timezone
from research_campaign import R,D,RAW,RUNS,save

def main(scanner_pid=None):
 old=json.loads((D/'HOST_ARCHIVE_MANIFEST.json').read_text());by_source={r['source']:r for r in old['files']}
 destination=old['destination'];rows=[]
 for result in sorted(RUNS.glob('*/rollout_result.json')):
  record=json.loads(result.read_text())
  if record['status']=='RUNNING':raise RuntimeError('rollout still open')
  for entry in record.get('lossless_archives',[]):
   from pathlib import Path
   rel=Path(entry['archive_path']);source=R/rel if rel.parts[0]=='stages' else result.parent/rel
   expected_target=str(Path(destination)/source.relative_to(RAW))
   if not source.is_symlink() or os.readlink(source)!=expected_target:raise RuntimeError('archive still copying or target mismatch')
   key=str(source.relative_to(R));previous=by_source.get(key)
   if previous:
    if previous['destination']!=expected_target or previous['sha256']!=entry['gzip_sha256']:raise RuntimeError('published metadata mismatch')
    size=previous['bytes']
   else:size=source.stat().st_size
   rows.append({'source':key,'destination':expected_target,'sha256':entry['gzip_sha256'],'bytes':size})
 pid=scanner_pid;proc=None if pid is None else Path('/proc')/str(pid)
 if proc is not None and proc.exists():
  if os.readlink(proc/'cwd')!=str(R):raise RuntimeError('scanner workspace identity mismatch')
  args=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode()
  if 'scripts/value_learning_v1/offload_new_archives.py' not in args:raise RuntimeError('own scanner PID identity mismatch')
  os.kill(pid,signal.SIGTERM)
 save(D/'HOST_ARCHIVE_MANIFEST.json',{**old,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'files':rows,
  'total_bytes':sum(r['bytes'] for r in rows),'finalization':'all sources verified as exact dedicated-target symlinks; prior byte-verified published sizes retained; newly published sizes read from target; independent final verification rehashes every gzip'})
 print('closed archive manifest',len(rows),'files',flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--scanner-pid',type=int);args=parser.parse_args();main(args.scanner_pid)

