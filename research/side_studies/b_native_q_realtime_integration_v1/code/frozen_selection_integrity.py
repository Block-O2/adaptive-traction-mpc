"""Recompute frozen Q from saved causal candidate records; no predictions/physics."""
from task_bootstrap import *
import numpy as np

def main():
 import study_common,native_core
 from native_inference import Networks
 net=Networks(STUDY/'weights/frozen_Q_v1');rows=[];issues=[];total=0
 for path in sorted((STUDY/'output').glob('*_SELECTIONS.json')):
  id=path.name[:-len('_SELECTIONS.json')];rp=STUDY/'output'/(id+'_RESULT.json')
  if not rp.exists():continue
  result=json.loads(rp.read_text());cfg=result.get('inputs',{});records=json.loads(path.read_text()).get('rows',[])
  if cfg.get('method')!='M2' or not records:continue
  carry=np.zeros((2,5,3));local=[]
  for s in records:
   candidates=s['candidate_records'];count=s['count_before'];features=np.asarray([native_core.feature(s['context'],r['plan'],count,carry) for r in candidates]);allq=net.values(features);valid=[j for j,r in enumerate(candidates) if r.get('feasible') and r.get('proposal_accepted')];subset=net.values(features[valid]) if valid else [];selected=valid[int(np.argmin(subset))] if valid else 0
   # SCI/fallback stores valid-subset Q; the fast actual route may store all-Q.
   use_subset=s.get('scientific_full_validation_shadow',False) or s.get('close_rank_fallback',False) or 'q_first_order' not in s
   expected={j:float(v) for j,v in zip(valid,subset)} if use_subset else {j:float(allq[j]) for j in range(len(candidates))}
   qerror=max([abs(float(r['Q'])-expected[j]) for j,r in enumerate(candidates) if r.get('Q') is not None and j in expected] or [0.]);allerror=max(abs(np.asarray(s['q_all'])-allq)) if 'q_all' in s else 0.
   # All candidates in SCI are completely checked; fast actual record contains
   # only evaluated candidates, so its argmin proof is limited to that subset.
   fully_evaluated=all(r.get('feasible') is not None for r in candidates);chosen_match=(selected==s['selected_index']) if fully_evaluated or use_subset else None
   applied=np.asarray(s['applied_plan']);expected_plan=carry if s.get('late_discard') or not valid else np.asarray(candidates[s['selected_index']]['plan']);applied_exact=np.array_equal(applied,expected_plan)
   row=dict(request_id=s['request_id'],phase=s['context']['phase'],count_before=count,candidate_count=len(candidates),fully_evaluated=fully_evaluated,reconstructed_selected_index=selected if fully_evaluated else None,saved_selected_index=s['selected_index'],complete_pool_rank_match=chosen_match,Q_max_abs_error_N_s=float(qerror),all_Q_max_abs_error_N_s=float(allerror),late_discard=bool(s.get('late_discard')),applied_plan_matches_selected_or_prior_carry=applied_exact,carry_before_sha256=hashlib.sha256(carry.astype('<f8').tobytes()).hexdigest())
   if qerror>1e-10 or allerror>1e-10 or chosen_match is False or not applied_exact:issues.append(dict(id=id,**row))
   local.append(row);carry=applied.copy();total+=1
  rows.append(dict(id=id,execution_mode=cfg.get('execution_mode'),valid=result.get('metric',{}).get('valid',False),rows=local))
 out=dict(status='PASS' if not issues else 'FAIL',runs=len(rows),native_selection_rows=total,issues=issues,rows=rows,Q_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),tolerance=1e-10,Q_updates=0,physics_added=0,remaining_cost_physics_predictions=0,interpretation='Initial carry is the unchanged native coordinator zero table for each recorded episode; subsequent carry is the saved applied plan. Prefix-owned actions do not update the coordinator carry table. All saved current-state features use original native_core.feature and frozen normalization/weights. Q is recomputed only, no training or future reward. This audit cannot turn partial fast validation into full-pool acceptance evidence or actual wall qualification.')
 save(STUDY/'reports/FROZEN_SELECTION_INTEGRITY.json',out);print(json.dumps(dict(status=out['status'],runs=len(rows),native_selection_rows=total,issue_count=len(issues),first_issues=issues[:3])))
if __name__=='__main__':main()
