"""Dimensionless differential commands, explicit C2 realization and feasibility.

An action is a scalar or an arbitrary number of phase-progress knots. The
request is piecewise linear; execution is a declared quintic C2 interpolation
through the same knots. No target, progress, or amplitude clipping is used.
"""
from dataclasses import dataclass, asdict
import numpy as np
from scipy.interpolate import BPoly, PPoly
from traction_mpc_stage5.human_waypoint_scheduler import ScheduledHumanReferenceSample
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22

@dataclass(frozen=True)
class ResidualAction:
 phase:str
 current_progress:float
 current_state:tuple  # d, dd/ds, d2d/ds2 at activation
 knots:tuple          # future (normalized phase-clock location, residual)
 horizon:float
 version:str='coordination_residual_pwl_C2_v1'
 provenance:str='declared_research_command'
 def __post_init__(self):
  if self.phase not in ('OUTBOUND','RETURN'):raise ValueError('HOLD_ACTION_DISABLED')
  vals=np.array([self.current_progress,*self.current_state,self.horizon,*[v for k in self.knots for v in k]],float)
  if not np.all(np.isfinite(vals)) or len(self.current_state)!=3:raise ValueError('NONFINITE_ACTION')
  if not 0<=self.current_progress<self.horizon<=1:raise ValueError('INVALID_HORIZON')
  xs=[self.current_progress]+[k[0] for k in self.knots]
  if len(xs)<2 or any(b<=a for a,b in zip(xs,xs[1:])) or xs[-1]!=self.horizon:raise ValueError('INVALID_KNOT_LOCATIONS')
  if self.horizon==1 and self.knots[-1][1]!=0:raise ValueError('ENDPOINT_RESIDUAL_MUST_BE_ZERO')
  if self.current_progress==0 and any(self.current_state):raise ValueError('PHASE_START_REQUIRES_ZERO_C2_STATE')
 @classmethod
 def scalar(cls,phase,s,state,value,horizon,provenance='scalar'):
  if horizon>=1:raise ValueError('SCALAR_NEEDS_CATCHUP_HORIZON_BEFORE_ENDPOINT')
  return cls(phase,s,tuple(state),((horizon,float(value)),(1.,0.)),1.,provenance=provenance)
 def record(self):return asdict(self)
 def realize(self):
  xs=[self.current_progress]+[k[0] for k in self.knots]
  ds=[list(self.current_state)]+[[v,0.,0.] for _,v in self.knots]
  if self.horizon<1:
   if any(ds[-1]):raise ValueError('CHUNK_REQUIRES_ZERO_C2_CONTINUATION_BOUNDARY')
   xs.append(1.);ds.append([0.,0.,0.])
  return BPoly.from_derivatives(xs,ds,extrapolate=False)

class PhaseTape:
 def __init__(self,phase,t,q,v,a,span):
  self.phase=phase;self.t=np.asarray(t,float);self.duration_s=float(self.t[-1]);self.span=np.asarray(span,float)
  self.base=BPoly.from_derivatives(self.t,[[qi,vi,ai] for qi,vi,ai in zip(q,v,a)],extrapolate=False)
  self.q=np.asarray(q);self.v=np.asarray(v);self.a=np.asarray(a)
 def sample(self,t):
  if t<0:raise ValueError('NO_BACKDATED_REFERENCE')
  u=min(t,self.duration_s)
  if t>self.duration_s:return ScheduledHumanReferenceSample(self.q[-1].copy(),np.zeros(2),np.zeros(2))
  return ScheduledHumanReferenceSample(np.asarray(self.base(u)),np.asarray(self.base(u,1)),np.asarray(self.base(u,2)))

class DifferentialSchedule:
 def __init__(self,tape,action,spec,phase,*,offset_s=0.):
  self.tape=tape;self.action=action;self.offset_s=float(offset_s);self.duration_s=tape.duration_s-self.offset_s
  self.reference_period_s=.005;self.span=tape.span
  self.residual=None if action is None else action.realize()
  self.maximum_reference_velocity_rad_s=np.asarray(spec.task_joint_velocity_limit_rad_s)
  self.candidate=HumanWaypointCandidate(label='B_pacing_coordination_v1',phase=phase,phase_goal_rad=np.asarray(spec.start_return_target_rad if phase.value=='RETURN' else spec.outbound_goal_target_rad),q_waypoint_rad=tape.q[-1].copy(),dq_waypoint_rad_s=np.zeros(2))
  self.poly=self._poly()
 def sample(self,t):
  absolute=self.offset_s+max(0.,float(t));b=self.tape.sample(absolute)
  if self.residual is None:return b
  s=min(absolute/self.tape.duration_s,1.)
  # Prefixes are owned by the preceding schedule; this schedule starts at its
  # explicit current-progress C2 state.
  z=np.array([float(self.residual(s,j))/self.tape.duration_s**j for j in range(3)])
  if not np.all(np.isfinite(z)):raise ValueError('RESIDUAL_OUTSIDE_DECLARED_CHUNK')
  direction=self.span*np.array([1.,-1.])
  return ScheduledHumanReferenceSample(b.q_rad+direction*z[0],b.dq_rad_s+direction*z[1],b.ddq_rad_s2+direction*z[2])
 def residual_state(self,absolute):
  if self.residual is None:return (0.,0.,0.)
  return tuple(float(self.residual(min(absolute/self.tape.duration_s,1.),j)) for j in range(3))
 def _poly(self):
  # Repartition at ALL B and residual knots; derivatives determine exact quintics.
  cuts=self.tape.t[self.tape.t>=self.offset_s-1e-12].tolist()+[self.offset_s,self.tape.duration_s]
  if self.action is not None:cuts += [x*self.tape.duration_s for x,_ in self.action.knots]
  xs=np.unique(cuts);ds=[]
  for t in xs:
   b=self.sample(t-self.offset_s);ds.append([b.q_rad,b.dq_rad_s,b.ddq_rad_s2])
  return PPoly.from_bernstein_basis(BPoly.from_derivatives(xs,ds,extrapolate=False))
 def extrema(self,order):
  pp=self.poly.derivative(order);low=[];high=[]
  for joint in range(2):
   one=PPoly(pp.c[:,:,joint],pp.x,extrapolate=False);points=np.r_[pp.x,one.derivative().roots(extrapolate=False)];points=points[np.isfinite(points)]
   y=one(points);low.append(float(np.min(y)));high.append(float(np.max(y)))
  return np.array(low),np.array(high)

