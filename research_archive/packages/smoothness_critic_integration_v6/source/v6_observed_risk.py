"""Risk of an already occurred irreversible motion-condition violation."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from v6_observed_history import NAMES,FLOORS
from v6_model import predict_risk as legacy_predict

def fit(rows):
 X=np.array([r['features'] for r in rows]);y=np.array([r['already_irreversible_failure'] for r in rows],float)
 if not (y.any() and (1-y).any()):return dict(available=False,reason='INSUFFICIENT_INDEPENDENT_FAILURE_CLASS_SUPPORT')
 xc=X.mean(0);xs=np.maximum(X.std(0),FLOORS);Z=(X-xc)/xs;A=np.c_[np.ones(len(Z)),Z]
 # Equal parent-family mass, then equal class mass; aliased runs cannot create extra independent weight.
 gs=[r['state_family'] for r in rows];base=np.array([1/sum(g==x for x in gs) for g in gs]);weights=base*np.where(y==1,.5/base[y==1].sum(),.5/base[y==0].sum());weights*=len(y)
 def obj(w):
  z=A@w;reg=w.copy();reg[0]=0.;return float(np.mean(weights*(np.logaddexp(0,z)-y*z))+.05*(reg@reg)),A.T@(weights*(expit(z)-y))/len(y)+.1*reg
 out=minimize(obj,np.zeros(A.shape[1]),jac=True,method='L-BFGS-B',options={'maxiter':500,'ftol':1e-12})
 return dict(available=True,schema='v6.full_observed_history_irreversible_risk.v2',feature_names=NAMES,x_center=xc.tolist(),x_scale=xs.tolist(),weights=out.x.tolist(),train_ids=[r['id'] for r in rows],train_state_families=sorted(set(gs)),positive_state_families=sorted(set(r['state_family'] for r in rows if r['already_irreversible_failure'])),converged=bool(out.success),threshold=.5,scope='uncalibrated prediction of already occurred irreversible native peak/excursion/travel/JM condition from whole-task causal observer and measured-wrench history; no future continuation labels')
def predict(model,inputs):
 if model.get('schema')!='v6.full_observed_history_irreversible_risk.v2':return legacy_predict(model,inputs)
 if not model.get('available'):return None
 z=(np.array(inputs['history_risk_features'])-model['x_center'])/model['x_scale'];w=np.array(model['weights']);return float(expit(w[0]+z@w[1:]))
