from pathlib import Path
import json,time,copy,hashlib,shutil
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert (P/'Adev_DONE.json').exists()
assert not (P/'NEW_FROZEN_SELECTION.json').exists(),'Never reselect a frozen candidate'
rows=[r for r in read('EXPERIMENT_RESULTS.json')['rows'] if r['id'].startswith('Adev_') and r['candidate'].get('approach')]
eligible=[r for r in rows if r['eligible_primary']];selected=next((r for name in ['AV090','AV080'] for r in eligible if r['candidate']['id']==name),None)
out=dict(status='FROZEN_PENDING_REPEAT_AND_UNUSED_PREFIX' if selected else 'NO_ELIGIBLE_NEW_CANDIDATE',frozen_unix=time.time(),primary=None if selected is None else selected['candidate'],development_id=None if selected is None else selected['id'],execution_manifest_sha256=sha(P/'EXECUTION_CODE_MANIFEST.json'),selection_rule_sha256=sha(P/'CANDIDATE_SELECTION_RULE.json'),development_results_sha256=sha(P/'Adev_RESULTS.json'),development_outcomes=[dict(id=r['id'],eligible=r['eligible_primary'],qualified=r['all_original_qualifications'],failed=r['motion']['failed_requirements'],overshoot_change_vs_ER_deg=r['overshoot_change_vs_ER_deg']) for r in rows],validation_used_for_selection=False)
put('NEW_FROZEN_SELECTION.json',out)
if selected:
 base=read('Adev_PLAN.json');arms=copy.deepcopy(base['arms'][:4]);candidate=copy.deepcopy(selected['candidate']);candidate.pop('conditional_second',None);arms.append(candidate);repeat=copy.deepcopy(candidate);repeat['id']+='_repeat';repeat['repeat_of']=candidate['id'];arms.append(repeat)
 cond=copy.deepcopy(base['condition']);cond['name']='Arepeat';cond['role']='same W1 condition new cold parent plus deterministic same-parent repeat; not new state'
 put('Arepeat_PLAN.json',dict(frozen_unix=time.time(),condition=cond,fork_after_prefix=1,reproduce_W1=True,arms=arms,frozen_selection_sha256=sha(P/'NEW_FROZEN_SELECTION.json')))
 cond=copy.deepcopy(read('HOLDOUT_REGISTRATION.json')['condition']);cond['name']='W2';cond['role']='unused legal prefix independent of candidate development, same Human'
 put('W2_PLAN.json',dict(frozen_unix=time.time(),condition=cond,fork_after_prefix=1,reproduce_W1=False,arms=copy.deepcopy(arms[:-1]),frozen_selection_sha256=sha(P/'NEW_FROZEN_SELECTION.json'),requires_repeat_gate_before_dispatch=True))
else:
 put('VALIDATION_RESULTS.json',dict(status='NOT_STARTED_NO_ELIGIBLE_NEW_CANDIDATE',primary=None,deterministic_repeat=False,unused_prefix_validation=False,W2_unconsumed=True,reason='Original development qualification or preregistered efficacy failed; continue other tracks without tuning on holdout',evidence_level='PHYSICAL_LEVEL1 development only'))
with (P/'MULTI_TRACK_DECISION_LOG.md').open('a') as f:
 f.write('\n## D3 — Track A开发选择冻结\n'+json.dumps(out,ensure_ascii=False,indent=2)+'\n')
for n in ['NEW_FROZEN_SELECTION.json','MULTI_TRACK_DECISION_LOG.md','Arepeat_PLAN.json','W2_PLAN.json','VALIDATION_RESULTS.json']:
 if (P/n).exists():shutil.copy2(P/n,R/n)
print(json.dumps(out,ensure_ascii=False),flush=True)
