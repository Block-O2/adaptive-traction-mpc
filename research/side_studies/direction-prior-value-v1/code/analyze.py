from freeze import *
import numpy as np,collections,csv,sys
def collect(version=None,batch=None):
 results=[]
 for p in (STUDY/'output').glob('*_RESULT.json'):
  r=json.loads(p.read_text());request=r.get('inputs',{})
  if request.get('split')!='test' or request.get('mode')!='search' or (version is not None and request.get('version')!=version) or (batch is not None and request.get('batch')!=batch):continue
  metric=r.get('metric',{});search_path=STUDY/'output'/(r['id']+'_SEARCH.json');search=json.loads(search_path.read_text()) if search_path.exists() else {}
  row=dict(id=r['id'],method=request['method'],group=request['group'],version=request['version'],batch=request['batch'],worker_status=r['status'],valid=bool(metric.get('valid') and metric.get('matched_eligible') and metric.get('status')=='COMPLETE'),metric=metric,model_calls=search.get('model_calls',0),model_schedule_calls=search.get('model_schedule_calls',0),wall_s=r['wall_seconds'],model_wall_s=search.get('model_wall_s',0),decisions=len(search.get('rows',[])),decision_wall_s=[x['decision_wall_s'] for x in search.get('rows',[])],selected_G=sum(x['selected_source']=='G' for x in search.get('rows',[])),candidate_G=sum(c['source']=='G' for x in search.get('rows',[]) for c in x['candidates']),rejected_G=sum(c['source']=='G' and c['rejected'] for x in search.get('rows',[]) for c in x['candidates']),rejected_candidates=sum(c['rejected'] for x in search.get('rows',[]) for c in x['candidates']),total_candidates=sum(len(x['candidates']) for x in search.get('rows',[])))
  folder=STUDY/'source/results'/r['id'];summarypath=folder/'summary.json'
  if summarypath.exists():
   summary=json.loads(summarypath.read_text());events=[]
   def walk(x):
    if isinstance(x,dict):
     if 'coordination_residual_v2' in x:events.append(x['coordination_residual_v2'])
     for v in x.values():walk(v)
    elif isinstance(x,list):
     for v in x:walk(v)
   walk(summary);events=list({json.dumps(e,sort_keys=True):e for e in events}.values())
   row.update(common_mode_sample_error_max=max([abs(e['common_error']) for e in events] or [0.]),residual_accepted=sum(e['status']=='ACCEPTED' for e in events),residual_rejected=sum(e['status']!='ACCEPTED' for e in events),residual_activated=sum(d.get('plan_activated',False) and d.get('selection_mode')=='native_residual_v2_ACCEPTED' for d in summary['decisions']),safety_mode_counts=summary.get('safety_mode_counts'),safe_fallback_events=summary.get('safe_fallback_events',[]))
  results.append(row)
  row.update(full_research_model_inverse_dynamics_calls=search.get('full_model_inverse_dynamics_calls'),main_model_inverse_dynamics_api_calls=metric.get('main_model_inverse_dynamics_api_calls'),native_worker_model_inverse_dynamics_api_calls=metric.get('native_worker_model_inverse_dynamics_api_calls'),network_inference_s=search.get('network_inference_s'),network_calls=search.get('network_calls'))
  row['candidate_budget_qualified']=all(len(event['candidates'])==16 and all(sum(c['source']=='G' for c in event['candidates'] if c['generation']==generation)<=3 for generation in (0,1)) for event in search.get('rows',[])) and search.get('online_physics_branches')==0
  tracepath=folder/'trace.npz'
  if tracepath.exists():
   with np.load(tracepath) as z:
    task=z['stage']=='TASK';true_error=np.degrees(z['evaluation_only_human_state_rad_rad_s'][task,:2]-z['reference_q_rad'][task]);estimated_error=np.degrees(z['estimated_human_state_rad_rad_s'][task,:2]-z['reference_q_rad'][task])
    row['tracking_evaluation_only_deg']=dict(RMS_per_joint=np.sqrt(np.mean(true_error**2,axis=0)).tolist(),peak_per_joint=np.max(np.abs(true_error),axis=0).tolist());row['tracking_causal_estimate_deg']=dict(RMS_per_joint=np.sqrt(np.mean(estimated_error**2,axis=0)).tolist(),peak_per_joint=np.max(np.abs(estimated_error),axis=0).tolist())
 # Nominal target common-progress preservation at each request does not imply
 # identical common-mode reference trajectories between requests.
 for arms in groups_for_reference(results).values():
  if 'P' not in arms:continue
  base_path=STUDY/'source/results'/arms['P']['id']/'native_reference.npz'
  if not base_path.exists():continue
  baseline_trace=STUDY/'source/results'/arms['P']['id']/'trace.npz'
  if baseline_trace.exists():
   with np.load(baseline_trace) as z:
    pretask=np.flatnonzero(z['stage']=='TASK')[0];fields=('time_s','estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','cr12_q_rad','cr12_dq_rad_s','physical_cuff_position_world_m','physical_cuff_rotation_world','physical_cuff_force_world_n','physical_cuff_moment_world_nm');base_prefix={key:z[key][:pretask].copy() for key in fields}
   for row in arms.values():
    own_trace=STUDY/'source/results'/row['id']/'trace.npz'
    if not own_trace.exists():continue
    with np.load(own_trace) as z:row['paired_pretask_initial_conditions_exact']={key:bool(np.array_equal(array,z[key][:pretask],equal_nan=True)) for key,array in base_prefix.items()}
  with np.load(base_path) as z:base_data=z['data'].copy();base_phase=z['phase'].copy()
  for row in arms.values():
   reference_path=STUDY/'source/results'/row['id']/'native_reference.npz'
   if not reference_path.exists():continue
   comparisons={}
   with np.load(reference_path) as z:
    data=z['data'];phases=z['phase']
    for phase in ('OUTBOUND','RETURN'):
     a=base_data[base_phase==phase];b=data[phases==phase]
     if len(a)<2 or len(b)<2:continue
     start=np.radians([5,10]);span=np.radians([120,120])-start
     pa=((a[:,1:3]-start)/span).mean(1);pb=((b[:,1:3]-start)/span).mean(1);grid=np.linspace(max(a[0,0],b[0,0]),min(a[-1,0],b[-1,0]),1001)
     difference=np.interp(grid,b[:,0],pb)-np.interp(grid,a[:,0],pa);comparisons[phase]=dict(RMS=float(np.sqrt(np.mean(difference**2))),peak=float(np.max(np.abs(difference))))
   row['reference_common_progress_vs_P']=comparisons
 return sorted(results,key=lambda r:r['id'])
