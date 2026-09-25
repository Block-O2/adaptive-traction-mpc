"""Outward binary64 enclosures for a narrow sagittal common-progress proof.

All arithmetic bounds use nextafter. Sin/cos use interval Taylor polynomials
(degrees35/34) with Lagrange remainder for |angle|<=4. No libm sin/cos error
assumption or coefficient-only generic epsilon is used in acceptance.
"""
import math
from fractions import Fraction
import numpy as np
from traction_mpc_stage3.coupled import (SLEEVE_HALF_LENGTH_M, SLEEVE_OUTER_RADIUS_M,
                                       SHANK_RADIUS_M, BED_HEIGHT_M)
from ..geometry import STAGE5_GEOMETRY


def down(x): return math.nextafter(x, -math.inf)
def up(x): return math.nextafter(x, math.inf)


class I:
    __slots__ = ('lo','hi')
    def __init__(self, lo, hi=None):
        self.lo=float(lo); self.hi=float(lo if hi is None else hi)
        if not (math.isfinite(self.lo) and math.isfinite(self.hi) and self.lo<=self.hi):
            raise ValueError('invalid finite interval')
    def __add__(self,other):
        b=as_i(other); return I(down(self.lo+b.lo),up(self.hi+b.hi))
    __radd__=__add__
    def __neg__(self): return I(-self.hi,-self.lo)
    def __sub__(self,other): return self+-as_i(other)
    def __rsub__(self,other): return as_i(other)+-self
    def __mul__(self,other):
        b=as_i(other); products=(self.lo*b.lo,self.lo*b.hi,self.hi*b.lo,self.hi*b.hi)
        return I(down(min(products)),up(max(products)))
    __rmul__=__mul__
    def abs(self):
        return I(0. if self.lo<=0.<=self.hi else min(abs(self.lo),abs(self.hi)),max(abs(self.lo),abs(self.hi)))
    def pair(self): return [self.lo,self.hi]


def as_i(value): return value if isinstance(value,I) else I(value)
def minimum(a,b): return I(min(a.lo,b.lo),min(a.hi,b.hi))

def nonnegative_sqrt(value):
    return I(max(0.,down(math.sqrt(max(0.,value.lo)))),up(math.sqrt(max(0.,value.hi))))

def rational(n,d):
    value=float(Fraction(n,d))
    return I(down(value),up(value))


SIN_COEFFICIENTS=tuple(rational((-1)**k,math.factorial(2*k+1)) for k in range(18))
COS_COEFFICIENTS=tuple(rational((-1)**k,math.factorial(2*k)) for k in range(18))
SIN_REMAINDER=up(float(Fraction(4**37,math.factorial(37))))
COS_REMAINDER=up(float(Fraction(4**36,math.factorial(36))))


def trig(x,cosine=False):
    if x.abs().hi>4.: raise ValueError('trig interval outside registered proof domain')
    coefs=COS_COEFFICIENTS if cosine else SIN_COEFFICIENTS
    square=x*x; value=coefs[-1]
    for coefficient in reversed(coefs[:-1]): value=coefficient+square*value
    if not cosine: value=x*value
    remainder=COS_REMAINDER if cosine else SIN_REMAINDER
    value=value+I(-remainder,remainder)
    return I(max(-1.,value.lo),min(1.,value.hi))


def endpoint(envelope,q):
    g=envelope.geometry; shank=trig(q[0]-q[1]); radial=trig(q[0]-q[1],True)
    knee=I(g.origin_world_m[2])+I(g.hip_plane_m[1])+I(g.thigh_length_m)*trig(q[0])
    cuff=knee+I(g.cuff_distance_m)*shank+I(envelope.cuff_reference_translation_world_m[2])
    thigh=I(envelope.registered_proximal_installation_gap_lower_m)
    distal=minimum(knee,knee+I(envelope.shank_length_upper_m)*shank)-SHANK_RADIUS_M-BED_HEIGHT_M-envelope.existing_shank_margin_m
    sleeve_radial=nonnegative_sqrt(I(1.)-shank*shank)
    sleeve=cuff-I(SLEEVE_HALF_LENGTH_M)*shank.abs()-I(SLEEVE_OUTER_RADIUS_M)*sleeve_radial-BED_HEIGHT_M
    bar=cuff-I(.5*STAGE5_GEOMETRY.cuff_bar_length_m)*shank.abs()-I(STAGE5_GEOMETRY.cuff_bar_radius_m)*sleeve_radial-BED_HEIGHT_M
    # Registered exact signed-permutation R_EC and positive y translation:
    # adapter endpoints are cuff+t_y*cos(phi), cuff+R_sleeve*cos(phi).
    ty=float(STAGE5_GEOMETRY.end_effector_from_cuff.translation[1])
    adapter=minimum(cuff+I(ty)*radial,cuff+I(SLEEVE_OUTER_RADIUS_M)*radial)-I(.018)*nonnegative_sqrt(I(1.)-radial*radial)-BED_HEIGHT_M
    return dict(proximal_thigh_m=thigh,distal_shank_m=distal,sleeve_m=sleeve,cuff_bar_m=bar,cuff_adapter_m=adapter)


