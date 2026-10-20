"""Finite-action Monte Carlo cost regression, with explicit state-action interaction."""
import numpy as np
def fit(x,y,alpha):
    mu=x.mean(0);sd=np.maximum(x.std(0),1e-7);z=np.c_[np.ones(len(x)),(x-mu)/sd]
    reg=np.eye(z.shape[1]);reg[0,0]=0
    w=np.linalg.solve(z.T@z+alpha*reg,z.T@y.reshape(len(x),-1))
    return dict(mu=mu,sd=sd,w=w,shape=y.shape[1:])
def predict(m,x):
    x=np.atleast_2d(x);z=np.c_[np.ones(len(x)),(x-m['mu'])/m['sd']]
    return (z@m['w']).reshape((len(x),*m['shape']))
def choose(delta,margin,cost_error,margin_error):
    eligible=np.all(margin-margin_error>0,axis=1)
    improvement=(-delta)>cost_error
    # Qualification recovery has priority when H150 lacks a positive lower
    # margin. This is a prediction, never a guarantee of actual motion.
    options=np.flatnonzero(eligible if not eligible[0] else eligible&improvement)
    return int(options[np.argmin(delta[options])]) if len(options) else 0
