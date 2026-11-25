"""One bounded attempt, with a separately owned B schedule and original capture time."""
import numpy as np
from time import monotonic_ns
from reactive import DT, observe, target
from native_rt2 import admission

def offer(kind, path, s, planner, decision, env, *, enabled=True, previous=None, mobile=None):
    begin=monotonic_ns()
    result=dict(status='retain', reason=None, timing={}, native=None, changed=False)
    if not enabled or env['phase'].value=='HOLD' or path.duration_s-s<DT-1e-12:
        result['reason']='native ownership';return result
    if env['sequence']!=env['belief'].sequence or env['phase'] is not env['request_phase'] or not env['valid']:
        result['reason']='source model/phase/acceleration unavailable';return result
    if env['now']()-env['capture']>=40_000_000:
        result['reason']='update deadline';return result
    try:
        sch=planner.scheduler
        model=env['belief'].human_model()
        obs=observe(model,env['x'],env['wrench'],env['owned'],env['vmax'],env['amax'],env['span'],env['sign'])
        computed=monotonic_ns()
        get,new_state=target(kind,obs,path,s,DT,previous,mobile)
        origin=get(0.);end=get(DT); nominal=path.sample(s+DT)
        result['delta_q']=end[0]-nominal.q_rad
        result['delta_v']=end[1]-nominal.dq_rad_s
        result['changed']=bool(np.any(result['delta_v']!=0) or np.any(result['delta_q']!=0))
        result['start_a']=origin[2];result['end_a']=end[2]
        built=monotonic_ns()
        result['timing'].update(local_model=(computed-begin)/1e6,law_and_jet=(built-computed)/1e6)
        schedule,validation=admission(kind,path,s,DT,get,new_state,planner,decision,env)
        result['validation']=validation
        if validation['feasible'] and env['now']()-env['capture']<40_000_000:
            result.update(status='offered',native=schedule,next_state=new_state)
        else: result['reason']='native current admission or update deadline'
    except (RuntimeError,ValueError,ArithmeticError,np.linalg.LinAlgError) as error:
        result['reason']=str(error)
    finally:
        finish=monotonic_ns()
        if 'built' in locals():result['timing']['native_build_admit']=(finish-built)/1e6
        result['timing']['offer_total']=(finish-begin)/1e6
    return result
