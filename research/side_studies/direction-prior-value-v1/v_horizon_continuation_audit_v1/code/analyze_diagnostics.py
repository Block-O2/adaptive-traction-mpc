from audit_common import *
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np,importlib.util
_spec=importlib.util.spec_from_file_location('frozen_diagnostic_networks',OLD/'code/inference.py');_netmodule=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_netmodule)
def metric_extra(metric,base):
 path=Path(metric['trace']);path=path if path.is_absolute() else base/'source'/path
 with np.load(path) as z:
  mask=z['stage']=='TASK';t=z['time_s'][mask];f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);cum=np.r_[0.,np.cumsum(f[:-1]*np.diff(t))]
  q=z['evaluation_only_human_state_rad_rad_s'][mask,:2];ref=z['reference_q_rad'][mask];tracking=np.rad2deg(q-ref)
  result=dict(truth_tracking_RMS_deg=np.sqrt(np.mean(tracking**2,axis=0)).tolist(),truth_tracking_peak_deg=np.max(np.abs(tracking),axis=0).tolist(),trace_cost_error=float(cum[-1]-metric['J_F']),phase_durations=metric['phase_durations'],F_peak=metric['force_peak'],M_integral=metric['moment_integral'],M_peak=metric['moment_peak'],clearance=metric['physical_clearance'])
 return result,t,cum
def prefix_proof(case):
 p=STUDY/'output'/(case['state']+'_REPLAY_PROOF.json')
 if not p.exists():return None
 proof=read(p);checks=dict(causal=proof['context_equal'])
 if case['old_snapshot']:
  old=read(case['old_snapshot'])['manifest'];new=proof['snapshot']['manifest']
  for k in ('native_integration','numpy_rng','python_rng','task_last_physics_time','reference_state','reference_acceleration'):checks[k]=old.get(k)==new.get(k)
  assert all(checks.values()),('REUSE_PREFIX_PROOF_FAILED',case['state'],checks)
 return dict(checks=checks,qualified=all(checks.values()),physical_time=proof['physical_time'],prefix_J_F=proof['prefix_J_F'],prefix_M=proof['prefix_M'])
def scores_loss(rows,key,costkey='committed_cost'):
 valid=[r for r in rows if r.get('committed_valid')];accepted=[r for r in valid if r['screening_accepted']]
 if not valid or not accepted:return None
 best=min(r[costkey] for r in valid);abest=min(r[costkey] for r in accepted);choice=min(accepted,key=lambda r:r[key])
 return dict(selected_identity=choice['identity'],screening_loss_Ns=abest-best,accepted_pool_ranking_loss_Ns=choice[costkey]-abest,total_finite_pool_regret_Ns=choice[costkey]-best)
