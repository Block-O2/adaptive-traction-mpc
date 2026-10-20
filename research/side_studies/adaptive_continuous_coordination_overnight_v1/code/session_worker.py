"""Four sequential fresh native episodes in one interpreter, one plant at once."""
from pathlib import Path
import sys,json,time,os,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_overnight_v1')
sys.path.insert(0,str(S/'code'))
def append(row):
 with (S/'ATTEMPTS.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
def main():
 specs=json.loads(Path(sys.argv[1]).read_text())
 import study_common as sc,run_one,mode_metadata
 persist=sc.rt.persist_runtime_artifacts;original_metadata=mode_metadata.install;metadata_done=False
 def metadata_once():
  nonlocal metadata_done
  if not metadata_done:original_metadata();metadata_done=True
 mode_metadata.install=metadata_once
 rows=[]
 for j,cfg in enumerate(specs):
  assert not (S/'output'/(cfg['id']+'_RESULT.json')).exists()
  p=S/'inputs'/(cfg['id']+'.json');p.write_text(json.dumps(cfg,indent=2)+'\n')
  sc.rt.persist_runtime_artifacts=persist
  append(dict(event='START',id=cfg['id'],unix=time.time(),cfg=cfg,same_interpreter_pid=os.getpid(),source_sha256={str(S/'code'/n):hashlib.sha256((S/'code'/n).read_bytes()).hexdigest() for n in ('session_worker.py','run_one.py','multirate.py','commissioning_owner.py','slow_owner.py','admission_certificates.py')}))
  run_one.main(cfg_override=cfg,reuse=j>0)
  r=json.loads((S/'output'/(cfg['id']+'_RESULT.json')).read_text())
  append(dict(event='END',id=cfg['id'],unix=time.time(),status=r['status'],error=r.get('error'),same_interpreter_pid=os.getpid()))
  rows.append(dict(id=cfg['id'],pid=os.getpid(),status=r['status'],valid=r.get('metric',{}).get('valid',False),physical_state_reset=True,model_state_reset=True,native_and_commissioning_workers_joined=True))
 sc.save('R3_CONSECUTIVE_SESSION.json',dict(status='COMPLETE',rows=rows,same_interpreter=True,single_plant_at_once=True,interpretation='Four same-interpreter timing repetitions. Each original task commissions a fresh plant and model; not a continuous plant session or adaptation.'))
if __name__=='__main__':main()
