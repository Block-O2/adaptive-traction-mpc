from study_common import *
import matched_harness as mh
S=STUDY
def put(n,x):mh.put(S/n,x)
def ranges(t,mask):
 ids=np.flatnonzero(mask)
 if not len(ids):return []
 groups=np.split(ids,np.flatnonzero(np.diff(ids)>1)+1)
 return [dict(start_s=float(t[g[0]]),end_s=float(t[g[-1]]),duration_s=float(t[g[-1]]-t[g[0]]+.00025),samples=len(g)) for g in groups]
def analyze(group='baseline'):
 ev=[json.loads(l) for l in (S/'EVALUATIONS.jsonl').read_text().splitlines()];baseid=group+'_B0_repeat_1';b=json.loads((S/'reports'/(baseid+'_MEASURED.json')).read_text());out=[]
 with np.load(S/'source/results'/baseid/'trace.npz') as z:
  ix=z['stage']=='TASK';bt=z['time_s'][ix];bf=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1)
 for row in ev:
  if not row['id'].startswith(group+'_'):continue
  ident=row['id'];m=json.loads(Path(row['metrics_path']).read_text());line=json.loads((S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')).read_text())
  with np.load(S/'source/results'/ident/'trace.npz') as z:
   ix=z['stage']=='TASK';tt=z['time_s'][ix];ff=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1)
  # Aligned absolute physics-clock bins are descriptive, never new acceptance or time-warp.
  bins=[]
  for lo in np.arange(bt[0],min(bt[-1],tt[-1]),.5):
   hi=min(lo+.5,bt[-1],tt[-1]);bi=np.maximum(0,np.minimum(bt[1:],hi)-np.maximum(bt[:-1],lo));ci=np.maximum(0,np.minimum(tt[1:],hi)-np.maximum(tt[:-1],lo));bins.append(dict(start_s=float(lo),end_s=float(hi),B_J_F_N_s=float(bf[:-1]@bi),candidate_J_F_N_s=float(ff[:-1]@ci),gain_N_s=float(bf[:-1]@bi-ff[:-1]@ci)))
  burdens={};slot_scores=[];dec=json.loads((S/'output'/(ident+'_DECISIONS.json')).read_text())['rows']
  with np.load(S/'motion_series'/(ident+'.npz')) as z:
   t=z['time_s'];sig={'velocity_deg_s':np.rad2deg(z['true_dq_rad_s']),'acceleration_deg_s2':np.rad2deg(z['acceleration_rad_s2']),'jerk_deg_s3':np.rad2deg(z['jerk_rad_s3'])}
   excess=np.zeros(len(t),bool)
   for k,v in sig.items():
    threshold=np.asarray(b['motion']['raw']['full'][k]['max_abs'])*1.1+1e-7;mask=np.any(abs(v)>threshold,axis=1)
    if k!='jerk_deg_s3':excess|=mask
    burdens[k]=dict(max_threshold=threshold,pointwise_max_exceedance_ranges=ranges(t,mask),exceedance_duration_s=float(mask.sum()*.00025),hard_max_gate=k!='jerk_deg_s3',p95_and_RMS_still_full_task_statistics=True)
   for r in line['rows']:
    if not r['physically_executed_nonzero']:continue
    receipts=r['actual_command_receipts'];lo=min(v['start_physics_s'] for v in receipts);hi=max(v['end_physics_s'] for v in receipts);mask=(t>=lo)&(t<=hi);score=float(np.maximum(abs(sig['acceleration_deg_s2'][mask])-np.asarray(b['motion']['raw']['full']['acceleration_deg_s2']['max_abs'])*1.1,0).sum()*.00025)
    ds=[d for d in dec if d['phase']==r['phase']];d=min(ds,key=lambda d:abs(d['task_s']+tt[0]-r['proposal_physics_s'])) if ds and r['proposal_physics_s'] is not None else {}
    slot_scores.append(dict(phase=r['phase'],decision_index=r['decision_index'],native_index=d.get('native_index'),proposal_s=r['proposal_physics_s'],start_s=lo,end_s=hi,acceleration_excess_area=score,native_metadata=r['native_coordination_metadata']))
   cf=ff[np.clip(np.searchsorted(tt,t,side='right')-1,0,len(ff)-1)];bb=bf[np.clip(np.searchsorted(bt,t,side='right')-1,0,len(bf)-1)];positive=np.maximum(bb-cf,0)
   overlap=dict(positive_force_reduction_area_N_s=float(positive.sum()*.00025),positive_force_reduction_in_speed_or_accel_excess_N_s=float(positive[excess].sum()*.00025),interpretation='association on common absolute clock, not proof that excess causes force gain; full objective uses original TASK quadrature')
  shapes={}
  for ph in ['OUTBOUND','HOLD','RETURN']:
   diff=np.asarray(m['dose']['phase_shapes'][ph])-b['dose']['phase_shapes'][ph];i,j=np.unravel_index(np.argmax(abs(diff)),diff.shape);mask=np.max(abs(diff),axis=1)>.5;shapes[ph]=dict(max_abs_deg=float(abs(diff[i,j])),public_phase_fraction=float(i/200),joint=['hip','knee'][j],fractions_above_point5=[float(v/200) for v in np.flatnonzero(mask)],diagnostic_only=True)
  out.append(dict(id=ident,gain_percent=row['comparison']['gain_percent'],phase_cost=m['phase_cost'],bins=bins,burdens=burdens,slot_scores=sorted(slot_scores,key=lambda r:-r['acceleration_excess_area']),overlap=overlap,phase_shape=shapes,full_metrics_path=row['metrics_path'],association_only=True))
 put('MECHANISM_'+group+'.json',dict(B=baseid,rows=out,source='new matched native dense true motion, original force TASK trace and audited receipts',no_causal_inference_without_intervention=True))
 return out
if __name__=='__main__':analyze(sys.argv[1] if len(sys.argv)>1 else 'baseline')
