import numpy as np
def visible_y_limits(ax):
 lo,hi=ax.get_xlim();ys=[]
 for line in ax.lines:
  x=np.asarray(line.get_xdata(),dtype=float);y=np.asarray(line.get_ydata(),dtype=float)
  if len(x)!=len(y):continue
  keep=(x>=lo)&(x<=hi)&np.isfinite(y)
  if keep.any():ys.extend(y[keep].tolist())
 if not ys:return
 mn,mx=min(ys),max(ys);pad=max((mx-mn)*.07,abs(mx)*.002,1e-8);ax.set_ylim(mn-pad,mx+pad)
