"""Source-only pure math for causal slot-aligned RETURN x3 ILC.

No simulation, model fit, file IO, native truth, or future outcome access.
Target displacement follows existing RetimedModalPlanner exactly. It is not
the derivative of the actual force, scheduling, or closed-loop trajectory.
"""
import math


def return_relative_basis_deg(slot,endpoint_locked=(False,False)):
    if type(slot) is not int or not 0<=slot<=5:raise ValueError('REGISTERED_SLOT_DOMAIN')
    u=max(0.,min(1.,(slot+.5)/6.));weight=math.sin(math.pi*u)**2
    return [0. if endpoint_locked[j] else (-1. if j==0 else 1.)*.30*weight for j in (0,1)]


def project_slot_history(slot_statistics,*,gain=.25,max_abs_x3=.5):
    if not 0.<=gain<=1. or not 0.<max_abs_x3<=1.:raise ValueError('FROZEN_ILC_GAIN_DOMAIN')
    numerator=0.;denominator=0.;used=[]
    for row in slot_statistics:
        if set(row)-{'phase','slot','duration_s','estimated_minus_reference_mean_deg','endpoint_locked','actual_native_steps','activated'}:
            raise ValueError('ILC_INPUT_ALLOWLIST')
        if row['phase']!='RETURN' or row['activated'] is not True or row['actual_native_steps']<=0:continue
        duration=float(row['duration_s'])
        if duration<=0.:continue
        error=[float(v) for v in row['estimated_minus_reference_mean_deg']]
        if len(error)!=2 or not all(math.isfinite(v) for v in error):raise ValueError('INVALID_CAUSAL_ESTIMATED_ERROR')
        b=return_relative_basis_deg(row['slot'],row['endpoint_locked'])
        numerator+=duration*sum(b[j]*error[j] for j in (0,1))
        denominator+=duration*sum(v*v for v in b)
        used.append(dict(slot=row['slot'],basis_deg=b,error_deg=error,duration_s=duration))
    update=0. if denominator<=1e-12 else gain*numerator/(denominator+1e-6)
    update=max(-max_abs_x3,min(max_abs_x3,update))
    return dict(x3=update,unclipped_projection_numerator=numerator,projection_denominator=denominator,
                gain=gain,max_abs_x3=max_abs_x3,used_slots=used,force_gradient_identified=False,
                reference_effect='RETURN target hip=-0.30*w*x3, knee=+0.30*w*x3 degrees, with original joint endpoint locks')


def make_modal_action(x3):
    if not math.isfinite(float(x3)) or abs(x3)>.5+1e-12:raise ValueError('LOCAL_TRUST_REGION')
    x=[0.]*8;x[3]=float(x3)
    return dict(family='modal8_retimed',x=x,legacy=[0.,0.])


def extract_executed_slot_statistics(causal_rows,slot_requests,summary,lineage):
    """Join known actual request ids and positive receipts, using no truth.

    slot_requests contain only {request_id,phase,slot,public_phase_goal_rad}
    captured by the existing decision callback BEFORE original control.
    summary/lineage supply only already happened selected reference/execution.
    """
    requests={r['request_id']:r for r in slot_requests};out=[]
    executed={r['decision_index']:r for r in lineage['rows']}
    if lineage['status']!='PASS':raise ValueError('ORIGINAL_RECEIPT_OWNERSHIP_REQUIRED')
    for record in summary['learning_records']:
        index=record['decision_index'];decision=summary['decisions'][index]
        request_id=decision.get('timing_request_id')
        if request_id not in requests:raise ValueError('UNRECORDED_REAL_SLOT_REQUEST')
        req=requests[request_id]
        if req['phase']!='RETURN':continue
        own=executed.get(index)
        if own is None or record.get('selected_plan_activated') is not True or own['actual_native_steps']<=0:continue
        target=record['selected_plan']['target_q_rad']
        # RetimedModalPlanner.reference_phase_goal reads the internal legal
        # terminal reference target, which can differ from nominal spec center.
        # The original accepted decision records that exact causal target.
        selection=decision.get('terminal_reference_selection')
        if not selection or selection.get('feasible') is not True or 'reference_target_rad' not in selection:
            raise ValueError('EXACT_EXECUTED_INTERNAL_REFERENCE_GOAL_REQUIRED')
        goal=selection['reference_target_rad']
        locks=[abs(float(target[j])-float(goal[j]))<=1e-10 for j in (0,1)]
        begin=float(record['start_time_s']);end=float(record['end_time_s']);duration=0.;integral=[0.,0.]
        intervals=own['actual_command_receipts']
        for a,b in zip(causal_rows[:-1],causal_rows[1:]):
            if a['phase']!='RETURN' or a.get('truth_used') is not False:continue
            dt=max(0.,min(float(b['time_s']),end)-max(float(a['time_s']),begin))
            if dt<=0.:continue
            # Admission and activation alone are insufficient: only actually
            # positive receipt-owned native intervals contribute a signal.
            owned=sum(max(0.,min(float(b['time_s']),end,float(r['end_physics_s']))-
                          max(float(a['time_s']),begin,float(r['start_physics_s']))) for r in intervals)
            if owned>dt+1e-8:raise ValueError('OVERLAPPING_RECEIPT_OWNERSHIP')
            duration+=owned
            for j in (0,1):
                integral[j]+=(float(a['estimated_q_dq'][j])-float(a['reference_q_dq'][j]))*180./math.pi*owned
        if duration>0.:
            out.append(dict(phase='RETURN',slot=int(req['slot']),duration_s=duration,
                estimated_minus_reference_mean_deg=[v/duration for v in integral],endpoint_locked=locks,
                actual_native_steps=own['actual_native_steps'],activated=True))
    return out
