"""Frozen earlier selector. No results, truth or future-outcome reads."""
from pathlib import Path
import json,hashlib
import numpy as np
P=Path(__file__).resolve().parents[1]
def select(state):
    f=P/'models/early_value_ridge.npz';freeze=json.loads((P/'models/EARLY_VALUE_FREEZE.json').read_text());assert hashlib.sha256(f.read_bytes()).hexdigest()==freeze['model_sha256']
    z=np.load(f);x=np.array(state['features']);assert x.shape==(10,) and not state['truth_used'] and not state['future_outcomes_used']
    d=np.r_[1.,(x-z['mu'])/z['sd']]@z['cost_w'];m=(np.r_[1.,(x-z['margin_mu'])/z['margin_sd']]@z['margin_w']).reshape(tuple(z['margin_shape']))
    eligible=np.all(m-z['margin_error']>0,axis=1);distance=float(np.min(np.linalg.norm((z['train_x']-x)/z['sd'],axis=1)));supported=distance<=float(z['support_radius']);useful=(-d)>z['cost_error'];opts=np.flatnonzero(eligible&useful)
    a=int(opts[np.argmin(d[opts])]) if supported and len(opts) else 0
    return dict(selected=str(z['actions'][a]),direct_force_argmin=str(z['actions'][np.argmin(d)]),delta_cost_vs_B_N_s=d.tolist(),conservative_lower_min_margin=(m-z['margin_error']).min(1).tolist(),eligible=eligible.tolist(),supported=supported,distance=distance,support_radius=float(z['support_radius']),model_sha256=freeze['model_sha256'],state=state,selection_reason='predicted_qualified_force_gain_vs_B' if a else 'B_reference_fallback',future_outcomes_used=False)
