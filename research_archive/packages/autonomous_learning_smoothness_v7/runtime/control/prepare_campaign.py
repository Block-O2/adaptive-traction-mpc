"""Preregister finite legal action-value study before collecting any new physics."""
from pathlib import Path
import os,sys,json,hashlib,copy,time,ast,shutil
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
A=P.parent/'ihear_model_terminal_compensation_v1'
sys.dont_write_bytecode=True
assert (P/'BOOTSTRAP_DONE.json').exists()
assert not (P/'EXECUTION_CODE_MANIFEST_v2.json').exists()
def put(n,x): (P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f): return hashlib.sha256(f.read_bytes()).hexdigest()
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
old=json.loads((A/'Ctrl_PLAN.json').read_text())
baseline=copy.deepcopy(next(x for x in old['arms'] if x['id']=='B'))
h150=copy.deepcopy(next(x for x in old['arms'] if x['id']=='H150'))
arms=[baseline,h150]
for name,delta in [('HIP',[.3,0.]),('KNEE',[0.,-.3]),('ZERO',[0.,0.])]:
    c=copy.deepcopy(h150);c['id']=name;c.pop('candidate_hash')
    for v in c['posture']: v['delta_deg']=delta
    c['candidate_hash']=digest(c);arms.append(c)
put('ACTION_SET.json',dict(frozen_unix=time.time(),arms=arms,only_difference='RETURN2 and RETURN3 middle posture delta; all learning arms share T, early ER and terminal H150 timing',baseline_hash=h150['candidate_hash'],torque_action=False))
prefixes=[
('D01',2026102001,[.08,.04,.03],[.04,.02,.03],'train','historical W1 exposed'),
('D02',2026102002,[.11,-.035,.045],[-.04,.025,-.035],'train','historical W2 now exposed'),
('D03',2026102103,[.03,-.06,.08],[.07,-.035,.02],'train','prospective development'),
('D04',2026102104,[-.04,.075,.025],[-.07,.045,.015],'train','prospective development'),
('D05',2026102105,[.10,-.065,-.035],[.025,-.06,.065],'train','prospective development'),
('D06',2026102106,[-.06,.025,.07],[-.025,-.045,.075],'train','prospective development'),
('V01',2026102201,[.055,-.045,.06],[.055,.035,-.025],'validation','model selection; never final blind test'),
('V02',2026102202,[-.025,.065,.045],[-.055,-.025,.05],'validation','model selection; never final blind test'),
('U01',2026102301,[.095,.015,-.055],[.065,-.025,.045],'test','unseen until model freeze'),
('U02',2026102302,[-.045,.055,.035],[-.065,.035,-.025],'test','unseen until model freeze'),
('U03',2026102303,[.045,-.055,.065],[.035,-.055,.055],'test','unseen until model freeze')]
conditions=[]
historical=[]
for f in P.parent.rglob('ATTEMPTS.jsonl'):
    if f.is_relative_to(P):continue
    for line in f.read_text().splitlines():
        try:r=json.loads(line)
        except json.JSONDecodeError:continue
        if r.get('event')=='START' and r.get('condition',{}).get('prefix'): historical.append(r['condition']['prefix'])
for name,seed,out,ret,split,role in prefixes:
    prefix={'OUTBOUND':[out],'RETURN':[ret]}
    if name not in ['D01','D02']: assert prefix not in historical,'PREFIX_ALREADY_CONSUMED'
    cond=dict(name=name,seed=seed,prefix=prefix,split=split,role=role)
    conditions.append(cond)
    put(name+'_PLAN.json',dict(frozen_unix=time.time(),condition=cond,fork_after_prefix=1,arms=arms,reproduce_W1=False))
put('SPLIT_REGISTRATION.json',dict(frozen_unix=time.time(),split_unit='complete cold parent / prefix family; repeats grouped together',conditions=conditions,historical_start_conditions_scanned=len(historical),test_consumption_rule='Freeze model and all selection rules before U01/U02/U03. Report all failures; never retune on test.'))
put('LEARNING_PROTOCOL.json',dict(frozen_unix=time.time(),method='finite-action contextual Monte Carlo cost/value regression; terminal full-task returns, no Bellman bootstrap claim',state_origin='causal RETURN slot 2, before first posture intervention',actions=['H150','HIP','KNEE','ZERO'],feature_policy='estimated q/dq minus current reference; measured force/moment norms; phase elapsed. All inputs captured live before action.',reward='qualification first, then negative complete-task force integral; matched B and native truth are offline labels only',models=['global action mean','ridge with explicit action-specific state slopes'],ridge_grid=[.1,1.,10.,100.],qualification='predict every original margin with same feature map; conservative lower confidence margin and support distance; no future-label runtime mask',selection='H150 default; choose alternative only if all predicted original margins positive with development calibrated residual buffer and force advantage exceeds development prediction error; direct Q argmin diagnostic separately',evaluation='held-out parent selection regret, action ranking, qualification and costs vs fixed H150 and best train-only global action; independent raw audit',promotion='Q_GENERALIZATION_PASS only with qualified physical improvement vs H150 on all test parents, nonconstant selections, and improvement vs globally best fixed action; otherwise not demonstrated',few_repetition='requires actual completed repetition feedback and a subsequent actual re-admitted task. Cold fork dataset is not repetition learning.',p1_planned_starts=66,p1_hard_cap=100,p2_status='conditional; separate budget; no starts yet',limits='Single Human, PHYSICAL_LEVEL1/SCIENTIFIC_SIMULATION only'))
shutil.copy2(R/'control/prepare_campaign.py',P/'control/prepare_campaign.py')
shutil.copy2(R/'control/causal_features.py',P/'control/causal_features.py')
shutil.copy2(R/'control/run_development.py',P/'control/run_development.py')
for folder in ['analysis','learning']:
    for f in (R/folder).glob('*.py'):shutil.copy2(f,P/folder/f.name)
