from pathlib import Path
import json,time,hashlib,copy
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
assert not (P/'FROZEN_SELECTION.json').exists(),'Never reselect frozen primary'
for g in ['dev','refine']:assert read(g+'_DONE.json')['all_children_joined']
assert read('audit/INTERVENTION_EXECUTION_AUDIT.json')['status']=='PASS'
assessment=read('derived/ASSESSMENT_dev_refine.json')['rows'];eligible=[r for r in assessment if r['eligible'] and r['candidate']['id'] not in ['T','T_zero']]
eligible.sort(key=lambda r:tuple(r['delta_vs_T'][k] for k in ['TV_v','TV_a','jerk_RMS'])+(r['J_F'],))
primary=eligible[0] if eligible else None
frozen=dict(frozen_unix=time.time(),primary=None if primary is None else primary['candidate'],source_id=None if primary is None else primary['id'],development_assessment=assessment,selection_rule_sha256=sha(P/'SELECTION_RULE.json'),execution_manifest_sha256=sha(P/'EXECUTION_CODE_MANIFEST.json'),frozen_18D_sha256=sha(P/'FROZEN_18D.json'),validation_data_used_for_selection=False,selection_rule_unchanged=True,qualified_force_ranking=[dict(id=r['id'],J_F=r['J_F'],delta_J_F_vs_T=r['delta_J_F_vs_T']) for r in sorted([r for r in assessment if r['qualified']],key=lambda r:r['J_F'])],interpretation='Preregistered research threshold only; magnitude and actual motion benefit must be reported, not a clinical/substantial-gain claim.',reason='Eligible full-task physical candidate' if primary else 'No candidate meets unchanged full-task force/motion research criteria; no joint smoothing or held-out promotion')
put('FROZEN_SELECTION.json',frozen)
if primary is None:
 put('VALIDATION_RESULTS.json',dict(status='NOT_TRIGGERED',new_conditions=0,primary=None,reason=frozen['reason'],historical_T_four_prefix='history only, not new candidate validation'))
 print('NO_PRIMARY_STOP_DIRECTION',flush=True);raise SystemExit(0)
c=copy.deepcopy(primary['candidate']);repeat=copy.deepcopy(c);repeat['id']=c['id']+'_repeat';repeat['repeat_of']=c['id']
common=[dict(id=a,base=a,posture=[],changes=[]) for a in ['B','T']]
condition=dict(name='repeat',seed=2026101901,prefix={'OUTBOUND':[[-.045,-.075,-.055]]})
put('repeat_PLAN.json',dict(frozen_unix=time.time(),condition=condition,fork_after_prefix=1,archive_condition='V1',arms=common+[c,repeat],evidence='deterministic same-condition/live-parent repeat, not new state'))
known={}
def walk(value,path):
 if isinstance(value,dict):
  if 'prefix' in value:known.setdefault(json.dumps(value['prefix'],sort_keys=True,separators=(',',':')),[]).append(str(path))
  for v in value.values():walk(v,path)
 elif isinstance(value,list):
  for v in value:walk(v,path)
for root in P.parent.iterdir():
 if not root.is_dir() or root==P:continue
 for filename in ['RUN_PLAN.json','EXPERIMENT_PROTOCOL.json','VALIDATION_RESULTS.json','ATTEMPTS.jsonl']:
  f=root/filename
  if not f.exists():continue
  if f.suffix=='.jsonl':
   for line in f.read_text().splitlines():
    try:walk(json.loads(line),f)
    except json.JSONDecodeError:pass
  else:
   try:walk(json.loads(f.read_text()),f)
   except json.JSONDecodeError:pass
conditions=[dict(name='W1',seed=2026102001,prefix={'OUTBOUND':[[.08,.04,.03]],'RETURN':[[.04,.02,.03]]},coverage='positive OUTBOUND K3 prefix gives a new complete fork state; positive RETURN0 residual graph challenges incoming posture before the frozen RETURN2/3 intervention'),dict(name='W2',seed=2026102002,prefix={'OUTBOUND':[[.11,-.035,.045]],'RETURN':[[-.04,.025,-.035]]},coverage='mixed-sign OUTBOUND K3 prefix gives a new complete fork state; mixed-sign RETURN0 residual graph varies the near-intervention motion history')]
for cond in conditions:
 key=json.dumps(cond['prefix'],sort_keys=True,separators=(',',':'));assert key not in known,(cond,known.get(key))
 arms=[dict(id=a,base=a,posture=[],changes=[]) for a in ['B','E','T']]+[copy.deepcopy(c),copy.deepcopy(repeat)]
 put(cond['name']+'_PLAN.json',dict(frozen_unix=time.time(),condition=cond,fork_after_prefix=1,arms=arms,primary_fixed_before_validation=True,source_selection_sha256=sha(P/'FROZEN_SELECTION.json'),no_reselection=True))
put('NEW_PREFIX_VALIDATION_PROTOCOL.json',dict(frozen_unix=time.time(),conditions=conditions,inventory_checked='all root RUN_PLAN/EXPERIMENT_PROTOCOL/VALIDATION_RESULTS/ATTEMPTS in canonical Side Studies',inventory_unique_prefixes=len(known),inventory=known,primary_id=c['id'],selection_sha256=sha(P/'FROZEN_SELECTION.json'),execution_manifest_sha256=sha(P/'EXECUTION_CODE_MANIFEST.json'),prefix_semantics='Three coefficients are K3 differential residual graph values at remaining causal progress fractions0.1/0.4/0.7, not three Human joint states. OUTBOUND0 executes in the actual common parent before full address-space fork. RETURN0 is a separately registered common background prefix policy executed later in each arm, through each native current-state certificate; T and D follow the exact same physical history until D first acts at RETURN2. These are two new full-fork states plus distinct near-intervention histories; no hidden Human state assignment/replay.',rationale='Historical four T conditions have essentially identical RETURN integrals after settled HOLD; varying only OUTBOUND prefix weakly challenges a RETURN-only candidate. Vary a lawful RETURN0 graph too, without changing candidate amplitude/slots or the safety contract.',rules='Repeat must pass first. Each new condition actual cold native commissioning and legal prefix; complete live-state B/E/T/primary/repeat forks. Original full gates, primary>=0.5 N s force improvement vs T or >=0.5% full motion signal under original frozen selection rule, plus >=1% force gain vs matched B. Report every failure; no validation-driven primary change. Repeat is not a new state. These are same-Human tests only.',budget='5 repeat START + 12 validation START; 40 cap and final45minutes no START remain unchanged'))
print('FROZEN_PRIMARY',primary['id'],'VALIDATION_PROTOCOL_FROZEN',flush=True)
