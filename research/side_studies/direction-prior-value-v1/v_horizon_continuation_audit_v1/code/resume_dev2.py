from freeze import *
import os,sys,fcntl
sys.path.insert(0,str(STUDY/'code'))
from accounting import record
def main():
 handles=[]
 for name in ('runner.lock','controller.lock'):
  handle=(STUDY/name).open('a');fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);handles.append(handle)
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
  except (OSError,UnicodeError):continue
  assert str(STUDY/'code/worker.py') not in cmd,'OWNED_WORKER_ACTIVE'
 events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];ends={r['id'] for r in events if r['event']=='END'}
 for r in events:
  if r['event']=='START' and r['id'] not in ends:
   assert r.get('config',{}).get('group')=='parent_dev_0'
   record('END',r['id'],status='INTERRUPTED_RESOURCE_RECOVERY',reason='retry1 parent and child exited after SIGINT; resource samples and original error retained; no new physical result invented')
 request=json.loads((STUDY/'queue/011_parent_dev_0.json').read_text());name='011_parent_dev_0_retry2';path=STUDY/'queue'/(name+'.json');assert not path.exists()
 request.update(id=name,resume_of='011_parent_dev_0',result_path=str(STUDY/'output'/(name+'_RESULT.json')),original_input_sha256=sha(STUDY/'queue/011_parent_dev_0.json'),seed=2026100600)
 save(path,request)
 rows=[json.loads(x) for x in (STUDY/'output/RESOURCES.jsonl').read_text().splitlines()];near=[r for r in rows if 1791231300<=r['unix']<=1791231640]
 save(STUDY/'PLAN_AMENDMENT_06_RECOVERY_AND_LABELS.json',dict(unix=time.time(),before_heldout_tests=True,original_start_unix=1791222386,global_cap=300,physics_changes=[],safety_changes=[],B_changes=[],changes=['retract malloc_trim and explicit GC after fork hash mismatch; retained v1 failures','stream ALL long list contents and explicit Generator/deque/bytes cache entries in full-state fingerprint v2; mandatory B fork gate','loaded code/import hashes captured at cold worker start and inherited by forks','terminal K3 history reflects last applied action; new logger-only B-owned terminal value labels','whole-parent train/dev split, exclude exact feature duplicates across split and merge duplicate G inputs','recover only missing dev branches with explicit retry2; preserve original attempt/error/source aliases','resource backoff and disk initialization fixes; generous recent same-stage timeouts; finish current episode at dispatch cutoff'],V_base_cost_arithmetic_changed=False,resource_samples_near_interruption=near,remaining_development_branches=2))
 print(json.dumps(dict(queued=name,resource_near=[{k:r.get(k) for k in ('unix','mem_available','swap_in','swap_out','PSS','windows','psi')} for r in near]),indent=2))
if __name__=='__main__':main()