def certify(schedule,*,spec,belief,clearance,owned,scheduler,tracking_error=None):
 first=schedule.sample(0.);jumps=[float(np.max(np.abs(x-y))) for x,y in zip((first.q_rad,first.dq_rad_s,first.ddq_rad_s2),owned)]
 bounds=np.asarray(spec.q_bounds_rad);qlo,qhi=schedule.extrema(0)
 limits=[np.asarray(spec.task_joint_velocity_limit_rad_s)*scheduler.reference_velocity_fraction,np.asarray(spec.task_joint_acceleration_limit_rad_s2)*scheduler.reference_acceleration_fraction]
 limits.append(limits[1]/.020)
 derivatives=[]
 for order,limit in enumerate(limits,1):
  lo,hi=schedule.extrema(order);peak=np.maximum(np.abs(lo),np.abs(hi));derivatives.append(dict(order=order,peak=peak.tolist(),limit=limit.tolist(),feasible=bool(np.all(peak<=limit+1e-7))))
 # Exact normalized feasibility relative to the retained B phase endpoints.
 # The nominal task arrival box remains separate and unchanged.
 origin=schedule.tape.q[0];span=schedule.span
 plo=np.minimum((qlo-origin)/span,(qhi-origin)/span);phi=np.maximum((qlo-origin)/span,(qhi-origin)/span)
 progress_ok=bool(np.all(plo>=-1e-8) and np.all(phi<=1+1e-8))
 geometry=geometry_certificate(schedule,clearance)
 shifted=None if tracking_error is None else geometry_certificate(schedule,clearance,tracking_error)
 mechanics=AdaptiveMechanicsScreenV22().evaluate(belief,schedule.candidate,schedule)
 floor=max(0.,float(np.min(clearance.evaluate(np.vstack([spec.start_return_target_rad,schedule.candidate.phase_goal_rad])))))
 geometry['required_endpoint_clearance_floor_m']=floor
 geometry['feasible']=geometry['feasible'] and min(geometry['combined_body_lowers_m'].values())>=floor-1e-12
 feasible=bool(max(jumps)<=1e-10 and np.all(qlo>=bounds[:,0]-1e-10) and np.all(qhi<=bounds[:,1]+1e-10) and progress_ok and all(x['feasible'] for x in derivatives) and geometry['feasible'] and (shifted is None or shifted['feasible']) and mechanics['feasible'])
 return dict(feasible=feasible,C2=max(jumps)<=1e-10,jumps=jumps,ROM=[qlo.tolist(),qhi.tolist()],normalized_progress=[plo.tolist(),phi.tolist()],progress_feasible=progress_ok,derivatives=derivatives,current_geometry=geometry,causal_tracking_offset_clearance=shifted,current_model_mechanics=mechanics,truth_consumed=False)

def geometry_certificate(schedule,clearance,offset=None):
 # Existing body margins, with a per-cell bound on the EXACT polynomial
 # velocity instead of an unnecessarily loose global-velocity bound.
 cuts=np.unique(np.r_[schedule.poly.x,np.linspace(schedule.offset_s,schedule.tape.duration_s,int(np.ceil(schedule.duration_s/.002))+1)])
 q=schedule.poly(cuts)+(np.zeros(2) if offset is None else offset)
 margins=clearance.envelope.margins(q);g=clearance.envelope.geometry
 centers=(cuts[1:]+cuts[:-1])/2;dt=np.diff(cuts)/2
 pp=schedule.poly.derivative(1);vel=np.maximum(np.abs(pp(cuts[:-1])),np.abs(pp(cuts[1:])))
 # Cell derivative extrema guarantee validity, including interior extrema.
 for j in range(2):
  one=PPoly(pp.c[:,:,j],pp.x,extrapolate=False)
  roots=one.derivative().roots(extrapolate=False);roots=roots[np.isfinite(roots)]
  ix=np.searchsorted(cuts,roots,side='right')-1;ok=(ix>=0)&(ix<len(vel))
  np.maximum.at(vel[:,j],ix[ok],np.abs(one(roots[ok])))
 proximal=dt*g.thigh_length_m*vel[:,0]
 limb=dt*(g.thigh_length_m*vel[:,0]+(clearance.envelope.shank_length_upper_m+.045)*np.sum(vel,axis=1))
 # Use the original sleeve radius constant, never an invented margin.
 from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import SLEEVE_OUTER_RADIUS_M
 limb=dt*(g.thigh_length_m*vel[:,0]+(clearance.envelope.shank_length_upper_m+SLEEVE_OUTER_RADIUS_M)*np.sum(vel,axis=1))
 lo={name:float(np.min(np.minimum(value[:-1],value[1:])-(proximal if name=='proximal_thigh_m' else limb))) for name,value in margins.items()}
 return dict(feasible=all(np.isfinite(v) and v>=0 for v in lo.values()),combined_body_lowers_m=lo,method='unchanged_body_margins_exact_polynomial_cell_velocity_Lipschitz',threshold_m=0.,max_cell_s=float(np.max(np.diff(cuts))))
