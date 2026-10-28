"""Causal, transition-local research rewards; immutable task execution is upstream.

JF/JM are observed executed-time sensor integrals; acceleration is the existing
online Human-state estimate, a declared proxy independently checked against
actual native Human motion in frozen evaluation. No future/native truth input.
All potentials use gamma=1 and terminal potential zero on failure.
"""
VERSIONS = {
 'R0': dict(version='R0_original_pilot_v3', progress=5., complete=20., failure=-10.,
            force_per_Ns=.0002, moment_per_Nms=0., variation=.01, failure_floor=1.5,
            rationale='Exact original reward; use original environment output.'),
 'R1': dict(version='R1_completion_dominant_balanced_dose', progress=2., complete=20., failure=-15.,
            force_per_Ns=.0005, moment_per_Nms=.005, variation=.02, failure_floor=15.,
            rationale='Reduce transient progress credit, retain a large terminal success gap, jointly price observed force and moment.'),
 'R2': dict(version='R2_quadratic_phase_potential_balanced_dose', progress=2., complete=20., failure=-15.,
            force_per_Ns=.0005, moment_per_Nms=.005, variation=.10, failure_floor=15.,
            rationale='Quadratic normalized task potential gives more credit near full phase-chain completion; increase online acceleration proxy cost.'),
}
def potential(phi, version):
    return phi*phi/3. if version=='R2' else phi
def transition(version, before, after, terminal, success, baseline_reward):
    if version=='R0': return float(baseline_reward), {'original':float(baseline_reward)}
    c=VERSIONS[version]
    old=potential(before['phi'], version)
    new=0. if terminal and not success else potential(after['phi'], version)
    parts=dict(progress=c['progress']*(new-old),
               completion=c['complete'] if terminal and success else c['failure'] if terminal else 0.,
               force=-c['force_per_Ns']*(after['force']-before['force']),
               moment=-c['moment_per_Nms']*(after['moment']-before['moment']),
               variation=-c['variation']*(after['variation']-before['variation']))
    if terminal and not success:
        observed=c['force_per_Ns']*after['force']+c['moment_per_Nms']*after['moment']+c['variation']*after['variation']
        parts['completion']-=max(0.,c['failure_floor']-observed)
    return sum(parts.values()),parts
def measurement(env):
    return dict(phi=float(env.phi), force=float(env.force_integral),
                moment=float(env.moment_integral),variation=float(env.motion_variation))
