"""Exact rational polynomial evaluation before one binary64 output conversion.

No acquired/issued state is repaired retroactively. Boundary identities are
evaluated, not imposed by clearing acceleration. Original C2 tolerance retained.
"""
import bootstrap
from fractions import Fraction as F
from dataclasses import dataclass,replace
import hashlib
import numpy as np
from reference_kernel import Piece,Plan,rational_compose
from phase_coordinates import State
from native_integration import PolynomialSchedule
from traction_mpc_stage5.human_waypoint_scheduler import ScheduledHumanReferenceSample
from interval_certificate import bounds
def derivative(c,n):
    c=[F(x) for x in c]
    for _ in range(n):c=[i*x for i,x in enumerate(c)][1:]
    return c or [F(0)]
def eval_poly(c,s):
    v=F(0)
    for x in reversed(c):v=v*s+F(x)
    return v

def piece_time(piece):
    value=getattr(piece,'exact_duration',None)
    return F(float(piece.duration)) if value is None else value

def restricted_pieces(pieces,elapsed):
    left=F(elapsed);result=[]
    for p in pieces:
        H=piece_time(p)
        if left>=H:left-=H;continue
        if left==0:result.append(p)
        else:
            D=H-left
            co=tuple(tuple(rational_compose(list(c),[left/H,D/H])) for c in p.coefficients)
            result.append(ExactPiece(float(D),co,D));left=F(0)
    if not result:raise ValueError('empty exact suffix')
    return tuple(result)

def exact_plan_state(plan,t):
    if not np.isfinite(t) or t<0:raise ValueError('INVALID_REFERENCE_TIME')
    remaining=F(float(t));piece=plan.pieces[-1];local=piece_time(piece)
    if t<float(sum((piece_time(p) for p in plan.pieces),F(0))):
        for p in plan.pieces:
            H=piece_time(p)
            if remaining<=H:piece=p;local=remaining;break
            remaining-=H
    H=piece_time(piece);s=local/H
    return [[eval_poly(derivative(c,d),s)/H**d for c in piece.coefficients] for d in range(3)]

@dataclass(frozen=True)
class ExactPiece(Piece):
    """Exact restricted domain plus its binary64 public duration display."""
    exact_duration:F|None=None
    def __post_init__(self):
        super().__post_init__()
        if self.exact_duration is None:object.__setattr__(self,'exact_duration',F(float(self.duration)))
        else:object.__setattr__(self,'exact_duration',F(self.exact_duration))
        if self.exact_duration<=0 or float(self.exact_duration)!=self.duration:raise ValueError('EXACT_DURATION_DISPLAY_MISMATCH')
    def sample(self,t):
        if t<0 or t>self.duration:raise ValueError('time outside exactpiece')
        H=piece_time(self);s=F(1) if t==self.duration else F(float(t))/H
        return State(*[[float(eval_poly(derivative(c,d),s)/H**d) for c in self.coefficients] for d in range(3)])

@dataclass(frozen=True)
class ExactPlan(Plan):
    @property
    def duration(self):return float(sum((piece_time(p) for p in self.pieces),F(0)))
    def sample(self,t):return State(*[[float(x) for x in row] for row in exact_plan_state(self,t)])
    def suffix(self,t):
        if not np.isfinite(t) or t<0 or t>=self.duration:raise ValueError('suffix outside active exactplan')
        return ExactPlan(restricted_pieces(self.pieces,F(float(t))))

