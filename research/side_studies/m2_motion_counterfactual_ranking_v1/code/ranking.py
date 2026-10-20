from common import *
from analyze import compare_motion, PROFILES
import collections,itertools
def main():
 ds=load(OUT/'COUNTERFACTUAL_BRANCH_RESULTS.json');rows=ds['historical_rows'];by=collections.defaultdict(list)
 fw=ROOT/'m2_host_generalization_attribution_v1/weights/frozen_Q_v1/weights.npz'
 with np.load(fw) as z:w={k:z[k].copy() for k in z.files}
 for r in rows:
  raw=load(MATRIX/'output'/(r['id']+'_DATA.json'));trace=Path(next(p for p in r['sources'] if p.endswith('trace.npz')))
  with np.load(trace) as z:
   # Interval costs are accounted on the TASK logger boundary at fork, inclusive.
   # Preserve duplicate-timestamp records here; de-duplication is for derivatives.
   task=z['stage']=='TASK';at=raw['child']['physical_time_at_fork'];t=z['time_s'];c=z['interval_force_cost_n_s']
   future=float(np.sum(c[task&(t>=at-1e-8)]));prefix=float(np.sum(c[task&(t<at-1e-8)]));full=float(np.sum(c[task]))
  check=r['remaining_integral_check'];check['exclusive_boundary_diagnostic_error_N_s']=check['trace_sum_error_N_s'];check['trace_interval_sum_from_fork_inclusive_N_s']=future;check['inclusive_trace_sum_error_N_s']=future-r['remaining_J_F_N_s'];check['prefix_trace_sum_N_s']=prefix;check['prefix_trace_error_N_s']=prefix-raw['child']['start_J_F'];check['full_trace_sum_error_N_s']=full-r['full_J_F_N_s'];check['tick_integral_vs_native_scorer_error_N_s']=raw['metric']['tick_integral_vs_evaluation_J_F_error'];check['contract']='Interval cost at fork timestamp belongs to remaining label: child.start_J_F is captured before that TASK logger interval. Keep all TASK interval records, including repeated boundary timestamps. Exclusive diagnostic retained, not used as uncertainty.'
  assert abs(check['inclusive_trace_sum_error_N_s'])<1e-5 and abs(check['prefix_trace_error_N_s'])<1e-5
  x=np.asarray(r['x120'],np.float32);r['frozen_linear_score_N_s']=float(((x-w['x_mean'])/w['x_scale'])@w['linear_W']+w['linear_b'])*float(w['y_scale'])+float(w['y_mean'])
  r['causal_state_fingerprint_round4']=hashlib.sha256(np.round(x[np.r_[0:58,88:120]],4).tobytes()).hexdigest()
  r['carry_identity']=hashlib.sha256(x[88:118].tobytes()).hexdigest()
  by[r['snapshot']].append(r)
 snaprows=[];pairs=[]
 for g,rr in sorted(by.items()):
  base=next((r for r in rr if np.max(abs(np.asarray(r['x120'])[58:88]))<1e-8),None)
  x=np.array([r['x120'] for r in rr]);assert np.max(np.ptp(x[:,np.r_[0:58,88:120]],axis=0))<1e-6
  # Validate identical inherited physical prefix and the fork boundary.
  with np.load(rr[0]['derived_dense_trace']) as z: tt=z['time_s'];qq=z['true_q_rad'];vv=z['true_dq_rad_s'];at=float(z['fork_physical_s']);pm=tt<=at+1e-8;pt=tt[pm];pq=qq[pm];pv=vv[pm]
  prefixmax=0.
  for r in rr[1:]:
   with np.load(r['derived_dense_trace']) as z:
    ix=z['time_s']<=at+1e-8;assert np.array_equal(z['time_s'][ix],pt);prefixmax=max(prefixmax,float(np.max(abs(z['true_q_rad'][ix]-pq))),float(np.max(abs(z['true_dq_rad_s'][ix]-pv))))
  assert prefixmax<1e-8
  for r in rr:
   r['motion_profiles']={}
   for p in PROFILES:
    if base is None:r['motion_profiles'][p['id']]=dict(status='NOT_EVALUABLE_NO_ZERO_SUFFIX');continue
    check=compare_motion(r['full_dose'],base['full_dose'],p,r['motion']['raw']['full'],base['motion']['raw']['full'],dict(moment=r['remaining_moment_Nm_s'],tracking=r['tracking_RMS_deg']),dict(moment=base['remaining_moment_Nm_s'],tracking=base['tracking_RMS_deg']))
    check['status']='RETROSPECTIVE_RESEARCH_SCREEN';check['deployable_gate']=False;check['clinical_acceptability']='NOT_EVALUABLE';r['motion_profiles'][p['id']]=check
   save('branch_audits/'+r['id']+'.json',r)
  regimes={}
  for name in ['unconstrained','original_physical_task']+[p['id'] for p in PROFILES]:
   valid=rr if name=='unconstrained' else [r for r in rr if r['physical_pass'] and (name=='original_physical_task' or r['motion_profiles'][name].get('screen_pass',False))]
   if not valid:regimes[name]=dict(status='NO_EVALUABLE_CANDIDATE',count=0);continue
   best=min(valid,key=lambda r:r['remaining_J_F_N_s']);fixed=min(valid,key=lambda r:r['frozen_linear_score_N_s']);order=sorted(valid,key=lambda r:r['remaining_J_F_N_s']);runner=order[1]['remaining_J_F_N_s']-order[0]['remaining_J_F_N_s'] if len(order)>1 else None
   regimes[name]=dict(status='FINITE_RETROSPECTIVE_CANDIDATE_REFERENCE',count=len(valid),eligible_ids=[r['id'] for r in valid],best_id=best['id'],best_source=best['candidate_source'],best_plan_identity=best['candidate_identity_sha256'],best_cost_N_s=best['remaining_J_F_N_s'],score_margin_N_s=runner,fixed_id=fixed['id'],fixed_cost_N_s=fixed['remaining_J_F_N_s'],fixed_regret_N_s=fixed['remaining_J_F_N_s']-best['remaining_J_F_N_s'],zero_suffix_id=base['id'] if base else None,zero_suffix_cost_N_s=base['remaining_J_F_N_s'] if base else None,zero_minus_best_N_s=base['remaining_J_F_N_s']-best['remaining_J_F_N_s'] if base else None,reference='Best among observed valid candidates only; all original attempts not necessarily labelled, and no global oracle.',filtered_fixed='Uses future-label motion gate for retrospective screen; not a deployable masked selector.' if name not in ['unconstrained','original_physical_task'] else 'Frozen linear ranks same labelled legal pool.')
  for a,b in itertools.combinations(rr,2):pairs.append(dict(snapshot=g,parent=a['parent'],phase=a['phase'],a=a['id'],b=b['id'],plan_a=a['candidate_identity_sha256'],plan_b=b['candidate_identity_sha256'],remaining_cost_delta_N_s=a['remaining_J_F_N_s']-b['remaining_J_F_N_s'],linear_score_delta_N_s=a['frozen_linear_score_N_s']-b['frozen_linear_score_N_s']))
  snaprows.append(dict(snapshot=g,parent=rr[0]['parent'],phase=rr[0]['phase'],task_s=rr[0]['task_s'],model_hash=rr[0]['model_hash'],counts=rr[0]['counts'],mask=rr[0]['mask_identity'],carry=rr[0]['carry_identity'],causal_state=rr[0]['causal_state_fingerprint_round4'],prefix_max_q_dq_error=prefixmax,candidate_set=sorted(set(r['candidate_identity_sha256'] for r in rr)),regimes=regimes))
 strata=collections.defaultdict(list)
 for r in snaprows:strata[(r['phase'],r['mask'],r['carry'])].append(r)
 matched=[];inversions=[]
 for key,ss in strata.items():
  if len(ss)<2:continue
  common=set.intersection(*[set(r['candidate_set']) for r in ss]);groups=[]
  for s in ss:
   rr=[r for r in by[s['snapshot']] if r['candidate_identity_sha256'] in common]
   if len(rr)<2:continue
   regimes={}
   for regime in ['unconstrained','original_physical_task']+[p['id'] for p in PROFILES]:
    valid=rr if regime in ['unconstrained','original_physical_task'] else [r for r in rr if r['motion_profiles'][regime]['screen_pass']]
    if not valid:regimes[regime]=dict(count=0);continue
    best=min(valid,key=lambda r:r['remaining_J_F_N_s']);fixed=min(valid,key=lambda r:r['frozen_linear_score_N_s']);regimes[regime]=dict(count=len(valid),best_plan=best['candidate_identity_sha256'],best_source=best['candidate_source'],best_cost_N_s=best['remaining_J_F_N_s'],fixed_regret_N_s=fixed['remaining_J_F_N_s']-best['remaining_J_F_N_s'])
   groups.append(dict(snapshot=s['snapshot'],parent=s['parent'],causal_state=s['causal_state'],regimes=regimes,plan_costs={r['candidate_identity_sha256']:r['remaining_J_F_N_s'] for r in rr}))
  if len(common)<2:continue
  stratum_id=hashlib.sha256(str(key).encode()).hexdigest()
  matched.append(dict(stratum=stratum_id,phase=key[0],mask_identity=key[1],carry_identity=key[2],common_exact_plans=sorted(common),full_original_candidate_sets_identical=all(s['candidate_set']==ss[0]['candidate_set'] for s in ss),snapshots=groups,independent_parent_groups=sorted(set(g['parent'] for g in groups)),role='Exact common candidate intersection across states; no source-name or index matching. Common-pool analysis differs from full historical pools with seed-specific noisy candidates.'))
  for a,b in itertools.combinations(sorted(common),2):
   costs=[dict(snapshot=g['snapshot'],parent=g['parent'],state=g['causal_state'],delta_N_s=g['plan_costs'][a]-g['plan_costs'][b]) for g in groups]
   sensitivity={}
   for eps in [.001,.1,1.]:
    neg=[r for r in costs if r['delta_N_s'] < -eps];pos=[r for r in costs if r['delta_N_s'] > eps]
    sensitivity[str(eps)]=dict(inversion=bool(neg and pos),negative_states=len(neg),positive_states=len(pos),distinct_state_and_cross_parent_inversion=any(n['state']!=p['state'] and n['parent']!=p['parent'] for n in neg for p in pos))
   inversions.append(dict(stratum=stratum_id,plan_a=a,plan_b=b,cost_differences=costs,margin_sensitivity=sensitivity))
 summary={}
 for regime in ['unconstrained','original_physical_task']+[p['id'] for p in PROFILES]:
  a=[s for s in snaprows if s['regimes'][regime].get('count',0)>0];vals=[s['regimes'][regime]['fixed_regret_N_s'] for s in a];parents={p:float(np.mean([s['regimes'][regime]['fixed_regret_N_s'] for s in a if s['parent']==p])) for p in sorted(set(s['parent'] for s in a))}
  summary[regime]=dict(snapshots=len(a),eligible_rows=sum(s['regimes'][regime]['count'] for s in a),positive_force_opportunity_snapshots=sum(s['regimes'][regime]['zero_minus_best_N_s']>.001 for s in a if s['regimes'][regime]['zero_minus_best_N_s'] is not None),mean_snapshot_fixed_regret_N_s=float(np.mean(vals)),max_snapshot_fixed_regret_N_s=max(vals),per_parent_mean_fixed_regret_N_s=parents,equal_parent_mean_fixed_regret_N_s=float(np.mean(list(parents.values()))),phase={ph:dict(snapshots=len([s for s in a if s['phase']==ph]),mean_regret_N_s=float(np.mean([s['regimes'][regime]['fixed_regret_N_s'] for s in a if s['phase']==ph]))) for ph in ['OUTBOUND','RETURN']},mean_zero_minus_best_N_s=float(np.mean([s['regimes'][regime]['zero_minus_best_N_s'] for s in a if s['regimes'][regime]['zero_minus_best_N_s'] is not None])))
 grouped={}
 for split in ['train','validation','test']:
  a=[s for s in snaprows if by[s['snapshot']][0]['split']==split];grouped[split]=dict(snapshots=len(a),parents=sorted(set(s['parent'] for s in a)),mean_fixed_regret_N_s=float(np.mean([s['regimes']['original_physical_task']['fixed_regret_N_s'] for s in a])))
 result=dict(status='RETROSPECTIVE_FINITE_COMMITTED_LABEL_ANALYSIS',summary=summary,split_regret=grouped,snapshots=snaprows,same_snapshot_candidate_pairs=pairs,matched_fixed_candidate_strata=matched,matched_pair_ranking=inversions,uncertainty=dict(max_integral_closure_error_N_s=max(abs(r['remaining_integral_check']['inclusive_trace_sum_error_N_s']) for r in rows),label_replicate_uncertainty='NOT_EVALUABLE_NO_IDENTICAL_BRANCH_REPLICATES',decision_resolution_sensitivity_N_s=[.001,.1,1.],continuation_target_bias='NOT_EVALUABLE',warning='Exact arithmetic closure is not a noise/host-policy confidence bound.'),scope='13 historic snapshots, four source parent groups, one already exposed simulated Human. State oracle is a future-label reference, no deployable selector. Same-source dense samples are not independent.')
 save('RANKING_FEASIBILITY.json',result);ds['historical_rows']=rows;save('COUNTERFACTUAL_BRANCH_RESULTS.json',ds)
 print('RANKING_SUMMARY',json.dumps(summary),flush=True);print('MATCHED',len(matched),'inversions',[(eps,sum(v['margin_sensitivity'][str(eps)]['inversion'] for v in inversions)) for eps in [.001,.1,1.]],flush=True)
if __name__=='__main__':main()
