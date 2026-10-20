"""Retain v1 failure; prove Python at-fork RNG behavior without stepping physics."""
from pathlib import Path
import os,sys,json,hashlib,shutil,random,time
import numpy as np
R=Path(__file__).resolve().parent;P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def sha(x):return hashlib.sha256(x).hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
assert json.loads((P/'audit/P00_development_OWNER_EXIT.json').read_text())['joined']
archive=P/'versions/v1';archive.mkdir(parents=True,exist_ok=False)
for n in ['continuous_runner.py','EXECUTION_CODE_MANIFEST.json','EXECUTION_CODE_MANIFEST_v6.json','PREPHYSICAL_CHECKS.json']:shutil.copy2(P/n,archive/n)
random.seed(177);np.random.seed(177);pr=random.getstate();nr=np.random.get_state();before=sha(repr(pr).encode())
r,w=os.pipe();pid=os.fork()
if pid==0:
    os.close(r);changed=sha(repr(random.getstate()).encode())!=before
    random.setstate(pr);np.random.set_state(nr)
    restored=sha(repr(random.getstate()).encode())==before
    os.write(w,json.dumps(dict(python_rng_changed_after_osfork=changed,restored_exact=restored,numpy_restored_exact=np.array_equal(np.random.get_state()[1],nr[1]))).encode());os.close(w);os._exit(0)
os.close(w);probe=json.loads(os.read(r,4096));os.close(r);_,status=os.waitpid(pid,0)
assert probe['python_rng_changed_after_osfork'] and probe['restored_exact'] and probe['numpy_restored_exact'] and status==0
put('tests/FORK_RNG_REPAIR_PROBE.json',dict(status='PASS',native_steps=0,probe=probe,
    original_failed_attempt='P00_T2_B',original_new_native_steps=0,repair='restore inherited Python and NumPy RNG exactly, matching historical fork harness',unix=time.time()))
shutil.copy2(R/'continuous_runner.py',P/'continuous_runner.py')
cfg=json.loads((P/'P00_TEST_PLAN.json').read_text());cfg['condition']['name']='P00R';cfg['retry_of']='P00';cfg['same_patient_not_independent']=True
put('P00R_TEST_PLAN.json',cfg)
manifest=json.loads((P/'EXECUTION_CODE_MANIFEST.json').read_text());manifest['files']['continuous_runner.py']=sha((P/'continuous_runner.py').read_bytes());manifest.update(frozen_unix=time.time(),version=2,change='restore RNG in fork; unique retry identity; no controller/model/threshold change',previous_manifest_sha256=sha((archive/'EXECUTION_CODE_MANIFEST.json').read_bytes()))
put('EXECUTION_CODE_MANIFEST.json',manifest);shutil.copy2(P/'EXECUTION_CODE_MANIFEST.json',P/'EXECUTION_CODE_MANIFEST_v6.json')
put('audit/REPAIR_V2.json',dict(physics_before_repair=3,original_failure_retained=True,retry_group='P00R',patient_identity='P00',new_native_steps_in_probe=0,source_manifest_sha256=sha((P/'EXECUTION_CODE_MANIFEST.json').read_bytes())))
shutil.copy2(R/'repair_fork_v2.py',P/'repair_fork_v2.py')
print('FORK_RNG_REPAIR_V2_PASS',flush=True)
