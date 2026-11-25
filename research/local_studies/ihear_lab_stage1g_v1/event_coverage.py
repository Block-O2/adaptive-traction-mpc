"""Prepared 5 ms event suffixes, tied to one scientific frozen epoch.

Scope matches native deployable-reference geometry plus sampled mechanics.
This is not a robust plant invariant or recovery from a realized hard violation.
"""
import bootstrap
from dataclasses import dataclass,replace
from fractions import Fraction as F
import numpy as np
from native_integration import model_key
from escape_candidates import prepare
from exact_runtime_reference import ExactSchedule,convert,certify_motion,eval_poly,derivative
from reference_kernel import Piece,Plan,rational_compose
from phase_coordinates import Phase
from hermite_exact import quintic
from interval_certificate import certify_geometry
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22

def certificate(s,sch,b,offset,*,monotone=True):
    floor=max(0.,float(np.min(sch.clearance_evaluator.evaluate(np.vstack([sch.spec.start_return_target_rad,s.candidate.phase_goal_rad]))))) if sch.preserve_task_endpoint_clearance_floor else 0.
    motion=certify_motion(s,sch,b,offset,monotone=monotone)
    nominal=certify_geometry(s,sch.clearance_evaluator.envelope,floor=floor,runtime_roundoff=True)
    shifted=certify_geometry(s,sch.clearance_evaluator.envelope,offset=offset,floor=0.,runtime_roundoff=True)
    mechanics=AdaptiveMechanicsScreenV22().evaluate(b,s.candidate,s)
    return dict(feasible=bool(motion['accepted'] and nominal['status']=='CERTIFIED_MATHEMATICAL_REFERENCE' and shifted['status']=='CERTIFIED_MATHEMATICAL_REFERENCE' and mechanics['feasible']),motion=motion,geometry=nominal,shifted_geometry=shifted,mechanics=mechanics,numeric_policy='EXACT_RATIONAL_REFERENCE_PLUS_OUTWARD_GEOMETRY_V1')

def stop_schedule(bundle,sch):
    """Exact existing 35 ms ramp followed by native-duration Hermite stop."""
    bridge=convert(bundle.bridge);commit=float(bundle.commit_progress_s);x=bridge.sample(commit)
    # Retain only the executed bridge prefix; original declared bridge is40ms.
    pieces=[];left=F(commit)
    for p in bridge.plan.pieces:
        H=F(float(p.duration))
        if left>=H:pieces.append(p);left-=H
        elif left>0:
            pieces.append(Piece(float(left),tuple(tuple(rational_compose(list(c),[F(0),left/H])) for c in p.coefficients)));left=F(0)
        if left==0:break
    stop=bundle.stop;T=stop.duration_s;last=pieces[-1];H=F(float(last.duration))
    qs=[eval_poly(c,F(1)) for c in last.coefficients]
    vs=[eval_poly(derivative(c,1),F(1))/H for c in last.coefficients]
    acc=[eval_poly(derivative(c,2),F(1))/H**2 for c in last.coefficients]
    if any(a!=0 for a in acc):raise ValueError('STOP_REQUIRES_ANALYTIC_ZERO_A_BRIDGE_END')
    alimit=[F(float(v*sch.reference_acceleration_fraction)) for v in sch.spec.task_joint_acceleration_limit_rad_s2]
    # Original duration calculation subtracts1e-12 before grid ceil. At an
    # active bound this can round below the exact minimum. Round outward on
    # the SAME5ms grid; never loosen the acceleration bound.
    while any(F(3,2)*abs(v)>F(float(T))*a for v,a in zip(vs,alimit)):
        T=(int(round(T/sch.reference_period_s))+1)*sch.reference_period_s
    co=tuple((q,F(float(T))*v,F(0),-F(float(T))*v,F(float(T))*v/2) for q,v in zip(qs,vs))
    pieces.append(Piece(T,co))
    candidate=replace(stop.candidate,q_waypoint_rad=np.array([float(q+F(float(T))*v/2) for q,v in zip(qs,vs)]))
    steps=sum(int(round(p.duration/.00025)) for p in pieces)
    assert all(abs(p.duration-round(p.duration/.00025)*.00025)<=4*abs(np.spacing(p.duration)) for p in pieces)
    return ExactSchedule(Plan(tuple(pieces)),Phase(np.zeros(2),np.ones(2)),candidate,endpoint_native_steps=steps)