@dataclass(frozen=True)
class ExactSchedule(PolynomialSchedule):
    version:str='stage1g_exact_duration_v4'
    endpoint_native_steps:int|None=None
    def __post_init__(self):
        if not isinstance(self.plan,ExactPlan):object.__setattr__(self,'plan',ExactPlan(self.plan.pieces))
    @property
    def digest(self):return hashlib.sha256((super().digest+repr(self.endpoint_native_steps)).encode()).hexdigest()
    @property
    def duration_s(self):return float(sum((piece_time(p) for p in self.plan.pieces),F(0)))
    def suffix(self,elapsed):
        if not np.isfinite(elapsed) or elapsed<0 or elapsed>=self.duration_s:raise ValueError('suffix outside active exactplan')
        return replace(self,plan=ExactPlan(restricted_pieces(self.plan.pieces,F(float(elapsed)))),endpoint_native_steps=None)
    def sample(self,t):
        # The binary64 declared endpoint denotes the exact terminal identity.
        # Interior events denote their issued binary64 time exactly. Neither
        # acquired states nor sensor/phase/resource clocks are changed.
        progress=exact_plan_state(self.plan,t)
        values=[]
        for d in range(3):
            row=[]
            for j,x in enumerate(progress[d]):
                v=F(float(self.coordinates.sign[j]))*x
                if d==0:v+=F(float(self.coordinates.start[j]))
                row.append(float(v))
            values.append(np.array(row))
        return ScheduledHumanReferenceSample(*values)
    def bounds(self,derivative=0,offset=None):
        # Exact Bernstein enclosure of the SAME time-scaled polynomial.
        # This public protocol is conservative; acceptance uses certify_motion.
        shift=np.zeros(2) if offset is None else np.asarray(offset);low=[];high=[]
        for j in range(2):
            cells=[]
            for p in self.plan.pieces:
                co=[F(float(self.coordinates.sign[j]))*x/piece_time(p)**derivative for x in globals()['derivative'](p.coefficients[j],derivative)]
                if derivative==0:co[0]+=F(float(self.coordinates.start[j]))+F(float(shift[j]))
                cells.extend(bounds(co,F(k,16),F(k+1,16)) for k in range(16))
            a=min(x[0] for x in cells);b=max(x[1] for x in cells);af=float(a);bf=float(b)
            low.append(np.nextafter(af,-np.inf) if F(af)>a else af)
            high.append(np.nextafter(bf,np.inf) if F(bf)<b else bf)
        return np.asarray(low),np.asarray(high)

def convert(s):return ExactSchedule(s.plan,s.coordinates,s.candidate,s.reference_period_s)

def polynomial_in_bounds(c,lower,upper,max_depth=18):
    pending=[(F(0),F(1),0)];cells=0
    while pending:
        a,b,d=pending.pop();lo,hi=bounds(c,a,b);cells+=1
        if lo>=lower and hi<=upper:continue
        for t in (a,b,(a+b)/2):
            v=eval_poly(c,t)
            if v<lower or v>upper:return dict(status='REFUTED',cells=cells,at=str(t),value=str(v),bounds=[str(lower),str(upper)])
        if d==max_depth:
            # An interior even root can make Bernstein lower bounds negative
            # at every finite subdivision depth despite true nonnegativity.
            # Decide the SAME closed polynomial inequalities exactly; no slack.
            from exact_nonnegative import in_bounds
            return dict(cells=cells,bernstein_status='UNKNOWN',**in_bounds(c,lower,upper))
        m=(a+b)/2;pending.extend([(a,m,d+1),(m,b,d+1)])
    return dict(status='CERTIFIED',cells=cells)

