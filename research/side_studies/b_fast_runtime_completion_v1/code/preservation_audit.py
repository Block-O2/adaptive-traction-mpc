"""Read-only verification of protected old evidence, weights and primary Git."""
from task_bootstrap import *
def main():
 source=json.loads((STUDY/'SOURCE.json').read_text());old_bad=[];new_bad=[]
 for name,expected in source['originals'].items():
  p=Path(name)
  if not p.exists() or sha(p)!=expected:old_bad.append(name)
 for name,expected in source['frozen_files'].items():
  p=Path(name)
  if not p.exists() or sha(p)!=expected:new_bad.append(name)
 before=json.loads((STUDY/'GIT_BEFORE.json').read_text());git=lambda *args:subprocess.check_output(['git','-C',str(ROOT),*args],text=True)
 after=dict(branch=git('branch','--show-current'),head=git('rev-parse','HEAD'),status=git('status','--short'),index_sha256=sha(ROOT/'.git/index'),cached_diff_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(ROOT),'diff','--cached','--binary'])).hexdigest())
 weights=sha(STUDY/'weights/frozen_Q_v1/weights.npz');out=dict(status='PASS' if not old_bad and not new_bad and before==after and weights==source['weights_sha256'] else 'FAIL',old_protected_files_checked=len(source['originals']),old_protected_mismatches=old_bad,relocated_frozen_control_sources_checked=len(source['frozen_files']),relocated_control_source_mismatches=new_bad,primary_git_before=before,primary_git_after=after,primary_git_snapshot_equal=before==after,Q_weights_sha256=weights,Q_weights_equal=weights==source['weights_sha256'],no_git_mutations=True,limits='Git branch/HEAD/status/index/staged bytes and frozen old files are compared. No initial complete-primary-file hash was recorded, so unstaged primary byte equality beyond copied protected sources is not claimed.',unix=time.time())
 p=STUDY/'reports/PRESERVATION_AUDIT.json'
 if p.exists():shutil.copy2(p,STUDY/'reports'/('PRESERVATION_AUDIT_HISTORY_'+sha(p)+'.json'))
 save(p,out);print(json.dumps({k:out[k] for k in ('status','old_protected_files_checked','old_protected_mismatches','relocated_frozen_control_sources_checked','relocated_control_source_mismatches','primary_git_snapshot_equal','Q_weights_equal')}))
if __name__=='__main__':main()
