"""Versioned immutable multi-quintic suffix. Reuses original safety kernels."""
from dataclasses import dataclass,replace,asdict,is_dataclass
from math import comb
import hashlib,json,math
import numpy as np
from ..human_waypoint_scheduler import (QuinticHumanWaypointSchedule,
    ScheduledHumanReferenceSample,_polynomial_extrema,_real_unit_roots)
from ..architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22
from ..task import TaskPhase

TOL=1e-10

def primitive(x):
    if is_dataclass(x):return primitive(asdict(x))
    if isinstance(x,dict):return {str(k):primitive(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [primitive(v) for v in x]
    if isinstance(x,np.ndarray):return primitive(x.tolist())
    if isinstance(x,np.generic):return primitive(x.item())
    if isinstance(x,TaskPhase):return x.value
    return x

def encode(x):return json.dumps(primitive(x),sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(encode(x).encode()).hexdigest()
def tup(x):return tuple(tuple(float(y) for y in row) for row in np.asarray(x))

@dataclass(frozen=True)
class FrozenCandidate:
    label:str
    phase:TaskPhase
    goal:tuple
    target:tuple
    velocity:tuple
    @property
    def phase_goal_rad(self):return np.asarray(self.goal)
    @property
    def q_waypoint_rad(self):return np.asarray(self.target)
    @property
    def dq_waypoint_rad_s(self):return np.asarray(self.velocity)
    @classmethod
    def freeze(cls,c):return cls(c.label,c.phase,tuple(c.phase_goal_rad),tuple(c.q_waypoint_rad),tuple(c.dq_waypoint_rad_s))

@dataclass(frozen=True)
class FrozenPolynomial:
    values:tuple
    duration_s:float
    candidate:FrozenCandidate
    metadata_json:str
    @property
    def coefficients(self):return np.asarray(self.values,dtype=float)
    @property
    def version(self):return json.loads(self.metadata_json)['version']
    @property
    def reference_period_s(self):return float(json.loads(self.metadata_json)['reference_period_s'])
    @property
    def start_q_rad(self):return self.coefficients[:,0]
    @property
    def start_dq_rad_s(self):return self.coefficients[:,1]/self.duration_s
    @property
    def maximum_reference_velocity_rad_s(self):return _polynomial_extrema(self.coefficients,self.duration_s)[0]
    @property
    def maximum_reference_acceleration_rad_s2(self):return _polynomial_extrema(self.coefficients,self.duration_s)[1]
    @property
    def continuous_clearance_certificate(self):return json.loads(self.metadata_json).get('continuous_clearance_certificate')
    def sample(self,t):return QuinticHumanWaypointSchedule.sample(self,t)
    def record(self):
        first,last=self.sample(0.),self.sample(self.duration_s)
        return dict(version=self.version,reference_period_s=self.reference_period_s,
            duration_s=self.duration_s,immutable_coefficients=self.values,
            start_q_rad=first.q_rad,start_dq_rad_s=first.dq_rad_s,start_ddq_rad_s2=first.ddq_rad_s2,
            target_q_rad=last.q_rad,target_dq_rad_s=last.dq_rad_s,target_ddq_rad_s2=last.ddq_rad_s2,
            maximum_reference_velocity_rad_s=self.maximum_reference_velocity_rad_s,
            maximum_reference_acceleration_rad_s2=self.maximum_reference_acceleration_rad_s2,
            original_source_metadata=json.loads(self.metadata_json))
    @classmethod
    def freeze(cls,s):return cls(tup(s.coefficients),float(s.duration_s),FrozenCandidate.freeze(s.candidate),encode(s.record()))

@dataclass(frozen=True)
class FrozenEscape:
    bridge:FrozenPolynomial
    stop:FrozenPolynomial
    commit_progress_s:float
    certificate_json:str
    @property
    def certificate(self):return json.loads(self.certificate_json)
    @classmethod
    def freeze(cls,e):return None if e is None else cls(FrozenPolynomial.freeze(e.bridge),FrozenPolynomial.freeze(e.stop),float(e.commit_progress_s),encode(e.certificate))

@dataclass(frozen=True)
class MultiSegmentReference:
    segments:tuple
    knots_s:tuple
    candidate:FrozenCandidate
    original:FrozenPolynomial
    canonical_zero:bool
    binding_json:str
    safe_escape:FrozenEscape|None
    path_certificate_json:str='{}'
    sealed_digest:str=''
    sealed_certificate_id:str=''
    @property
    def duration_s(self):return self.knots_s[-1]
    @property
    def reference_period_s(self):return self.original.reference_period_s
    @property
    def version(self):return 'multisegment_reference_v1/'+self.sealed_digest
    @property
    def start_q_rad(self):return self.segments[0].sample(0.).q_rad
    @property
    def start_dq_rad_s(self):return self.segments[0].sample(0.).dq_rad_s
    @property
    def certificate(self):return json.loads(self.path_certificate_json)
    @property
    def maximum_reference_velocity_rad_s(self):return np.max([p.maximum_reference_velocity_rad_s for p in self.segments],axis=0)
    @property
    def maximum_reference_acceleration_rad_s2(self):return np.max([p.maximum_reference_acceleration_rad_s2 for p in self.segments],axis=0)
    @property
    def maximum_causal_20ms_reference_acceleration_rad_s2(self):return self.causal_acceleration()
    @property
    def maximum_nominal_tracking_acceleration_rad_s2(self):return np.zeros(2)
    def content(self):
        return dict(schema='multisegment_reference_v1',segments=self.segments,knots_s=self.knots_s,candidate=self.candidate,original=self.original,canonical_zero=self.canonical_zero,binding=self.binding_json,safe_escape=self.safe_escape)
    def assert_integrity(self,require_certificate=True):
        if digest(self.content())!=self.sealed_digest:raise ValueError('MULTISEGMENT_CONTENT_ID_MISMATCH')
        if self.canonical_zero:
            for p,lo,hi in zip(self.segments,self.knots_s,self.knots_s[1:]):
                if not np.array_equal(p.coefficients,restrict(self.original.coefficients,self.duration_s,lo,hi)):raise ValueError('CANONICAL_ALIAS_NOT_EQUIVALENT')
        if require_certificate and (digest([self.sealed_digest,self.path_certificate_json])!=self.sealed_certificate_id or self.certificate.get('reference_id')!=self.sealed_digest or not self.certificate.get('feasible')):raise ValueError('MULTISEGMENT_CERTIFICATE_ID_MISMATCH')
    def sample(self,elapsed_s):
        if not math.isfinite(elapsed_s) or elapsed_s<0:raise ValueError('elapsed_s must be finite and nonnegative')
        t=min(float(elapsed_s),self.duration_s)
        # Exact polynomial-identity optimization, NOT endpoint compression.
        # Nonzero local updates are explicitly excluded from this route.
        if self.canonical_zero:return self.original.sample(t)
        index=min(len(self.segments)-1,int(np.searchsorted(self.knots_s,t,side='right')-1))
        return self.segments[max(0,index)].sample(max(0.,t-self.knots_s[max(0,index)]))
    def causal_acceleration(self):
        steps=int(math.ceil(self.duration_s/self.reference_period_s-1e-12));t=np.minimum(np.arange(steps+1)*self.reference_period_s,self.duration_s)
        v=np.asarray([self.sample(float(x)).dq_rad_s for x in t]);history_steps=int(round(.020/self.reference_period_s));extended=np.vstack([np.repeat(v[:1],history_steps,axis=0),v])
        return np.max(abs((extended[history_steps:]-extended[:-history_steps])/.020),axis=0)
    def record(self):
        return dict(version=self.version,method='immutable_piecewise_quintic_full_path_v1',phase=self.candidate.phase.value,duration_s=self.duration_s,reference_period_s=self.reference_period_s,start_q_rad=self.start_q_rad,start_dq_rad_s=self.start_dq_rad_s,target_q_rad=self.candidate.q_waypoint_rad,target_dq_rad_s=self.candidate.dq_waypoint_rad_s,knots_s=self.knots_s,segments=[p.record() for p in self.segments],canonical_zero_identity_evaluation=self.canonical_zero,reference_id=self.sealed_digest,certificate_id=self.sealed_certificate_id,path_certificate=self.certificate,binding=json.loads(self.binding_json),maximum_reference_velocity_rad_s=self.maximum_reference_velocity_rad_s,maximum_reference_acceleration_rad_s2=self.maximum_reference_acceleration_rad_s2,safe_escape_identity=digest(self.safe_escape),identity_payload=primitive(self.content()))

def restrict(c,T,lo,hi):
    u,h=lo/T,(hi-lo)/T;out=np.zeros((2,6))
    for k in range(6):
        for j in range(k+1):out[:,j]+=c[:,k]*comb(k,j)*u**(k-j)*h**j
    return out

def hermite(q0,v0,a0,q1,v1,a1,T):
    c=np.zeros((2,6));c[:,0]=q0;c[:,1]=T*v0;c[:,2]=.5*T*T*a0
    rhs=np.column_stack([q1-c[:,0]-c[:,1]-c[:,2],T*v1-c[:,1]-2*c[:,2],T*T*a1-2*c[:,2]])
    c[:,3:]=np.linalg.solve(np.array([[1.,1,1],[3,4,5],[6,12,20]]),rhs.T).T
    return c

def model_signature(belief):
    return digest(belief)

def extrema_q(c):
    bounds=[]
    for row in c:
        roots=_real_unit_roots(np.polynomial.polynomial.polyder(row)[::-1]);v=np.polynomial.polynomial.polyval(np.r_[0.,1.,roots],row);bounds.append([float(v.min()),float(v.max())])
    return np.asarray(bounds)

def geometry_path(schedule,clearance,*,offset=None,spec=None,model=None):
    pieces=schedule.segments;lowers=[];certificates=[];rom=True;offset=np.zeros(2) if offset is None else np.asarray(offset)
    for p in pieces:
        c=p.coefficients.copy();c[:,0]+=offset;bounds=extrema_q(c)
        if spec is not None:
            qb=np.asarray(spec.q_bounds_rad);hb=np.column_stack([model.q_min_rad,model.q_max_rad]);rom=rom and bool(np.all(bounds[:,0]>=qb[:,0]) and np.all(bounds[:,1]<=qb[:,1]) and np.all(bounds[:,0]>=hb[:,0]) and np.all(bounds[:,1]<=hb[:,1]))
        lower=float(clearance.certified_minimum(c,p.duration_s));lowers.append(lower);certificates.append(primitive(clearance.last_certificate))
    return dict(lower_m=min(lowers),per_piece_lower_m=lowers,rom=bool(rom),certificates=certificates,offset_rad=offset.tolist(),method='original CombinedRigidTableClearanceV1 each exact polynomial, union over closed intervals')

def certify_path(schedule,belief,clearance,*,spec,q_bounds,velocity_limits,acceleration_limits,preserve_endpoint_floor=True):
    from .activation_validation import clearance_geometry_signature
    schedule.assert_integrity(require_certificate=False)
    reasons=[];jumps=[];maxv=[];maxa=[];rom=True
    if len(schedule.knots_s)!=len(schedule.segments)+1 or schedule.knots_s[0]!=0 or any(b<=a for a,b in zip(schedule.knots_s,schedule.knots_s[1:])):reasons.append('INVALID_SEGMENT_TIME_PARTITION')
    for i,p in enumerate(schedule.segments):
        if abs(p.duration_s-(schedule.knots_s[i+1]-schedule.knots_s[i]))>1e-12:reasons.append('SEGMENT_DURATION_MISMATCH')
        c=p.coefficients
        if c.shape!=(2,6) or not np.all(np.isfinite(c)):raise ValueError('INVALID_MULTISEGMENT_COEFFICIENTS')
        bounds=extrema_q(c);hb=np.column_stack([belief.human_model().q_min_rad,belief.human_model().q_max_rad]);qb=np.asarray(q_bounds)
        rom=rom and bool(np.all(bounds[:,0]>=qb[:,0]) and np.all(bounds[:,1]<=qb[:,1]) and np.all(bounds[:,0]>=hb[:,0]) and np.all(bounds[:,1]<=hb[:,1]))
        v,a=_polynomial_extrema(c,p.duration_s);maxv.append(v);maxa.append(a)
        if i:
            x=schedule.segments[i-1].sample(schedule.segments[i-1].duration_s);y=p.sample(0.);jumps.append([float(np.max(abs(getattr(x,k)-getattr(y,k)))) for k in ['q_rad','dq_rad_s','ddq_rad_s2']])
    maxv=np.max(maxv,axis=0);maxa=np.max(maxa,axis=0);causal=schedule.causal_acceleration()
    if not rom:reasons.append('REFERENCE_ROM')
    if jumps and np.max(jumps)>TOL:reasons.append('INTERNAL_C2')
    first,last=schedule.sample(0.),schedule.sample(schedule.duration_s)
    if max(np.max(abs(first.ddq_rad_s2)),np.max(abs(last.ddq_rad_s2)))>TOL:reasons.append('OUTER_ACCELERATION_CONTRACT')
    if np.max(abs(last.q_rad-schedule.candidate.q_waypoint_rad))>TOL or np.max(abs(last.dq_rad_s-schedule.candidate.dq_waypoint_rad_s))>TOL:reasons.append('OUTER_TARGET_IDENTITY')
    if np.any(maxv>np.asarray(velocity_limits)+1e-12):reasons.append('REFERENCE_VELOCITY')
    if np.any(maxa>np.asarray(acceleration_limits)+1e-12) or np.any(causal>np.asarray(acceleration_limits)+1e-12):reasons.append('REFERENCE_ACCELERATION')
    geometry=geometry_path(schedule,clearance,spec=spec,model=belief.human_model())
    floor=max(0.,float(np.min(clearance.evaluate(np.vstack([spec.start_return_target_rad,schedule.candidate.phase_goal_rad]))))) if preserve_endpoint_floor else 0.
    if not geometry['rom'] or geometry['lower_m']<floor-1e-12:reasons.append('CONTINUOUS_CLEARANCE_OR_ROM')
    offset=np.asarray(json.loads(schedule.binding_json)['tracking_offset_rad']);shifted=geometry_path(schedule,clearance,offset=offset,spec=spec,model=belief.human_model())
    if not shifted['rom'] or shifted['lower_m']<0.:reasons.append('TRACKING_OFFSET_PATH')
    screen=AdaptiveMechanicsScreenV22();global_mechanics=screen.evaluate(belief,schedule.candidate,schedule);piece_mechanics=[screen.evaluate(belief,p.candidate,p) for p in schedule.segments]
    if not global_mechanics['feasible'] or not all(x['feasible'] for x in piece_mechanics):reasons.append('CURRENT_MODEL_MECHANICS')
    e=schedule.safe_escape;moving=bool(np.any(abs(last.dq_rad_s)>1e-12))
    escape=dict(required=moving,feasible=not moving)
    if moving:
        if e is None:reasons.append('MISSING_FUTURE_ESCAPE')
        else:
            entry=e.bridge.sample(0.);stopend=e.stop.sample(e.stop.duration_s)
            matches=all(np.max(abs(getattr(entry,k)-getattr(last,k)))<=TOL for k in ['q_rad','dq_rad_s','ddq_rad_s2'])
            existing=bool(e.certificate['geometry_signature']==clearance_geometry_signature(clearance) and matches and np.max(abs(stopend.dq_rad_s))<=TOL and np.max(abs(stopend.ddq_rad_s2))<=TOL)
            bm=screen.evaluate(belief,e.bridge.candidate,e.bridge);sm=screen.evaluate(belief,e.stop.candidate,e.stop)
            from types import SimpleNamespace
            bridge_path=geometry_path(SimpleNamespace(segments=(e.bridge,)),clearance,spec=spec,model=belief.human_model())
            stop_path=geometry_path(SimpleNamespace(segments=(e.stop,)),clearance,spec=spec,model=belief.human_model())
            shifted_stop=geometry_path(SimpleNamespace(segments=(e.stop,)),clearance,offset=offset,spec=spec,model=belief.human_model())
            stop_origin=e.stop.sample(0.);bridge_commit=e.bridge.sample(e.commit_progress_s)
            stop_c2=all(np.max(abs(getattr(stop_origin,k)-getattr(bridge_commit,k)))<=TOL for k in ['q_rad','dq_rad_s','ddq_rad_s2'])
            limits_valid=all(np.all(p.maximum_reference_velocity_rad_s<=np.asarray(velocity_limits)+1e-12) and np.all(p.maximum_reference_acceleration_rad_s2<=np.asarray(acceleration_limits)+1e-12) for p in [e.bridge,e.stop])
            future_path=bool(bridge_path['rom'] and stop_path['rom'] and shifted_stop['rom'] and min(bridge_path['lower_m'],stop_path['lower_m'],shifted_stop['lower_m'])>=0.)
            bridge_clock=bool(abs(e.bridge.duration_s-8*schedule.reference_period_s)<=1e-12 and 0<=e.commit_progress_s<e.bridge.duration_s and abs(e.commit_progress_s/schedule.reference_period_s-round(e.commit_progress_s/schedule.reference_period_s))<=1e-10)
            escape=dict(required=True,feasible=bool(existing and bm['feasible'] and sm['feasible'] and stop_c2 and limits_valid and future_path and bridge_clock),geometry_signature=e.certificate['geometry_signature'],boundary_match=matches,stop_C2=stop_c2,limits_valid=limits_valid,bridge_clock=bridge_clock,bridge_path=bridge_path,stop_path=stop_path,shifted_stop_path=shifted_stop,bridge_mechanics=bm,stop_mechanics=sm,commit_progress_s=e.commit_progress_s,stop_duration_s=e.stop.duration_s)
            if not escape['feasible']:reasons.append('FUTURE_ESCAPE_INVALID')
    return primitive(dict(schema='multisegment_path_certificate_v1',reference_id=schedule.sealed_digest,feasible=not reasons,reasons=reasons,model_sequence=belief.sequence,model_signature=model_signature(belief),geometry_signature=clearance_geometry_signature(clearance),q_bounds=q_bounds,velocity_limits=velocity_limits,acceleration_limits=acceleration_limits,max_velocity=maxv,max_acceleration=maxa,max_causal_20ms_acceleration=causal,joint_boundary_jumps=jumps,ROM_continuous=rom,geometry=geometry,endpoint_clearance_floor_m=floor,tracking_offset=shifted,global_mechanics=global_mechanics,piece_mechanics=piece_mechanics,escape=escape,mechanics_scope='original 21-sample model screen globally plus 21 per piece; NOT a continuous wrench/invariance proof',continuous_scope='C2, analytic polynomial ROM/v/a extrema and original continuous geometric envelope',truth_consumed=False))

def legacy_build_reference(primary,*,binding,perturbation_rad=(0.,0.),fractions=(.25,.5,.75)):
    original=FrozenPolynomial.freeze(primary);T=original.duration_s;knots=tuple([0.]+[float(T*f) for f in fractions]+[T]);pieces=[]
    for lo,hi in zip(knots,knots[1:]):pieces.append(FrozenPolynomial(tup(restrict(original.coefficients,T,lo,hi)),float(hi-lo),original.candidate,original.metadata_json))
    change=np.asarray(perturbation_rad,float)
    if change.shape!=(2,) or not np.all(np.isfinite(change)) or np.max(abs(change))>np.radians(.05)+1e-12:raise ValueError('BOUNDED_SINGLE_KNOT_PERTURBATION')
    if np.any(change):
        i=2;states=[[original.sample(t).q_rad,original.sample(t).dq_rad_s,original.sample(t).ddq_rad_s2] for t in knots];states[i][0]=states[i][0]+change
        for j in [i-1,i]:pieces[j]=replace(pieces[j],values=tup(hermite(*states[j],*states[j+1],knots[j+1]-knots[j])))
    obj=MultiSegmentReference(tuple(pieces),knots,original.candidate,original,not np.any(change),encode(binding),FrozenEscape.freeze(getattr(primary,'safe_escape',None)))
    object.__setattr__(obj,'sealed_digest',digest(obj.content()))
    return obj

def build_reference(primary,*,binding,perturbation_rad=(0.,0.),fractions=(.25,.5,.75)):
    spec=binding.get('study_spec')
    if spec is None:return legacy_build_reference(primary,binding=binding,perturbation_rad=perturbation_rad,fractions=fractions)
    original=FrozenPolynomial.freeze(primary);T=original.duration_s
    geo=np.asarray(spec['fractions'],float);tim=np.asarray(spec.get('time_fractions',spec['fractions']),float);delta=np.radians(np.asarray(spec['deltas_deg'],float))
    if not 1<=len(geo)<=3 or delta.shape!=(len(geo),2) or len(tim)!=len(geo):raise ValueError('STUDY_DENSITY_SHAPE')
    if not np.all(np.isfinite(np.r_[geo,tim,delta.ravel()])) or np.any(np.diff(np.r_[0.,geo,1.])<=0) or np.any(np.diff(np.r_[0.,tim,1.])<=0):raise ValueError('STUDY_INVALID_KNOTS')
    if np.max(abs(delta))>np.radians(.05)+1e-12:raise ValueError('BOUNDED_SINGLE_KNOT_PERTURBATION')
    knots=tuple(T*np.r_[0.,tim,1.]);geom=tuple(T*np.r_[0.,geo,1.]);states=[[original.sample(t).q_rad,original.sample(t).dq_rad_s,original.sample(t).ddq_rad_s2] for t in geom]
    for i,d in enumerate(delta,1):states[i][0]=states[i][0]+d
    zero=bool(not np.any(delta) and np.array_equal(geo,tim));pieces=[]
    for i,(lo,hi) in enumerate(zip(knots,knots[1:])):
        values=restrict(original.coefficients,T,lo,hi) if zero else hermite(*states[i],*states[i+1],hi-lo)
        pieces.append(FrozenPolynomial(tup(values),float(hi-lo),original.candidate,original.metadata_json))
    obj=MultiSegmentReference(tuple(pieces),knots,original.candidate,original,zero,encode(binding),FrozenEscape.freeze(getattr(primary,'safe_escape',None)))
    object.__setattr__(obj,'sealed_digest',digest(obj.content()))
    # Keep the original amplitude envelope for this research extension.
    samples=np.linspace(0,T,501)
    if max(np.max(abs(obj.sample(float(t)).q_rad-original.sample(float(t)).q_rad)) for t in samples)>np.radians(.05)+1e-10:raise ValueError('STUDY_FULL_PATH_AMPLITUDE')
    return obj

def seal_certificate(schedule,certificate):
    s=replace(schedule,path_certificate_json=encode(certificate));object.__setattr__(s,'sealed_certificate_id',digest([s.sealed_digest,s.path_certificate_json]));s.assert_integrity();return s

def adapt_decision(decision,planner,belief,intent):
    if intent is None:return decision
    primary=decision.executed.schedule;scheduler=planner.scheduler
    binding=dict(**intent,request_model_sequence=belief.sequence,request_model_signature=model_signature(belief),tracking_offset_rad=primitive(decision.executed.execution_screen['causal_tracking_offset_clearance']['position_error_rad']),task_q_bounds=primitive(scheduler.spec.q_bounds_rad),velocity_limits=primitive(np.asarray(scheduler.spec.task_joint_velocity_limit_rad_s)*scheduler.reference_velocity_fraction),acceleration_limits=primitive(np.asarray(scheduler.spec.task_joint_acceleration_limit_rad_s2)*scheduler.reference_acceleration_fraction),reference_period_s=scheduler.reference_period_s,task_start=primitive(scheduler.spec.start_return_target_rad),task_goal=primitive(scheduler.spec.outbound_goal_target_rad))
    schedule=build_reference(primary,binding=binding,perturbation_rad=np.radians(intent['perturbation_deg']))
    cert=certify_path(schedule,belief,scheduler.clearance_evaluator,spec=scheduler.spec,q_bounds=binding['task_q_bounds'],velocity_limits=binding['velocity_limits'],acceleration_limits=binding['acceleration_limits'],preserve_endpoint_floor=scheduler.preserve_task_endpoint_clearance_floor)
    if not cert['feasible']:raise ValueError('MULTISEGMENT_PATH_REJECTED:'+','.join(cert['reasons']))
    schedule=seal_certificate(schedule,cert)
    executed=replace(decision.executed,schedule=schedule,execution_screen={**decision.executed.execution_screen,'multisegment_reference':dict(reference_id=schedule.sealed_digest,certificate_id=schedule.sealed_certificate_id,feasible=True,perturbation_deg=intent['perturbation_deg'],canonical_zero=schedule.canonical_zero)})
    return replace(decision,executed=executed,greedy=executed if decision.greedy is decision.executed else decision.greedy,evaluations=tuple(executed if x is decision.executed else x for x in decision.evaluations))

def current_path_check(schedule,belief,clearance,request_sequence,phase,request_phase,now_physics_s,future_handoff):
    schedule.assert_integrity();b=json.loads(schedule.binding_json);reasons=[]
    if phase is not schedule.candidate.phase or request_phase is not schedule.candidate.phase:reasons.append('REFERENCE_PHASE_MISMATCH')
    if request_sequence!=b['request_model_sequence'] or belief.sequence<request_sequence:reasons.append('MODEL_SEQUENCE_MISMATCH')
    if belief.sequence==request_sequence and model_signature(belief)!=b['request_model_signature']:reasons.append('MODEL_CONTENT_CHANGED_WITHOUT_VERSION')
    age=now_physics_s-float(b['source_sample_time_s'])
    if not np.isfinite(age) or not 0<=age<.100:reasons.append('ORIGINAL_SOURCE_AGE')
    if future_handoff is not None:
        if future_handoff['request_plan_version']!=schedule.version:reasons.append('REFERENCE_VERSION_MISMATCH')
        if future_handoff['original_sample_s']!=b['source_sample_time_s'] or future_handoff['original_capture_ns']!=b['sensor_capture_ns']:reasons.append('ORIGINAL_SOURCE_ID_MISMATCH')
    # Native current admission still performs its original lifecycle/source-age,
    # live state/motion, goal, shifted geometry, phase, and future escape checks.
    # Re-run current-model mechanics globally and over every actual piece.
    from types import SimpleNamespace
    spec=SimpleNamespace(q_bounds_rad=np.asarray(b['task_q_bounds']),start_return_target_rad=np.asarray(b['task_start']))
    current_certificate=certify_path(schedule,belief,clearance,spec=spec,q_bounds=b['task_q_bounds'],velocity_limits=b['velocity_limits'],acceleration_limits=b['acceleration_limits'])
    if not current_certificate['feasible']:reasons.extend(current_certificate['reasons'])
    screen=AdaptiveMechanicsScreenV22();checks=[screen.evaluate(belief,p.candidate,p) for p in schedule.segments]
    if not all(x['feasible'] for x in checks):reasons.append('CURRENT_PIECE_MECHANICS')
    return dict(feasible=not reasons,reasons=reasons,reference_id=schedule.sealed_digest,certificate_id=schedule.sealed_certificate_id,original_source_age_s=age,request_model_sequence=request_sequence,current_model_sequence=belief.sequence,current_piece_mechanics=checks,current_full_path_certificate=current_certificate,current_certificate_id=digest([schedule.sealed_digest,current_certificate]),truth_consumed=False)
