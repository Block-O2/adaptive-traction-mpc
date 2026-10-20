from pathlib import Path
import sys,json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
sys.path.insert(0,str(S/'code'));sys.path.insert(0,str(Path(__file__).resolve().parent))
import readiness_service as r,committed_endpoint_service as c,completed_result_service as ready
from readiness_service_regression import case
ordinary=[];r.ORIGINAL_NEXT=lambda w:ordinary.append(w.clock());c.ORIGINAL_NEXT=r.next_control_tick
c.PRECATCH=False;c.CONTINUOUS_PRECATCH=False
saved_select=r.select.select;saved_ready=ready.completed_task;rows=[]
try:
 for label in ('pending_readable','pending_timeout','committed_endpoint','consumed_endpoint_pending','overrun','commission'):
  w,l,req,f,k,calls=case();w.steps=4;w.sleeper=lambda s:setattr(k,'n',k.n+round(s*1e9));waits=[]
  if label=='committed_endpoint':
   l._outstanding=None;w.runtime['_c5_committed_endpoint']=dict(request_id=11,consumed=False,deadline_ns=2_000_000,target_step=8)
  if label=='consumed_endpoint_pending':w.runtime['_c5_committed_endpoint']=dict(request_id=11,consumed=True,deadline_ns=500_000,target_step=2)
  if label=='overrun':k.n=6_000_000
  if label=='commission':req.stage='COMMISSIONING'
  def select(read,write,error,timeout):
   waits.append(timeout);assert 0<timeout<=.004;k.n=2_000_000 if label!='pending_timeout' else 5_000_000
   return (read if label!='pending_timeout' else [],[],[])
  r.select.select=select;ready.completed_task=lambda wall:(req,f)
  before=len(ordinary);c.next_control_tick(w)
  if label in ('pending_readable','consumed_endpoint_pending'):assert len(calls)==2 and len(waits)==1 and len(ordinary)==before
  elif label=='committed_endpoint':assert len(calls)==1 and not waits and w.runtime['_c5_committed_endpoint']['consumed'] and k.n==2_000_000
  elif label=='pending_timeout':assert len(calls)==1 and len(waits)==1 and len(ordinary)==before+1
  else:assert not calls and not waits and len(ordinary)==before+1
  rows.append(label)
finally:r.select.select=saved_select;ready.completed_task=saved_ready
out=dict(status='PASS',cases=rows,physics_steps=0,model_API_calls=0,unix=time.time(),scope='Actual scheduler wrapper composition; no mathematical/planner change. Full scientific and host gates still required.')
(S/'output/C6_COMPOSITION_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
