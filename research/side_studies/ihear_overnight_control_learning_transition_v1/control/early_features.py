"""Earlier decision: completed measured sample and known planned reference only."""
import numpy as np
NAMES=['qerr_hip_deg','qerr_knee_deg','dqerr_hip_deg_s','dqerr_knee_deg_s','force_norm_N','moment_norm_Nm','outbound_elapsed_s','planned_return_prefix_0','planned_return_prefix_1','planned_return_prefix_2']
def vector(estimate,qref,vref,force,moment,elapsed,prefix):
    return np.r_[np.rad2deg(np.asarray(estimate)-np.r_[qref,vref]),np.linalg.norm(force),np.linalg.norm(moment),elapsed,prefix]
def capture(b,interface):
    now=float(b['physical_now'])
    row=next(r for r in reversed(b['runtime']['trace']) if r['stage']=='TASK' and r['time_s']<now-1e-9)
    assert row['task_phase']=='OUTBOUND' and now-row['time_s']<=.0100001
    known=interface.condition['prefix']['RETURN'][0]
    values=vector(row['estimated_state'],row['q_ref_rad'],row['dq_ref_rad_s'],row['cuff_force_world_n'],row['cuff_moment_world_nm'],row['task_elapsed_s'],known)
    assert values.shape==(10,) and np.all(np.isfinite(values))
    return dict(features=values.tolist(),feature_names=NAMES,source_sample_time_s=float(row['time_s']),physical_s=now,source_age_s=now-row['time_s'],origin='last completed TASK sample strictly before first intervention at OUTBOUND prefix boundary',known_return_prefix=known,truth_used=False,future_outcomes_used=False,planned_reference_is_not_future_physical_truth=True)
