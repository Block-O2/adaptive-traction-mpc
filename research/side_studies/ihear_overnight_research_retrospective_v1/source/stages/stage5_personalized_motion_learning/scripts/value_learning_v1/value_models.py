"""Small NumPy-only scaled cost-to-go estimators; immutable NPZ versions."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib, json, time
import numpy as np

@dataclass(frozen=True)
class ValueModel:
 kind:str
 mean:np.ndarray
 scale:np.ndarray
 y_mean:float
 y_scale:float
 weights:tuple
 interaction_state_indices:np.ndarray
 interaction_action_indices:np.ndarray
 metadata:dict

 def design(self,X):
  z=(np.asarray(X,float)-self.mean)/self.scale
  if self.kind=='ridge' and len(self.interaction_state_indices):
   interactions=(z[:,self.interaction_state_indices,None]*z[:,None,self.interaction_action_indices]).reshape(len(z),-1)
   z=np.c_[z,interactions]
  return z
 def predict(self,X):
  z=self.design(X)
  if self.kind=='ridge':y=z@self.weights[0]+self.weights[1]
  else:
   w1,b1,w2,b2,w3,b3=self.weights
   y=np.tanh(np.tanh(z@w1+b1)@w2+b2)@w3+b3
  output=np.asarray(y).reshape(-1)*self.y_scale+self.y_mean
  if not np.all(np.isfinite(output)):raise ValueError('nonfinite value output')
  return output

def scales(X,y):
 mean=np.mean(X,axis=0);scale=np.std(X,axis=0);scale=np.where(scale<1e-6,1.,scale)
 return mean,scale,float(np.mean(y)),max(float(np.std(y)),1.)

def fit_ridge(X,y,*,alpha=1.,feature_names=None,metadata=None):
 X=np.asarray(X,float);y=np.asarray(y,float);mean,scale,ym,ys=scales(X,y)
 names=feature_names or []
 si=np.array([i for i,n in enumerate(names) if n.startswith(('progress_','remaining_span_','beta_','goal_','start_','phase_'))],int)
 ai=np.array([i for i,n in enumerate(names) if n.startswith('candidate_delta_')],int)
 tmp=ValueModel('ridge',mean,scale,ym,ys,(),si,ai,metadata or {})
 z=tmp.design(X);design=np.c_[z,np.ones(len(z))]
 penalty=np.eye(design.shape[1])*alpha;penalty[-1,-1]=0.
 w=np.linalg.solve(design.T@design+penalty,design.T@((y-ym)/ys))
 return ValueModel('ridge',mean,scale,ym,ys,(w[:-1],np.array(w[-1])),si,ai,{**(metadata or {}),'regularization_alpha':alpha,'feature_design':'scaled linear plus interpretable progress/span/beta/phase x action delta interactions'})

def fit_mlp(X,y,*,validation=None,seed=20260930,epochs=500,learning_rate=.003,weight_decay=.001,metadata=None):
 X=np.asarray(X,float);y=np.asarray(y,float);mean,scale,ym,ys=scales(X,y)
 z=(X-mean)/scale;target=((y-ym)/ys)[:,None]
 rng=np.random.default_rng(seed);n=X.shape[1]
 weights=[rng.normal(0,np.sqrt(2/(n+32)),size=(n,32)),np.zeros(32),rng.normal(0,np.sqrt(1/32),size=(32,32)),np.zeros(32),rng.normal(0,np.sqrt(1/32),size=(32,1)),np.zeros(1)]
 adam_m=[np.zeros_like(w) for w in weights];adam_v=[np.zeros_like(w) for w in weights]
 if validation:
  xv,yv=validation;zv=(xv-mean)/scale;yv=(yv-ym)/ys
 else:zv=z;yv=target[:,0]
 best=None;best_loss=float('inf');patience=0;steps=0;history=[]
 def forward(a):
  h1=np.tanh(a@weights[0]+weights[1]);h2=np.tanh(h1@weights[2]+weights[3]);out=h2@weights[4]+weights[5]
  return h1,h2,out
 for epoch in range(epochs):
  permutation=rng.permutation(len(z))
  for begin in range(0,len(z),256):
   idx=permutation[begin:begin+256];a=z[idx];t=target[idx];h1,h2,out=forward(a)
   d=2*(out-t)/len(idx);g4=h2.T@d+weight_decay*weights[4];g5=np.sum(d,axis=0)
   d2=(d@weights[4].T)*(1-h2*h2);g2=h1.T@d2+weight_decay*weights[2];g3=np.sum(d2,axis=0)
   d1=(d2@weights[2].T)*(1-h1*h1);g0=a.T@d1+weight_decay*weights[0];g1=np.sum(d1,axis=0)
   steps+=1
   for j,g in enumerate([g0,g1,g2,g3,g4,g5]):
    adam_m[j]=.9*adam_m[j]+.1*g;adam_v[j]=.999*adam_v[j]+.001*g*g
    weights[j]-=learning_rate*(adam_m[j]/(1-.9**steps))/(np.sqrt(adam_v[j]/(1-.999**steps))+1e-8)
  loss=float(np.mean((forward(zv)[2][:,0]-yv)**2));history.append(loss)
  if loss<best_loss-1e-7:best_loss=loss;best=[w.copy() for w in weights];patience=0
  else:patience+=1
  if patience>=50:break
 return ValueModel('mlp',mean,scale,ym,ys,tuple(best),np.array([],int),np.array([],int),{**(metadata or {}),'seed':seed,'epochs_completed':epoch+1,'hidden_units':[32,32],'activation':'tanh','validation_scaled_MSE':best_loss,'training_history_validation_loss':history,'parameter_count':sum(w.size for w in best),'weight_decay':weight_decay})

def save_model(path,model):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():raise FileExistsError('immutable model already exists:'+str(path))
 data={'kind':np.array(model.kind),'mean':model.mean,'scale':model.scale,'y_mean':np.array(model.y_mean),'y_scale':np.array(model.y_scale),'state_indices':model.interaction_state_indices,'action_indices':model.interaction_action_indices,'metadata':np.array(json.dumps(model.metadata,sort_keys=True))}
 data.update({f'w{i}':w for i,w in enumerate(model.weights)})
 np.savez_compressed(path,**data)
 return hashlib.sha256(path.read_bytes()).hexdigest()
def load_model(path):
 with np.load(path,allow_pickle=False) as f:
  kind=str(f['kind']);count=2 if kind=='ridge' else 6
  return ValueModel(kind,f['mean'].copy(),f['scale'].copy(),float(f['y_mean']),float(f['y_scale']),tuple(f[f'w{i}'].copy() for i in range(count)),f['state_indices'].copy(),f['action_indices'].copy(),json.loads(str(f['metadata'])))

class ValidatedModelSlot:
 """Reference research model handoff. Active objects never train in place."""
 def __init__(self,path=None):self.active_path=path;self.active_version='ZERO' if path is None else hashlib.sha256(Path(path).read_bytes()).hexdigest();self.pending=None
 def propose(self,path,X_sanity):
  model=load_model(path);values=model.predict(X_sanity)
  if not np.all(np.isfinite(values)) or np.max(np.abs(values))>1e6:raise ValueError('model sanity validation failed')
  self.pending=(str(path),hashlib.sha256(Path(path).read_bytes()).hexdigest())
 def switch(self,*,at_safe_repetition_boundary):
  if not at_safe_repetition_boundary:raise RuntimeError('model switch prohibited within active repetition')
  if self.pending:self.active_path,self.active_version=self.pending;self.pending=None
  return self.active_path,self.active_version
