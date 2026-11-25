"""Local continuous certificates, with separate geometry assumption scopes."""
import math
import numpy as np
from reference import F, I, iv, GRID, H, RAMP, Stop, Window
from interval_certificate import geometry, interval
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22

def bounds(x):
    return [math.nextafter(float(x.a),-math.inf),math.nextafter(float(x.b),math.inf)]

def qbox(path,lo,hi,offset):
    # Preconditions: certified forward velocity and a constant sign per axis.
    l=path.jet(lo)[0]; r=path.jet(hi)[0]
    box=[]
    for a,b,e in zip(l,r,offset):
        low=min(bounds(a)[0],bounds(b)[0]);high=max(bounds(a)[1],bounds(b)[1])
        # Outward hull also encloses one binary64 sampling and offset addition.
        shifted=interval(low,high)+I(float(e))
        box.append(interval(*bounds(shifted)))
    return box

def continuous_geometry(path,env,offset,floor,rom,parameter_box=None):
    def check(lo,hi):
        box=qbox(path,lo,hi,offset)
        margins=geometry(box,env)
        if parameter_box is not None:
            g=env.geometry
            if list(g.plane_x_world)!=[1.,0.,0.] or list(g.plane_z_world)!=[0.,0.,1.] or box[0].a<0 or box[0].b>iv.pi.a:
                raise ValueError("parameter enclosure only for registered upright branch")
            hip,thigh,cuff=(interval(*v) for v in parameter_box)
            # Common additive displacement of the knee and all distal bodies.
            slide=(hip-I(g.hip_plane_m[1]))+(thigh-I(g.thigh_length_m))*iv.sin(box[0])
            tool_slide=slide+(cuff-I(g.cuff_distance_m))*iv.sin(box[0]-box[1])
            for name in ('sleeve_m','cuff_bar_m','cuff_adapter_m'):
                margins[name]+=tool_slide
            margins['distal_shank_m']+=slide
        inside=all(x.a>=I(float(a)) and x.b<=I(float(b)) for x,(a,b) in zip(box,rom))
        safe=inside and all(m.a>=I(floor) for m in margins.values())
        # A wholly violating interval is an infeasibility witness. A loose lower bound alone is not.
        outside=any(x.b<I(float(a)) or x.a>I(float(b)) for x,(a,b) in zip(box,rom))
        refuted=outside or any(m.b<I(floor) for m in margins.values())
        return dict(lo=float(lo),hi=float(hi),box=[bounds(x) for x in box],rom=inside,
                    margins={k:bounds(x) for k,x in margins.items()},status=(
                        "CERTIFIED_SAFE" if safe else "CERTIFIED_INFEASIBLE" if refuted else "UNRESOLVED"))
    whole=check(F(0),path.duration)
    cells=[whole]
    if whole['status']=='UNRESOLVED':
        cuts=[k*GRID for k in range(math.ceil(path.duration/GRID))]+[path.duration]
        cells=[check(a,b) for a,b in zip(cuts,cuts[1:])]
    statuses=[c['status'] for c in cells]
    status="CERTIFIED_INFEASIBLE" if "CERTIFIED_INFEASIBLE" in statuses else "CERTIFIED_SAFE" if all(s=="CERTIFIED_SAFE" for s in statuses) else "UNRESOLVED"
    return dict(status=status,whole=whole,cells=cells,floor_m=floor)

def normal_motion(path,V,A,goal):
    # No user-supplied u,z states: the sole root is exact rest. Check each ancestor.
    if path.parent is not None and not normal_motion(path.parent,V,A,goal):return False
    if any(not 0<=r<=v for r,v in zip(path.target,V)):return False
    if any((I(path.omega)*I(v)/iv.exp(I(1))).b>I(a) for v,a in zip(V,A)):return False
    s,u,z=path.state(0)
    for i,sign in enumerate(path.origin.sign):
        reserve=sign*(I(goal[i])-I(path.origin.q_start[i]))-s[i]-(u[i]+z[i])/I(path.omega)
        if reserve.a<(I(path.target[i])*I(path.duration)).b:return False
    return True

def stop_motion(stop,V,A,goal):
    alpha=I(stop.source.omega)*I(RAMP)/2
    if not (alpha.a>=0 and alpha.b<=1):return False
    for i,(v,b,a,ub) in enumerate(zip(V,A,stop.a0,stop.ub)):
        if abs(a).b>I(b) or ub.a<0 or ub.b>I(v):return False
        if stop.brake and (I(F(3,2))*abs(ub)/I(stop.brake)).b>I(b):return False
        end=stop.jet(stop.duration)[0][i]
        if (stop.origin.sign[i]*(I(goal[i])-end)).a<0:return False
    return True

def mechanics(b,candidate,path):
    return AdaptiveMechanicsScreenV22().evaluate(b,candidate,path)
