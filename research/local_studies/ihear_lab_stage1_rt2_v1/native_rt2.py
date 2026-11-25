"""Submit one reference to B's original fixed-duration scheduler and admission."""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import prepare_decision
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import validate_activation,clearance_geometry_signature
from traction_mpc_stage5.task import TaskPhase

def admission(kind, path, s, h, evaluate, proposal_state, planner, decision, env):
    start=evaluate(0.)
    end=evaluate(h)
    scheduler=planner.scheduler
    candidate=replace(path.candidate,label='rt2_'+kind,q_waypoint_rad=end[0],dq_waypoint_rad_s=end[1])
    native=scheduler.plan_fixed_duration_reference_contract(current_q_hat_rad=start[0],current_dq_hat_rad_s=start[1],candidate=candidate,duration_s=h,phase_elapsed_s=env['elapsed'])
    # Both planned jets must match the original native C2 tolerance.
    def jet_error(t):
        real=native.sample(t)
        return max(np.max(np.abs(x-y)) for x,y in zip((real.q_rad,real.dq_rad_s,real.ddq_rad_s2),evaluate(t)))
    # For II and III both representations are quintic, six boundary data uniquely determine the polynomial.
    # I's non-affine clock composed with a nonlinear path cannot in general be represented by B's quintic.
    if kind=='I':
        degree=max((j for j in range(6) if np.any(path.coefficients[:,j]!=0)),default=0)
        if proposal_state!=env.get('old_rate',1.) and 4*degree>5:
            raise ValueError('native quintic cannot encode exact shared clock')
    if max(jet_error(0.),jet_error(h))>1e-10:
        raise ValueError('original C2 boundary mismatch')
    offset=env['x'][:2]-env['owned'].q_rad
    screen={'causal_tracking_offset_clearance':{'position_error_rad':offset}}
    action=replace(decision.executed,schedule=native,execution_screen=screen)
    packet=replace(decision,executed=action,phase_elapsed_s=env['elapsed'])
    prepared=prepare_decision(packet,planner,env['belief']).executed.schedule
    return prepared,validate_current(prepared,env)

def validate_current(schedule,env):
    owned=env['owned']
    future=dict(spec=env['spec'],estimated_state=env['x'],observed_reference_state=np.r_[owned.q_rad,owned.dq_rad_s],
        estimated_acceleration=env['a'],reference_acceleration=owned.ddq_rad_s2,acceleration_valid=env['valid'],
        now_ns=env['now'](),original_capture_ns=env['capture'],revalidation_capture_ns=env['recheck'],
        request_plan_version=env['version'] if 'version' in env else schedule.version,
        original_sample_s=env['stamp'],revalidation_sample_s=env['stamp'],age_policy='wall')
    return validate_activation(belief=env['belief'],request_sequence=env['sequence'],schedule=schedule,
        clearance=env['clearance'],phase=env['phase'],request_phase=env['request_phase'],
        remaining_s=env['remaining'],reference_state=np.r_[owned.q_rad,owned.dq_rad_s],now_physics_s=env['stamp'],
        certificate_geometry_at_request=clearance_geometry_signature(env['clearance']),future_handoff=future)
