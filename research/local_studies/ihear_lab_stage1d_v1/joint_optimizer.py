"""Non-actuating continuous two-variable optimization and incumbent ownership.

No ratio/sum constraint, duration stretching, minimum speed, deadline or force
noninferiority condition. Solver success is neither feasibility nor safety.
"""
from dataclasses import dataclass
from types import SimpleNamespace
import numpy as np
from scipy.optimize import minimize
from phase_coordinates import Failure, Rejected
from reference_kernel import prefix, certify
from continuous_completion import make_plan

@dataclass(frozen=True)
class Selection:
    plan: object
    disposition: str
    evidence: dict

def select(state,phase,limits,h,objective,seed_u,roundoff,incumbent=None,validity=None):
    """incumbent must already be sliced at predicted physical handover time.

    validity is a mandatory external current-context check when supplied by native
    integration; this software module never substitutes for that integration.
    Invalid incumbent returns safety-required, not blindly carried motion.
    """
    key=objective.key; evidence={'scope':'offline_kinematics','failures':[]}
    if incumbent is not None:
        try:
            certify(incumbent,phase,limits,roundoff)
            if validity is not None and not validity(incumbent):
                raise Rejected(Failure.NATIVE,'incumbent invalid in current context')
            start=incumbent.sample(0)
            if any(np.max(np.abs(getattr(start,k)-getattr(state,k)))>roundoff for k in ('p','v','a')):
                raise Rejected(Failure.ACTIVATION,'incumbent does not start at handover state')
        except Rejected as exc:
            return Selection(None,'safety_required',{'category':exc.category.value,'detail':exc.detail})
        baseline=incumbent
    else:
        try: baseline,_=make_plan(state,seed_u,h,phase,limits,roundoff)
        except Rejected as exc:
            return Selection(None,'startup_not_found',{'category':exc.category.value,'detail':exc.detail})
        if validity is not None and not validity(baseline):
            return Selection(None,'safety_required',{'category':Failure.NATIVE.value})
    old=objective.evaluate(baseline)
    def evaluate(u):
        try:
            plan,_=make_plan(state,u,h,phase,limits,roundoff)
            return objective.evaluate(plan)['J']
        except Rejected: return float('inf')
    # Only the two terminal velocities are optimizer variables. No fixed sum.
    try:
        result=minimize(evaluate,np.asarray(seed_u,dtype=float),method='SLSQP',
                        bounds=[(0.,float(x)) for x in limits.velocity],
                        constraints=[dict(type='ineq',fun=lambda u:prefix(state,u,h).margins(phase,limits))])
    except (ValueError,FloatingPointError,np.linalg.LinAlgError) as exc:
        result=SimpleNamespace(success=False,x=np.asarray(seed_u,dtype=float),
                               message=f'numerical solver exception: {type(exc).__name__}: {exc}')
    evidence.update(solver_success=bool(result.success),solver_message=str(result.message),
                    u=result.x.tolist(),incumbent_cost=old)
    chosen=baseline; disposition='continue_incumbent' if incumbent is not None else 'startup_forward'
    try:
        if not result.success: raise Rejected(Failure.SOLVER,str(result.message))
        candidate,certificate=make_plan(state,result.x,h,phase,limits,roundoff)
        if validity is not None and not validity(candidate): raise Rejected(Failure.NATIVE,'candidate rejected')
        score=objective.evaluate(candidate)
        evidence.update(candidate_cost=score,certificate=certificate)
        if objective.key!=key: raise RuntimeError('snapshot changed during comparison')
        if score['J']<old['J']:
            chosen=candidate; disposition='improved'
    except Rejected as exc:
        evidence['failures'].append({'category':exc.category.value,'detail':exc.detail})
    evidence.update(chosen_cost=objective.evaluate(chosen),snapshot=repr(key),
                    actual_JF='NOT_MEASURED',same_snapshot=True)
    return Selection(chosen,disposition,evidence)
