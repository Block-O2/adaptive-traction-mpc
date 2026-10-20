from pathlib import Path
import sys,time,json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import runner
hard=json.loads((S/'RUN_PLAN.json').read_text())['hard_stop_unix'];next_at=0
while time.time()<hard and not (S/'checkpoints/CLOSING_DONE.json').exists():
 if time.time()>=next_at:
  r=runner.sample(owner='FINAL_VERIFICATION');print(json.dumps(dict(unix=r['unix'],available=r['mem_available'],commit=r['windows'].get('commit_headroom'),disk_c=r['windows'].get('disk_c'))),flush=True);next_at=time.time()+45
 time.sleep(.2)
print('CLOSING_MONITOR_JOINED',flush=True)
