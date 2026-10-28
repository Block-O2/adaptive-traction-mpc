"""Local acceleration-aware state-to-state research action realization.

No intermediate waypoints, cloud client, Human actuation or phase synchronization.
Certification callbacks are mandatory; this module alone is not a safety controller.
"""
from dataclasses import dataclass
import math,time
import numpy as np
import ruckig
import hashlib
from ..human_waypoint_scheduler import ScheduledHumanReferenceSample
from ..human_waypoint_shadow import HumanWaypointCandidate
from ..architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22
from .rigid_table_reference import SLEEVE_OUTER_RADIUS_M

def vector(x):
    x=np.asarray(x,dtype=float)
    if x.shape!=(2,) or not np.all(np.isfinite(x)):raise ValueError('finite joint pair required')
    return x.copy()

@dataclass(frozen=True)
class OnlineSchedule:
    trajectory: object
    candidate: object
    start_q_rad: np.ndarray
    start_dq_rad_s: np.ndarray
    start_ddq_rad_s2: np.ndarray
    maximum_reference_velocity_rad_s: np.ndarray
    maximum_reference_acceleration_rad_s2: np.ndarray
    maximum_reference_jerk_rad_s3: np.ndarray
    duration_s: float
    reference_period_s: float=.005
    version: str='local_ruckig_0.12.2_online_v1'
    def sample(self,t):
        if not np.isfinite(t) or t<0:raise ValueError('invalid elapsed time')
        q,v,a=self.trajectory.at_time(min(float(t),self.duration_s))
        return ScheduledHumanReferenceSample(np.array(q),np.array(v),np.array(a))
    def record(self):
        return dict(version=self.version,duration_s=self.duration_s,start_q_rad=self.start_q_rad.tolist(),start_dq_rad_s=self.start_dq_rad_s.tolist(),start_ddq_rad_s2=self.start_ddq_rad_s2.tolist(),target_q_rad=self.candidate.q_waypoint_rad.tolist(),target_dq_rad_s=self.candidate.dq_waypoint_rad_s.tolist(),max_velocity=self.maximum_reference_velocity_rad_s.tolist(),max_acceleration=self.maximum_reference_acceleration_rad_s2.tolist(),max_jerk=self.maximum_reference_jerk_rad_s3.tolist(),synchronization='None',local_only=True)

@dataclass(frozen=True)
class RemainingContinuation:
    original: object
    offset_s: float
    @property
    def duration_s(self):return max(self.original.reference_period_s,self.original.duration_s-self.offset_s)
    def sample(self,t):return self.original.sample(min(self.original.duration_s,self.offset_s+float(t)))
    def __getattr__(self,name):return getattr(self.original,name)

def realize(state,target,*,spec,phase,max_velocity,max_acceleration,max_jerk,dt=.005,label='online_intent'):
    q,v,a=(vector(x) for x in state);target=vector(target)
    vmax,amax,jmax=(vector(x) for x in (max_velocity,max_acceleration,max_jerk))
    if any(np.any(x<=0) for x in (vmax,amax,jmax)):raise ValueError('positive limits required')
    bounds=np.asarray(spec.q_bounds_rad)
    if np.any(target<bounds[:,0]) or np.any(target>bounds[:,1]):raise ValueError('TARGET_OUTSIDE_ROM')
    inp=ruckig.InputParameter(2)
    inp.current_position=q.tolist();inp.current_velocity=v.tolist();inp.current_acceleration=a.tolist()
    inp.target_position=target.tolist();inp.target_velocity=[0.,0.];inp.target_acceleration=[0.,0.]
    inp.max_velocity=vmax.tolist();inp.max_acceleration=amax.tolist();inp.max_jerk=jmax.tolist()
    inp.synchronization=ruckig.Synchronization.No
    trajectory=ruckig.Trajectory(2);otg=ruckig.Ruckig(2,dt)
    result=otg.calculate(inp,trajectory)
    if result not in (ruckig.Result.Working,ruckig.Result.Finished):raise ValueError('OTG_'+str(result))
    extrema=trajectory.position_extrema
    if any(x.min<bounds[i,0]-1e-10 or x.max>bounds[i,1]+1e-10 for i,x in enumerate(extrema)):raise ValueError('CONTINUATION_OUTSIDE_ROM')
    phase_goal=np.asarray(spec.start_return_target_rad if phase.value=='RETURN' else spec.outbound_goal_target_rad)
    candidate=HumanWaypointCandidate(label=label,phase=phase,phase_goal_rad=phase_goal,q_waypoint_rad=target,dq_waypoint_rad_s=np.zeros(2))
    return OnlineSchedule(trajectory,candidate,q,v,a,vmax,amax,jmax,max(float(trajectory.duration),dt),dt)

