"""Memoization lives for one worker invocation. The native 21-point screen remains its caller."""
from collections import Counter, defaultdict
from hashlib import sha256
from time import perf_counter_ns
import numpy as np
from fixture import ia, Window, AdaptiveMechanicsScreenV22, serialize
from reference import time_value


class Measurements:
    def __init__(self, reuse, audit):
        self.reuse = reuse
        self.audit = audit
        self.cache = defaultdict(dict)
        self.counts = Counter()
        self.ns = Counter()
        self.traces = defaultdict(sha256)

    def get(self, name, key, fn, args):
        cache = self.cache[name]
        if self.reuse and key in cache:
            result = cache[key]
            self.counts[name+'_hit'] += 1
        else:
            start = perf_counter_ns() if self.audit else 0
            result = fn(*args)
            if self.audit:
                self.ns[name] += perf_counter_ns() - start
            if self.reuse:
                cache[key] = result
            self.counts[name+'_executed'] += 1
        if self.audit and name != 'model':
            # Per-method ordered digests cover rows, including signed zero in binary64 jets.
            trace = self.traces[name]
            if name == 'sample':
                for value in (args[0], result.q_rad, result.dq_rad_s, result.ddq_rad_s2):
                    trace.update(np.asarray(value, dtype='<f8').tobytes())
            else:
                for v in args: trace.update(v.tobytes())
                if isinstance(result,dict):
                    for label in sorted(result):
                        trace.update(label.encode())
                        trace.update(serialize(result[label]).encode())
                else:
                    trace.update(np.asarray(result).tobytes())
        return result


class SampledPath:
    def __init__(self, path, measurements):
        self.path = path
        self.duration_s = path.duration_s
        self.m = measurements

    def sample(self, t):
        path = self.path
        key = None
        if self.m.reuse:
            local = time_value(t)
            if not 0 <= local <= path.duration:
                raise ValueError('outside finite schedule')
            if isinstance(path, Window):
                key = (id(path.source), path.offset + local)
            else:
                fixed = isinstance(path, ia.StaticHold) or getattr(path,'stationary',False)
                key = (id(path), 0 if fixed else local)
        return self.m.get('sample',key,path.sample,(t,))


class Model:
    def __init__(self, base, measurements):
        self.base = base
        self.m = measurements

    def run(self,name,*args):
        # Arrays in this native call have fixed logical layouts. Keep dtype and shape explicit.
        key = tuple((x.dtype.str,x.shape,x.tobytes()) for x in args) if self.m.reuse else None
        return self.m.get(name,key,getattr(self.base,name),args)

    def inverse_dynamics(self,*args):
        return self.run('inverse_dynamics',*args)

    def allocate_generalized_action(self,*args):
        return self.run('allocate_generalized_action',*args)

    def state_residual_nm(self,*args):
        return self.run('state_residual_nm',*args)


class Screen:
    def __init__(self,c,reuse=True,audit=False):
        self.belief = c.b
        self.sequence = c.b.sequence
        self.m = Measurements(reuse,audit)
        self.counts = self.m.counts

    def human_model(self):
        return Model(self.m.get('model', self.sequence, self.belief.human_model, ()), self.m)

    def evaluate(self,candidate,path):
        if self.m.audit:
            self.m.traces['sample'].update(np.float64(path.duration_s).tobytes())
        return AdaptiveMechanicsScreenV22().evaluate(self,candidate,SampledPath(path,self.m))
