"""Separate full-qualification risk head; no low-cost substitution for raw gates."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from v6_model import floors

def fit(rows):
 y=np.array([not r['qualified'] for r in rows],float)
 if not (y.any() and (1-y).any()):return dict(available=False,reason='no observed full-qualification class contrast in this continuation-policy training set',positive_ids=[r['id'] for r in rows if not r['qualified']])
 names=rows[0]['feature_names'];X=np.array([r['features'] for r in rows]);xc=X.mean(0);xs=np.maximum(X.std(0),floors(names));Z=(X-xc)/xs;A=np.c_[np.ones(len(X)),Z];weights=np.where(y==1,.5/y.mean(),.5/(1-y.mean()))
 def objective(w):
  z=A@w;reg=w.copy();reg[0]=0.;return float(np.mean(weights*(np.logaddexp(0,z)-y*z))+.1*(reg@reg)),A.T@(weights*(expit(z)-y))/len(y)+.2*reg
 o=minimize(objective,np.zeros(A.shape[1]),jac=True,method='L-BFGS-B',options={'maxiter':500,'ftol':1e-12})
 return dict(available=True,feature_names=names,x_center=xc.tolist(),x_scale=xs.tolist(),weights=o.x.tolist(),train_ids=[r['id'] for r in rows],positive_ids=[r['id'] for r in rows if not r['qualified']],converged=bool(o.success),scope='uncalibrated whole-task eligibility risk under common COMPOSE; original full gate remains authoritative')
def predict(model,inputs):
 if not model.get('available'):return None
 lookup=dict(zip(inputs['feature_names'],inputs['features']));z=(np.array([lookup[n] for n in model['feature_names']])-model['x_center'])/model['x_scale'];w=np.array(model['weights']);return float(expit(w[0]+z@w[1:]))
