"""Nested, interpretable endpoint-zero coordination proposals; no plant inputs."""
import numpy as np

DIMENSIONS = {1: 6, 2: 12, 3: 20}
NAMES = ['outbound_hip_lead', 'outbound_knee_lag', 'lead_peak_progress',
         'lead_duration_width', 'return_hip_lead', 'return_knee_lag']
NAMES += [f'{phase}_{part}_relative_offset' for phase in ('outbound', 'return')
          for part in ('early', 'middle', 'late')]
NAMES += [f'{phase}_smooth_control_{part}' for phase in ('outbound', 'return')
          for part in ('15', '35', '65', '85')]
LOW = np.array([-.10, -.10, .20, .50, -.10, -.10] + [-.04]*14)
HIGH = np.array([.10, .10, .80, 2., .10, .10] + [.04]*14)

def bump(s, peak, width=1.):
    s = min(1., max(0., float(s)))
    return ((s/peak)**(2*(1-peak))*((1-s)/(1-peak))**(2*peak))**(1/width)

def parameters(spec):
    level = int(spec['level'])
    p = np.asarray(spec['parameters'], float)
    if len(p) != DIMENSIONS[level] or not np.isfinite(p).all():
        raise ValueError('invalid coordination dimension or nonfinite parameters')
    if np.any(p < LOW[:len(p)]) or np.any(p > HIGH[:len(p)]):
        raise ValueError('coordination proposal outside declared domain')
    return np.pad(p, (0, 20-len(p)))

def neutral(level):
    p = np.zeros(DIMENSIONS[level]); p[2:4] = [.5, 1.]
    return p

def known_good(level):
    p = neutral(level); p[:2] = [.06, .06]
    return p

def phase_active(p, phase):
    ids = [0, 1, 6, 7, 8, 12, 13, 14, 15] if phase == 'OUTBOUND' else [4, 5, 9, 10, 11, 16, 17, 18, 19]
    return bool(np.any(p[ids] != 0))

def deformation(s, phase, spec):
    p = parameters(spec)
    hip, knee = p[:2] if phase == 'OUTBOUND' else p[4:6]
    result = np.array([hip, -knee])*bump(s, p[2], p[3])
    offset = 6 if phase == 'OUTBOUND' else 9
    extra = 12 if phase == 'OUTBOUND' else 16
    relative = sum(p[offset+i]*bump(s, peak) for i, peak in enumerate((.25,.5,.75)))
    relative += sum(p[extra+i]*bump(s, peak) for i, peak in enumerate((.15,.35,.65,.85)))
    return result + np.array([relative, -relative])

def test_space():
    for level in DIMENSIONS:
        for phase in ('OUTBOUND', 'RETURN'):
            spec = {'level': level, 'parameters': known_good(level).tolist()}
            assert np.array_equal(deformation(0,phase,spec), np.zeros(2))
            assert np.array_equal(deformation(1,phase,spec), np.zeros(2))
            assert np.array_equal(deformation(.4,phase,{'level':level,'parameters':neutral(level).tolist()}), np.zeros(2))
    base = known_good(1)
    for s in np.linspace(0,1,41):
        a = deformation(s,'OUTBOUND',{'level':1,'parameters':base.tolist()})
        assert np.allclose(a, [.06*bump(s,.5),-.06*bump(s,.5)],atol=1e-14)
        for level in (2,3):
            p = neutral(level); p[:6] = base
            assert np.array_equal(a,deformation(s,'OUTBOUND',{'level':level,'parameters':p.tolist()}))
    try: parameters({'level':1,'parameters':[1,0,.5,1,0,0]})
    except ValueError: pass
    else: raise AssertionError('domain guard missing')
    return {'nested_levels':True,'endpoint_preservation':True,'signed_hip_knee_support':True,
            'old_hip_lead_exact_equivalence':True,'domain_guard':True}
