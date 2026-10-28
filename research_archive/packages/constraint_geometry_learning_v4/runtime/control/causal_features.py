"""Strict live observation whitelist. No archived outcome, true Human state or future data."""
import numpy as np
FEATURE_NAMES=['qerr_hip_deg','qerr_knee_deg','dqerr_hip_deg_s','dqerr_knee_deg_s','force_norm_N','moment_norm_Nm','phase_elapsed_s']
def capture(b,interface):
    obs=np.asarray(b['observation'].as_array(),float)
    ref=np.asarray(b['arguments']['current_reference_state'],float)
    measured=b['interface']
    force=np.asarray(measured.measured_force_world_n,float)
    moment=np.asarray(measured.measured_moment_world_nm,float)
    req=b['request'];now=float(b['physical_now'])
    vector=np.r_[np.rad2deg(obs[:4]-ref[:4]),np.linalg.norm(force),np.linalg.norm(moment),float(b['task_state'].phase_elapsed_s)]
    assert vector.shape==(7,) and np.all(np.isfinite(vector))
    return dict(feature_names=FEATURE_NAMES,features=vector.tolist(),human_estimate=obs[:4].tolist(),reference_state=ref[:4].tolist(),force_world_N=force.tolist(),moment_world_Nm=moment.tolist(),phase=b['task_state'].phase.value,slot=interface.count['RETURN'],physical_s=now,source_sample_time_s=float(req.source_sample_time_s),source_age_s=now-float(req.source_sample_time_s),request_id=req.request_id,model_hash=interface.model_hash,observation_role='CAUSAL_MEASURED_OR_ESTIMATED',truth_used=False,future_matched_B_used=False,previous_complete_repetition_available=False)
