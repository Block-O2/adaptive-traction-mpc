"""Radians, seconds; phase progress is independent of measured Human state."""
from dataclasses import dataclass
from enum import Enum
import numpy as np

class Failure(str, Enum):
    NECESSARY = 'mathematical_necessary_condition_conflict'
    FAMILY = 'motion_family_representation_insufficient'
    SOLVER = 'optimizer_did_not_find_solution'
    NATIVE = 'native_feasibility_rejection'
    ACTIVATION = 'activation_failure'
    RESPONSE = 'actual_physical_response_deviation'

class Rejected(ValueError):
    def __init__(self, category, detail):
        self.category, self.detail = category, detail
        super().__init__(f'{category.value}: {detail}')

def vector(x, n=2):
    a=np.array(x, dtype=float, copy=True)
    if a.shape!=(n,) or not np.isfinite(a).all(): raise ValueError('finite vector required')
    a.setflags(write=False)
    return a

@dataclass(frozen=True)
class State:
    p: np.ndarray
    v: np.ndarray
    a: np.ndarray
    def __post_init__(self):
        for k in ('p','v','a'): object.__setattr__(self,k,vector(getattr(self,k)))

@dataclass(frozen=True)
class Phase:
    start: np.ndarray
    goal: np.ndarray
    def __post_init__(self):
        for k in ('start','goal'): object.__setattr__(self,k,vector(getattr(self,k)))
    @property
    def length(self): return np.abs(self.goal-self.start)
    @property
    def sign(self): return np.sign(self.goal-self.start)
    def physical(self, state):
        return self.start+self.sign*state.p, self.sign*state.v, self.sign*state.a
    def remaining(self, state):
        active=self.length>0
        return float(np.sum((self.length[active]-state.p[active])/self.length[active]))

@dataclass(frozen=True)
class Limits:
    velocity: np.ndarray
    acceleration: np.ndarray
    rom: np.ndarray
    def __post_init__(self):
        for k in ('velocity','acceleration'):
            object.__setattr__(self,k,vector(getattr(self,k)))
            if np.any(getattr(self,k)<=0): raise ValueError('positive limits required')
        a=np.array(self.rom,dtype=float,copy=True)
        if a.shape!=(2,2) or not np.isfinite(a).all() or np.any(a[:,0]>a[:,1]):
            raise ValueError('finite ordered ROM required')
        a.setflags(write=False); object.__setattr__(self,'rom',a)
