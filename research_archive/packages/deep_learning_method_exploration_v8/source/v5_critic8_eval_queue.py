"""Finite no-physics evaluation of pre-frozen 8-label secondary models."""
from pathlib import Path
import os,sys,json,time,subprocess,datetime
P=Path(__file__).resolve().parents[1];deadline=json.loads((P/'ACTIVATION.json').read_text())['hard_stop_unix']-600
def put(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
put('owned/CRITIC8_EVAL_START.json',dict(pid=os.getpid(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),deadline_unix=deadline,maximum_model_evaluations=2,maximum_new_physical_START=0))
done=[];reason='FINITE_SECONDARY_MODEL_EVALUATION_COMPLETED'
try:
 for _ in range(max(1,int(deadline-time.time())+1)):
  if time.time()>=deadline or (P/'STOP_REQUESTED').exists():raise TimeoutError('CRITIC8_EVAL_DEADLINE')
  f=P/'owned/CRITIC_QUEUE_END.json'
  if f.exists():
   end=json.loads(f.read_text());assert end['reason']=='FINITE_CONDITIONAL_STUDY_COMPLETED','PRIMARY_CRITIC_TEST_UNAVAILABLE';break
  time.sleep(1)
 else:raise TimeoutError('CRITIC8_PRIMARY_NOT_CLOSED')
 for model in ['COSTO8','COSTR8']:
  with (P/'logs'/('CRITIC_'+model+'_TEST.log')).open('w') as log:
   rc=subprocess.run([sys.executable,'-B',str(P/'source/v5_cost_critic.py'),'experiments/CRITIC_'+model+'.json','evaluate_only'],stdout=log,stderr=subprocess.STDOUT,timeout=60).returncode
  assert rc==0,'SECONDARY_MODEL_EVALUATION_FAILED';done.append(model)
except BaseException as e:reason=type(e).__name__+':'+str(e);raise
finally:put('owned/CRITIC8_EVAL_END.json',dict(pid=os.getpid(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reason=reason,completed=done,new_physical_START=0))
