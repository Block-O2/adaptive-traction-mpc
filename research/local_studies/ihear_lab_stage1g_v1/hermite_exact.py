"""Exact Hermite boundary diagnostic; never rewrites an issued reference state."""
from fractions import Fraction as F
def quintic(q0,v0,a0,q1,v1,a1,T):
    q0,v0,a0,q1,v1,a1,T=map(lambda x:F(float(x)),(q0,v0,a0,q1,v1,a1,T))
    c0,c1,c2=q0,T*v0,T*T*a0/2
    A=q1-c0-c1-c2;B=T*v1-c1-2*c2;C=T*T*a1-2*c2
    return (c0,c1,c2,10*A-4*B+C/2,-15*A+7*B-C,6*A-3*B+C/2)
def evaluate(c,T,s,derivative=0):
    c=list(c)
    for _ in range(derivative):c=[i*x for i,x in enumerate(c)][1:]
    val=F(0);s=F(s)
    for x in reversed(c):val=val*s+x
    return val/F(float(T))**derivative