def main():
 contract=read(STUDY/'AUDIT_CONTRACT.json');states=[];allrows=[];divergences=[]
 outcomes=[read(p) for p in (STUDY/'output').glob('*_OUTCOME.json')]
 for case in contract['cases']:
  path=STUDY/'output'/(case['state']+'_POOL.json');proof=prefix_proof(case)
  if not path.exists() or not proof:continue
  pool=read(path);rows=[];network=_netmodule.Networks(case['weights'])
  for raw in pool['rows']:
   item=raw['item'];pred=raw['KNOWN']['prediction'];index=item['diagnostic_index'];row=dict(state=case['state'],identity=item['identity'],index=index,role=item['role'],plan=item['plan'],pending_count=raw['counts'],screening_accepted=raw['KNOWN']['screening_accepted'],EST_screening_accepted=raw['EST']['screening_accepted'],near_cost=raw['KNOWN']['near_cost'],V_base=raw['KNOWN']['V_base'],DeltaV=raw['KNOWN']['DeltaV'],P_score=raw['KNOWN']['P_score'],PV_score=raw['KNOWN']['PV_score'],EST_score=raw['EST']['P_score'],model_origin_task_s=pred['audit_origin_task_s'],model_terminal_task_s=pred['terminal']['task_s'],model_end_task_s=pred['audit_end_task_s'],model_segments=pred['audit_segments'],mode_costs={},mode_metrics={},mode_sources={})
   committed=None;base=OLD
   if item['committed_source']:
    r=read(item['committed_source']);committed=dict(metric=r['metric'],remaining_J_F=r['remaining_J_F'],remaining_M=r['remaining_M'],child=r['child'])
    row['mode_sources']['COMMITTED']=item['committed_source']
   else:
    committed=next((r for r in outcomes if r['child']['item']['identity']==item['identity'] and r['child']['mode']=='COMMITTED'),None);base=STUDY
   if committed:
    row['committed_cost']=committed['remaining_J_F'];row['committed_valid']=bool(committed['metric']['valid'] and committed['metric']['matched_eligible'] and committed['metric']['status']=='COMPLETE');row['mode_costs']['COMMITTED']=committed['remaining_J_F']
    extra,t,cum=metric_extra(committed['metric'],base);row['mode_metrics']['COMMITTED']={**extra,'qualified':row['committed_valid'],'full_J_F':committed['metric']['J_F'],'remaining_M':committed['remaining_M']}
    start=proof['physical_time'];split=start+pred['terminal']['task_s']-pred['audit_origin_task_s'];modelend=start+pred['audit_end_task_s']-pred['audit_origin_task_s'];near=float(np.interp(min(split,t[-1]),t,cum)-np.interp(start,t,cum));remainder=committed['remaining_J_F']-near
    row.update(true_cost_corresponding_model_near_interval=near,true_tail_cost_after_model_clock_split=remainder,near_forecast_error=pred['near_cost']-near,V_terminal_cost_error=pred['V_base']+row['DeltaV']-remainder,P_committed_score_error=row['P_score']-row['committed_cost'],PV_committed_score_error=row['PV_score']-row['committed_cost'],physical_start_s=start,model_split_physical_clock_s=split,model_end_physical_clock_s=modelend,actual_end_physical_s=float(t[-1]),prefix_cost_alignment_error=float(np.interp(start,t,cum)-proof['prefix_J_F']),synthetic_terminal_state_is_not_actual_state=True)
    row['true_cost_over_full_model_clock_interval']=float(np.interp(min(modelend,t[-1]),t,cum)-np.interp(start,t,cum));row['model_end_vs_actual_end_s']=modelend-float(t[-1])
   for mode in ('P_RECEDING','PV_RECEDING'):
    result=next((r for r in outcomes if r['child']['item']['identity']==item['identity'] and r['child']['mode']==mode),None)
    if result is None:continue
    row['mode_costs'][mode]=result['remaining_J_F'];extra,_,_=metric_extra(result['metric'],STUDY);row['mode_metrics'][mode]={**extra,'qualified':bool(result['metric']['valid'] and result['metric']['matched_eligible']),'full_J_F':result['metric']['J_F'],'remaining_M':result['remaining_M']};row['mode_sources'][mode]=result['metric']['trace']
    replacement=next((e for e in result['events'] if e['decision_index']>0 and not e['original_pending_suffix_retained']),None)
    divergence=dict(state=case['state'],identity=item['identity'],mode=mode,first_replacement=replacement,all_events=result['events'],all_carry_present=all(len(e.get('carry_candidates',[]))==2 for e in result['events'][1:]),remaining_J_F=result['remaining_J_F'],remaining_M=result['remaining_M'],network_calls=result['network_calls'],decision_wall_s=[r['decision_wall_s'] for r in result['search_rows']])
    if committed:divergence['rolling_minus_committed_Ns']=result['remaining_J_F']-committed['remaining_J_F']
    if committed and replacement:
     search=next((s for s in result['search_rows'] if s['context']['task_s']==replacement['context']['task_s'] and s['count_before']==replacement['count']),None)
     carry=[] if search is None else [r for r in search['candidates'] if r['source']=='remaining_plan' and not r['rejected']]
     if carry:
      p=carry[0]['prediction'];delta=network.value(np.asarray(p['terminal']['feature'],np.float32));at=replacement['physical_time'];actual_original_remaining=committed['metric']['J_F']-float(np.interp(at,t,cum))
      divergence['original_carry_at_first_replacement']=dict(model_total=p['total_cost'],DeltaV=delta,PV_score=p['total_cost']+delta,actual_original_committed_remaining=actual_original_remaining,PV_error_Ns=p['total_cost']+delta-actual_original_remaining,model_terminal=p['terminal'],interpretation='counterfactual original committed suffix at the first whole-plan replacement; physical prefix equality is separately tested')
    divergences.append(divergence)
   row['all_three_mode_outcomes_complete']=all(mode in row['mode_costs'] for mode in ('COMMITTED','P_RECEDING','PV_RECEDING'))
   if row['all_three_mode_outcomes_complete']:
    row['rolling_minus_committed_Ns']={m:row['mode_costs'][m]-row['mode_costs']['COMMITTED'] for m in ('P_RECEDING','PV_RECEDING')}
   rows.append(row);allrows.append(row)
  valid=[r for r in rows if r.get('committed_valid')];accepted=[r for r in valid if r['screening_accepted']]
  ranking={k:sorted(valid,key=lambda r:r[k]) for k in ('P_score','PV_score','EST_score','committed_cost')}
  def ids(key):return [r['identity'] for r in ranking[key]]
  state=dict(state=case['state'],pool_size=len(rows),completed_three_modes=sum(r['all_three_mode_outcomes_complete'] for r in rows),P_loss=scores_loss(rows,'P_score'),PV_loss=scores_loss(rows,'PV_score'),ranking={k:ids(k) for k in ranking},accepted_top1_changed=False,accepted_top3_changed=False,reuse_proof=proof,rows=rows)
  if accepted:
   pr=sorted(accepted,key=lambda r:r['P_score']);vr=sorted(accepted,key=lambda r:r['PV_score']);er=sorted([r for r in valid if r['EST_screening_accepted']],key=lambda r:r['EST_score'])
   state.update(accepted_top1_changed=pr[0]['identity']!=vr[0]['identity'],accepted_top3_changed=[r['identity'] for r in pr[:3]]!=[r['identity'] for r in vr[:3]],DeltaV_range=max(r['DeltaV'] for r in accepted)-min(r['DeltaV'] for r in accepted),P_score_gap=None if len(pr)<2 else pr[1]['P_score']-pr[0]['P_score'],EST_selected=None if not er else er[0]['identity'],KNOWN_selected=pr[0]['identity'])
   ir={r['identity']:i for i,r in enumerate(vr)};vranks=np.asarray([ir[r['identity']] for r in pr]);state['accepted_rank_correlation']=float(np.corrcoef(np.arange(len(pr)),vranks)[0,1]) if len(pr)>1 else None
   gap=state['P_score_gap'];state['V_correction_score_gap_ratio']=None if gap is None or abs(gap)<1e-12 else state['DeltaV_range']/gap
   if er:state['KNOWN_vs_EST_committed_effect_Ns']=er[0]['committed_cost']-pr[0]['committed_cost']
  states.append(state)
 complete=len(states)==5 and len(allrows)==15 and all(r['all_three_mode_outcomes_complete'] for r in allrows)
 save(STUDY/'SCORE_DECOMPOSITION.json',dict(complete=complete,states=states,interval_definition='true interval uses exact same recorded task-clock start and forecast split duration; left-endpoint force integration with cumulative interpolation; synthetic terminal state is not actual sampled state'))
 save(STUDY/'CONTINUATION_DIAGNOSIS.json',dict(rows=divergences,mode_definition='same forced first native row; afterward current P/PV rolling search with carry as explicit candidate in both generations',Mode_D_required=False,reason_D='normal implementation already carries previous plan in both generations; logged every future request'))
 print(json.dumps(dict(states=len(states),candidates=len(allrows),three_modes_complete=sum(r['all_three_mode_outcomes_complete'] for r in allrows),complete=complete,screening_ranking=[dict(state=s['state'],P=s['P_loss'],PV=s['PV_loss']) for s in states])))
if __name__=='__main__':main()
