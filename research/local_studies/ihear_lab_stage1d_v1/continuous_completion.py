"""Continuous Bernstein completion witness, separate from safety stopping.

Uses b=[u,u,c,c,0,0], c=3D/T-u. Each axis may finish earlier;
the other continues. Convex-hull derivative bounds give constructive T.
Failure is only failure of this sufficient construction, not physical impossibility.
"""
from math import comb, sqrt
from fractions import Fraction
import numpy as np
from numpy.polynomial import Polynomial as Poly
from phase_coordinates import Failure, Rejected, State
from reference_kernel import (Piece, Plan, prefix, certify, necessary_conditions,
                              rational_add,rational_mul,rational_compose,rational_integral)

def bernstein(b):
    out=[Fraction(0)]
    n=len(b)-1
    for k,x in enumerate(b):
        term=[Fraction(0)]*k+[Fraction(x)*comb(n,k)]
        for _ in range(n-k): term=rational_mul(term,[Fraction(1),Fraction(-1)])
        out=rational_add(out,term)
    return out

def axis_tail(D,u,vmax,amax):
    if D<0 or u<0: raise Rejected(Failure.FAMILY,'prefix overshoot or negative terminal speed')
    if D==0:
        if u!=0: raise Rejected(Failure.NECESSARY,'nonzero speed at endpoint')
        return 0.,(Fraction(0),),(0.,)*6
    # c<=vmax and 5*c/T<=amax. Stable positive quadratic root.
    T=max(3*D/(vmax+u),30*D/(sqrt(25*u*u+60*amax*D)+5*u))
    disc=100*u*u-60*amax*D
    if disc>0:
        low=30*D/(10*u+sqrt(disc)); high=(10*u+sqrt(disc))/(2*amax)
        if low<T<high: T=high
    if u>0 and T>3*D/u:
        raise Rejected(Failure.FAMILY,'symmetric Bernstein hull construction has no certified T')
    c=3*Fraction(float(D))/Fraction(float(T))-Fraction(float(u))
    if c<0: raise Rejected(Failure.FAMILY,'negative Bernstein interior coefficient')
    b=(Fraction(float(u)),Fraction(float(u)),c,c,Fraction(0),Fraction(0))
    return T,tuple(Fraction(float(T))*x for x in rational_integral(bernstein(b))),b

def completion(state,phase,limits,roundoff):
    if np.any(state.a!=0): raise Rejected(Failure.FAMILY,'tail requires algebraic a=0')
    data=[axis_tail(D,u,v,a) for D,u,v,a in zip(phase.length-state.p,state.v,limits.velocity,limits.acceleration)]
    ends=sorted(set(T for T,_,_ in data if T>0))
    pieces=[]; start=0.
    for end in ends:
        co=[]
        for j,(T,p,_) in enumerate(data):
            if T<=start: q=[Fraction(float(phase.length[j]))]
            else:
                transform=[Fraction(start)/Fraction(T),Fraction(end-start)/Fraction(T)]
                q=rational_add([Fraction(float(state.p[j]))],rational_compose(p,transform))
            co.append(tuple(q))
        pieces.append(Piece(end-start,tuple(co))); start=end
    return tuple(pieces),[dict(T=T,b=[float(x) for x in b]) for T,_,b in data]

def make_plan(state,u,h,phase,limits,roundoff):
    necessary_conditions(state,phase,limits)
    u=np.asarray(u,dtype=float)
    if u.shape!=(2,) or np.any(u<0): raise Rejected(Failure.FAMILY,'nonnegative two-vector u required')
    first=prefix(state,u,h)
    if np.min(first.margins(phase,limits)) < -roundoff:
        raise Rejected(Failure.FAMILY,'prefix fails analytic kinematic bounds')
    # Analytic endpoints avoid cancellation masquerading as a different boundary.
    p=state.p+h*(state.v+u)/2+h*h*state.a/12
    end=State(p,u,[0.,0.])
    if np.any(p>phase.length): raise Rejected(Failure.FAMILY,'prefix crosses exact goal')
    if np.any(p<phase.length) and np.all(u==0):
        raise Rejected(Failure.FAMILY,'unfinished internal dual-zero stop/restart')
    tail,meta=completion(end,phase,limits,roundoff)
    plan=Plan((first,)+tail)
    certificate=certify(plan,phase,limits,roundoff)
    return plan,dict(certificate=certificate,tail=meta)
