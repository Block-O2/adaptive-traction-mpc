"""Read-only frozen-model, H prediction, and pre-state ranking chronology."""
from pathlib import Path
import json,time,hashlib
P=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def main():
 ev=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];starts={r['id']:r for r in ev if r['event']=='START'};ends={r['id']:r for r in ev if r['event']=='END'};errors=[];rows=[]
 for f in sorted((P/'analysis/evaluation').glob('*.json')):
  e=json.loads(f.read_text());g=e['group'];cfg=read('experiments/'+g+'.json');model=read(e['model_path']);first=min(r['unix'] for r in starts.values() if r['group']==g)
  bad=[]
  if first<=model['frozen_unix']:bad.append('MODEL_NOT_FROZEN_BEFORE_START')
  if sha(P/e['model_path'])!=e['model_sha256']:bad.append('MODEL_CHANGED_AFTER_EVALUATION')
  if e['future_qualification_mask_in_deployed_choices']:bad.append('FUTURE_QUALIFICATION_MASK')
  for tag in e['primary_menu']:
   ident=g+'_'+tag;pred=read('predictions/'+ident+'_H05.json')
   if not starts[ident]['unix']<pred['created_unix']<ends[ident]['unix']:bad.append('PREDICTION_TIMING:'+tag)
   if pred['full_task_outcome_exists'] or pred['uses_native_truth']:bad.append('FUTURE_OR_NATIVE_TRUTH:'+tag)
   if pred['frozen_bundle_sha256']!=e['model_sha256']:bad.append('LIVE_MODEL_IDENTITY:'+tag)
  rows.append(dict(group=g,model_frozen_unix=model['frozen_unix'],first_physics_START=first,menu=e['primary_menu'],independence_role='TRAINING_PARENT_REPLAY' if g=='LEGACY_BOUNDARY_O3' else 'FROZEN_NEW_PREFIX',errors=bad));errors += [g+':'+b for b in bad]
 screen=[]
 for g in ['SCREEN_S1','SCREEN_S2','SCREEN_S3','SCREEN_AUDIT']:
  q=P/'predictions'/f'{g}_PRESTATE_SCREEN.json'
  if not q.exists():continue
  d=json.loads(q.read_text());cfg=read('experiments/'+g+'.json');model=read(cfg['frozen_proxy']);first=min(s['unix'] for s in starts.values() if s['group']==g and s['id'] in [g+'_'+t for t in d['unique_menu']]);bad=[]
  if d['created_unix']>=first:bad.append('RANKING_NOT_BEFORE_CANDIDATE_START')
  if d['uses_H_state'] or d['uses_candidate_physics']:bad.append('CANDIDATE_PHYSICS_LEAK')
  if sha(P/cfg['frozen_proxy'])!=d['frozen_proxy_sha256']:bad.append('PROXY_CHANGED')
  if d['created_unix']<=model['created_unix']:bad.append('PROXY_NOT_FROZEN_BEFORE_QUERY')
  screen.append(dict(group=g,prediction_unix=d['created_unix'],first_offered_candidate_START=first,
   paid_B_anchor_may_precede_ranking=True,errors=bad));errors += [g+':'+b for b in bad]
 risk=read('models/WHOLE_HISTORY_RISK_V5_FROZEN.json');bad=[]
 if sha(P/'data/WHOLE_HISTORY_RISK_ROWS_V5.json')!=risk['training_data_sha256']:bad.append('RISK_DATA_CHANGED')
 for n,h in risk['source_sha256'].items():
  if sha(P/'source'/n)!=h:bad.append('RISK_SOURCE_CHANGED:'+n)
 for name in ['COMMON_COMPOSE_FROZEN.json','LEGACY_B_REVISED_V5_FROZEN.json']:
  m=read('models/'+name)
  if not all(bundle['risk']==risk['model'] for bundle in m['phases'].values()):bad.append('OPERATIVE_RISK_WEIGHT_IDENTITY:'+name)
 errors+=bad
 # The4-action main comparison and evaluation code identities were fixed before its first START.
 proto=read('freeze/PRIMARY_TEST_PROTOCOL_FROZEN.json')
 for key,path in [('model_sha256','models/COMMON_COMPOSE_FROZEN.json'),('selection_source_sha256','source/v6_selection.py'),('evaluation_source_sha256','source/v6_evaluate.py'),('test_worker_sha256','source/v6_test_worker.py'),('return_worker_sha256','source/v6_coordinated_return_worker.py')]:
  if sha(P/path)!=proto[key]:errors.append('PRIMARY_FREEZE_IDENTITY:'+path)
 global_freeze=read('freeze/WHOLE_POLICY_CONFIRMATIONS_FINAL_FROZEN.json')
 for g in ['SMOOTH_A1','SMOOTH_A2']:
  first=min(s['unix'] for s in starts.values() if s['group']==g)
  if first<=global_freeze['frozen_unix'] or sha(P/'experiments'/f'{g}.json')!=global_freeze['configs_sha256'][g]:errors.append('WHOLE_POLICY_FREEZE:'+g)
 second=P/'analysis/SECOND_LOCAL_BOUNDARY_RESULT.json';expected=7 if second.exists() and read('analysis/SECOND_LOCAL_BOUNDARY_RESULT.json')['status']=='COMPLETED_FROZEN_LOCAL_CHALLENGE' else 6
 out=dict(status='PASS' if not errors and len(rows)==expected and len(screen)==4 else 'FAIL' if errors else 'IN_PROGRESS',
  checked_unix=time.time(),audit_source_sha256=sha(Path(__file__)),frozen_evaluations=rows,
  prospective_screens=screen,risk_weight_and_source_errors=bad,errors=errors,
  main_test_states=4,independent_extra_risk_states=2,training_parent_replays=expected-6,scope='Chronology checks alone do not establish state independence. O3 alias separately sealed and excluded from independent validation. Full-menu choice is deterministic retrospective aggregation of saved H predictions, not a low-cost closed-loop deployment. Adaptive phase follow-up is outside independent model validation.')
 (P/'audit/FREEZE_AND_CAUSAL_PREDICTION_CHRONOLOGY.json').write_text(json.dumps(out,indent=2)+'\n')
 print('FREEZE_CHRONOLOGY',out['status'],len(rows),'evaluations',len(screen),'screens',errors[:5],flush=True)
 if errors:raise SystemExit(1)
if __name__=='__main__':main()
