from pathlib import Path
import os,json,subprocess,datetime,hashlib
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');py='/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python'
assert not (P/'jobs/TAILOT/SOURCE_MANIFEST.json').exists() and not (P/'jobs/TAILRT/SOURCE_MANIFEST.json').exists()
for ph,x in [('OUTBOUND','O'),('RETURN','R')]:
 c=dict(id='COST'+x+'8',gate_groups=['TAIL'+x+'1'],train_groups=['TAIL'+x+'1'],test_groups=['TAIL'+x+'T'],phases=[ph],horizon_s=.5,gamma=1.,continuation='original B rolling/replan',role='SECONDARY_PREREGISTERED_DATA_SIZE_ABLATION; main COSTO/COSTR16-row results unchanged; no best-of-model selection on test')
 f=P/'experiments'/('CRITIC_'+c['id']+'.json');f.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
 with (P/'logs'/('CRITIC_'+c['id']+'_FIT.log')).open('w') as log:
  r=subprocess.run([py,'-B',str(P/'source/v5_cost_critic.py'),str(f.relative_to(P)),'fit_only'],stdout=log,stderr=subprocess.STDOUT,timeout=60)
 assert r.returncode==0,'PREFROZEN_8ROW_FIT_FAILED'
src='''"""Finite no-physics evaluation of pre-frozen 8-label secondary models."""
from pathlib import Path
import os,sys,json,time,subprocess,datetime
P=Path(__file__).resolve().parents[1];deadline=json.loads((P/'ACTIVATION.json').read_text())['hard_stop_unix']-600
def put(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\\n')
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
'''
compile(src,str(P/'source/v5_critic8_eval_queue.py'),'exec');(P/'source/v5_critic8_eval_queue.py').write_text(src)
record=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),hypothesis='A few extra true parent states may or may not improve remaining-cost ranking; 8 versus16 fitted labels isolates data quantity using the same future locked test menu.',experiment='Freeze COSTO8/COSTR8 now using C1-only eight labels/phase, before any TAILOT/TAILRT START. Compare once on the same later test parents as prespecified main16-label models.',result='SECONDARY_MODELS_FROZEN_BEFORE_TEST',diagnosis='No new physical attempts; three H labels are not independent samples. This is a secondary ablation and cannot replace the main model based on test outcomes.',decision='Evaluate two frozen extra models only after the primary Critic chain finishes; all actual full-menu cost remains charged, no physical-saving claim.',evidence=['models/CRITIC_COSTO8_FROZEN.json','models/CRITIC_COSTR8_FROZEN.json'],new_physical_START=0)
with (P/'RESEARCH_DECISIONS.jsonl').open('a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
with (P/'logs/CRITIC8_EVAL_QUEUE.log').open('w') as log:
 child=subprocess.Popen([py,'-B',str(P/'source/v5_critic8_eval_queue.py')],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
f=P/'queue/FINAL_AUDIT_DEPENDENCIES.json';d=json.loads(f.read_text());d['required_queue_end'].append('owned/CRITIC8_EVAL_END.json');f.write_text(json.dumps(d,indent=2)+'\n')
print('C1_ONLY8_MODELS_FROZEN','EVAL_QUEUE_PID',child.pid,'NEW_PHYSICS',0)
