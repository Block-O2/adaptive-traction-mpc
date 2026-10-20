"""Lightweight clock read of ended attempts; never read active trace writers."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
from freeze import *
import numpy as np
def main():
 events=[json.loads(line) for line in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];ended={r['id'] for r in events if r['event']=='END'};missing=[];errors=[];readable=0
 for name in sorted(ended):
  path=STUDY/'source/results'/name/'trace.npz'
  if not path.exists():missing.append(name);continue
  try:
   with np.load(path) as z:steps=int(z['physics_steps'][-1]);seconds=float(z['time_s'][-1])
   assert steps>0 and abs(seconds/steps-.00025)<1e-8
   readable+=1
  except Exception as error:errors.append(dict(id=name,path=str(path),error=str(error)))
 result=dict(unix=time.time(),ended_attempts=len(ended),readable_trace_clocks=readable,missing_trace_ids=missing,trace_clock_errors=errors,active_attempts_not_read=True)
 save(STUDY/'TRACE_CLOCK_PRECHECK.json',result);print(json.dumps(result))
if __name__=='__main__':main()
