"""Non-actuating Stage1D adapter. No production import, live defaults or new planner.

Numerical certification settings remain research-only pending approval item 5.
Mechanics keeps the native sampled scope; it is not interval physical dynamics.
"""
import bootstrap
from dataclasses import dataclass, replace
from types import SimpleNamespace
import hashlib
import pickle
import numpy as np
from phase_coordinates import State, Phase, Limits
from reference_kernel import Plan, extrema, certify
from continuous_completion import make_plan
from joint_optimizer import select
from traction_mpc_stage5.human_waypoint_scheduler import ScheduledHumanReferenceSample
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_reference import OnlineReferenceOwner, clearance_certificate
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import clearance_geometry_signature
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import EscapeBundle, FallbackLatch, braking_duration


def model_key(belief, clearance):
    return (belief.sequence, hashlib.sha256(pickle.dumps(belief, protocol=5)).hexdigest(),
            clearance_geometry_signature(clearance))


@dataclass(frozen=True)
class PolynomialSchedule:
    plan: Plan
    coordinates: Phase
    candidate: object
    reference_period_s: float = .005
    version: str = 'stage1e_polynomial_v1_RESEARCH_ONLY'

    @property
    def duration_s(self): return self.plan.duration

    def sample(self, t):
        if not np.isfinite(t) or t < 0: raise ValueError('invalid physical reference time')
        return ScheduledHumanReferenceSample(*self.coordinates.physical(self.plan.sample(t)))

    @property
    def digest(self):
        return hashlib.sha256(repr((self.plan, self.coordinates.start.tolist(),
            self.coordinates.goal.tolist(), self.candidate.phase.value, self.version)).encode()).hexdigest()

    def bounds(self, derivative=0, offset=None):
        low, high = np.full(2, np.inf), np.full(2, -np.inf)
        offset = np.zeros(2) if offset is None else np.asarray(offset)
        for piece in self.plan.pieces:
            for i, poly in enumerate(piece.positions):
                physical = self.coordinates.sign[i]*poly
                if derivative == 0: physical += self.coordinates.start[i]+offset[i]
                lo, hi = extrema(physical.deriv(derivative)/piece.duration**derivative)
                low[i], high[i] = min(low[i], lo), max(high[i], hi)
        return low, high

    @property
    def maximum_reference_velocity_rad_s(self):
        lo, hi = self.bounds(1); return np.maximum(np.abs(lo), np.abs(hi))

    @property
    def maximum_reference_acceleration_rad_s2(self):
        lo, hi = self.bounds(2); return np.maximum(np.abs(lo), np.abs(hi))

    @property
    def trajectory(self):
        lo, hi = self.bounds()
        return SimpleNamespace(position_extrema=[SimpleNamespace(min=a, max=b) for a,b in zip(lo,hi)])

    def suffix(self, elapsed):
        return replace(self, plan=self.plan.suffix(elapsed))


def schedule(plan, coordinates, phase):
    return PolynomialSchedule(plan, coordinates, HumanWaypointCandidate(
        'stage1e_joint_u', phase, coordinates.goal, coordinates.goal, np.zeros(2)))