def groups_for_reference(results):
 groups=collections.defaultdict(dict)
 for row in results:groups[row['group']][row['method']]=row
 return groups
def main():
 version=int(sys.argv[1]) if len(sys.argv)>1 else None;batch=sys.argv[2] if len(sys.argv)>2 else None;rows=collect(version,batch);groups=collections.defaultdict(dict)
 for row in rows:groups[row['group']][row['method']]=row
 methods={};paired=[]
 for method in ('P','P+G','P+V','P+G+V'):
  own=[r for r in rows if r['method']==method];valid=[r for r in own if r['valid']]
  gains=[];momentchanges=[];phasechanges=[]
  for group,arms in groups.items():
   base=arms.get('P');current=arms.get(method)
   if base and current and base['valid'] and current['valid']:
    gain=(base['metric']['J_F']-current['metric']['J_F'])/base['metric']['J_F'];gains.append(gain);momentchanges.append(current['metric']['moment_integral']/base['metric']['moment_integral']-1.)
    phasechanges.append(max(abs(current['metric']['phase_durations'][p]-base['metric']['phase_durations'][p]) for p in ('OUTBOUND','HOLD','RETURN')))
    paired.append(dict(group=group,method=method,J_F_improvement_fraction=gain,moment_integral_change_fraction=momentchanges[-1],duration_change_s=current['metric']['duration_s']-base['metric']['duration_s']))
  methods[method]=dict(attempted=len(own),valid=len(valid),mean_J_F_Ns=float(np.mean([r['metric']['J_F'] for r in valid])) if valid else None,mean_paired_gain_fraction=float(np.mean(gains)) if gains else None,paired_gains=gains,all_cases_valid=bool(own) and len(valid)==len(own),model_calls=sum(r['model_calls'] for r in own),model_schedule_calls=sum(r['model_schedule_calls'] for r in own),wall_s=sum(r['wall_s'] for r in own),mean_moment_integral_change_fraction=float(np.mean(momentchanges)) if momentchanges else None)
  methods[method]['max_paired_phase_duration_change_s']=max(phasechanges,default=None);methods[method]['all_candidate_budgets_qualified']=bool(own) and all(r['candidate_budget_qualified'] for r in own);methods[method]['max_common_mode_sample_error']=max((r.get('common_mode_sample_error_max',float('inf')) for r in own),default=None)
  methods[method]['all_paired_pretask_initial_conditions_exact']=bool(own) and all(all(r.get('paired_pretask_initial_conditions_exact',{'missing':False}).values()) for r in own)
 eligible=[m for m in methods if m!='P' and methods[m]['all_cases_valid'] and len(methods[m]['paired_gains'])>=4 and methods[m]['mean_paired_gain_fraction']>=.005 and all(x>0 for x in methods[m]['paired_gains']) and methods[m]['all_candidate_budgets_qualified'] and methods[m]['max_common_mode_sample_error']<=1e-12 and methods[m]['max_paired_phase_duration_change_s']<=.0050001 and methods[m]['all_paired_pretask_initial_conditions_exact']]
 factorial=[]
 for group,arms in groups.items():
  if set(arms)=={'P','P+G','P+V','P+G+V'} and all(r['valid'] for r in arms.values()):
   costs={m:arms[m]['metric']['J_F'] for m in arms};factorial.append(dict(group=group,G_gain_without_V_Ns=costs['P']-costs['P+G'],G_gain_with_V_Ns=costs['P+V']-costs['P+G+V'],V_gain_without_G_Ns=costs['P']-costs['P+V'],V_gain_with_G_Ns=costs['P+G']-costs['P+G+V'],extra_combination_gain_beyond_additive_Ns=costs['P+G']+costs['P+V']-costs['P']-costs['P+G+V']))
 summary=dict(version=version,batch=batch,methods=methods,rows=rows,paired=paired,factorial_interactions=factorial,groups_complete=sum(len(arms)==4 for arms in groups.values()),eligible_pilot_methods=eligible,engineering_threshold=.005,statistical_significance_claim=False,nominal_exposed_human_only=True,no_online_full_physics_predictions=True)
 save(STUDY/f'ANALYSIS_v{version}_{batch}.json',summary)
 (STUDY/f'RESULTS_v{version}_{batch}.csv').parent.mkdir(exist_ok=True)
 with (STUDY/f'RESULTS_v{version}_{batch}.csv').open('w',newline='') as f:
  fields=['group','method','valid','J_F','force_peak','moment_integral','moment_peak','duration_s','clearance','physical_clearance','model_calls','model_schedule_calls','wall_s','residual_activated','residual_rejected','common_mode_sample_error_max'];writer=csv.DictWriter(f,fields);writer.writeheader()
  for r in rows:writer.writerow({k:r.get(k,r['metric'].get(k)) for k in fields})
 print(json.dumps(dict(groups_complete=summary['groups_complete'],methods=methods,eligible=eligible),indent=2))
if __name__=='__main__':main()
