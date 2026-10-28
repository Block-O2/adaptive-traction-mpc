"""Actual activation and actual-timestamp audit for all completed one-decision tails."""
from pathlib import Path
import json,datetime
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');groups=[];errors=[]
for file in sorted((P/'analysis/tail').glob('*.json')):
 d=json.loads(file.read_text());group=d['group'];rr=[]
 for row in d['rows']:
  ident=row['id']
  if not row['complete']:
   rr.append(dict(id=ident,status='PARTIAL_RETAINED_UNRANKED'));continue
  cap=json.loads((P/'history'/(ident+'_TAIL_CAUSAL.json')).read_text());fork=cap['fork_physical_s'];su=json.loads((P/'runtime/source/results'/ident/'summary.json').read_text());current=[];later=[];bad=[]
  for lr in su['learning_records']:
   if lr['request_time_s']<fork-1e-8:continue
   screen=lr.get('selected_plan',{}).get('execution_screen',{});intent=any(screen.get(k) for k in ['coordination_modal_v2','free_trajectory','second_round_posture','early_return_duration','terminal_hip_timing'])
   rec=dict(decision_index=lr['decision_index'],request_time_s=lr['request_time_s'],activated=lr.get('selected_plan_activated'),has_T_or_modal_intent=bool(intent),completion=lr.get('completion'))
   if abs(lr['request_time_s']-fork)<1e-8:current.append(rec)
   else:
    later.append(rec)
    if intent:bad.append('LATER_DECISION_HAS_INTERVENTION')
  offsets={h:feat['physical_s']-fork-float(h) for h,feat in cap['captures'].items()}
  if len(current)!=1:bad.append('CURRENT_DECISION_NOT_UNIQUE')
  if any(abs(z)>.005+1e-8 for z in offsets.values()):bad.append('CAPTURE_TIME_OUTSIDE_BOUNDARY_GRID')
  if row.get('continuation_audit','').split(':')[0]!='PASS':bad.append('BASE_POLICY_AUDIT_NOT_PASS')
  if current and current[0]['has_T_or_modal_intent'] and not current[0]['activated']:bad.append('INTERVENTION_NOT_ACTIVATED')
  policy=P/'history'/(ident+'_TAIL_POLICY_INPUTS.json')
  if policy.exists():
   pp=json.loads(policy.read_text())['rows'];interventions=sum(bool(x['candidate_intervention']) for x in pp)
   if interventions>1 or any(x['active_action'].get('family')!='B' for x in pp if not x['candidate_intervention']):bad.append('POLICY_INPUT_NOT_ONE_THEN_B')
  else:interventions=None
  rr.append(dict(id=ident,status='PASS' if not bad else 'FAIL',current=current,later=later,captured_time_offset_from_requested_H_s=offsets,policy_input_log_interventions=interventions,original_qualified=row['qualified'],errors=bad))
  errors.extend([ident+':'+b for b in bad])
 groups.append(dict(group=group,common_parent_hashes=d['parent_hashes'],rows=rr))
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS' if not errors else 'FAIL',groups=groups,errors=errors,scope='Actual learning-record activation and actual boundary timestamps; subsequent selected records have no extra intervention. Original full receipt/native/source/scorer audits independently verify execution. This is not an optimality or Markov sufficiency proof.',new_native_steps=0)
(P/'audit/ROLLING_TAIL_POLICY_AND_TIME.json').write_text(json.dumps(out,indent=2)+'\n');print('TAIL_POLICY',out['status'],'groups',len(groups),'rows',sum(len(g['rows']) for g in groups));assert not errors,errors
