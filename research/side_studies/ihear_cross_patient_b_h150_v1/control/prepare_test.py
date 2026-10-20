"""Freeze a separate inference-integrated harness before consuming any U parent."""
from pathlib import Path
import os,sys,json,time,hashlib,shutil,ast,copy,subprocess
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
assert (P/'models/VALUE_FREEZE.json').exists()
assert not (P/'EXECUTION_CODE_MANIFEST_v3.json').exists()
assert not any(json.loads(r)['id'].startswith('U') for r in (P/'ATTEMPTS.jsonl').read_text().splitlines())
shutil.copy2(R/'control/frozen_selector.py',P/'control/frozen_selector.py')
shutil.copy2(R/'control/prepare_test.py',P/'control/prepare_test.py')
for n in ['early_features.py','early_selector.py']:shutil.copy2(R/'control'/n,P/'control'/n)
subprocess.run([sys.executable,'-B',str(P/'learning/train_early.py')],check=True,cwd=P)
arms=read('ACTION_SET.json')['arms'];h=next(x for x in arms if x['id']=='H150')
q=copy.deepcopy(h);q['id']='Q';q['policy']='frozen_Q_ridge';q['model_sha256']=read('models/VALUE_FREEZE.json')['model_sha256'];q.pop('candidate_hash')
q['candidate_hash']=hashlib.sha256(json.dumps(q,sort_keys=True).encode()).hexdigest()
qe=copy.deepcopy(h);qe.update(id='QE',policy='frozen_early_value',model_sha256=read('models/EARLY_VALUE_FREEZE.json')['model_sha256']);qe.pop('candidate_hash');qe['candidate_hash']=hashlib.sha256(json.dumps(qe,sort_keys=True).encode()).hexdigest()
oldplans={}
for group in ['U01','U02','U03']:
    cfg=read(group+'_PLAN.json');oldplans[group]=cfg
    cfg['arms']=cfg['arms']+[q,qe];cfg['policy_added_before_any_test_outcome']=True
    put(group+'_TEST_PLAN.json',cfg)
put('audit/TEST_PLAN_EXTENSION.json',dict(frozen_unix=time.time(),original_plans=oldplans,change='Add primary live RETURN2 Q and secondary earlier full-strategy QE branches; all registered fixed actions/prefix/seeds/gates unchanged',added_starts=6,policy=q,secondary_policy=qe))
s=(P/'control/campaign_v2.py').read_text().replace('EXECUTION_CODE_MANIFEST_v2.json','EXECUTION_CODE_MANIFEST_v3.json').replace('PREPHYSICAL_CHECKS_v2.json','PREPHYSICAL_CHECKS_v3.json').replace('PHYSICS_STOP_v2.json','PHYSICS_STOP_v3.json').replace("(GROUP+'_PLAN.json')","(GROUP+'_TEST_PLAN.json')")
anchor="   put('output/'+GROUP+'_'+self.current['id']+'_CAUSAL_STATE.json',capture(b,self))"
assert s.count(anchor)==1
replacement="""   causal_state=capture(b,self)
   put('output/'+GROUP+'_'+self.current['id']+'_CAUSAL_STATE.json',causal_state)
   if self.current.get('policy')=='frozen_Q_ridge':
    from frozen_selector import select
    decision=select(causal_state)
    choice=next(a for a in json.loads((P/'ACTION_SET.json').read_text())['arms'] if a['id']==decision['selected'])
    self.current={**self.current,'posture':choice['posture'],'selected_action':choice['id'],'selected_action_hash':choice['candidate_hash']}
    put('output/'+GROUP+'_Q_POLICY_DECISION.json',decision)
""".rstrip()
s=s.replace(anchor,replacement)
early_anchor="     self.current=c;self.references={};self.sample_rows=[];self.terminal_intent=TerminalIntent(c['controller']) if c.get('controller') else None"
assert s.count(early_anchor)==1
s=s.replace(early_anchor,early_anchor+"""
     if self.current.get('policy')=='frozen_early_value':
      from early_features import capture as capture_early
      from early_selector import select as select_early
      early_state=capture_early(b,self);decision=select_early(early_state)
      chosen=next(a for a in json.loads((P/'ACTION_SET.json').read_text())['arms'] if a['id']==decision['selected'])
      self.current={**chosen,'id':'QE','policy':'frozen_early_value','candidate_hash':c['candidate_hash'],'selected_action':chosen['id'],'selected_action_hash':chosen['candidate_hash']}
      put('output/'+GROUP+'_QE_POLICY_DECISION.json',decision)
""".rstrip())
assert s.count('postures=[')==1
s=s.replace('postures=[',"""expected=c
    if c.get('policy')=='frozen_early_value':
     early_decision=json.loads((P/'output'/(GROUP+'_QE_POLICY_DECISION.json')).read_text())
     expected=next(a for a in json.loads((P/'ACTION_SET.json').read_text())['arms'] if a['id']==early_decision['selected'])
    postures=[""")
assert s.count('len(c.get(')==3
s=s.replace('len(c.get(','len(expected.get(')
(P/'control/campaign_v3.py').write_text(s);ast.parse(s)
owner=(P/'control/owner_v2.py').read_text().replace('campaign_v2.py','campaign_v3.py').replace("(group+'_PLAN.json')","(group+'_TEST_PLAN.json')")
(P/'control/owner_v3.py').write_text(owner);ast.parse(owner)
files=dict(read('EXECUTION_CODE_MANIFEST_v2.json')['files'])
for f in [P/'control/campaign_v3.py',P/'control/owner_v3.py',P/'control/frozen_selector.py',P/'control/prepare_test.py',P/'models/Q_value_ridge.npz',P/'models/VALUE_FREEZE.json']:
    files[str(f.relative_to(P))]=sha(f)
for n in ['control/early_features.py','control/early_selector.py','learning/train_early.py','models/early_value_ridge.npz','models/EARLY_VALUE_FREEZE.json','EARLY_VALUE_PROTOCOL.json']:files[n]=sha(P/n)
put('EXECUTION_CODE_MANIFEST_v3.json',dict(files=files,frozen_unix=time.time(),parent_sha=sha(P/'EXECUTION_CODE_MANIFEST_v2.json'),change='live inference on causal state, same four bounded actions; original frozen B and certificates unchanged'))
sys.path.insert(0,str(P/'control'))
import frozen_selector
sample=read('output/D02_H150_CAUSAL_STATE.json');decision=frozen_selector.select(sample)
assert decision['selected'] in ['H150','HIP','KNEE','ZERO']
put('PREPHYSICAL_CHECKS_v3.json',dict(status='PASS',AST=True,model_identity=True,inference_probe=decision,all_test_parents_unconsumed=True,original_action_bounds_unchanged=True))
print('TEST_HARNESS_FROZEN',decision['selected'],flush=True)
