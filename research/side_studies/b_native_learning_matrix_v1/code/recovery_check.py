"""Read-only recovery and protected-source audit, safe to run between tasks."""
from task_bootstrap import *
def main():
 source=json.loads((STUDY/'SOURCE.json').read_text());git_before=json.loads((STUDY/'GIT_BEFORE.json').read_text());git=lambda *args:subprocess.check_output(['git','-C',str(ROOT),*args],text=True)
 changed=[p for p,h in source['originals'].items() if sha(p)!=h]
 diffs={r['relative']:r['primary_sha256'] for r in source['primary_vs_old_freeze_differences']}
 primary=[]
 for p,h in source['originals'].items():
  p=Path(p)
  try:rel=p.relative_to(OLD/'source')
  except ValueError:continue
  q=ROOT/rel
  if q.exists() and sha(q)!=diffs.get(str(rel),h):primary.append(str(q))
 git_equal=dict(branch=git('branch','--show-current')==git_before['branch'],head=git('rev-parse','HEAD')==git_before['head'],status=git('status','--short')==git_before['status'],index=sha(ROOT/'.git/index')==git_before['index_sha256'],cached_diff=hashlib.sha256(subprocess.check_output(['git','-C',str(ROOT),'diff','--cached','--binary'])).hexdigest()==git_before['cached_diff_sha256'])
 rows=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r['id'] for r in rows if r['event']=='START'];ends={r['id'] for r in rows if r['event']=='END'}
 assert len(starts)==len(set(starts)),'ATTEMPT_ID_COLLISION'
 assert len(starts)<=240,'ATTEMPT_CAP'
 ledger=json.loads((STUDY/'TASK_LEDGER.json').read_text());completed=[]
 for id,item in ledger.items():
  if item['status']!='COMPLETE':continue
  p=Path(item['config']['result_path']);assert p.exists();assert sha(p)==item['result_sha256'];completed.append(id)
 result=dict(unix=time.time(),status='PASS' if not changed and not primary and all(git_equal.values()) else 'FAIL',old_sources_changed=changed,primary_sources_changed=primary,git_equal=git_equal,attempts=len(starts),open_attempts=[x for x in starts if x not in ends],recoverable_completed_ids=completed,restart_behavior='runner ledger excludes all completed IDs; explicit retry names only; original clock and 240 cap retained',remaining_attempts=240-len(starts))
 save(STUDY/'RECOVERY_AUDIT.json',result);print(json.dumps(result))
if __name__=='__main__':main()
