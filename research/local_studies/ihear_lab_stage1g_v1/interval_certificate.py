"""Outward interval geometry on the unchanged registered envelope.

Exact rational Bernstein bounds for the stored mathematical polynomial. mpmath
iv operations enclose transcendental arithmetic. This does not certify plant
tracking error or the floating point controller's execution of the polynomial.
"""
import bootstrap
from fractions import Fraction as F
from math import comb
from mpmath.ctx_iv import MPIntervalContext
from reference_kernel import rational_compose
from traction_mpc_stage3.coupled import BED_HEIGHT_M,SHANK_RADIUS_M,THIGH_RADIUS_M,SLEEVE_HALF_LENGTH_M,SLEEVE_OUTER_RADIUS_M
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
import numpy as np
iv=MPIntervalContext();iv.dps=50
def I(x):
    if isinstance(x,F):return iv.mpf(x.numerator)/x.denominator
    return iv.mpf(float(x))
def bounds(c,lo,hi):
    c=rational_compose([F(x) for x in c],[lo,hi-lo]);n=len(c)-1
    b=[sum(c[k]*F(comb(j,k),comb(n,k)) for k in range(j+1)) for j in range(n+1)]
    return min(b),max(b)
def interval(lo,hi):return iv.mpf([I(lo).a,I(hi).b])
def minimum(a,b):return iv.mpf([min(a.a,b.a),min(a.b,b.b)])
def nonnegative(a):return iv.mpf([max(I(0),a.a),max(I(0),a.b)])
def gap(a,b,axis,r):return minimum(a,b)-I(r)*iv.sqrt(nonnegative(1-axis**2))-I(BED_HEIGHT_M)
def geometry(q,env):
    g=env.geometry;q1,q2=q;phi=q1-q2;px=I(g.plane_x_world[2]);pz=I(g.plane_z_world[2])
    hip=I(g.origin_world_m[2])+I(g.hip_plane_m[0])*px+I(g.hip_plane_m[1])*pz
    thigh=iv.cos(q1)*px+iv.sin(q1)*pz;shank=iv.cos(phi)*px+iv.sin(phi)*pz
    knee=hip+I(g.thigh_length_m)*thigh;ankle=knee+I(env.shank_length_upper_m)*shank
    cuff=knee+I(g.cuff_distance_m)*shank+I(env.cuff_reference_translation_world_m[2])
    proximal=I(env.registered_proximal_installation_gap_lower_m) if q1.a>=0 and q1.b<=iv.pi.a and abs(float(g.plane_x_world[2]))<1e-9 and float(g.plane_z_world[2])>0 else minimum(hip,knee)-I(THIGH_RADIUS_M)-I(BED_HEIGHT_M)
    sh=I(SLEEVE_HALF_LENGTH_M)*shank;bar=I(STAGE5_GEOMETRY.cuff_bar_length_m)*shank/2
    out={'proximal_thigh_m':proximal,'distal_shank_m':minimum(knee,ankle)-I(SHANK_RADIUS_M)-I(BED_HEIGHT_M)-I(env.existing_shank_margin_m),
         'sleeve_m':gap(cuff-sh,cuff+sh,shank,SLEEVE_OUTER_RADIUS_M),'cuff_bar_m':gap(cuff-bar,cuff+bar,shank,STAGE5_GEOMETRY.cuff_bar_radius_m)}
    # Fixed calibrated tool transform is the exact binary64 calibration used by
    # native code; its derived length/direction are enclosed, not rounded first.
    trans=[I(x) for x in STAGE5_GEOMETRY.end_effector_from_cuff.translation]
    rotation=STAGE5_GEOMETRY.end_effector_from_cuff.rotation
    norm=iv.sqrt(sum(x*x for x in trans));length=norm-I(SLEEVE_OUTER_RADIUS_M)
    if length.a>0:
        tool=[sum(I(rotation[k,j])*trans[k] for k in range(3)) for j in range(3)]
        cross=I(g.plane_z_world[0])*I(g.plane_x_world[1])-I(g.plane_z_world[1])*I(g.plane_x_world[0])
        z=-iv.sin(phi)*px+iv.cos(phi)*pz;ez=shank*tool[0]+cross*tool[1]+z*tool[2]
        flange=cuff-ez;connector=flange+length/norm*ez
        out['cuff_adapter_m']=gap(flange,connector,ez/norm,.018)
    elif length.b<=0:out['cuff_adapter_m']=cuff-I(.018)-I(BED_HEIGHT_M)
    else:raise ValueError('UNKNOWN_CONNECTOR_BRANCH')
    return out
def certify_geometry(s,env,offset=(0,0),floor=0.,max_depth=16,runtime_roundoff=False):
    # Each accepted cell encloses every physical time inside it. Sampling alone
    # never establishes acceptance; exact midpoint intervals can refute a path.
    pending=[(i,F(0),F(1),0) for i in range(len(s.plan.pieces))];count=0;lowers={};unknown=[]
    while pending:
        i,lo,hi,depth=pending.pop();p=s.plan.pieces[i];q=[]
        for j,c in enumerate(p.coefficients):
            a,z=bounds(c,lo,hi);sg=F(float(s.coordinates.sign[j]));base=F(float(s.coordinates.start[j]))+F(float(offset[j]))
            if sg<0:a,z=-z,-a
            low,high=base+a,base+z
            if runtime_roundoff:
                # ExactSchedule converts a rational physical q once; the
                # existing constant-offset prediction can add one float.
                # Eight ulps bound those operations, not physical slack.
                scale=max(1.,abs(float(low)),abs(float(high)),abs(float(offset[j])))
                error=F(float(8*np.spacing(scale)))
                low-=error;high+=error
            q.append(interval(low,high))
        result=geometry(q,env);count+=1
        if all(v.a>=I(floor) for v in result.values()):
            for k,v in result.items():lowers[k]=min(lowers.get(k,float('inf')),float(np.nextafter(float(v.a),-np.inf)))
            continue
        mid=(lo+hi)/2;point=[]
        for j,c in enumerate(p.coefficients):
            a,z=bounds(c,mid,mid);base=F(float(s.coordinates.start[j]))+F(float(offset[j]));sg=F(float(s.coordinates.sign[j]));low=base+sg*a;high=base+sg*z
            error=F(float(8*np.spacing(max(1.,abs(float(low)),abs(float(high)),abs(float(offset[j])))))) if runtime_roundoff else F(0)
            point.append(interval(low-error,high+error))
        witness=geometry(point,env)
        bad={k:str(v) for k,v in witness.items() if v.b<I(floor)}
        if bad:return dict(status='REFUTED_REFERENCE_ENVELOPE',piece=i,fraction=str(mid),components=bad,cells=count)
        if depth==max_depth:unknown.append(dict(piece=i,lo=str(lo),hi=str(hi),bounds={k:str(v) for k,v in result.items()}))
        else:pending.extend([(i,lo,mid,depth+1),(i,mid,hi,depth+1)])
    return dict(status='UNKNOWN' if unknown else 'CERTIFIED_MATHEMATICAL_REFERENCE',cells=count,lowers=lowers,unknown=unknown,precision_dps=50,max_depth=max_depth,threshold_m=floor,runtime_roundoff_enclosed=runtime_roundoff)
