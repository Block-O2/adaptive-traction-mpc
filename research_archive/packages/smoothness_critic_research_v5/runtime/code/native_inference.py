"""Tiny frozen numpy MLP inference, avoiding CUDA/torch in physics owners."""
from study_common import *
class Networks:
 def __init__(self,path):
  with np.load(Path(path)/'weights.npz') as z:self.w={k:z[k].copy() for k in z.files}
  self.meta=json.loads((Path(path)/'TRAINING.json').read_text());self.Q_calls=0;self.G_calls=0
 def scale(self,x):return (np.asarray(x,np.float32)-self.w['x_mean'])/self.w['x_scale']
 def mlp(self,x,prefix):
  h=self.scale(x)
  for i in range(3):
   h=h@self.w[prefix+'_W'+str(i)].T+self.w[prefix+'_b'+str(i)]
   if i<2:h=np.maximum(h,0)
  return h
 def values(self,x):
  self.Q_calls+=len(x)
  if self.meta['selected_Q']=='linear':y=self.scale(x)@self.w['linear_W']+self.w['linear_b']
  else:y=self.mlp(x,'Q').reshape(-1)
  return y*self.w['y_scale']+self.w['y_mean']
 def proposals(self,x):
  self.G_calls+=1;return np.tanh(self.mlp(np.asarray(x)[None],'G')).reshape(3,2,5,3)
