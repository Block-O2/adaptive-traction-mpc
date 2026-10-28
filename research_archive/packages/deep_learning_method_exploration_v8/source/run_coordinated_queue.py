from pathlib import Path
import json,time,subprocess,sys,os
P=Path(__file__).resolve().parents[1];a=json.loads((P/'ACTIVATION.json').read_text());groups=json.loads((P/'freeze/TRAIN_PLAN.json').read_text())['new_coordinated_return_groups']
(P/'owned/COORD_QUEUE_START.json').write_text(json.dumps(dict(pid=os.getpid(),unix=time.time(),groups=groups)))
try:
 while not (P/'jobs/TRAIN_QUEUE_DONE.json').exists():
  assert time.time()<a['hard_stop_unix']-2400-7200
  time.sleep(3)
 for g in groups:
  assert time.time()<a['hard_stop_unix']-2400-6000
  with (P/'logs'/f'{g}_supervisor.log').open('w') as f:rc=subprocess.run([sys.executable,'-B',str(P/'source/supervise_v2.py'),'experiments/'+g+'.json'],stdout=f,stderr=subprocess.STDOUT).returncode
  if rc:raise RuntimeError('COORD_JOB_FAILED:'+g)
  print('COORD_COMPLETE',g,flush=True)
 (P/'jobs/COORD_QUEUE_DONE.json').write_text(json.dumps(dict(groups=groups,unix=time.time())))
finally:(P/'owned/COORD_QUEUE_END.json').write_text(json.dumps(dict(pid=os.getpid(),unix=time.time())))