def certify_schedule(s, scheduler, belief, *, offset, roundoff):
    """All polynomial intervals; native envelope and native mechanics unchanged."""
    model = belief.human_model(); spec = scheduler.spec
    bounds = np.c_[np.maximum(np.asarray(spec.q_bounds_rad)[:,0], model.q_min_rad),
                   np.minimum(np.asarray(spec.q_bounds_rad)[:,1], model.q_max_rad)]
    limits = Limits(np.asarray(spec.task_joint_velocity_limit_rad_s)*scheduler.reference_velocity_fraction,
                    np.asarray(spec.task_joint_acceleration_limit_rad_s2)*scheduler.reference_acceleration_fraction, bounds)
    kinematics = certify(s.plan, s.coordinates, limits, roundoff)
    lo, hi = s.bounds(offset=offset)
    shifted_rom = bool(np.all(lo >= bounds[:,0]) and np.all(hi <= bounds[:,1]))
    clearance = scheduler.clearance_evaluator
    # Existing arbitrary-path Lipschitz certificate uses exact polynomial extrema
    # through this schedule protocol; never invokes old quintic certificate reuse.
    geometry = clearance_certificate(s, clearance)
    shifted = clearance_certificate(s, clearance, q_offset=offset)
    floor = max(0., float(np.min(clearance.evaluate(np.vstack([
        spec.start_return_target_rad, s.candidate.phase_goal_rad]))))) if scheduler.preserve_task_endpoint_clearance_floor else 0.
    mechanics = AdaptiveMechanicsScreenV22().evaluate(belief, s.candidate, s)
    return dict(feasible=bool(shifted_rom and geometry['feasible'] and shifted['feasible']
        and min(geometry['combined_body_lowers_m'].values()) >= floor and mechanics['feasible']),
        polynomial_kinematics=kinematics, shifted_rom=shifted_rom, geometry=geometry,
        shifted_geometry=shifted, endpoint_floor_m=floor, mechanics=mechanics,
        old_quintic_certificate_reused=False, numerical_policy='ITEM_5_PENDING',
        scope='native software reference checks; not physical invariance')


def prepare_escape(s, fork_s, scheduler, belief, offset, phase_elapsed_s):
    """Independent native 40ms bridge/stop at a zero-a fork, not completion tail.

    Preserves native prepare_decision construction, grid, limits and latest-node
    search. Works on a distinct safety suffix, never recasts the scored polynomial.
    A nonzero-a fork is rejected; the first Stage1D prefix endpoint has a=0.
    """
    endpoint = s.sample(fork_s)
    if np.max(np.abs(endpoint.ddq_rad_s2)) > 1e-10:
        raise ValueError('SAFE_FALLBACK_NONZERO_ENDPOINT_ACCELERATION')
    dt = scheduler.reference_period_s; bridge_duration = 8*dt
    screen = AdaptiveMechanicsScreenV22(); clearance = scheduler.clearance_evaluator
    make = lambda label,q,v: replace(s.candidate,label=label,q_waypoint_rad=q,dq_waypoint_rad_s=v)
    v = endpoint.dq_rad_s
    bc = make('safe_fallback_bridge', endpoint.q_rad+bridge_duration*v, v)
    bridge = scheduler.plan_fixed_duration_reference_contract(current_q_hat_rad=endpoint.q_rad,
        current_dq_hat_rad_s=v,candidate=bc,duration_s=bridge_duration,phase_elapsed_s=phase_elapsed_s+fork_s)
    bm = screen.evaluate(belief,bc,bridge)
    if not bm['feasible']: raise ValueError('SAFE_FALLBACK_BRIDGE_MECHANICS')
    limits = np.asarray(scheduler.spec.task_joint_acceleration_limit_rad_s2)*scheduler.reference_acceleration_fraction
    duration = braking_duration(v,limits,dt); attempts=[]
    for index in range(7,-1,-1):
        commit = index*dt; start = bridge.sample(commit)
        sc = make('safe_fallback_stop',start.q_rad+.5*duration*v,np.zeros(2))
        try:
            stop = scheduler.plan_fixed_duration_reference_contract(current_q_hat_rad=start.q_rad,
                current_dq_hat_rad_s=start.dq_rad_s,candidate=sc,duration_s=duration,
                phase_elapsed_s=phase_elapsed_s+fork_s+commit)
            sm = screen.evaluate(belief,sc,stop)
            shifted=stop.coefficients.copy(); shifted[:,0]+=offset
            lower=float(clearance.certified_minimum(shifted,duration))
            qbounds=np.asarray(scheduler.spec.q_bounds_rad)
            hard=np.c_[scheduler.human_model.q_min_rad,scheduler.human_model.q_max_rad]
            ends=np.vstack([start.q_rad+offset,sc.q_waypoint_rad+offset])
            rom=bool(np.all(ends>=qbounds[:,0]) and np.all(ends<=qbounds[:,1]) and np.all(ends>=hard[:,0]) and np.all(ends<=hard[:,1]))
            if not sm['feasible'] or lower<0 or not rom: raise ValueError('SAFE_FALLBACK_SHIFTED_PATH_OR_MECHANICS')
            return EscapeBundle(bridge,stop,commit,dict(geometry_signature=clearance_geometry_signature(clearance),
                belief_sequence=belief.sequence,bridge_mechanics=bm,stop_mechanics=sm,
                shifted_lower_m=lower,shifted_rom_valid=rom,normal_bridge_duration_s=bridge_duration,
                fork_s=fork_s,earlier_rejections=attempts,scope='native sampled mechanics and continuous clearance'))
        except (ValueError,RuntimeError) as e: attempts.append(dict(commit_progress_s=commit,reason=str(e)))
    raise ValueError('SAFE_FALLBACK_ARCHITECTURE_NOT_JUSTIFIED:'+repr(attempts))


