"""Polynomial extrema by all derivative roots, never a sampled certificate.

Floating point root arithmetic is software evidence, not a native safety proof.
roundoff is explicit algebra tolerance only, never clipping or a physical margin.
"""
from dataclasses import dataclass
from fractions import Fraction
import numpy as np
from numpy.polynomial import Polynomial as Poly
from phase_coordinates import State, Failure, Rejected

def extrema(poly):
    roots=poly.deriv().roots()
    pts=[0.,1.]+[float(r.real) for r in roots if np.isreal(r) and 0<r.real<1]
    vals=poly(pts)
    return float(np.min(vals)),float(np.max(vals))

def _trim(p):
    while len(p)>1 and p[-1]==0: p.pop()
    return p

def _remainder(a,b):
    a=_trim(list(a)); b=_trim(list(b))
    while len(a)>=len(b) and any(a):
        k=len(a)-len(b); c=a[-1]/b[-1]
        for j in range(len(b)): a[k+j]-=c*b[j]
        _trim(a)
    return a

def _eval(p,x):
    result=Fraction(0)
    for c in reversed(p): result=result*x+c
    return result

def rational_add(a,b):
    c=[Fraction(0)]*max(len(a),len(b))
    for i,x in enumerate(a): c[i]+=x
    for i,x in enumerate(b): c[i]+=x
    return _trim(c)

def rational_mul(a,b):
    c=[Fraction(0)]*(len(a)+len(b)-1)
    for i,x in enumerate(a):
        for j,y in enumerate(b): c[i+j]+=x*y
    return _trim(c)

def rational_compose(a,b):
    result=[Fraction(0)]
    for c in reversed(a): result=rational_add(rational_mul(result,b),[Fraction(c)])
    return result

def rational_integral(a): return [Fraction(0)]+[Fraction(x)/(i+1) for i,x in enumerate(a)]

def simultaneous_internal_zero(piece, endpoint_roundoff=0.):
    """Exact rational GCD + Sturm count for stored float coefficients.

    Distinguishes actual shared zero from arbitrarily small positive velocities;
    no velocity epsilon is introduced. Endpoints are handled by splice rules.
    """
    # Match the same floating differentiation used by sample(), then do exact
    # root counting. Multiplying rationalized integration coefficients first
    # would describe a different polynomial from the issued float derivative.
    if all(isinstance(c,Fraction) for row in piece.coefficients for c in row):
        a,b=[_trim([i*c for i,c in enumerate(row)][1:]) for row in piece.coefficients]
    else:
        a,b=[_trim([Fraction(float(c)) for c in p.deriv().coef]) for p in piece.positions]
    a=a or [Fraction(0)]; b=b or [Fraction(0)]
    if not any(a) and not any(b): return True
    while any(b): a,b=b,_remainder(a,b)
    g=[x/a[-1] for x in a]
    # Remove endpoint factors without changing the open-interval root set.
    while len(g)>1 and g[0]==0: g=g[1:]
    while len(g)>1 and sum(g)==0:
        q=[Fraction(0)]*(len(g)-1); q[-1]=g[-1]
        for i in range(len(q)-2,-1,-1): q[i]=g[i+1]+q[i+1]
        g=q
    if len(g)==1: return False
    chain=[g,[i*c for i,c in enumerate(g)][1:]]
    while any(chain[-1]):
        r=[-x for x in _remainder(chain[-2],chain[-1])]
        if not any(r): break
        chain.append(r)
    def changes(x):
        signs=[1 if v>0 else -1 for p in chain if (v:=_eval(p,x))!=0]
        return sum(a!=b for a,b in zip(signs,signs[1:]))
    # Endpoint localization tolerance is the caller's algebra roundoff, not a
    # minimum allowed velocity. Both full-interval kinematic bounds still apply.
    return changes(Fraction(endpoint_roundoff))-changes(Fraction(1-endpoint_roundoff))>0

@dataclass(frozen=True)
class Piece:
    """Two p polynomials in normalized time. All derivatives share time."""
    duration: float
    coefficients: tuple
    def __post_init__(self):
        if not np.isfinite(self.duration) or self.duration<=0: raise ValueError('positive duration')
        if len(self.coefficients)!=2: raise ValueError('two axes required')
        co=tuple(tuple(x if isinstance(x,Fraction) else float(x) for x in c) for c in self.coefficients)
        if not all(np.isfinite([float(x) for x in c]).all() for c in co): raise ValueError('finite coefficients')
        object.__setattr__(self,'coefficients',co)
    @property
    def positions(self): return tuple(Poly([float(x) for x in c]) for c in self.coefficients)
    def sample(self,t):
        if t<0 or t>self.duration: raise ValueError('time outside piece')
        s=t/self.duration
        return State([p(s) for p in self.positions],
                     [p.deriv()(s)/self.duration for p in self.positions],
                     [p.deriv(2)(s)/self.duration**2 for p in self.positions])
    def margins(self,phase,limits):
        result=[]
        for j,p in enumerate(self.positions):
            lo,hi=extrema(p); vl,vh=extrema(p.deriv()/self.duration)
            al,ah=extrema(p.deriv(2)/self.duration**2)
            ql,qh=extrema(phase.start[j]+phase.sign[j]*p)
            result.extend([lo,phase.length[j]-hi,vl,limits.velocity[j]-vh,
                           limits.acceleration[j]+al,limits.acceleration[j]-ah,
                           ql-limits.rom[j,0],limits.rom[j,1]-qh])
        return np.array(result)

