from common import *
import subprocess
ps=subprocess.check_output(['ps','-eo','pid,args'],text=True)
assert not any('/coordination_research_interface_v1/branching.py' in line and 'python' in line and 'bash -c' not in line for line in ps.splitlines()),'PHYSICS_OWNER_STILL_RUNNING'
archive=O/'failed_fork_rng_attempt';archive.mkdir(exist_ok=False)
for name in ('B_branch_parent','branches','snapshots'):
 p=O/name
 if p.exists():
  assert p.resolve().parent==O.resolve();shutil.move(str(p),str(archive/name))
for name in ('BRANCH_SMOKE_PROGRESS.json','BRANCH_SMOKE.json','B_branch_parent.json'):
 p=L/name
 if p.exists():shutil.move(str(p),str(L/('failed_fork_rng_'+name)))
save('FORK_RNG_REPAIR.json',dict(error='CPython at-fork reseeds global random singleton; full-state hash correctly rejected children',repair='restore Python and NumPy global RNG before post-fork hash; preserve observer RNG via full process clone',archive=str(archive),formal_continuations_before_repair=0,failed_attempts_preserved=True))
shutil.copy2(W/'branching.py',P/'branching.py')
print('saved failed fork attempts')
