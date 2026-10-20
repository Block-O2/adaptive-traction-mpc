"""Read-only NumPy scorer. No native-controller imports, adaptation or actuation."""
from pathlib import Path
import numpy as np
class NeuralQ:
 def __init__(self,path):
  with np.load(Path(path),allow_pickle=False) as f:self.w={k:f[k].copy() for k in f.files}
 def score(self,x):
  x=np.asarray(x,dtype=np.float32)
  if x.ndim!=2 or x.shape[1]!=120 or not np.isfinite(x).all():raise ValueError('Expected finite Nx120 native features')
  h=(x-self.w['x_mean'])/self.w['x_scale']
  for i in range(3):
   h=h@self.w[f'Q_W{i}'].T+self.w[f'Q_b{i}']
   if i<2:h=np.maximum(h,0)
  y=h[:,0]*float(self.w['y_scale'])+float(self.w['y_mean'])
  if not np.isfinite(y).all():raise ValueError('Nonfinite Q output')
  return y
