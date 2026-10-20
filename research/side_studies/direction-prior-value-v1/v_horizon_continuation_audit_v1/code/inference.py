"""NumPy CPU inference only; safe in quiescent CPU fork parents."""
from pathlib import Path
import numpy as np,time
class Networks:
 def __init__(self,path):
  p=Path(path);self.weights={}
  with np.load(p,allow_pickle=False) as z:
   for name in z.files:self.weights[name]=z[name].copy()
  self.inference_s=0.;self.calls=0
 def _mlp(self,kind,x):
  w=self.weights;y=(np.asarray(x)-w[kind+'_mean'])/w[kind+'_scale']
  for i in range(3):
   y=y@w[kind+f'_W{i}'].T+w[kind+f'_b{i}']
   if i<2:y=np.maximum(y,0.)
  return y
 def proposals(self,x):
  t=time.monotonic();y=np.tanh(self._mlp('G',x)).reshape(3,30);self.inference_s+=time.monotonic()-t;self.calls+=1;return y
 def value(self,x):
  t=time.monotonic();w=self.weights
  if int(w['V_type'])==0:y=self._mlp('V',x).item()*float(w['V_target_scale'])+float(w['V_target_mean'])
  else:y=((np.r_[1.,(x-w['V_mean'])/w['V_scale']]@w['V_linear'])*float(w['V_target_scale'])+float(w['V_target_mean'])).item()
  self.inference_s+=time.monotonic()-t;self.calls+=1;return float(y)
