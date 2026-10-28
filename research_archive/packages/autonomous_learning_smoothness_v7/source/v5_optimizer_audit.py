"""Fixed-budget optimizer accounting and pre-action feedback chronology; no new physics."""
from pathlib import Path
import os,sys,json,datetime
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
d=json.loads((P/'analysis/optimization/OPT01_MATCHED_BUDGET.json').read_text());events=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];starts={x['id']:x for x in events if x['event']=='START'};ends={x['id']:x for x in events if x['event']=='END'};rows=[];errors=[]
for arm,aa in d['arms'].items():
 for i,r in enumerate(aa):
  pred=r['predicted'];when=datetime.datetime.fromisoformat(pred['created_utc']).timestamp();ident=r['id']
  if pred['training_physical_attempts']!=i:errors.append(ident+':OWN_FEEDBACK_COUNT')
  if not pred['only_own_arm_feedback']:errors.append(ident+':FEEDBACK_SCOPE')
  if when>starts[ident]['unix']:errors.append(ident+':PREDICTION_AFTER_START')
  if i and when<ends[aa[i-1]['id']]['unix']:errors.append(ident+':CREATED_BEFORE_PREVIOUS_FEEDBACK')
 for budget in d['fixed_checkpoints']:
  use=aa[:budget];valid=[r for r in use if r['qualified'] and r['complete']];best=min(valid,key=lambda r:r['score']);e=json.loads((P/'analysis/extended'/(best['id']+'.json')).read_text());w=json.loads((P/'analysis/native_wrench'/(best['id']+'.json')).read_text())
  rows.append(dict(arm=arm,physical_trial_budget=budget,actual_new_native_steps=sum(r['new_native_steps'] for r in use),complete_candidates=sum(r['complete'] for r in use),original_qualified_candidates=len(valid),qualification_fraction=len(valid)/budget,best_S=best['score'],selected_id=best['id'],JF=best['JF'],JM=best['JM'],native_jerk_RMS_deg_s3=e['native_motion']['jerk_deg_s3']['rms'],native_force_norm_rate_RMS_N_s=w['force']['norm_rate']['rms'],proxy_candidate_queries=sum(r['predicted'].get('proxy_queries',0) for r in use),individually_isolated_surrogate_CPU_time='NOT_MEASURED; included in finite group host wall, no physical-time saving inferred'))
prediction_errors=[]
for r in d['arms']['BO']:
 if r['predicted']['type']=='GP_BO_EI':prediction_errors.append(dict(id=r['id'],original_qualified=r['qualified'],predicted_S=r['predicted']['predicted_score'],observed_S=r['score'],score_std=r['predicted']['score_std'],interpretation='GP objective includes a discontinuous post-motion penalty. Posterior variance is a search heuristic, not calibrated feasibility or confidence.'))
out=dict(status='PASS' if not errors else 'FAIL',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),fixed_checkpoints=rows,BO_prediction_errors=prediction_errors,errors=errors,shared_sunk_history_START=7,shared_new_anchor_and_parent_START=3,own_new_trials_per_arm=12,total_OPT01_START=27,scope='One registered search seed and one nominal Human/condition. A result at 12 trials is not a general statistical superiority claim. Adaptive phase composition uses pooled histories and is explicitly excluded from these arm budgets.',new_native_steps_in_audit=0)
(P/'analysis/optimization/OPT01_POSTHOC_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
for r in rows:print(r['arm'],r['physical_trial_budget'],'qualified',r['original_qualified_candidates'],'S',r['best_S'],'selected',r['selected_id'])
assert not errors,errors