def validate(s, *, scheduler, belief, owned, observed, observed_a, acceleration_valid,
             phase, phase_elapsed_s, request_key, escape, fork_s, roundoff):
    """Current-state admission and unchanged timeout; no zero-a reset at splice."""
    first=s.sample(0); spec=scheduler.spec; observed=np.asarray(observed); observed_a=np.asarray(observed_a)
    finite=bool(observed.shape==(4,) and observed_a.shape==(2,) and np.all(np.isfinite(np.r_[observed,observed_a])))
    if not finite: return dict(feasible=False,reason='INVALID_OBSERVATION')
    qerr=observed[:2]-owned.q_rad; verr=observed[2:]-owned.dq_rad_s
    cert=certify_schedule(s,scheduler,belief,offset=qerr,roundoff=roundoff)
    c2=all(np.max(np.abs(getattr(first,k)-getattr(owned,k)))<=1e-10 for k in ('q_rad','dq_rad_s','ddq_rad_s2'))
    model=belief.human_model(); bounds=np.asarray(spec.q_bounds_rad)
    state_rom=bool(np.all(observed[:2]>=bounds[:,0]) and np.all(observed[:2]<=bounds[:,1])
        and np.all(observed[:2]>=model.q_min_rad) and np.all(observed[:2]<=model.q_max_rad))
    motion=bool(acceleration_valid and np.all(np.abs(observed[2:])<=np.asarray(spec.task_joint_velocity_limit_rad_s)+1e-12)
        and np.all(np.abs(observed_a)<=np.asarray(spec.task_joint_acceleration_limit_rad_s2)+1e-12)
        and np.all(s.maximum_reference_velocity_rad_s+np.abs(verr)<=np.asarray(spec.task_joint_velocity_limit_rad_s)+1e-12)
        and np.all(s.maximum_reference_acceleration_rad_s2+np.abs(observed_a-owned.ddq_rad_s2)<=np.asarray(spec.task_joint_acceleration_limit_rad_s2)+1e-12))
    remaining=spec.phase_timeout_s-phase_elapsed_s
    # Full normal witness AND independent stop fit original remaining phase time.
    time_ok=s.duration_s<=remaining+1e-12 and fork_s+escape.commit_progress_s+escape.stop.duration_s<=remaining+1e-12
    key_ok=request_key==model_key(belief,scheduler.clearance_evaluator)
    escape_ok=escape.certificate['geometry_signature']==request_key[2] and escape.certificate['belief_sequence']==belief.sequence
    # Rebuild the safety suffix against the current offset/model, not merely its label.
    try:
        current_escape=prepare_escape(s,fork_s,scheduler,belief,qerr,phase_elapsed_s)
        escape_ok=bool(escape_ok and current_escape.commit_progress_s==escape.commit_progress_s
            and np.array_equal(current_escape.bridge.coefficients,escape.bridge.coefficients)
            and np.array_equal(current_escape.stop.coefficients,escape.stop.coefficients))
    except (ValueError,RuntimeError):escape_ok=False
    goal=spec.start_return_target_rad if phase.value=='RETURN' else spec.outbound_goal_target_rad
    phase_ok=s.candidate.phase is phase and np.allclose(s.candidate.phase_goal_rad,goal,atol=1e-12,rtol=0)
    current_clearance=float(scheduler.clearance_evaluator.evaluate(observed[:2]))
    cert.update(C2=c2,state_rom=state_rom,motion=motion,original_timeout=time_ok,phase=phase_ok,
        version=key_ok,escape=escape_ok,current_clearance_m=current_clearance)
    cert['feasible']=bool(cert['feasible'] and c2 and state_rom and motion and time_ok and phase_ok and key_ok and escape_ok and current_clearance>=0.)
    return cert


