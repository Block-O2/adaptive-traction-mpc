"""C2 safety suffix candidates; no live event coverage claim."""
import bootstrap
from dataclasses import replace
from fractions import Fraction as F
import numpy as np
from reference_kernel import Piece,Plan,extrema,rational_integral,rational_add
from native_integration import PolynomialSchedule,model_key
from phase_coordinates import Phase
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import EscapeBundle,braking_duration
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_reference import clearance_certificate
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22

def ramp(endpoint,T,kind):
    co=[]
    for q,v,a in zip(endpoint.q_rad,endpoint.dq_rad_s,endpoint.ddq_rad_s2):
        # a(t)=a0*(1-s) or a0*(1-3s²+2s³), integrated without a reset.
        aa=[F(float(a))*x for x in ([1,-1] if kind=='linear' else [1,0,-3,2])]
        vv=rational_add([F(float(v))],[F(T)*x for x in rational_integral(aa)])
        qq=rational_add([F(float(q))],[F(T)*x for x in rational_integral(vv)])
        co.append(tuple(qq))
    return Piece(T,tuple(co))

def check(s,sch,b,offset):
    lo,hi=s.bounds(offset=offset);bounds=np.c_[np.maximum(np.asarray(sch.spec.q_bounds_rad)[:,0],b.human_model().q_min_rad),np.minimum(np.asarray(sch.spec.q_bounds_rad)[:,1],b.human_model().q_max_rad)]
    geometry=clearance_certificate(s,sch.clearance_evaluator)
    shifted_geometry=clearance_certificate(s,sch.clearance_evaluator,q_offset=offset)
    mechanics=AdaptiveMechanicsScreenV22().evaluate(b,s.candidate,s)
    velocity=s.maximum_reference_velocity_rad_s;acceleration=s.maximum_reference_acceleration_rad_s2
    motion=bool(np.all(velocity<=np.asarray(sch.spec.task_joint_velocity_limit_rad_s)*sch.reference_velocity_fraction) and np.all(acceleration<=np.asarray(sch.spec.task_joint_acceleration_limit_rad_s2)*sch.reference_acceleration_fraction))
    rom=bool(np.all(lo>=bounds[:,0]) and np.all(hi<=bounds[:,1]))
    floor=max(0.,float(np.min(sch.clearance_evaluator.evaluate(np.vstack([sch.spec.start_return_target_rad,s.candidate.phase_goal_rad]))))) if sch.preserve_task_endpoint_clearance_floor else 0.
    ok=motion and rom and geometry['feasible'] and min(geometry['combined_body_lowers_m'].values())>=floor and shifted_geometry['feasible'] and mechanics['feasible']
    return dict(feasible=bool(ok),motion=motion,rom=rom,velocity=velocity,acceleration=acceleration,geometry=geometry,shifted_geometry=shifted_geometry,mechanics=mechanics,floor_m=floor)

def prepare(s,t,sch,b,offset,elapsed,kind='linear',ramp_s=.035):
    x=s.sample(t);p=ramp(x,ramp_s,kind);y=p.sample(p.duration)
    # The zero-a boundary follows the defining integral analytically.
    v=x.dq_rad_s+x.ddq_rad_s2*ramp_s/2
    q=y.p;tail=Piece(.040-ramp_s,tuple((F(float(qi)),F(.040-ramp_s)*F(float(vi))) for qi,vi in zip(q,v)))
    ph=Phase(np.zeros(2),np.ones(2));candidate=replace(s.candidate,label='stage1g_'+kind+'_escape')
    bridge=PolynomialSchedule(Plan((p,tail)),ph,candidate)
    bc=check(bridge,sch,b,offset)
    if not bc['feasible']:raise ValueError('BRIDGE_REJECTED:'+str(bc))
    acceleration=np.asarray(sch.spec.task_joint_acceleration_limit_rad_s2)*sch.reference_acceleration_fraction
    duration=braking_duration(v,acceleration,sch.reference_period_s);attempts=[]
    for i in range(7,-1,-1):
        commit=i*sch.reference_period_s
        if commit<ramp_s:continue
        qstart=bridge.sample(commit).q_rad
        c=replace(candidate,q_waypoint_rad=qstart+.5*duration*v,dq_waypoint_rad_s=np.zeros(2))
        try:
            stop=sch.plan_fixed_duration_reference_contract(current_q_hat_rad=qstart,current_dq_hat_rad_s=v,candidate=c,duration_s=duration,phase_elapsed_s=elapsed+t+commit)
            shifted=stop.coefficients.copy();shifted[:,0]+=offset
            lower=sch.clearance_evaluator.certified_minimum(shifted,duration)
            mechanics=AdaptiveMechanicsScreenV22().evaluate(b,c,stop)
            bounds=np.asarray(sch.spec.q_bounds_rad);ends=np.vstack([qstart,c.q_waypoint_rad])+offset
            hard=np.c_[b.human_model().q_min_rad,b.human_model().q_max_rad]
            if lower<0 or not mechanics['feasible'] or np.any(ends<bounds[:,0]) or np.any(ends>bounds[:,1]) or np.any(ends<hard[:,0]) or np.any(ends>hard[:,1]):raise ValueError('SHIFTED_STOP_OR_MECHANICS_REJECTED')
            return EscapeBundle(bridge,stop,commit,dict(bridge=bc,stop_mechanics=mechanics,shifted_stop_lower=lower,model_key=model_key(b,sch.clearance_evaluator),ramp_s=ramp_s,kind=kind,earlier_rejections=attempts,scope='point-fork reference certificate; no interval event coverage'))
        except (ValueError,RuntimeError) as e:attempts.append(str(e))
    raise ValueError('NO_CERTIFIED_STOP:'+str(attempts))
