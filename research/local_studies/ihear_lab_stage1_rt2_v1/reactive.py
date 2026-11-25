"""Pure 25 Hz one-proposal laws. All angular units SI."""
from dataclasses import dataclass
import numpy as np

DT = .04
def smooth_jet(u):
    return u**3-.5*u**4, 3*u*u-2*u**3, 6*u*(1-u)

@dataclass(frozen=True)
class Input:
    excess: np.ndarray
    inertia: np.ndarray
    torque_scale: float
    lag: float
    vmax: np.ndarray
    amax: np.ndarray
    span: np.ndarray
    sign: float

def observe(model, state, wrench, reference, vmax, amax, span, sign):
    q,v = state[:2],state[2:]
    tau = model.geometry.generalized_input_from_wrench(q,wrench[:3],wrench[3:])
    rest = model.inverse_dynamics(q,np.zeros(2),np.zeros(2))
    mass = model.mass_matrix(q)
    scale = np.linalg.norm(mass * amax)
    if not np.isfinite(scale) or scale<=0 or not np.isfinite(np.r_[q,v,wrench,tau,rest]).all():
        raise ValueError("invalid model or measurement")
    lag = sign*np.mean((reference.q_rad-q)/span)
    return Input(tau-rest,mass,scale,lag,vmax,amax,span,sign)

class Governor:
    def action(self, obs, nominal, h, accepted_rate=1.):
        speed = np.linalg.norm(nominal)
        direction = nominal/speed if speed else np.zeros(2)
        power_ratio = float(obs.excess@direction)/obs.torque_scale
        equilibrium = 1/(1+max(0.,power_ratio)+max(0.,obs.lag))
        rate = equilibrium+(accepted_rate-equilibrium)*np.exp(-h/DT)
        return float(rate)

class Analytical:
    def action(self, obs, nominal, h, mobile):
        if not all(mobile): return np.zeros(2)
        # The differential direction has zero sum in normalized task coordinates.
        basis = obs.sign*obs.span*np.array([1.,-1.])*np.min(obs.amax/obs.span)*h/1.5
        sensitivity = obs.inertia@basis/(h*obs.torque_scale)
        torque = obs.excess/obs.torque_scale
        return basis*np.tanh(-(sensitivity@torque)/(1+sensitivity@sensitivity))

class QP:
    def action(self, obs, nominal, h, mobile, previous_delta):
        scale = obs.amax*h/1.5
        sensitivity = obs.inertia*scale/(h*obs.torque_scale)
        gram = sensitivity.T@sensitivity+2*np.eye(2)
        rhs = previous_delta/scale-sensitivity.T@(obs.excess/obs.torque_scale)
        lower = np.maximum(-1.,(-obs.vmax-nominal)/scale)
        upper = np.minimum(1.,(obs.vmax-nominal)/scale)
        if obs.sign>0: lower=np.maximum(lower,-nominal/scale)
        else: upper=np.minimum(upper,-nominal/scale)
        lower[~mobile]=0.
        upper[~mobile]=0.
        if np.any(lower>upper) or not np.all(np.isfinite(np.r_[rhs,gram.ravel(),lower,upper])):
            raise ValueError("infeasible/nonfinite QP")
        free = np.linalg.solve(gram,rhs)
        candidates = [free] if np.all((lower<=free)&(free<=upper)) else []
        for i in range(2):
            j=1-i
            for edge in (lower[i],upper[i]):
                z=np.empty(2)
                z[i]=edge
                z[j]=np.clip((rhs[j]-gram[j,i]*edge)/gram[j,j],lower[j],upper[j])
                candidates.append(z)
        best=min(candidates,key=lambda z:.5*z@gram@z-rhs@z)
        return scale*best

def target(kind, obs, path, s, h, previous=None, mobile=None):
    origin=path.sample(s)
    end=path.sample(s+h)
    if kind=='I':
        old=1. if previous is None else previous
        rate=Governor().action(obs,end.dq_rad_s,h,old)
        def evaluate(t):
            u=t/h
            b,v,a=smooth_jet(u)
            ds=rate-old
            sample=path.sample(s+old*t+h*ds*b)
            r=old+ds*v
            return sample.q_rad,sample.dq_rad_s*r,sample.ddq_rad_s2*r*r+sample.dq_rad_s*ds*a/h
        return evaluate,rate
    flags=np.array([True,True]) if mobile is None else np.array(mobile,dtype=bool)
    if kind=='II': delta=Analytical().action(obs,end.dq_rad_s,h,flags)
    elif kind=='III': delta=QP().action(obs,end.dq_rad_s,h,flags,np.zeros(2) if previous is None else previous)
    else: raise ValueError(kind)
    def evaluate(t):
        b,v,a=smooth_jet(t/h)
        p=path.sample(s+t)
        return p.q_rad+h*b*delta,p.dq_rad_s+v*delta,p.ddq_rad_s2+(a/h)*delta
    return evaluate,delta
