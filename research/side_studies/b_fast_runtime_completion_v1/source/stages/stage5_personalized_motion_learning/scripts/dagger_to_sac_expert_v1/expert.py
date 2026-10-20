"""Stateless causal query: no environment, simulator, demo or trajectory access."""
import numpy as np
class CausalHipLeadingExpert:
    def __init__(self,config,scales):
        self.hip_release=float(config['estimated_hip_release_rad'])
        self.ref_release=float(config['reference_hip_release_rad'])
        self.knee_preview=float(config['knee_preview_rad'])
        self.scales=np.asarray(scales).copy()
    def query(self,observation):
        raw=np.asarray(observation,dtype=float)*self.scales
        if raw.shape!=(55,) or not np.all(np.isfinite(raw)):raise ValueError('INVALID_CAUSAL_QUERY')
        q,dq,ref_q,ref_dq,ref_ddq=raw[:2],raw[2:4],raw[4:6],raw[6:8],raw[8:10]
        phase=raw[41:44];elapsed,phase_elapsed=raw[44],raw[47]
        if np.count_nonzero(phase>.5)!=1:raise ValueError('INVALID_PHASE')
        target=raw[45:47].copy() # Current causal robust terminal reference, not nominal truth.
        lead=bool(phase[0]>.5 and (q[0]<self.hip_release or ref_q[0]<self.ref_release))
        if lead:target[1]=min(target[1],ref_q[1]+self.knee_preview)
        # Frozen absolute action interface ROM [0,125] deg, exactly as SAC adapter.
        action=(2*target/np.radians(125.)-1).astype(np.float32)
        if np.any(np.abs(action)>1+1e-6):raise ValueError('EXPERT_ILLEGAL_ROM')
        return action,dict(mode='HIP_LEAD' if lead else 'TERMINAL_RECOVERY',estimated_q=q,estimated_dq=dq,
            reference_q=ref_q,reference_dq=ref_dq,reference_ddq=ref_ddq,phase=phase,elapsed_s=elapsed,
            phase_elapsed_s=phase_elapsed,target=target,truth_consumed=False,trajectory_lookup=False)
