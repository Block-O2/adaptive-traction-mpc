from pathlib import Path
import json,time,hashlib,shutil
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
base=json.loads((S/'queue/048_N13_C2b_host.json').read_text())
groups=[]
for group,first,reuse in [('N13_C2b_COLD4',53,False),('N13_C2b_REUSE4',57,True)]:
 configs=[]
 for n in range(first,first+4):
  cfg=base|dict(id=f'{n:03d}_{group}_{n-first+1}',seed=2026100700+n,dependencies=['046_N13_C2b_science_nominal'],series='independent_runtime_diagnostic')
  configs.append(cfg)
 out=dict(id=group,same_interpreter=reuse,configs=configs,registered_unix=time.time(),purpose='Independent full-task engineering/safety/cold/cache-reset evidence; original R2 failures remain FAIL, no BEST/M2 promotion without full ladder.',physical_session_continuous=False)
 dest=S/'queue'/(group+'.json');assert not dest.exists();dest.write_text(json.dumps(out,indent=2)+'\n');groups.append(str(dest))
dest=S/'versions/N13_C2b_COHORT_CODE';assert not dest.exists();dest.mkdir()
for root in ('code','native','build'):
 shutil.copytree(S/root,dest/root,ignore=shutil.ignore_patterns('__pycache__'))
manifest={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()}
(dest/'MANIFEST.json').write_text(json.dumps(dict(unix=time.time(),files=manifest),indent=2)+'\n')
out=dict(status='FROZEN_DIAGNOSTIC_CANDIDATE',version='N13_C2b',groups=groups,registered_unix=time.time(),functional_protocol_sha256=hashlib.sha256((S/'versions/RUNTIME_FUNCTIONAL_CHECKS.json').read_bytes()).hexdigest(),Q_OFF=True,G_OFF=True,no_training=True,R2_NOT_PASSED=True,code=str(dest))
(S/'versions/N13_C2b_COHORT_REGISTRATION.json').write_text(json.dumps(out,indent=2)+'\n')
with (S/'PROGRESS.md').open('a') as f:f.write('\nSCI049 C3 and SCI051 C3b bit-exact. Hosts050/052 physical/current/causal/allservice PASS but HOLD originalR2FAIL; C3 extra completed message services did not remove HOLD bottleneck. N13/C2b diagnostic candidate frozen for4 fresh cold+4 same-interpreter full tasks with new independent seeds, unchanged frozenfunctional/strict/physical/R2 labels. Reused interpreter still new plant, not continuous physical adaptation. Cross-shape saved-input attribution only~.08ms/input unsupportedpath opportunity: no further microtranslation. No BEST or M2 yet.\n')
print(json.dumps(out))