def certify_motion(s,sch,b,offset=(0.,0.),monotone=True):
    spec=sch.spec;model=b.human_model();rom=np.c_[np.maximum(np.asarray(spec.q_bounds_rad)[:,0],model.q_min_rad),np.minimum(np.asarray(spec.q_bounds_rad)[:,1],model.q_max_rad)]
    rows=[];joins=[]
    for index,p in enumerate(s.plan.pieces):
        H=piece_time(p)
        for j,c in enumerate(p.coefficients):
            q=[F(float(s.coordinates.sign[j]))*F(x) for x in c];q[0]+=F(float(s.coordinates.start[j]))+F(float(offset[j]))
            vm=F(float(spec.task_joint_velocity_limit_rad_s[j]*sch.reference_velocity_fraction))
            # The emitted position is rounded once, then the predictor adds
            # its current binary64 tracking offset. Enclose both operations.
            qlo,qhi=bounds(q,F(0),F(1));rounding=F(float(8*np.spacing(max(1.,abs(float(qlo)),abs(float(qhi)),abs(float(offset[j])))))) if offset[j]!=0 else F(0)
            for label,co,lo,hi in [('rom',q,F(float(rom[j,0]))+rounding,F(float(rom[j,1]))-rounding),('monotone_velocity',[v/H for v in derivative(c,1)],F(0) if monotone else -vm,vm),('acceleration',[v/H**2 for v in derivative(c,2)],-F(float(spec.task_joint_acceleration_limit_rad_s2[j]*sch.reference_acceleration_fraction)),F(float(spec.task_joint_acceleration_limit_rad_s2[j]*sch.reference_acceleration_fraction)))]:
                row=polynomial_in_bounds(co,lo,hi);rows.append(dict(piece=index,axis=j,quantity=label,**row))
        if index:
            previous=s.plan.pieces[index-1];K=piece_time(previous)
            delta=[[abs(eval_poly(derivative(previous.coefficients[j],d),F(1))/K**d-eval_poly(derivative(p.coefficients[j],d),F(0))/H**d) for j in range(2)] for d in range(3)]
            joins.append(dict(exact=all(v==0 for row in delta for v in row),within_original_c2=all(v<=F(1e-10) for row in delta for v in row),deltas=[[str(v) for v in row] for row in delta]))
    progress=certify_joint_progress(s,spec) if monotone else dict(accepted=True,scope='explicit safety stop; normal no-rest/restart rule not applied')
    return dict(accepted=all(r['status']=='CERTIFIED' for r in rows) and all(r['within_original_c2'] for r in joins) and progress['accepted'],rows=rows,joins=joins,joint_progress=progress,velocity_acceleration_output_rounding='single correctly rounded rational-to-binary64 conversion; bounds are binary64 endpoints so rounding cannot cross them',c2_tolerance='unchanged original1e-10',geometry_roundoff_separate=True)


def certify_joint_progress(s,spec):
    """Repair the existing normal no-internal-joint-rest rule exactly.

    reference_kernel.certify already disallows simultaneous internal rest and
    rest/restart joins before the endpoint. Its float endpoint zero test can
    miss exact polynomial zeros. Terminal holds use the original legal
    terminal set and add no minimum velocity. Explicit safety stops skip it.
    """
    from exact_nonnegative import trim,gcd,interior_roots
    from traction_mpc_stage5.task import at_goal
    def velocities(piece):return [trim([F(float(s.coordinates.sign[j]))*v for v in derivative(c,1)]) for j,c in enumerate(piece.coefficients)]
    def stationary_from(index):return all(v==[0] for piece in s.plan.pieces[index:] for v in velocities(piece))
    def at_endpoint(piece,t):
        q=[F(float(s.coordinates.start[j]))+F(float(s.coordinates.sign[j]))*eval_poly(c,t) for j,c in enumerate(piece.coefficients)]
        return at_goal(spec,np.array([float(v) for v in q]),np.zeros(2),s.candidate.phase_goal_rad)
    for i,p in enumerate(s.plan.pieces):
        vel=velocities(p)
        if i and all(eval_poly(v,F(0))==0 for v in vel) and (not at_endpoint(p,F(0)) or not stationary_from(i)):
            return dict(accepted=False,reason='SIMULTANEOUS_REST_AT_JOIN_START',piece=i)
        if all(v==[0] for v in vel):
            if not at_endpoint(p,F(0)) or not stationary_from(i):return dict(accepted=False,reason='INCOMPLETE_OR_RESTARTING_SIMULTANEOUS_CONSTANT_HOLD',piece=i)
        else:
            common=gcd(*vel)
            roots=interior_roots(common,F(0),F(1))
            if roots:return dict(accepted=False,reason='SIMULTANEOUS_INTERNAL_VELOCITY_ZERO',piece=i,exact_roots=roots)
        if i<len(s.plan.pieces)-1 and all(eval_poly(v,F(1))==0 for v in vel) and (not at_endpoint(p,F(1)) or not stationary_from(i+1)):
            return dict(accepted=False,reason='INCOMPLETE_SIMULTANEOUS_REST_AT_JOIN',piece=i)
    return dict(accepted=True,scope='exact internal joint-rest and join tests; single-axis holds and original-terminal-set final holds retained',terminal_set='original task.at_goal with exactzero velocity; all subsequent pieces stationary')