def clearance_certificate(schedule,clearance,*,max_cell_s=.002,q_offset=None):
    """Extend existing envelope Lipschitz proof to arbitrary bounded OTG paths.

    Existing geometry, body margins and length priors are used unchanged. Bounds
    use global OTG velocity limits rather than quintic derivative extrema.
    """
    envelope=clearance.envelope;g=envelope.geometry
    count=max(3,int(math.ceil(schedule.duration_s/max_cell_s))+1)
    t=np.linspace(0.,schedule.duration_s,count);q=np.array([schedule.sample(float(x)).q_rad for x in t])
    offset=np.zeros(2) if q_offset is None else vector(q_offset);q+=offset
    margins=envelope.margins(q)
    half_cell=schedule.duration_s/(count-1)/2.
    v=schedule.maximum_reference_velocity_rad_s
    thigh=half_cell*g.thigh_length_m*v[0]
    limb=half_cell*(g.thigh_length_m*v[0]+(envelope.shank_length_upper_m+SLEEVE_OUTER_RADIUS_M)*sum(v))
    extrema=schedule.trajectory.position_extrema[0]
    if extrema.min+offset[0]>=0 and extrema.max+offset[0]<=math.pi and abs(g.plane_x_world[2])<1e-9 and g.plane_z_world[2]>0:thigh=0.
    lowers={name:float(np.min(value))-(thigh if name=='proximal_thigh_m' else limb) for name,value in margins.items()}
    # Combined constructor guarantees retained distal-shank formula equivalence.
    return dict(feasible=all(np.isfinite(x) and x>=0. for x in lowers.values()),combined_body_lowers_m=lowers,sample_count=count,max_cell_s=schedule.duration_s/(count-1),lipschitz_bound_m=limb,method='existing_body_margins_plus_OTG_global_velocity_Lipschitz',full_horizon_s=schedule.duration_s,threshold_m=0.)

def validate_online_activation(*,schedule,owned_state,belief,clearance,phase,remaining_s,spec=None,tracking_error=None):
    started=time.perf_counter();first=schedule.sample(0.)
    jumps=[float(np.max(np.abs(x-y))) for x,y in zip((first.q_rad,first.dq_rad_s,first.ddq_rad_s2),owned_state)]
    geometry=clearance_certificate(schedule,clearance)
    mechanics=AdaptiveMechanicsScreenV22().evaluate(belief,schedule.candidate,schedule)
    floor=0. if spec is None else max(0.,float(np.min(clearance.evaluate(np.vstack([spec.start_return_target_rad,schedule.candidate.phase_goal_rad])))))
    geometry['required_endpoint_clearance_floor_m']=floor
    geometry['feasible']=geometry['feasible'] and min(geometry['combined_body_lowers_m'].values())>=floor
    shifted=None if tracking_error is None else clearance_certificate(schedule,clearance,q_offset=tracking_error)
    finite=np.all(np.isfinite(jumps));c2=finite and max(jumps)<=1e-10
    accepted=bool(c2 and geometry['feasible'] and (shifted is None or shifted['feasible']) and mechanics['feasible'] and schedule.candidate.phase is phase and schedule.duration_s<=remaining_s+1e-12)
    return dict(feasible=accepted,C2=c2,jumps=jumps,current_geometry=geometry,causal_tracking_offset_clearance=shifted,current_model_mechanics=mechanics,belief_sequence=belief.sequence,remaining_phase_time_s=remaining_s,full_continuation_to_zero_velocity_acceleration=True,validation_ms=1000*(time.perf_counter()-started),truth_consumed=False)

