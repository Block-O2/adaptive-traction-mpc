from pathlib import Path
import shutil
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
p=S/'code/slow_owner.py';text=p.read_text()
if 'research_model_invocations=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before' not in text:
 shutil.copy2(p,S/'versions/SLOW_COUNTER_BEFORE.py')
 anchor=' start=time.monotonic_ns();args,kwargs=pickle.loads(payload)'
 assert text.count(anchor)==1
 text=text.replace(anchor,' from traction_mpc_stage4 import estimator_v2 as ma\n before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS\n'+anchor)
 anchor='pid=os.getpid(),kind=kind,payload='
 assert text.count(anchor)==1
 text=text.replace(anchor,'pid=os.getpid(),kind=kind,research_model_invocations=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,model_counter_scope="entire finite commissioning target/fit operation",payload=')
 p.write_text(text)
p=S/'code/commissioning_owner.py';text=p.read_text()
if "commissioning_model_API_calls=result.get('research_model_invocations')" not in text:
 shutil.copy2(p,S/'versions/COMMISSION_COUNTER_BEFORE.py')
 anchor='ROW_PLACEHOLDER'
 anchor="source_timestamp_rewritten=False)"
 assert text.count(anchor)==1
 text=text.replace(anchor,"source_timestamp_rewritten=False,commissioning_model_API_calls=result.get('research_model_invocations'),commissioning_counter_scope=result.get('model_counter_scope'))")
 p.write_text(text)
print('S2_FINITE_COMMISSIONING_COUNTERS_INSTALLED')
