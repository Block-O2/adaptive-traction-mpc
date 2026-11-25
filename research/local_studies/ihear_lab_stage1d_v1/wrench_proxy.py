"""One frozen joint Human model, local measured residual, no learning updates."""
from dataclasses import dataclass
from copy import deepcopy
import numpy as np
from phase_coordinates import vector

def model_wrench(model,q,dq,ddq):
    tau=model.inverse_dynamics(q,dq,ddq)
    return np.asarray(model.allocate_generalized_action(tau,q)['wrench_world'],dtype=float)

@dataclass(frozen=True)
class FrameStamp:
    time: float
    frame: str
    point: str
    direction: str

class FrozenProxy:
    """Snapshot creation requires matching frame, reference point, sign and time.

    Caller authenticates native observation/receipt; labels are not authentication.
    Private deepcopy prevents subsequent belief changes modifying this scoring run.
    """
    def __init__(self,model,version,receipt_id,state,measured,observation_stamp,wrench_stamp):
        if observation_stamp!=wrench_stamp: raise ValueError('unaligned state and wrench')
        self.__model=deepcopy(model)
        self.version=version; self.receipt_id=receipt_id; self.stamp=observation_stamp
        self.residual=vector(np.asarray(measured)-model_wrench(self.__model,*state),6)
        self._calls=0
    def predict(self,phase,state):
        self._calls+=1
        return model_wrench(self.__model,*phase.physical(state))+self.residual
    @property
    def key(self):
        return (self.version,self.receipt_id,self.stamp,tuple(self.residual))

class MeasuredMetrics:
    """Separate recorder for authenticated measurement samples. No JF subtraction.

    Authentication occurs upstream. This is offline integration, not a receipt hook.
    Missing tracking/jerk data remain missing; no invented measurements.
    """
    def __init__(self):
        self.JF=0.; self.JM=0.; self.force_rate_squared=0.
        self.tracking_squared=0.; self.jerk_squared=0.; self.previous=None
    def add(self,t,wrench,tracking_error,jerk):
        row=(float(t),vector(wrench,6),vector(tracking_error),vector(jerk))
        if self.previous is not None:
            t0,w0,e0,j0=self.previous; dt=t-t0
            if dt<=0: raise ValueError('measurement time must increase')
            self.JF+=dt*(np.linalg.norm(w0[:3])+np.linalg.norm(row[1][:3]))/2
            self.JM+=dt*(np.linalg.norm(w0[3:])+np.linalg.norm(row[1][3:]))/2
            self.force_rate_squared+=np.sum((row[1][:3]-w0[:3])**2)/dt
            self.tracking_squared+=dt*(e0@e0+row[2]@row[2])/2
            self.jerk_squared+=dt*(j0@j0+row[3]@row[3])/2
        self.previous=row
