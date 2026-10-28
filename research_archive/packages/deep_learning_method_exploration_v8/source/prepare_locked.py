from pathlib import Path
import json,copy,datetime,hashlib
P=Path(__file__).resolve().parents[1];dev=json.loads((P/'experiments/DEV.json').read_text());by={a['tag']:a['action'] for a in dev['actions']};model=json.loads((P/'analysis/FROZEN_BRANCH_MODEL.json').read_text());locks=[]
for group,seed,prefix,tags in [('VAL_A',2026102211,{'OUTBOUND':[[.09,.03,.025]],'RETURN':[[.03,.025,.025]]},['B','H150','BEST','C19','SAFE_M','SAFE_P']),('VAL_B',2026102212,{'OUTBOUND':[[.06,.055,.035]],'RETURN':[[.025,.04,.015]]},['B','BEST','C19'])]:
 c=copy.deepcopy(dev);c.update(group=group,mode='validation',historical_repeats={},actions=[],job_wall_cap_s=3600);c['condition']=dict(name=group,seed=seed,prefix=prefix,split='locked_unseen_prefix',role='frozen before new-state evaluation',Human='unchanged nominal; new causally executed legal prefix')
 for tag in tags:
  action=copy.deepcopy(by['C19'] if tag.startswith('SAFE') else by[tag]);delta=-.0006 if tag=='SAFE_M' else .0006 if tag=='SAFE_P' else 0.
  if tag.startswith('SAFE'):action['x'][3]+=delta
  pred=dict(type='STRICT_DOMAIN_ABSTENTION',reason='unseen full causal prefix; no generalization certificate',model_sha256=hashlib.sha256((P/'analysis/FROZEN_BRANCH_MODEL.json').read_bytes()).hexdigest(),truth_input=False)
  if tag in ['C19','SAFE_M','SAFE_P']:
   phi,rate=[model['coefficients'][0][i]+delta*model['coefficients'][1][i] for i in range(2)];curve=-2*model['L_m']*max(0.,model['h_s']*abs(rate)-abs(phi))/model['h_s']**2;pred['naive_transfer_diagnostic']=dict(predicted_motion_pass=curve>=-50,predicted_curvature_spike=curve,delta=delta,status='EXPLORATORY_FROZEN_TRANSFER_TEST_NO_DECISION_AUTHORITY')
  c['actions'].append(dict(tag=tag,action=action,category='locked_cross_state',prediction=pred))
 for n in [f'experiments/{group}.json',f'runtime/{group}_TEST_PLAN.json']:(P/n).write_text(json.dumps(c,indent=2)+'\n')
 locks.append(dict(group=group,config_sha256=hashlib.sha256((P/f'experiments/{group}.json').read_bytes()).hexdigest(),condition=c['condition'],actions=[a['tag'] for a in c['actions']],physical_attempt_cap=len(c['actions'])+1))
(P/'analysis/LOCKED_VALIDATION_FREEZE.json').write_text(json.dumps(dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),groups=locks,no_selection_from_validation=True,guard='UNCHANGED_ORIGINAL',all_conditions_frozen_before_any_new_state_result=True),indent=2)+'\n');print(locks)
