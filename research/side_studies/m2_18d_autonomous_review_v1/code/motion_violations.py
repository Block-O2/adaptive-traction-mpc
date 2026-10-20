from study_common import *
import matched_harness as mh
def summarize_intervals(t,mask,dt=.00025):
 ids=np.flatnonzero(mask)
 if not len(ids):return dict(total_duration_s=0.,interval_count=0,longest_intervals=[])
 groups=np.split(ids,np.flatnonzero(np.diff(ids)>1)+1)
 spans=[dict(start_s=float(t[g[0]]),end_s=float(t[g[-1]]),duration_s=float(t[g[-1]]-t[g[0]]+dt),samples=len(g)) for g in groups]
 return dict(total_duration_s=float(len(ids)*dt),interval_count=len(spans),longest_intervals=sorted(spans,key=lambda x:-x['duration_s'])[:20],all_ranges_reconstructible_from_retained_boolean_mask=True)
def timeline(ident,base):
 S=STUDY;out={};masks={};p=S/'motion_series'/(ident+'.npz')
 with np.load(p) as z:
  t=z['time_s'];q=np.rad2deg(z['true_q_rad']);sigs={'velocity_deg_s':np.rad2deg(z['true_dq_rad_s']),'acceleration_deg_s2':np.rad2deg(z['acceleration_rad_s2']),'jerk_deg_s3':np.rad2deg(z['jerk_rad_s3'])}
  for sig,values in sigs.items():
   for met in ['max_abs','p95_abs']:
    threshold=np.asarray(base['motion']['raw']['full'][sig][met])*1.1+1e-7
    for j,joint in enumerate(['hip','knee']):
     key=sig+'_'+met+'_'+joint;mask=abs(values[:,j])>threshold[j];masks[key]=mask;out[key]=dict(**summarize_intervals(t,mask),threshold=float(threshold[j]),max_pointwise_exceedance=float(np.maximum(abs(values[:,j])-threshold[j],0).max()),meaning='hard full-task max exceedance' if met=='max_abs' and sig!='jerk_deg_s3' else 'diagnostic pointwise exposure above B statistic; p95 gate uses full-task quantile; jerk max stays diagnostic')
  masks['time_s']=t;np.savez_compressed(S/'motion_series'/(ident+'_EXPOSURE_MASKS.npz'),**masks)
 return dict(rows=out,masks_path=str(S/'motion_series'/(ident+'_EXPOSURE_MASKS.npz')),continuous_full_statistics='EVALUATIONS continuous_constraints covers RMS, p95, dose, phase timing, boundaries, moments, tracking and peaks without changing acceptance',scope='raw native dense motion; exposure intervals diagnose duration, never replace frozen full statistics')
