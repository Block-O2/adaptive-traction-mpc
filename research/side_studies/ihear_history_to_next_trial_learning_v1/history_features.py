"""Pure allowlisted causal history representation. No plant/native truth or future outcome input."""
import hashlib,json
import numpy as np
PHASES=('OUTBOUND','HOLD','RETURN')
FEATURE_NAMES=['JF','moment','out_force_mid','return_force_mid','out_knee_error_deg','return_knee_error_deg',
    'out_hip_error_deg','return_hip_error_deg','knee_tracking_rms_deg','hip_tracking_rms_deg',
    'return_knee_velocity_p95_deg_s','out_knee_velocity_p95_deg_s']
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def make_action(phase=None,slot=None,knee_delta_deg=0.,kind='B'):
    x=dict(base=kind,phase=phase,slot=slot,knee_delta_deg=float(knee_delta_deg),units='deg',parent='native_B',limit_deg=.3)
    x['action_hash']=digest(x);return x
def grid():
    return [make_action()]+[make_action(p,s,d) for p,s in [('OUTBOUND',1),('RETURN',3)] for d in [-.3,.3]]
def encode_action(a):
    # Phase-local signed amplitude and curvature terms; explicit H x action design in value learner.
    v=np.zeros(2)
    if a['phase'] in ['OUTBOUND','RETURN']:v[['OUTBOUND','RETURN'].index(a['phase'])]=a['knee_delta_deg']/.3
    return v
def summarize(rows, metadata):
    assert len(rows)>2 and metadata['complete_task_observed'], 'INCOMPLETE_HISTORY_NOT_TRAINING_SAMPLE'
    t=np.array([r['physical_s'] for r in rows]);dt=np.diff(t)
    assert np.all(dt>0) and np.max(dt)<.006, 'HISTORY_NOT_FULL_5MS'
    ph=np.array([r['phase'] for r in rows]);force=np.linalg.norm([r['force_world_N'] for r in rows],axis=1)
    moment=np.linalg.norm([r['moment_world_Nm'] for r in rows],axis=1)
    est=np.array([r['estimated_q_dq'] for r in rows]);ref=np.array([r['reference_q_dq'] for r in rows])
    err=np.rad2deg(est[:,:2]-ref[:,:2]);dq=np.rad2deg(est[:,2:]);acc=np.gradient(dq,t,axis=0,edge_order=2);jerk=np.gradient(acc,t,axis=0,edge_order=2)
    prog=np.array([r['reference_progress'] for r in rows]);weights=np.r_[dt,0.]
    phase={};windows=[]
    for p in PHASES:
        m=ph==p;w=weights[m];den=max(w.sum(),1e-12)
        phase[p]=dict(duration_s=float(w.sum()),JF_N_s=float(force[m]@w),moment_Nm_s=float(moment[m]@w),
            peak_force_N=float(force[m].max()),force_p90_N=float(np.percentile(force[m],90)),
            tracking_RMS_deg=np.sqrt(np.sum(err[m]**2*w[:,None],axis=0)/den).tolist(),
            velocity_p95_deg_s=np.percentile(abs(dq[m]),95,axis=0).tolist(),
            acceleration_p95_deg_s2=np.percentile(abs(acc[m]),95,axis=0).tolist(),
            jerk_p95_deg_s3=np.percentile(abs(jerk[m]),95,axis=0).tolist(),
            derivative_source='estimated 5ms history; not native truth qualification')
        for lo,hi in [(0,.2),(.2,.4),(.4,.6),(.6,.8),(.8,1.00001)]:
            q=m&(prog>=lo)&(prog<hi);wq=weights[q];denq=max(wq.sum(),1e-12)
            windows.append(dict(phase=p,progress=[lo,min(hi,1.)],duration_s=float(wq.sum()),JF_N_s=float(force[q]@wq),
                mean_force_N=float(force[q]@wq/denq),tracking_mean_deg=(np.sum(err[q]*wq[:,None],axis=0)/denq).tolist()))
    local={}
    for p in ['OUTBOUND','RETURN']:
        m=(ph==p)&(prog>=.2)&(prog<.6);w=weights[m];den=max(w.sum(),1e-12)
        local[p]=dict(mean_force_N=float(force[m]@w/den),tracking_mean_deg=(np.sum(err[m]*w[:,None],axis=0)/den).tolist())
    jf=float(force@weights);mi=float(moment@weights)
    rms=np.sqrt(np.sum(err**2*weights[:,None],axis=0)/weights.sum())
    features=[jf,mi,local['OUTBOUND']['mean_force_N'],local['RETURN']['mean_force_N'],
        local['OUTBOUND']['tracking_mean_deg'][1],local['RETURN']['tracking_mean_deg'][1],
        local['OUTBOUND']['tracking_mean_deg'][0],local['RETURN']['tracking_mean_deg'][0],rms[1],rms[0],
        phase['RETURN']['velocity_p95_deg_s'][1],phase['OUTBOUND']['velocity_p95_deg_s'][1]]
    return dict(schema='causal_full_history_v1',metadata=metadata,phase=phase,progress_windows=windows,local=local,
        feature_names=FEATURE_NAMES,features=list(map(float,features)),JF_N_s=jf,moment_Nm_s=mi,
        max_source_age_s=max(r['source_age_s'] for r in rows),sample_count=len(rows),first_s=float(t[0]),last_s=float(t[-1]),
        commissioned_belief=metadata['commissioned_belief'],
        truth_used=False,policy_can_use_native_derivatives=False,raw_history_sha256=digest(rows))
def ilc(history, enabled=True, previous=None):
    if not enabled:return dict(method='ILC',history_enabled=False,action=make_action(),reason='NO_PREVIOUS_HISTORY_A0',model_updates=0)
    # Compliant correction hypothesis: move the middle knee reference toward the
    # prior measured/estimated lag, reducing displacement in the larger-load window.
    p=max(['OUTBOUND','RETURN'],key=lambda p:history['local'][p]['mean_force_N'])
    e=history['local'][p]['tracking_mean_deg'][1]
    delta=float(np.clip(.25*e,-.3,.3))
    if previous is not None and previous.get('phase')==p:delta=float(np.clip(previous['knee_delta_deg']+delta,-.3,.3))
    a=make_action(p,1 if p=='OUTBOUND' else 3,delta)
    return dict(method='ILC',history_enabled=True,action=a,chosen_window=p,observed_knee_lag_deg=e,gain=.25,
        rule='delta=clip(previous_delta+0.25*(estimated_actual-reference),+-0.3deg)',
        hypothesis='compliant middle-posture correction may reduce cuff displacement; cumulative force benefit is unproven',
        history_sha256=history['raw_history_sha256'],model_updates=1)