@dataclass(frozen=True)
class PreparedEvent:
    fork_s:float
    schedule:ExactSchedule
    certificate:dict
    original_bridge_s:float
    commit_s:float
    stop_s:float
    @property
    def reserve_s(self):return .005+self.schedule.duration_s

@dataclass(frozen=True)
class EventCoverage:
    digest:str
    key:object
    offset:tuple
    epoch_s:float
    through_s:float
    events:tuple
    policy:str='SCIENTIFIC_5MS_GRID_CURRENT_OFFSET_V1'
    def validate(self,s,key,offset,epoch):
        if self.digest!=s.digest or self.key!=key or self.offset!=tuple(map(float,offset)) or self.epoch_s!=epoch:raise ValueError('CURRENT_EVENT_COVERAGE_REQUIRED')
        expected=tuple(round(k*.005,12) for k in range(int(round(self.through_s/.005))+1))
        if tuple(round(e.fork_s,12) for e in self.events)!=expected or not all(e.certificate['feasible'] is True for e in self.events):raise ValueError('INCOMPLETE_EVENT_COVERAGE')
        return self
    def at(self,elapsed):
        for e in self.events:
            if abs(e.fork_s-elapsed)<=1e-10:return e
        raise ValueError('UNCOVERED_EVENT')

def prepare_events(s,sch,b,offset,phase_elapsed_s,epoch_s,through_s=.100):
    if not isinstance(s,ExactSchedule):raise ValueError('EXACT_SCHEDULE_REQUIRED')
    if abs(round(through_s/.005)*.005-through_s)>1e-12 or through_s<0:raise ValueError('EVENT_GRID_REQUIRED')
    events=[]
    for k in range(int(round(through_s/.005))+1):
        t=k*.005;x=s.sample(t)
        if np.all(x.dq_rad_s==0) and np.all(x.ddq_rad_s2==0):
            stop=ExactSchedule(Plan((Piece(.005,tuple((F(float(q)),) for q in x.q_rad)),)),Phase(np.zeros(2),np.ones(2)),replace(s.candidate,q_waypoint_rad=x.q_rad,dq_waypoint_rad_s=np.zeros(2)),endpoint_native_steps=20)
            cert=certificate(stop,sch,b,offset,monotone=False)
            if not cert['feasible']:raise ValueError('STATIONARY_EVENT_HOLD_REJECTED')
            events.append(PreparedEvent(t,stop,cert,0.,0.,.005));continue
        bundle=prepare(s,t,sch,b,np.asarray(offset),phase_elapsed_s)
        stop=stop_schedule(bundle,sch);cert=certificate(stop,sch,b,offset,monotone=False)
        if not cert['feasible']:raise ValueError('OUTWARD_EVENT_STOP_REJECTED:'+str(k)+':'+str(cert))
        first=s.sample(t);new=stop.sample(0)
        if max(np.max(np.abs(getattr(first,n)-getattr(new,n))) for n in ('q_rad','dq_rad_s','ddq_rad_s2'))>1e-10:raise ValueError('EVENT_C2_REJECTED')
        events.append(PreparedEvent(t,stop,cert,.040,bundle.commit_progress_s,stop.plan.pieces[-1].duration))
    return EventCoverage(s.digest,model_key(b,sch.clearance_evaluator),tuple(map(float,offset)),float(epoch_s),float(through_s),tuple(events))