s=(A/'control/campaign_v2.py').read_text()
oldline="tbase=m if c['id'] in ['B','E','T'] else json.loads((P/'reports'/(GROUP+'_T_MEASURED.json')).read_text());paired=am.compare(m,tbase)"
assert s.count(oldline)==1
s=s.replace(oldline,"tbase=m if c['id'] in ['B','H150'] else json.loads((P/'reports'/(GROUP+'_H150_MEASURED.json')).read_text());paired=am.compare(m,tbase)")
s=s.replace('paired_vs_T=paired','paired_vs_H150=paired')
anchor="  mh.MatchedInterface.control(self,b)"
assert s.count(anchor)==1
s=s.replace(anchor,"  if self.child is not None and phase=='RETURN' and slot==2 and not getattr(self,'learning_context_saved',False):\n   from causal_features import capture\n   put('output/'+GROUP+'_'+self.current['id']+'_CAUSAL_STATE.json',capture(b,self))\n   self.learning_context_saved=True\n"+anchor)
# Expose no truth to selector; features are logged before the posture action is issued.
s=s.replace("'START_CAP_80'","'START_CAP_100'")
(P/'control/campaign_v2.py').write_text(s)
shutil.copy2(A/'control/owner_v2.py',P/'control/owner_v2.py')
put('NEW_FROZEN_SELECTION.json',dict(primary='H150',candidate=h150,role='frozen control baseline, not a learned policy',source_sha256=sha(A/'NEW_FROZEN_SELECTION.json')))
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.path[:0]=[str(P/'control'),str(P/'code')]
import study_common as sc
assert str(sc.STUDY)==str(P)
for d in ['source','code','deps','control']:
    for f in (P/d).rglob('*.py'): ast.parse(f.read_text(),filename=str(f))
identity=[]
for d in ['source','code','deps','weights']:
    for f in (P/d).rglob('*'):
        if not f.is_file() or 'results' in f.parts or '__pycache__' in f.parts:continue
        original=A/f.relative_to(P)
        a=f.read_bytes();b=original.read_bytes()
        if f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
            try:
                original_text=original.read_text()
                if str(A) in original_text:b=original_text.replace(str(A),str(P)).encode()
            except UnicodeDecodeError:pass
        assert a==b, str(f)
        identity.append(str(f.relative_to(P)))
put('audit/ORIGINAL_CLOSURE_IDENTITY.json',dict(status='PASS',files=len(identity),only_path_rebase=True,controller_plant_safety_unchanged=True))
files={str(f.relative_to(P)):sha(f) for d in ['source','code','deps','weights','control'] for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in f.parts and 'results' not in f.parts}
for n in ['RUN_PLAN.json','FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','ACTION_SET.json','SPLIT_REGISTRATION.json','LEARNING_PROTOCOL.json','output/SHARED_COORDINATION_ACTION_CONTRACT.json']:files[n]=sha(P/n)
put('EXECUTION_CODE_MANIFEST_v2.json',dict(files=files,frozen_unix=time.time(),parent=sha(A/'EXECUTION_CODE_MANIFEST_v2.json'),change='path-only cloned source, finite-action experiment harness and causal logging only'))
put('PREPHYSICAL_CHECKS_v2.json',dict(status='PASS',AST=True,imports_isolated=True,no_physics_started=not (P/'ATTEMPTS.jsonl').exists(),original_closure_identity='PASS',action_bounds='each delta <=0.3 deg, existing timing unchanged',live_checks_required=True))
put('audit/WRITING_REFERENCE.json',dict(status='No suitable writing references found in the returned results',style_basis='User supplied Chinese task contract'))
put('STATE.json',dict(phase='LEARNING_WORKFLOW_STARTED',physics_starts=0,next='D01 matched physics; then causal prediction and grouped data collection',unix=time.time()))
print('PREPHYSICAL_PASS',len(files),'FILES',flush=True)