class ReceiptBinding:
    """One native owner, mutated ONLY after native lifecycle + actual receipt.

    The producer binds request/digest/model externally because the native receipt
    does not contain them. A dict bearing 'applied' is never enough authentication.
    No production hook is installed by importing this module.
    """
    def __init__(self, initial, epoch_s, lifecycle, wall):
        self.owner=OnlineReferenceOwner(initial,epoch_s=epoch_s)
        self.lifecycle,self.wall=lifecycle,wall
        self.history=[];self.seen=set();self.pending=None;self.revoked=False

    def propose(self, request, s, epoch, key, certificate, escape):
        if not all(certificate.get(k) for k in ('feasible','C2','state_rom','motion','original_timeout','phase','version','escape')):
            raise ValueError('FULL_ACTIVATION_CERTIFICATE_REQUIRED')
        if self.lifecycle.records()[request.request_id]['outcome']!='PENDING':
            raise ValueError('REQUEST_NOT_PENDING')
        self.pending=(request,s,epoch,key,certificate,escape,s.digest)
        self.bound_receipt=None

    def bind_prepared_receipt(self, request, receipt):
        """Bind the exact native write transaction before apply; never a later dict."""
        if self.pending is None or self.pending[0] is not request:raise ValueError('REQUEST_MISMATCH')
        if receipt.get('applied') or not any(r is receipt for r in self.wall.applied_commands):
            raise ValueError('UNOWNED_OR_ALREADY_APPLIED_RECEIPT')
        self.bound_receipt=receipt

    def sample(self,t):
        if self.revoked: raise RuntimeError('SAFETY_OWNER_REQUIRED')
        return self.owner.sample(t)

    def commit(self, receipt, current_key):
        if not any(row is receipt for row in self.wall.applied_commands): return False
        rid=receipt.get('receipt_index')
        if rid in self.seen or not receipt.get('applied'): return False
        if receipt.get('supervisor_mode')!='TRACK':
            self.revoked=True;self.pending=None;return False
        if self.pending is None: return False
        if receipt is not self.bound_receipt:return False
        request,s,epoch,key,cert,escape,digest=self.pending
        row=self.lifecycle.records()[request.request_id]
        age=max(receipt['apply_ns'],receipt['effective_activation_ns'])-request.sensor_capture_ns
        if row['outcome']!='ACTIVATED' or not 0<=age<self.lifecycle.maximum_age_ns: return False
        if current_key!=key or s.digest!=digest: return False
        if receipt.get('source_sample_time_s')!=request.source_sample_time_s: return False
        if receipt.get('source_capture_ns')!=request.sensor_capture_ns: return False
        if receipt.get('start_physics_s')!=epoch: return False
        first=s.sample(0)
        if any(not np.array_equal(receipt.get(name),value) for name,value in
               (('q_ref_rad',first.q_rad),('dq_ref_rad_s',first.dq_rad_s))): return False
        old=self.owner.sample(epoch)
        if any(np.max(np.abs(getattr(first,k)-getattr(old,k)))>1e-10 for k in ('q_rad','dq_rad_s','ddq_rad_s2')): return False
        self.owner.schedule=s;self.owner.schedule_epoch_s=epoch
        self.owner.owned_segments.append((epoch,s));self.owner.target=s.candidate.q_waypoint_rad.copy()
        self.owner.model_key=key;self.owner.certificate=cert
        self.history.append(dict(receipt_index=rid,epoch_s=epoch,digest=digest,
            q=first.q_rad.copy(),dq=first.dq_rad_s.copy(),ddq=first.ddq_rad_s2.copy()))
        self.seen.add(rid);self.pending=None
        return True

    def commit_tick(self, receipt, *, expected_physics_s, current_key):
        """Progress journal from an already owned polynomial; no governor scaling."""
        if not any(row is receipt for row in self.wall.applied_commands):return False
        if not receipt.get('applied') or receipt.get('receipt_index') in self.seen:return False
        if receipt.get('supervisor_mode')!='TRACK':
            self.revoked=True;self.pending=None;return False
        if self.revoked or self.owner.schedule is None or self.owner.model_key!=current_key:return False
        age=max(receipt['apply_ns'],receipt['effective_activation_ns'])-receipt['source_capture_ns']
        if not 0<=age<self.lifecycle.maximum_age_ns:return False
        if receipt['start_physics_s']!=expected_physics_s:return False
        if self.history and expected_physics_s<=self.history[-1]['epoch_s']:return False
        x=self.sample(expected_physics_s)
        if not np.array_equal(receipt.get('q_ref_rad'),x.q_rad) or not np.array_equal(receipt.get('dq_ref_rad_s'),x.dq_rad_s):return False
        self.history.append(dict(receipt_index=receipt['receipt_index'],epoch_s=expected_physics_s,
            digest=self.owner.schedule.digest,q=x.q_rad.copy(),dq=x.dq_rad_s.copy(),ddq=x.ddq_rad_s2.copy()))
        self.seen.add(receipt['receipt_index']);return True


