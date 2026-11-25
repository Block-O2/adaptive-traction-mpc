"""A finite proposal and its proof family. This module has no plant write API."""
from collections import defaultdict
from time import perf_counter_ns
import numpy as np
from fixture import (F,GRID,H,RAMP,Origin,Segment,Stop,Window,pair,old,ia,sha,serialize,
                     current_state,mapped_target,joins,normal_motion,stop_motion,continuous_geometry,mechanics)

class Meter:
    def __init__(self):self.ns=defaultdict(int);self.count=defaultdict(int)
    def call(self,label,fn,*args):
        start=perf_counter_ns()
        try:return fn(*args)
        finally:
            self.ns[label]+=perf_counter_ns()-start
            self.count[label]+=1

def direction(c):
    geom=c.model.geometry
    basis=np.column_stack((geom.plane_x_world,geom.plane_z_world))
    G=basis.T@geom.translational_jacobian_world(c.x[:2])
    if np.linalg.matrix_rank(G)!=2 or not np.all(c.goal>c.q):raise ValueError('invalid startup geometry')
    return old.directions(G,c.goal-c.q,c.V,c.A,basis.T@c.F,float(H))

def construct(c,r):
    model_version=sha(repr(ia.model_key(c.b,c.clear)).encode())
    geometry_version=old.clearance_geometry_signature(c.clear)
    origin=Origin(c.phase.value,pair(c.q),(1,1),'offline-strict-rest',model_version,geometry_version,c.stamp,c.capture)
    return Segment(origin,pair(r),c.omega)

def worker(c,screen_factory=None):
    start=perf_counter_ns()
    m=Meter()
    rows,idx,cap,speed,r=m.call('direction',direction,c)
    seg=m.call('normal_construct',construct,c,r)
    first=seg.sample(0)
    if not np.array_equal(ia.vec(first),np.r_[c.q,[0.,0.,0.,0.]]):raise ValueError('root')
    offset=m.call('current_state',current_state,c,first)
    if not m.call('normal_motion',normal_motion,seg,c.V,c.A,c.goal):raise ValueError('normal motion')
    floor=max(0.,float(np.min(c.clear.evaluate(np.vstack([c.spec.start_return_target_rad,c.goal])))))
    screen=screen_factory(c) if screen_factory else None
    checks={}
    object_paths=[]
    def check(name,path,kind):
        label='fgdw_interface_fixture'
        final=path.sample(path.duration)
        candidate=old.runtime._candidate(label,c.phase,final.q_rad,final.dq_rad_s,c.spec)
        # Retain the native goal, boundary q/velocity and phase resource request checks.
        zero=path.sample(0)
        c.sch._validate_request(zero.q_rad,zero.dq_rad_s,candidate,c.elapsed)
        proof={}
        for scope,off,lower in [('nominal',np.zeros(2),floor),('shifted',offset,0.)]:
            proof[scope]=m.call(scope+'_geometry',continuous_geometry,path,c.clear.envelope,off,lower,c.rom)
            if proof[scope]['status']!='CERTIFIED_SAFE':raise ValueError(name+' '+scope)
        if screen is None:
            res=m.call(kind+'_mechanics',mechanics,c.b,candidate,path)
        else:
            res=m.call(kind+'_mechanics',screen.evaluate,candidate,path)
        if not res['feasible'] or res['sample_count']!=21:raise ValueError('mechanics '+name)
        checks[name]=dict(**proof,mechanics=res)
        object_paths.append((name,path))
    check('normal',seg,'normal')
    stops=[];planes=[];previous_pose=None
    for k in range(9):
        t=k*GRID
        pose,plane=m.call('normal_robot_target',mapped_target,c,seg.sample(t))
        tool=m.call('normal_robot_target',ia.tool_increment_certificate,previous_pose or pose,pose)
        if not tool['feasible'] or any(plane['normals']):raise ValueError('registered plane/tool')
        previous_pose=pose;planes.append(dict(**plane,tool=tool))
        st=m.call('stop_construct',Stop,seg,t,c.A)
        if not m.call('stop_motion',stop_motion,st,c.V,c.A,c.goal):raise ValueError('stop motion')
        continuity=m.call('c2',joins,seg,st,t)
        reserve=float(t+st.duration+GRID)
        if reserve>min(c.phase_limit-c.elapsed,c.task_limit-c.elapsed):raise ValueError('resource')
        prefix='stop'+str(k)
        check(prefix,st,'stop')
        if not st.stationary:
            check(prefix+'/bridge',Window(st,F(0),H),'stop')
            check(prefix+'/brake',Window(st,H,st.brake),'stop')
        hold_start=perf_counter_ns()
        hold=ia.StaticHold(st)
        check(prefix+'/hold',hold,'hold')
        hold_pose,hdata=m.call('hold_robot_target',mapped_target,c,hold.sample(0))
        hold_tool=m.call('hold_robot_target',ia.tool_increment_certificate,hold_pose,hold_pose)
        if not hold_tool['feasible'] or any(hdata['normals']):raise ValueError('static loaded target')
        m.ns['hold_inclusive']+=perf_counter_ns()-hold_start
        m.count['hold_inclusive']+=1
        stops.append(dict(node_ms=5*k,brake_s=float(st.brake),duration_s=st.duration_s,reserve_s=reserve,
                    junctions=continuity,static_tool=hold_tool))
    if len(checks)!=35:raise ValueError('incomplete coverage')
    def pack():
        packet=dict(authority='OFFLINE_PREPARED_ONLY',identity=seg.identity,owner=seg.origin.owner,
            phase=seg.origin.phase,model=seg.origin.model_version,geometry=seg.origin.geometry_version,
            source_time=seg.origin.source_time_s,source_capture_ns=seg.origin.source_capture_ns,
            offset=offset,elapsed=c.elapsed,phase_limit=c.phase_limit,task_limit=c.task_limit,
            scores=[x['score_N'] for x in rows],selected=idx,target=r,end=ia.vec(seg.sample(H)),omega=seg.omega,
            stops=stops,planes=planes,checks=checks)
        # Immutable transferable evidence bytes, distinct from measurement arrival or native application.
        encoded=serialize(packet).encode()
        return packet,sha(encoded),len(encoded)
    packet,digest,size=m.call('pack',pack)
    m.ns['worker_total']=perf_counter_ns()-start;m.count['worker_total']=1
    return packet,digest,size,dict(m.ns),dict(m.count),object_paths,screen
