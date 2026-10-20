from freeze import *
import numpy as np
def main():
 fields=('time_s','physics_steps','stage','estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','cr12_q_rad','cr12_dq_rad_s','physical_cuff_position_world_m','physical_cuff_rotation_world','physical_cuff_force_world_n','physical_cuff_moment_world_nm');rows=[]
 for parent,branches in (('014_streaming_fork_v2_regression',('streaming_fork_v2_regression_OUTBOUND_0_candidate0','streaming_fork_v2_regression_RETURN_1_candidate0')),('013_encoder_v3_late_gate',('encoder_v3_gate_RETURN_1_candidate0',))):
  with np.load(STUDY/'source/results'/parent/'trace.npz') as z:base={k:z[k].copy() for k in fields}
  for branch in branches:
   checks={}
   with np.load(STUDY/'source/results'/branch/'trace.npz') as z:
    for key,a in base.items():
     b=z[key];numeric=a.dtype.kind in 'fci';exact=bool(np.array_equal(a,b,equal_nan=True)) if numeric else bool(np.array_equal(a,b));difference=float(np.nanmax(np.abs(a-b))) if numeric and a.shape==b.shape else None;checks[key]=dict(exact=exact,max_abs_difference=difference,shape_equal=a.shape==b.shape)
   rows.append(dict(parent=parent,branch=branch,fields=checks,all_physical_and_reference_fields_exact=all(c['exact'] for c in checks.values())))
 status='PASS' if all(r['all_physical_and_reference_fields_exact'] for r in rows) else 'NOT_BIT_EXACT'
 save(STUDY/'FORK_WHOLE_TRACE_AUDIT.json',dict(status=status,rows=rows,host_wall_timing_intentionally_excluded=True,physics_or_policy_not_rerun=True));print(json.dumps(dict(status=status,comparisons=len(rows))))
if __name__=='__main__':main()
