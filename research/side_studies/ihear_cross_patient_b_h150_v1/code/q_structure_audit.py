"""Frozen linear Q feature/ranking audit, no physics or fitting."""
from task_bootstrap import *
import numpy as np
def main():
 weights=np.load(STUDY/'weights/frozen_Q_v1/weights.npz');meta=json.loads((STUDY/'weights/frozen_Q_v1/TRAINING.json').read_text());assert meta['selected_Q']=='linear'
 coef=weights['linear_W']/weights['x_scale']*weights['y_scale'];offset=float(weights['y_mean']+weights['y_scale']*weights['linear_b']-coef@weights['x_mean'])
 groups=[]
 for p in sorted((BASE/'output').glob('040_v1_*_M2_SELECTIONS.json')):
  f=json.loads(p.read_text())
  for row in f['rows']:
   plans=[np.asarray(r['plan'],float).reshape(-1) for r in row['candidate_records']]
   contributions=[float(coef[58:88]@u) for u in plans];recorded=[r.get('Q') for r in row['candidate_records']]
   valid=[j for j,q in enumerate(recorded) if q is not None]
   delta_errors=[abs((recorded[a]-recorded[b])-(contributions[a]-contributions[b])) for a in valid for b in valid]
   groups.append(dict(source=p.name,request=row['request_id'],phase=row['context']['phase'],issued_counts=row['count_before'],selected=row['selected_index'],fixed_plan_preference_rank=sorted(range(len(plans)),key=lambda i:contributions[i]),native_accepted_indices=valid,plan_contributions_N_s=contributions,max_counterfactual_difference_error=max(delta_errors or [0.])))
 dims=dict(state_and_history=[0,58],candidate_U=[58,88],carry=[88,118],issued_counts=[118,120]);summary={k:dict(L1=float(np.sum(np.abs(coef[a:b]))),L2=float(np.linalg.norm(coef[a:b])),coefficients=coef[a:b].tolist()) for k,(a,b) in dims.items()}
 out=dict(status='STATE_DEPENDENCE_LIMITED',weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),selected_Q='linear',feature_dim=120,equation='Q(x)=offset + coef_state*b + coef_U*masked(U) + coef_carry*masked(carry) + coef_count*count',state_times_plan_interactions=False,offset=offset,feature_groups=summary,counterfactual_groups=groups,max_same_state_difference_error_N_s=max(g['max_counterfactual_difference_error'] for g in groups),interpretation='At a fixed boundary, state/history/carry/count cancel in candidate differences. Fixed plan coefficients rank candidate vectors; issued mask changes active U components, feasible pool and actual residual realization depend on causal state, carry changes candidate identity. Existing control benefit remains valid; value ranking alone is not evidence of state-conditioned preference or learned personalization.',physics_attempts_added=0)
 save(STUDY/'Q_STRUCTURE_AUDIT.json',out);print(json.dumps({k:out[k] for k in ('status','state_times_plan_interactions','max_same_state_difference_error_N_s','physics_attempts_added')}))
if __name__=='__main__':main()