def prefix(state,u,h):
    # Retain exact rational construction metadata so endpoint double roots do
    # not split into spurious interior roots when a plan is sliced repeatedly.
    H=Fraction(float(h)); co=[]
    for p,v,a,end in zip(state.p,state.v,state.a,u):
        p,v,a,end=map(lambda x:Fraction(float(x)),(p,v,a,end)); ha=H*a
        vel=[v,ha,3*(end-v)-2*ha,2*(v-end)+ha]
        co.append(tuple(rational_add([H*c for c in rational_integral(vel)],[p])))
    return Piece(h,tuple(co))

@dataclass(frozen=True)
class Plan:
    pieces: tuple
    @property
    def duration(self): return sum(p.duration for p in self.pieces)
    def sample(self,t):
        if t<0: raise ValueError('negative physical time')
        for p in self.pieces:
            if t<=p.duration: return p.sample(t)
            t-=p.duration
        # Explicit endpoint hold, never trajectory clipping before completion.
        return self.pieces[-1].sample(self.pieces[-1].duration)
    def suffix(self,t):
        if t<0 or t>=self.duration: raise ValueError('suffix outside active plan')
        pieces=[]
        for p in self.pieces:
            if t>=p.duration: t-=p.duration; continue
            d=p.duration-t
            H=Fraction(p.duration); transform=[Fraction(t)/H,Fraction(d)/H]
            pieces.append(Piece(d,tuple(tuple(rational_compose(q,transform)) for q in p.coefficients)))
            t=0.
        return Plan(tuple(pieces))

def certify(plan,phase,limits,roundoff):
    """Kinematics only; geometry/current state/escape remain separate native work."""
    minimum=float('inf')
    previous=None
    for piece in plan.pieces:
        minimum=min(minimum,float(np.min(piece.margins(phase,limits))))
        if simultaneous_internal_zero(piece,roundoff):
            # Constant joint hold is allowed only after both endpoints.
            at_goal=all(len(p.coef)==1 and abs(p(0)-L)<=roundoff
                        for p,L in zip(piece.positions,phase.length))
            if not at_goal:
                raise Rejected(Failure.FAMILY,'simultaneous internal velocity zero')
        if previous is not None:
            start=piece.sample(0)
            if any(np.max(np.abs(getattr(start,k)-getattr(previous,k)))>roundoff for k in ('p','v','a')):
                raise Rejected(Failure.FAMILY,'non-C2 splice')
            if np.any(phase.length-previous.p>roundoff) and np.all(np.abs(previous.v)<=roundoff):
                # Algebraic normal-trajectory restriction; not a minimum speed.
                # Use exact polynomial endpoint derivatives for zero, below.
                if all(x==0 for x in previous.v):
                    raise Rejected(Failure.FAMILY,'internal joint rest followed by restart')
        previous=piece.sample(piece.duration)
    if minimum < -roundoff: raise Rejected(Failure.FAMILY,f'polynomial bound margin {minimum}')
    if np.max(np.abs(previous.p-phase.length))>roundoff or np.max(np.abs(previous.v))>roundoff or np.max(np.abs(previous.a))>roundoff:
        raise Rejected(Failure.FAMILY,'completion must reach both endpoints at rest')
    return {'minimum_kinematic_margin':minimum,'native_certificate':False}

def necessary_conditions(state,phase,limits):
    D=phase.length-state.p
    if np.any(D<0) or np.any(state.p<0) or np.any(state.v<0):
        raise Rejected(Failure.NECESSARY,'outside monotone phase domain')
    if np.any(state.v>limits.velocity) or np.any(np.abs(state.a)>limits.acceleration):
        raise Rejected(Failure.NECESSARY,'initial derivative already violates limits')
    if np.any((state.v==0)&(state.a<0)):
        raise Rejected(Failure.NECESSARY,'negative initial acceleration at zero speed')
    if np.any(state.v**2/(2*limits.acceleration)>D):
        raise Rejected(Failure.NECESSARY,'remaining distance below v^2/(2 a_max)')
