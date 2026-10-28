"""Inference only. Reads a frozen model and present causal features, never outcomes."""
from pathlib import Path
import json,hashlib
import numpy as np
P=Path(__file__).resolve().parents[1]
def select(state):
    f=P/'models/Q_value_ridge.npz';identity=json.loads((P/'models/VALUE_FREEZE.json').read_text())
    assert hashlib.sha256(f.read_bytes()).hexdigest()==identity['model_sha256']
    z=np.load(f);x=np.asarray(state['features'],float)
    assert state['truth_used'] is False and state['future_matched_B_used'] is False
    assert x.shape==(7,) and np.all(np.isfinite(x))
    ds=np.r_[1.,(x-z['cost_mu'])/z['cost_sd']];delta=ds@z['cost_w']
    dm=np.r_[1.,(x-z['margin_mu'])/z['margin_sd']];margin=(dm@z['margin_w']).reshape(tuple(z['margin_shape']))
    distance=float(np.min(np.linalg.norm((z['train_x']-x)/z['cost_sd'],axis=1)))
    supported=distance<=float(z['support_radius'])
    eligible=np.all(margin-z['margin_error']>0,axis=1)
    useful=(-delta)>z['cost_error'];options=np.flatnonzero(eligible if not eligible[0] else eligible&useful)
    chosen=int(options[np.argmin(delta[options])]) if supported and len(options) else 0
    reason='outside_support_keep_reference' if not supported else 'no_robust_candidate_keep_reference' if not len(options) else 'predicted_qualification_recovery' if not eligible[0] else 'predicted_qualified_force_gain'
    return dict(selected=str(z['actions'][chosen]),selection_reason=reason,direct_Q_argmin=str(z['actions'][np.argmin(delta)]),predicted_delta_J_F_N_s=delta.tolist(),predicted_min_margin=margin.min(axis=1).tolist(),conservative_lower_min_margin=(margin-z['margin_error']).min(axis=1).tolist(),eligible=eligible.tolist(),force_improvement_confident=useful.tolist(),support_distance=distance,support_radius=float(z['support_radius']),supported=supported,model_sha256=identity['model_sha256'],state=state,uses_future_outcome=False,selection_timing='live RETURN2 boundary before posture modification')
