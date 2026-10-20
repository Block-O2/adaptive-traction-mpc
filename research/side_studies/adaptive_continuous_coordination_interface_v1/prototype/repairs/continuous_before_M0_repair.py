"""Local C2 quintic state interpolation and exact refinement. No actuation."""
from dataclasses import dataclass
from math import comb
import numpy as np
from scipy.interpolate import BSpline

def coefficients(q0,v0,a0,q1,v1,a1,T):
 q0,v0,a0,q1,v1,a1=[np.asarray(x,float) for x in [q0,v0,a0,q1,v1,a1]]
 if T<=0 or not np.isfinite(T):raise ValueError('positive finite duration')
 c=np.zeros((2,6));c[:,0]=q0;c[:,1]=T*v0;c[:,2]=.5*T*T*a0
 rhs=np.column_stack([q1-c[:,:3].sum(axis=1),T*v1-c[:,1]-2*c[:,2],T*T*a1-2*c[:,2]])
 c[:,3:]=np.linalg.solve(np.array([[1.,1,1],[3,4,5],[6,12,20]]),rhs.T).T
 return c

@dataclass
class Piece:
 c:np.ndarray
 T:float
 def evaluate(self,t,der=0):
  x=np.asarray(t,float)/self.T
  if np.any(x< -1e-12) or np.any(x>1+1e-12):raise ValueError('outside piece')
  c=np.asarray(self.c,float).copy()
  for _ in range(der):c=c[:,1:]*np.arange(1,c.shape[1])[None,:]/self.T
  return np.polynomial.polynomial.polyval(x,c.T).T
 def subpiece(self,lo,hi):
  # Exact affine change of normalized monomial variable, no fitting.
  if not 0<=lo<hi<=self.T:raise ValueError('invalid refinement interval')
  u=lo/self.T;h=(hi-lo)/self.T;c=np.zeros_like(self.c)
  for k in range(6):
   for j in range(k+1):c[:,j]+=self.c[:,k]*comb(k,j)*u**(k-j)*h**j
  return Piece(c,hi-lo)
 def bspline(self):
  b=np.zeros_like(self.c)
  for i in range(6):
   for k in range(i+1):b[:,i]+=self.c[:,k]*comb(i,k)/comb(5,k)
  return BSpline(np.r_[np.zeros(6),np.full(6,self.T)],b.T,5,extrapolate=False)

class LocalQuintic:
 def __init__(self,knots,q,v,a):
  self.knots=np.asarray(knots,float);self.q=np.asarray(q,float);self.v=np.asarray(v,float);self.a=np.asarray(a,float)
  if len(self.knots)<2 or np.any(np.diff(self.knots)<=0):raise ValueError('increasing knots')
  if any(x.shape!=(len(self.knots),2) or not np.all(np.isfinite(x)) for x in [self.q,self.v,self.a]):raise ValueError('finite Nx2 states')
  self.pieces=[Piece(coefficients(*[x[i] for x in [self.q,self.v,self.a]],*[x[i+1] for x in [self.q,self.v,self.a]],T),T) for i,T in enumerate(np.diff(self.knots))]
 @classmethod
 def from_piece(cls,piece,insertions=()):
  t=np.r_[0,sorted(insertions),piece.T];q=piece.evaluate(t,0);v=piece.evaluate(t,1);a=piece.evaluate(t,2)
  o=cls(t,q,v,a)
  o.pieces=[piece.subpiece(float(lo),float(hi)) for lo,hi in zip(t,t[1:])]
  return o
 def evaluate(self,t,der=0):
  t=np.asarray(t,float);flat=t.ravel();out=np.zeros((len(flat),2))
  if np.any(flat<self.knots[0]-1e-12) or np.any(flat>self.knots[-1]+1e-12):raise ValueError('outside schedule')
  indices=np.clip(np.searchsorted(self.knots,flat,side='right')-1,0,len(self.pieces)-1)
  for i,p in enumerate(self.pieces):
   use=indices==i;out[use]=p.evaluate(flat[use]-self.knots[i],der)
  return out.reshape(t.shape+(2,))
 def update(self,index,*,dq=None,dv=None,da=None):
  if index<=0 or index>=len(self.knots)-1:raise ValueError('task anchors immutable')
  q,v,a=self.q.copy(),self.v.copy(),self.a.copy()
  for x,d in [(q,dq),(v,dv),(a,da)]:
   if d is not None:x[index]+=d
  return LocalQuintic(self.knots,q,v,a)
 def record(self):return dict(representation='local_C2_quintic_states_v1',knots_s=self.knots.tolist(),q_rad=self.q.tolist(),v_rad_s=self.v.tolist(),a_rad_s2=self.a.tolist(),normalized_coefficients=[p.c.tolist() for p in self.pieces])
 def collapse_original(self,original,tol=1e-11):
  # Fail closed: preserve original object only if all restrictions match its
  # coefficients. Changed inner controls cannot be hidden behind old proof.
  errors=[np.max(abs(p.c-original.subpiece(float(lo),float(hi)).c)) for p,lo,hi in zip(self.pieces,self.knots,self.knots[1:])]
  if max(errors)>tol:raise ValueError('NONCOLLAPSIBLE_PIECEWISE_REFERENCE_REQUIRES_FULL_PATH_CERTIFICATE')
  return original

class LocalTimeWarp:
 def __init__(self,curve,lo,hi,amplitude):
  self.curve,self.lo,self.hi,self.amp=curve,float(lo),float(hi),float(amplitude)
  if hi<=lo or abs(amplitude)>.05*(hi-lo):raise ValueError('bounded local time allocation')
  # Polynomial derivative bound checked at all real critical points.
  self.b=np.array([0.,0,0,64,-192,192,-64])
  db=np.polynomial.polynomial.polyder(self.b);ddb=np.polynomial.polynomial.polyder(db)
  roots=np.polynomial.polynomial.polyroots(ddb);u=np.r_[0.,1.,[r.real for r in roots if abs(r.imag)<1e-10 and 0<r.real<1]]
  self.minimum_rate=float(np.min(1+self.amp/(hi-lo)*np.polynomial.polynomial.polyval(u,db)))
  if self.minimum_rate<=0:raise ValueError('nonmonotone time map')
 def mapping(self,t):
  t=np.asarray(t,float);u=(t-self.lo)/(self.hi-self.lo);inside=(u>=0)&(u<=1);uc=np.clip(u,0,1)
  g=lambda d:np.where(inside,np.polynomial.polynomial.polyval(uc,np.polynomial.polynomial.polyder(self.b,d)),0.)
  T=self.hi-self.lo;return t+self.amp*g(0),1+self.amp/T*g(1),self.amp/T**2*g(2)
 def evaluate(self,t,der=0):
  u,rate,acc=self.mapping(t)
  if der==0:return self.curve.evaluate(u,0)
  if der==1:return self.curve.evaluate(u,1)*rate[...,None]
  if der==2:return self.curve.evaluate(u,2)*rate[...,None]**2+self.curve.evaluate(u,1)*acc[...,None]
  raise ValueError('q/dq/ddq interface only')
