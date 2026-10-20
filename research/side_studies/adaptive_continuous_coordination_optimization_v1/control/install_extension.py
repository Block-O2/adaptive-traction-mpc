from pathlib import Path
import shutil
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');OLD=P.parent/'adaptive_continuous_coordination_interface_v1'
f=P/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/multisegment_reference.py'
s=f.read_text();a=s.index('def build_reference(');b=s.index('\ndef seal_certificate',a)
legacy=s[a:b].replace('def build_reference(','def legacy_build_reference(',1)
extension='''
def build_reference(primary,*,binding,perturbation_rad=(0.,0.),fractions=(.25,.5,.75)):
    spec=binding.get('study_spec')
    if spec is None:return legacy_build_reference(primary,binding=binding,perturbation_rad=perturbation_rad,fractions=fractions)
    original=FrozenPolynomial.freeze(primary);T=original.duration_s
    geo=np.asarray(spec['fractions'],float);tim=np.asarray(spec.get('time_fractions',spec['fractions']),float);delta=np.radians(np.asarray(spec['deltas_deg'],float))
    if not 1<=len(geo)<=3 or delta.shape!=(len(geo),2) or len(tim)!=len(geo):raise ValueError('STUDY_DENSITY_SHAPE')
    if not np.all(np.isfinite(np.r_[geo,tim,delta.ravel()])) or np.any(np.diff(np.r_[0.,geo,1.])<=0) or np.any(np.diff(np.r_[0.,tim,1.])<=0):raise ValueError('STUDY_INVALID_KNOTS')
    if np.max(abs(delta))>np.radians(.05)+1e-12:raise ValueError('BOUNDED_SINGLE_KNOT_PERTURBATION')
    knots=tuple(T*np.r_[0.,tim,1.]);geom=tuple(T*np.r_[0.,geo,1.]);states=[[original.sample(t).q_rad,original.sample(t).dq_rad_s,original.sample(t).ddq_rad_s2] for t in geom]
    for i,d in enumerate(delta,1):states[i][0]=states[i][0]+d
    zero=bool(not np.any(delta) and np.array_equal(geo,tim));pieces=[]
    for i,(lo,hi) in enumerate(zip(knots,knots[1:])):
        values=restrict(original.coefficients,T,lo,hi) if zero else hermite(*states[i],*states[i+1],hi-lo)
        pieces.append(FrozenPolynomial(tup(values),float(hi-lo),original.candidate,original.metadata_json))
    obj=MultiSegmentReference(tuple(pieces),knots,original.candidate,original,zero,encode(binding),FrozenEscape.freeze(getattr(primary,'safe_escape',None)))
    object.__setattr__(obj,'sealed_digest',digest(obj.content()))
    # Keep the original amplitude envelope for this research extension.
    samples=np.linspace(0,T,501)
    if max(np.max(abs(obj.sample(float(t)).q_rad-original.sample(float(t)).q_rad)) for t in samples)>np.radians(.05)+1e-10:raise ValueError('STUDY_FULL_PATH_AMPLITUDE')
    return obj
'''
f.write_text(s[:a]+legacy+extension+s[b:])
shutil.copytree(OLD/'tests',P/'tests',ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
for p in (P/'tests').glob('*.py'):p.write_text(p.read_text().replace(str(OLD),str(P)))
(P/'key_traces').symlink_to(OLD/'key_traces',target_is_directory=True)
print('Builder extended; certify_path and current_path_check unchanged')
