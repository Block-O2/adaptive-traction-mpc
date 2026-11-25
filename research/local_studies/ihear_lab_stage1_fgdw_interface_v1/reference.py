"""FGDW reference functions. Software samples carry no execution authority."""
from dataclasses import dataclass
from fractions import Fraction as F
import hashlib
import math

import numpy as np
from interval_certificate import I, iv
from traction_mpc_stage5.human_waypoint_scheduler import ScheduledHumanReferenceSample

GRID = F(1,200)
H = 8*GRID
RAMP = 7*GRID

def time_value(t):
    return t if isinstance(t,F) else F(str(float(t)))

def numeric(intervals):
    return np.array([float(x.mid) for x in intervals])

def pair(x):
    return tuple(float(v) for v in x)

@dataclass(frozen=True)
class Origin:
    phase: str
    q_start: tuple
    sign: tuple
    owner: str
    model_version: str
    geometry_version: str
    source_time_s: float
    source_capture_ns: int | None

@dataclass(frozen=True)
class Segment:
    origin: Origin
    target: tuple
    omega: float
    parent: object = None
    parent_progress: F = F(0)
    duration: F = H

    def __post_init__(self):
        if self.duration<=0 or not math.isfinite(self.omega) or self.omega<=0:
            raise ValueError("invalid segment")
        if self.origin.phase not in ("OUTBOUND","RETURN") or len(self.origin.q_start)!=2 or len(self.target)!=2:
            raise ValueError("invalid joint reference")
        if any(x not in (-1,1) for x in self.origin.sign) or len(self.origin.sign)!=2:
            raise ValueError("invalid signed basis")
        if not all(math.isfinite(x) for x in (*self.target,*self.origin.q_start,self.origin.source_time_s)):
            raise ValueError("nonfinite reference")
        if self.parent is None and self.parent_progress!=0: raise ValueError("invalid rest origin")
        if self.parent is not None and (self.origin.q_start!=self.parent.origin.q_start or
             self.origin.sign!=self.parent.origin.sign or self.origin.phase!=self.parent.origin.phase or
             self.omega!=self.parent.omega or not 0<=self.parent_progress<=self.parent.duration):
            raise ValueError("unconnected analytical history")

    @property
    def duration_s(self): return float(self.duration)

    @property
    def identity(self):
        lineage = None if self.parent is None else (self.parent.identity,self.parent_progress)
        return hashlib.sha256(repr((self.origin,self.target,self.omega,self.duration,lineage)).encode()).hexdigest()

    def state(self,t):
        t=time_value(t)
        if not 0<=t<=self.duration: raise ValueError("outside finite reference")
        zero=(I(0),I(0))
        s0,u0,z0=(zero,zero,zero) if self.parent is None else self.parent.state(self.parent_progress)
        if not t:return s0,u0,z0
        w=I(self.omega); dt=I(t); x=w*dt; decay=iv.exp(-x)
        s=[];u=[];z=[]
        for a,b,c,rate in zip(s0,u0,z0,self.target):
            r=I(rate)
            zz=r+(c-r)*decay
            uu=r+(b-r+x*(c-r))*decay
            s.append(a+dt*r-(uu+zz-b-c)/w);u.append(uu);z.append(zz)
        return tuple(s),tuple(u),tuple(z)

    def jet(self,t):
        s,u,z=self.state(t)
        a=tuple(I(self.omega)*(x-y) for x,y in zip(z,u))
        return physical(self.origin,s,u,a)

    def sample(self,t):return sample(self.jet(t))

    def suffix(self,t):return Window(self,time_value(t),self.duration-time_value(t))

    def successor(self,target,origin):
        return Segment(origin,pair(target),self.omega,self,self.duration)

def physical(origin,s,u,a):
    sign=origin.sign
    return (tuple(I(q)+j*x for q,j,x in zip(origin.q_start,sign,s)),
            tuple(j*x for j,x in zip(sign,u)),tuple(j*x for j,x in zip(sign,a)))

def sample(jet):
    return ScheduledHumanReferenceSample(*(numeric(x) for x in jet))

@dataclass(frozen=True)
class Window:
    source: object
    offset: F
    duration: F
    def __post_init__(self):
        if min(self.offset,self.duration)<0 or self.offset+self.duration>self.source.duration:
            raise ValueError("invalid finite window")
    @property
    def identity(self):return self.source.identity
    @property
    def duration_s(self):return float(self.duration)
    def jet(self,t):
        t=time_value(t)
        if not 0<=t<=self.duration:raise ValueError("outside window")
        return self.source.jet(self.offset+t)
    def sample(self,t):return sample(self.jet(t))

class Stop:
    """A fork of one authenticated mathematical history. No duration search."""
    def __init__(self,source,node,limits):
        self.source=source; self.node=node; self.origin=source.origin
        self.s0,self.u0,z=source.state(node)
        self.a0=tuple(I(source.omega)*(c-b) for c,b in zip(z,self.u0))
        self.ub=tuple(b+a*I(RAMP)/2 for b,a in zip(self.u0,self.a0))
        self.stationary=all(x==I(0) for x in (*self.u0,*self.a0))
        self.identity=(source.identity,str(node),"escape")
        if self.stationary:
            self.brake=F(0);self.duration=GRID;return
        k=0
        for u,lim in zip(self.ub,limits):
            ratio=I(F(3,2))*abs(u)/(I(lim)*I(GRID))
            # mp endpoints are binary floats; recover their exact represented rationals.
            def ceil_endpoint(mpf):
                sign,mantissa,exponent,_=mpf
                return math.ceil((-1 if sign else 1)*F(mantissa)*F(2)**exponent)
            lo,hi=(ceil_endpoint(v) for v in ratio._mpi_)
            if lo!=hi:raise ValueError("unresolved exact grid ceiling")
            k=max(k,hi)
        self.brake=k*GRID
        self.duration=H+self.brake

    @property
    def duration_s(self):return float(self.duration)

    def jet(self,t):
        t=time_value(t)
        if not 0<=t<=self.duration:raise ValueError("outside stop")
        if self.stationary:return physical(self.origin,self.s0,self.u0,self.a0)
        T=I(RAMP);b=I(self.brake)
        s=[];u=[];a=[]
        for q,v,acc,ub in zip(self.s0,self.u0,self.a0,self.ub):
            if t<RAMP:
                x=I(t)
                ss=q+v*x+acc*(x*x/2-x**3/(6*T))
                uu=v+acc*(x-x*x/(2*T));aa=acc*(1-x/T)
            else:
                sb=q+v*T+acc*T*T/3
                if t<=H: ss=sb+I(t-RAMP)*ub;uu=ub;aa=I(0)
                elif t==self.duration:
                    ss=sb+ub*(I(GRID)+b/2);uu=I(0);aa=I(0)
                else:
                    x=I((t-H)/self.brake)
                    ss=sb+ub*(I(GRID)+b*(x-x**3+x**4/2))
                    uu=ub*(1-3*x*x+2*x**3);aa=ub*6*x*(x-1)/b
            s.append(ss);u.append(uu);a.append(aa)
        return physical(self.origin,s,u,a)
    def sample(self,t):return sample(self.jet(t))