class OnlineReferenceOwner:
    """Short prefix ownership with explicit activation times and retained continuation."""
    def __init__(self,initial,*,epoch_s=0.,dt=.005,initial_schedule=None):
        self.state=tuple(vector(x) for x in initial);self.epoch_s=float(epoch_s);self.dt=dt
        self.schedule=None;self.schedule_epoch_s=self.epoch_s;self.target=None;self.certificate=None;self.records=[]
        self.owned_segments=[];self.model_key=None;self.last_received_s=self.epoch_s
        if initial_schedule is not None:
            sample=initial_schedule.sample(0.)
            if any(np.max(np.abs(x-y))>1e-10 for x,y in zip(self.state,(sample.q_rad,sample.dq_rad_s,sample.ddq_rad_s2))):raise ValueError('INITIAL_CONTINUATION_C2_MISMATCH')
            self.schedule=initial_schedule;self.target=initial_schedule.candidate.q_waypoint_rad.copy()
            self.owned_segments=[(self.epoch_s,initial_schedule)]
    def sample(self,t):
        if t<self.epoch_s-1e-12:raise ValueError('NO_REFERENCE_BACKDATING')
        for epoch,schedule in reversed(self.owned_segments):
            if t>=epoch-1e-12:return schedule.sample(max(0.,t-epoch))
        if t>self.epoch_s+1e-12 and any(np.any(x!=0) for x in self.state[1:]):raise ValueError('MOVING_INITIAL_STATE_REQUIRES_OWNED_CONTINUATION')
        return ScheduledHumanReferenceSample(*self.state)
    def offer(self,target,*,received_s,ready_s,requested_s,spec,phase,remaining_s,belief,clearance,max_velocity,max_acceleration,max_jerk,tracking_error=None):
        if not all(np.isfinite(x) for x in (received_s,ready_s,requested_s)) or ready_s<received_s:raise ValueError('INVALID_COMMAND_TIMESTAMPS')
        if received_s<self.last_received_s-1e-12:raise ValueError('OUT_OF_ORDER_COMMAND_RECEIPT')
        self.last_received_s=received_s
        boundary=self.epoch_s+math.ceil(max(0.,max(received_s,ready_s,requested_s)-self.epoch_s)/self.dt-1e-10)*self.dt
        old=self.sample(boundary);owned=(old.q_rad,old.dq_rad_s,old.ddq_rad_s2)
        target=vector(target);start=time.perf_counter()
        row=dict(command_received_s=received_s,command_ready_s=ready_s,requested_boundary_s=requested_s,actual_activation_s=boundary,late=ready_s>requested_s+1e-12,target_rad=target.tolist(),status=None,first_reference_effect_s=None)
        from .activation_validation import clearance_geometry_signature
        key=hashlib.sha256(np.asarray(belief.beta,dtype='<f8').tobytes()+np.asarray(belief.state_residual_weights_nm,dtype='<f8').tobytes()+clearance_geometry_signature(clearance).encode()).hexdigest()
        if self.schedule is not None and key!=self.model_key:
            # Existing continuation must also survive the current model update.
            continuation=RemainingContinuation(self.schedule,max(0.,boundary-self.schedule_epoch_s))
            first=continuation.sample(0.)
            current=validate_online_activation(schedule=continuation,owned_state=(first.q_rad,first.dq_rad_s,first.ddq_rad_s2),belief=belief,clearance=clearance,phase=phase,remaining_s=remaining_s-(boundary-received_s),spec=spec,tracking_error=tracking_error)
            if not current['feasible']:
                row.update(status='BLOCKED_CONTINUATION_INVALIDATED',reason='CURRENT_MODEL_REQUIRES_NEW_SAFE_FALLBACK',activation_validation=current)
                self.records.append(row);return row
            self.model_key=key;self.certificate=current
        if self.schedule is not None and np.array_equal(target,self.target):
            # Identical commands retain the exact already owned OTG, without any restart.
            row.update(status='IDENTICAL_CONTINUATION',acceleration_reset=False)
            self.records.append(row);return row
        try:
            proposed=realize(owned,target,spec=spec,phase=phase,max_velocity=max_velocity,max_acceleration=max_acceleration,max_jerk=max_jerk,dt=self.dt)
            cert=validate_online_activation(schedule=proposed,owned_state=owned,belief=belief,clearance=clearance,phase=phase,remaining_s=remaining_s-(boundary-received_s),spec=spec,tracking_error=tracking_error)
            row['activation_validation']=cert
            if not cert['feasible']:raise ValueError('FULL_CONTINUATION_CERTIFICATION_REJECTED')
            previous=self.schedule;previous_epoch=self.schedule_epoch_s
            if previous is None:row['first_reference_effect_s']=boundary+self.dt
            for k in range(1,int(math.ceil(proposed.duration_s/self.dt))+1) if previous is not None else ():
                t=boundary+k*self.dt;new=proposed.sample(k*self.dt);before=self.sample(t)
                if max(np.max(np.abs(x-y)) for x,y in zip((new.q_rad,new.dq_rad_s,new.ddq_rad_s2),(before.q_rad,before.dq_rad_s,before.ddq_rad_s2)))>1e-10:
                    row['first_reference_effect_s']=t;break
            self.schedule=proposed;self.schedule_epoch_s=boundary;self.target=target;self.certificate=cert
            self.owned_segments.append((boundary,proposed));self.model_key=key
            # Retain the previous committed prefix until future activation, then
            # discard old segments only after their successor is already owned.
            while len(self.owned_segments)>2 and self.owned_segments[1][0]<=received_s:self.owned_segments.pop(0)
            row.update(status='ACCEPTED',reference_effect_latency_s=None if row['first_reference_effect_s'] is None else row['first_reference_effect_s']-received_s,old_endpoint_s=None if previous is None else previous_epoch+previous.duration_s,acceleration_reset=False)
        except (ValueError,RuntimeError) as error:row.update(status='REJECTED_CONTINUE_CERTIFIED',reason=str(error))
        row['host_realization_ms']=1000*(time.perf_counter()-start);self.records.append(row);return row
