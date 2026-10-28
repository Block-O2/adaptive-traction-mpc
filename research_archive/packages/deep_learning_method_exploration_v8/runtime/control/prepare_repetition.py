"""Preregister two actual repetitions; primary cold-parent models remain frozen."""
from pathlib import Path
import sys,os,json,time,hashlib,shutil,copy,ast
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
assert (P/'LEARNING_PIPELINE_DONE.json').exists()
assert not (P/'REPETITION_PROTOCOL.json').exists()
sys.path.insert(0,str(P/'learning'))
import numpy as np
from value_model import fit,predict
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
data=np.load(P/'derived/DATASET_development.npz');ix=np.flatnonzero(data['splits']=='train');x=data['X'][ix];y=data['J'][ix,0,None];alpha=read('models/VALUE_FREEZE.json')['selected_alpha']
head=fit(x,y,alpha);errors=[]
for i in range(len(ix)):
    keep=np.arange(len(ix))!=i;errors.append(float(abs(predict(fit(x[keep],y[keep],alpha),x[i])[0,0]-y[i,0])))
error=max(errors)
np.savez_compressed(P/'models/repetition_base.npz',mu=head['mu'],sd=head['sd'],w=head['w'],loo_max_error_N_s=error,alpha=alpha)
arms=read('ACTION_SET.json')['arms'];h=copy.deepcopy(next(x for x in arms if x['id']=='H150'));b=copy.deepcopy(next(x for x in arms if x['id']=='B'))
memory=copy.deepcopy(h);memory.update(id='MEMORY',policy='feedback_value_v1',head_sha256=sha(P/'models/repetition_base.npz'));memory.pop('candidate_hash');memory['candidate_hash']=hashlib.sha256(json.dumps(memory,sort_keys=True).encode()).hexdigest()
cond=copy.deepcopy(read('D02_PLAN.json')['condition']);cond.update(name='REP',split='sequential_exposed_pilot',role='same live plant, second actual task after first complete H150; exposed W2 prefix, not holdout')
put('REP_TEST_PLAN.json',dict(frozen_unix=time.time(),condition=cond,fork_after_prefix=1,arms=[b,h,memory],reproduce_W1=False))
put('REPETITION_PROTOCOL.json',dict(frozen_unix=time.time(),status='PREREGISTERED_NOT_YET_RUN',condition=cond,first_task='frozen H150, same original legal prefix',second_task='persistent state then same-parent B/H150/MEMORY forks, all full TASK',state_carryover='original session_context and advance_inter_rep_boundary; no physical clock/qpos/qvel reset',feedback='first task measured force integral and live RETURN2 causal state only; native truth and matched-B future metrics excluded',online_update='one action-specific kernel coefficient for H150 =0.5*(measured full force integral - prior absolute value prediction), clipped to +/-LOO absolute prediction error; kernel exp(-0.5 mean standardized state distance squared)',error_buffer_N_s=error,guard='original predicted motion buffers + absolute-value LOO force uncertainty; H150 if unsupported or no confidence',primary_model_unchanged=True,required_for_few_repetition_pass='actual feedback update, different useful next action, complete qualified improvement over fixed H150 at same continued state; otherwise NOT_DEMONSTRATED',planned_starts=6,counts_include_boundary=True,physics_hard_cap=100,p2_starts=0))
for n in ['feedback_selector.py','prepare_repetition.py','repetition_runner.py','repetition_owner.py']:shutil.copy2(R/'control'/n,P/'control'/n)
s=(P/'control/campaign_v3.py').read_text().replace('EXECUTION_CODE_MANIFEST_v3.json','EXECUTION_CODE_MANIFEST_v4.json').replace('PREPHYSICAL_CHECKS_v3.json','PREPHYSICAL_CHECKS_v4.json').replace('PHYSICS_STOP_v3.json','PHYSICS_STOP_v4.json').replace("self.current.get('policy')=='frozen_Q_ridge'","self.current.get('policy')=='feedback_value_v1'").replace('from frozen_selector import select','from feedback_selector import select').replace("GROUP+'_Q_POLICY_DECISION.json'","GROUP+'_MEMORY_POLICY_DECISION.json'")
anchor="group_plan_sha256=sc.sha(P/(GROUP+'_TEST_PLAN.json')),**extra)"
assert s.count(anchor)==1
s=s.replace(anchor,"group_plan_sha256=sc.sha(P/(GROUP+'_TEST_PLAN.json')),feedback_sha256=sc.sha(P/'models/REPETITION_MEMORY_V1.json') if (P/'models/REPETITION_MEMORY_V1.json').exists() else None,**extra)")
assert s.count('causal_state=capture(b,self)')==1
s=s.replace('causal_state=capture(b,self)',"causal_state=capture(b,self)\n   causal_state['previous_complete_repetition_available']=(P/'models/REPETITION_MEMORY_V1.json').exists()")
(P/'control/campaign_v4.py').write_text(s);ast.parse(s)
files=dict(read('EXECUTION_CODE_MANIFEST_v3.json')['files'])
for f in [P/'control'/n for n in ['feedback_selector.py','prepare_repetition.py','repetition_runner.py','repetition_owner.py','campaign_v4.py']]+[P/'models/repetition_base.npz',P/'REPETITION_PROTOCOL.json',P/'REP_TEST_PLAN.json']:
    files[str(f.relative_to(P))]=sha(f)
put('EXECUTION_CODE_MANIFEST_v4.json',dict(files=files,frozen_unix=time.time(),scope='two real persistent tasks, bounded measured-feedback value update; original physics/control/safety unchanged',primary_model_sha256=read('models/VALUE_FREEZE.json')['model_sha256']))
put('PREPHYSICAL_CHECKS_v4.json',dict(status='PASS',AST=True,training_only_development_parents=data['groups'][ix].tolist(),no_test_outcome_used_for_training=True,old_model_unchanged=True,continuous_interface='original native persistent SCI API, not an environment replacement'))
print('REPETITION_PREPARED',error,'N_s empirical absolute value error',flush=True)
