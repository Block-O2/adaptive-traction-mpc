"""Stage1-BG offline proposal mathematics. The caller owns the receipt and the plant."""
from fractions import Fraction as R
from math import comb, exp, factorial, isfinite, nextafter
import numpy as np
from wrench_proxy import model_wrench
from traction_mpc_stage5.human_waypoint_scheduler import ScheduledHumanReferenceSample

H = .040
EPS = .001

def rate(x):
    if not isfinite(x) or not 0 < x <= 1:
        raise ValueError('invalid rate')
    return x

def vector(x, n):
    y = np.asarray(x, dtype=float)
    if y.shape != (n,) or not np.all(np.isfinite(y)):
        raise ValueError('invalid vector')
    return y

def force_pair(model, posture, reference, alpha):
    rate(alpha)
    q = vector(posture, 2)
    v = vector(reference.dq_rad_s, 2)
    a = vector(reference.ddq_rad_s2, 2)
    def evaluate(lam):
        return vector(model_wrench(model, q, lam*v, lam**2*a), 6)[:3]
    return evaluate(alpha), evaluate(alpha*exp(-EPS))

def desired(force, pair, alpha):
    rate(alpha)
    force = vector(force, 3)
    upper, lower = (vector(v, 3) for v in pair)
    derivative = vector((upper-lower)/EPS, 3)
    if not np.any(force):
        return None, 1.
    # Common scaling keeps the dimensionless quotient unchanged.
    scale = max(np.max(abs(force)), np.max(abs(derivative)))
    f, d = force/scale, derivative/scale
    f2 = f@f
    denominator = np.linalg.norm(f)*np.linalg.norm(d) + f2
    if not isfinite(denominator) or denominator <= 0:
        raise ValueError('incomputable normalization')
    g = float((f@d-f2)/denominator)
    if not isfinite(g):
        raise ValueError('incomputable sensitivity')
    return g, rate(min(1., alpha*exp(-g)))

def clock(s, a0, a1, t):
    rate(a0)
    rate(a1)
    if not isfinite(s) or s < 0 or not 0 <= t <= H:
        raise ValueError('outside transition')
    u = t/H
    delta = a1-a0
    return (s+a0*t+H*delta*(u**3-.5*u**4),
            a0+delta*u*u*(3-2*u), delta*6*u*(1-u)/H)

def sample(path, s, a0, a1, t):
    sigma, alpha, adot = clock(s, a0, a1, t)
    if sigma > path.duration_s:
        raise ValueError('past owned path')
    nominal = path.sample(sigma)
    return ScheduledHumanReferenceSample(nominal.q_rad, nominal.dq_rad_s*alpha,
          nominal.ddq_rad_s2*alpha**2+nominal.dq_rad_s*adot)

def bernstein_abs_bound(c, order, duration, start, width):
    # Exact power-basis restriction on the normalized time interval, followed
    # by the Bernstein convex-hull bound. No root tolerances or sampled maxima.
    lo, dx = start/duration, width/duration
    deriv = [R(float(c[j])) * (factorial(j)//factorial(j-order))/duration**order
             for j in range(order, len(c))]
    n = len(deriv)-1
    powers = [dx**i*sum(deriv[j]*comb(j,i)*lo**(j-i) for j in range(i,n+1))
              for i in range(n+1)]
    return max(abs(sum(powers[i]*R(comb(k,i),comb(n,i)) for i in range(k+1)))
               for k in range(n+1))

def allowance(path, boundary, vmax, amax):
    duration, start, width = R(path.duration_s), R(boundary), 2*R(H)
    if start < 0 or start+width > duration:
        raise ValueError('two periods do not fit')
    vmax, amax = vector(vmax, 2), vector(amax, 2)
    delta = R(1)  # natural maximum separation of admissible rates
    bounds = []
    for axis,c in enumerate(path.coefficients):
        v, a = (bernstein_abs_bound(c,j,duration,start,width) for j in (1,2))
        bounds.append((float(v),float(a)))
        slack = R(float(amax[axis]))-a
        if v > R(float(vmax[axis])) or slack < 0:
            raise ValueError('motion bound unavailable')
        if v:
            delta = min(delta, R(H)*slack/(R(3,2)*v))
    return delta, bounds

def project(target, alpha, delta):
    target, alpha = R(rate(target)), R(rate(alpha))
    if delta < 0:
        raise ValueError('negative allowance')
    lo, hi = max(R(0),alpha-delta,1-delta), min(R(1),alpha+delta)
    if hi <= 0 or lo > hi:
        raise ValueError('empty change/recovery intersection')
    x = float(max(lo,min(target,hi)))
    if R(x)<lo: x=nextafter(x,float('inf'))
    if R(x)>hi: x=nextafter(x,0.)
    if not lo<=R(x)<=hi or x<=0:
        raise ValueError('no representable admissible rate')
    return x
