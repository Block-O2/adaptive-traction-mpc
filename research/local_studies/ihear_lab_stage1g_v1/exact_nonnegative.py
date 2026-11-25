"""Exact rational univariate nonnegativity on a closed rational interval.

Square-free multiplicities plus Sturm root counts, without root approximation.
Any odd-multiplicity interior root changes sign. Even roots preserve sign.
Endpoints and a nonroot rational probe determine the remaining constant sign.
"""
from fractions import Fraction as F

def trim(p):
    p=[F(x) for x in p]
    while len(p)>1 and p[-1]==0:p.pop()
    return p or [F(0)]

def value(p,x):
    y=F(0)
    for c in reversed(p):y=y*x+c
    return y

def derivative(p):return trim([i*p[i] for i in range(1,len(p))])

def divmod_poly(a,b):
    a=trim(a);b=trim(b)
    if b==[0]:raise ZeroDivisionError('zero polynomial divisor')
    q=[F(0)]*max(1,len(a)-len(b)+1)
    while a!=[0] and len(a)>=len(b):
        k=len(a)-len(b);c=a[-1]/b[-1];q[k]+=c
        for j,x in enumerate(b):a[k+j]-=c*x
        a=trim(a)
    return trim(q),a

def divide(a,b):
    q,r=divmod_poly(a,b)
    if r!=[0]:raise ArithmeticError('inexact polynomial division')
    return q

def monic(p):
    p=trim(p)
    return [x/p[-1] for x in p] if p!=[0] else p

def gcd(a,b):
    a=trim(a);b=trim(b)
    while b!=[0]:a,b=b,divmod_poly(a,b)[1]
    return monic(a)

def square_free_factors(p):
    p=monic(p);g=gcd(p,derivative(p));w=divide(p,g);i=1;result=[]
    while len(w)>1:
        y=gcd(w,g);z=divide(w,y)
        if len(z)>1:result.append((z,i))
        w=y;g=divide(g,y);i+=1
    return result

def interior_roots(p,a,b):
    p=trim(p)
    # Remove interval-endpoint factors, which are checked separately.
    for x in (a,b):
        while len(p)>1 and value(p,x)==0:p=divide(p,[-x,F(1)])
    if len(p)==1:return 0
    chain=[p,derivative(p)]
    while chain[-1]!=[0]:
        r=divmod_poly(chain[-2],chain[-1])[1]
        if r==[0]:break
        chain.append([-x for x in r])
    def variations(x):
        signs=[1 if y>0 else -1 for poly in chain if (y:=value(poly,x))!=0]
        return sum(u!=v for u,v in zip(signs,signs[1:]))
    return variations(a)-variations(b)

def nonnegative(p,a=F(0),b=F(1)):
    p=trim(p);a=F(a);b=F(b)
    if not a<b:raise ValueError('ordered nonempty interval required')
    if p==[0]:return dict(nonnegative=True,reason='IDENTICALLY_ZERO',degree=0)
    for t in (a,b):
        v=value(p,t)
        if v<0:return dict(nonnegative=False,reason='NEGATIVE_ENDPOINT',at=str(t),value=str(v))
    factors=square_free_factors(p)
    odd=sum(interior_roots(f,a,b) for f,m in factors if m%2)
    if odd:return dict(nonnegative=False,reason='ODD_MULTIPLICITY_INTERIOR_ROOT',odd_roots=odd)
    # A nonzero degree-d polynomial cannot vanish at d+1 distinct probes.
    for k in range(1,len(p)+1):
        t=a+(b-a)*F(k,len(p)+1);v=value(p,t)
        if v!=0:return dict(nonnegative=v>0,reason='EXACT_STURM_SIGN',odd_roots=0,at=str(t),value=str(v),multiplicities=[m for _,m in factors])
    raise ArithmeticError('nonzero polynomial vanished at too many distinct probes')

def in_bounds(c,lower,upper):
    c=trim(c);lo=list(c);lo[0]-=lower;hi=[-x for x in c];hi[0]+=upper
    proofs=[nonnegative(lo),nonnegative(hi)]
    return dict(status='CERTIFIED' if all(x['nonnegative'] for x in proofs) else 'REFUTED',method='EXACT_RATIONAL_SQUAREFREE_STURM',bound_proofs=proofs)