def coordinate(binding, *, activation_s, coordinates, limits, h, objective, seed_u,
               roundoff, scheduler, belief, phase, phase_elapsed_s, observed, observed_a):
    """One Stage1D optimizer replaces B direction selection; no live entrypoint.

    Caller owns observation validity/freshness. This function never commits an
    owner and never substitutes a planned state for actual Human observations.
    """
    origin=binding.sample(activation_s)
    state=State(coordinates.sign*(origin.q_rad-coordinates.start),coordinates.sign*origin.dq_rad_s,
                coordinates.sign*origin.ddq_rad_s2)
    incumbent=None
    if binding.owner.schedule is not None:
        elapsed=activation_s-binding.owner.schedule_epoch_s
        if elapsed<binding.owner.schedule.duration_s:incumbent=binding.owner.schedule.plan.suffix(elapsed)
    records=[];key=model_key(belief,scheduler.clearance_evaluator)
    def validity(plan):
        s=schedule(plan,coordinates,phase);fork=plan.pieces[0].duration
        try:
            esc=prepare_escape(s,fork,scheduler,belief,np.asarray(observed)[:2]-origin.q_rad,phase_elapsed_s)
            cert=validate(s,scheduler=scheduler,belief=belief,owned=origin,observed=observed,
                observed_a=observed_a,acceleration_valid=True,phase=phase,phase_elapsed_s=phase_elapsed_s,
                request_key=key,escape=esc,fork_s=fork,roundoff=roundoff)
            records.append(dict(digest=s.digest,certificate=cert));return cert['feasible']
        except (ValueError,RuntimeError) as e:
            records.append(dict(digest=s.digest,rejection=str(e)));return False
    result=select(state,coordinates,limits,h,objective,seed_u,roundoff,incumbent=incumbent,validity=validity)
    return result,records


def route(original_B, *args, enabled=False, **kwargs):
    if not enabled: return original_B(*args,**kwargs)
    raise RuntimeError('LIVE_PENDING_ITEMS_5_6_7_AND_FULL_RUNTIME_WIRING')
