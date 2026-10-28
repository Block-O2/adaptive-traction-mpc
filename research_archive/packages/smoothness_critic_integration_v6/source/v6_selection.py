"""Frozen causal menu decisions; outcome labels cannot enter this API."""
from v6_model import predict_cost,causal_inputs
from v6_observed_risk import predict as predict_risk
from v6_eligibility import predict as predict_eligibility

def select(bundle,rows,known_original_failure=False):
 if known_original_failure:
  return dict(choice=None,rows=[],reason="ORIGINAL_CONTRACT_FAILURE_ABSORBING",future_qualification_mask_used=False,original_full_gate_is_final=True)
 pred=[]
 for row in rows:
  inputs=causal_inputs(row)
  if 'history_risk_features' in row:inputs['history_risk_features']=row['history_risk_features']
  p=predict_cost(bundle['cost'],inputs);rp=predict_risk(bundle['risk'],inputs);fp=predict_eligibility(bundle.get('eligibility',{}),inputs);p.update(tag=inputs['tag'],risk=rp,eligibility_risk=fp,short_JF=row['short_JF'],score=row['short_JF']+p['mean'][bundle['score_index']]);pred.append(p)
 allowed=[p for p in pred if p['distance']<=bundle['ood_distance_limit'] and (p['risk'] is None or p['risk']<.5) and (p['eligibility_risk'] is None or p['eligibility_risk']<.5)]
 choice=min(allowed,key=lambda r:r['score'])['tag'] if allowed else None
 return dict(choice=choice,unrestricted_cost_choice=min(pred,key=lambda r:r['score'])['tag'],rows=pred,reason='RISK_DOMAIN_SCREEN_THEN_COST' if allowed else 'ABSTAIN_NO_SUPPORTED_QUALIFIED_CONTINUATION',future_qualification_mask_used=False,original_full_gate_is_final=True)
