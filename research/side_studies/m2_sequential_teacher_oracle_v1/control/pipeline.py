from pathlib import Path
import subprocess,json,time,sys
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1');C=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_sequential_teacher_oracle_v1_control');P=json.loads((S/'SEARCH_PROTOCOL.json').read_text());PY='/home/hank/envs/adaptive-online-rl-v1/bin/python'
def put(x):(S/'SEARCH_PIPELINE.json').write_text(json.dumps(x,indent=2)+'\n')
assert (S/'seqO_DONE.json').exists(),'SEQUENTIAL_PARENT_NOT_JOINED'
try:
 for mode in ['seqR','repair','seqMargin']:
  n=sum(json.loads(l)['event']=='START' for l in (S/'ATTEMPTS.jsonl').read_text().splitlines())
  if n>=72 or time.time()>=P['search_cutoff_unix']-600:put(dict(status='STOPPED_BUDGET_OR_WALL',mode=mode,unix=time.time()));break
  if mode!='repair':subprocess.run([PY,str(C/'manage.py'),mode],check=True)
  subprocess.run([PY,str(C/'deploy.py')],check=True)
  put(dict(status='RUNNING',mode=mode,unix=time.time(),attempts_before=n))
  with (S/'logs'/(mode+'.log')).open('w') as f:subprocess.run([PY,str(S/'code/sequential_runner.py'),mode],stdout=f,stderr=subprocess.STDOUT,check=True)
  subprocess.run([PY,str(C/'manage.py'),'compact'],check=True)
 else:put(dict(status='COMPLETE',unix=time.time(),all_children_joined=True))
except BaseException as e:
 put(dict(status='FAILED_STOPPED',unix=time.time(),error=str(e)));raise