def monotonic_certificate(envelope,coefficients):
    c=np.asarray(coefficients,dtype=float); g=envelope.geometry; tool=STAGE5_GEOMETRY.end_effector_from_cuff
    record={'method':'outward_interval_common_progress_v2','eligible':False,'lowers':{},'body_proofs':{},
            'proof_scope':'model reference geometry only; no physical invariance or state-estimation guarantee'}
    arrays=(c,g.origin_world_m,g.hip_plane_m,g.plane_x_world,g.plane_z_world,tool.translation,tool.rotation,
            envelope.cuff_reference_translation_world_m)
    if not all(np.all(np.isfinite(x)) for x in arrays):
        raise ValueError('nonfinite geometry or polynomial cannot be certified')
    if c.shape!=(2,6): return record
    if not (np.array_equal(g.plane_x_world,[1.,0.,0.]) and np.array_equal(g.plane_z_world,[0.,0.,1.])
        and np.array_equal(tool.rotation,[[1.,0.,0.],[0.,0.,-1.],[0.,1.,0.]])
        and tool.translation[0]==tool.translation[2]==0. and tool.translation[1]>SLEEVE_OUTER_RADIUS_M): return record
    vals=[g.thigh_length_m,g.cuff_distance_m,envelope.shank_length_upper_m]
    if not np.all(np.isfinite(vals)) or min(vals)<=0.: raise ValueError('invalid geometry dimensions')
    q0=[I(x) for x in c[:,0]]
    delta=[I(float(math.fsum(row)-row[0])) for row in c]
    q1=[a+b for a,b in zip(q0,delta)]
    canonical=[0.,0.,0.,10.,-15.,6.]
    residual=[[I(c[j,k])-(q0[j] if k==0 else delta[j]*canonical[k]) for k in range(6)] for j in range(2)]
    e1=sum((x.abs() for x in residual[0]),I(0.)).hi
    ephi=sum(((a-b).abs() for a,b in zip(*residual)),I(0.)).hi
    # Recognition only controls specialization; all residuals are paid below.
    if max(e1,ephi)>1e-10: return record
    lo=min(q0[0].lo,q1[0].lo); hi=max(q0[0].hi,q1[0].hi)
    if lo<0. or hi>math.pi/2: return record
    if max((q0[0]-q0[1]).abs().hi,(q1[0]-q1[1]).abs().hi)>4.: return record
    coslo=trig(I(hi),True).lo; coshi=trig(I(lo),True).hi
    k=I(g.thigh_length_m)*delta[0]*I(coslo,coshi)
    dphi=(delta[0]-delta[1]).abs()
    def hypot_upper(a,b):
        square=I(a)*I(a)+I(b)*I(b)
        return up(math.sqrt(square.hi))
    radii={'distal_shank_m':I(envelope.shank_length_upper_m),
        'sleeve_m':I(g.cuff_distance_m)+I(hypot_upper(SLEEVE_HALF_LENGTH_M,SLEEVE_OUTER_RADIUS_M)),
        'cuff_bar_m':I(g.cuff_distance_m)+I(hypot_upper(.5*STAGE5_GEOMETRY.cuff_bar_length_m,STAGE5_GEOMETRY.cuff_bar_radius_m)),
        'cuff_adapter_m':I(g.cuff_distance_m)+I(float(tool.translation[1]))+I(.018)}
    ends=[endpoint(envelope,q0),endpoint(envelope,q1)]
    record.update(eligible=True,coefficient_residual_q1_rad=e1,coefficient_residual_phi_rad=ephi,
                  knee_derivative_interval=k.pair(),delta_phi_abs_interval=dphi.pair())
    for name,radius in radii.items():
        derivative=I(k.lo-(radius*dphi).hi,k.hi+(radius*dphi).hi)
        # One extra outward rounding includes the last subtraction/addition.
        derivative=I(down(derivative.lo),up(derivative.hi))
        which=0 if derivative.lo>=0. else (1 if derivative.hi<=0. else None)
        loss=I(g.thigh_length_m)*I(e1)+radius*I(ephi)
        proof={'derivative_interval':derivative.pair(),'radius_upper_m':radius.hi,
               'selected_endpoint':which,'residual_loss_upper_m':loss.hi}
        if which is not None:
            lower=(ends[which][name]-loss).lo
            record['lowers'][name]=lower
            proof.update(endpoint_interval_m=ends[which][name].pair(),lower_m=lower)
        record['body_proofs'][name]=proof
    if (I(lo)-I(e1)).lo>=0. and (I(hi)+I(e1)).hi<=math.pi/2:
        record['lowers']['proximal_thigh_m']=envelope.registered_proximal_installation_gap_lower_m
        record['body_proofs']['proximal_thigh_m']={'constant_registered_floor':True,'lower_m':envelope.registered_proximal_installation_gap_lower_m}
    return record


def monotonic_component_lowers(envelope,coefficients):
    return monotonic_certificate(envelope,coefficients)['lowers']
