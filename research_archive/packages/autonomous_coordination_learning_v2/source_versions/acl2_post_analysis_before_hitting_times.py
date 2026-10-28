"""Read-only scientific analysis of actual outcomes and frozen predictions."""
from pathlib import Path
import os,json,time,csv,collections,re
import numpy as np
from scipy.stats import spearmanr
from acl2_shared import P,R,put,read,sha,utc,records,native_used

def get(n,default=None):return read(n) if (P/n).exists() else default
def rows():return [json.loads(s) for s in (P/'ALL_RESULTS.jsonl').read_text().splitlines()] if (P/'ALL_RESULTS.jsonl').exists() else []
def pair_accuracy(pred,actual):
 good=total=ties=0
 for i in range(len(pred)):
  for j in range(i):
   a=pred[i]-pred[j];b=actual[i]-actual[j]
   if abs(a)<1e-10 or abs(b)<1e-10:ties+=1;continue
   total+=1;good+=a*b>0
 return dict(correct=int(good),ordered_pairs=total,accuracy=good/total if total else None,ties_excluded=ties)
def prediction_metrics(dataset):
 full=[r for r in dataset if r.get('complete')];out=dict(all_cases=len(dataset),complete_cost_defined=len(full),incomplete_cases=[r['id'] for r in dataset if not r.get('complete')],motion_failing_complete_cases=[r['id'] for r in full if not r['qualified']])
 if not full:return out
 actual=np.array([[r['JF'],r['JM'],r['worst_ratio']] for r in full]);pred=np.array([r['prediction']['predicted_outcome'] for r in full]);sd=np.array([r['prediction']['predicted_sd'] for r in full]);err=pred-actual
 out.update(RMSE=np.sqrt(np.mean(err*err,axis=0)),MAE=np.mean(abs(err),axis=0),empirical_95pct_coverage=np.mean(abs(err)<=1.96*sd,axis=0),coverage_n=len(full),JF_Spearman=float(spearmanr(pred[:,0],actual[:,0]).statistic) if len(full)>2 and np.std(pred[:,0])>0 and np.std(actual[:,0])>0 else None,JF_pairwise_order=pair_accuracy(pred[:,0],actual[:,0]),predicted_margin_pass_but_not_qualified=[r['id'] for r in dataset if r['prediction']['predicted_outcome'][2]+r['prediction']['predicted_sd'][2]<=1 and not r.get('qualified')],motion_margin_not_a_safety_certificate=True)
 completion=[r for r in dataset if r['prediction'].get('empirical_completion_score') is not None]
 if completion:out['completion_Brier_descriptive']=float(np.mean([(r['prediction']['empirical_completion_score']-float(r['complete']))**2 for r in completion]))
 return out

def accounting(allrows):
 ev=records();starts=[r for r in ev if r['event']=='START'];closed=[r for r in ev if r['event']=='END'];tele=[json.loads(s) for s in (P/'RESOURCE_TELEMETRY.jsonl').read_text().splitlines()] if (P/'RESOURCE_TELEMETRY.jsonl').exists() else [];jobs=[]
 for f in sorted((P/'jobs').glob('*/START.json')):
  s=json.loads(f.read_text());end=f.parent/'END.json';jobs.append(dict(id=f.parent.name,start=s,end=json.loads(end.read_text()) if end.exists() else None))
 bycat=collections.Counter(r.get('category','UNSPECIFIED') for r in starts);bygroup=collections.Counter(r.get('group','UNSPECIFIED') for r in starts);modelcalls=dict(main_calls=0,native_worker_calls=0,unknown_main_attempts=[],unknown_worker_attempts=[])
 nativebygroup=collections.defaultdict(int)
 for r in starts:
  d=get('runtime/output/'+r['id']+'_DATA.json');p=get('runtime/output/'+r['id']+'_PARTIAL_COMPUTE.json');m=(d or {}).get('metric',p or {});n=m.get('actual_new_native_physics_steps');nativebygroup[r.get('group','UNSPECIFIED')]+=int(n or 0)
  for key,target,unknown in [('actual_new_main_model_inverse_dynamics_api_calls','main_calls','unknown_main_attempts'),('actual_new_native_worker_model_inverse_dynamics_api_calls','native_worker_calls','unknown_worker_attempts')]:
   if m.get(key) is not None:modelcalls[target]+=int(m[key])
   else:modelcalls[unknown].append(r['id'])
 A=read('ACTIVATION.json');out=dict(utc=utc(),T0_utc=A['T0_utc'],elapsed_h=(time.time()-A['t0_unix'])/3600,hard_stop_utc=A['hard_stop_utc'],actual_physical_START=len(starts),closed_native_END_records=len(closed),actual_new_native_steps=native_used(),by_category=dict(bycat),by_group=dict(bygroup),new_native_by_group=dict(nativebygroup),candidate_rows=len(allrows),complete_task_candidates=sum(r['complete'] for r in allrows),qualified_candidates=sum(r['qualified'] for r in allrows),failed_or_unqualified_candidates=sum(not r['qualified'] for r in allrows),cold_parent_attempts=sum(r['id'].endswith('_parent') for r in starts),native_counter_note='Every branch subtracts its inherited47,060-step prefix; full archived trajectories are not summed as new integration. Full JF includes the common executed task prefix.',model_API_calls=modelcalls,jobs=jobs,telemetry=dict(samples=len(tele),start_utc=tele[0]['utc'] if tele else None,min_available_ram_gib=min((r['available_ram_gib'] for r in tele),default=None),min_free_disk_gib=min((r['free_disk_gib'] for r in tele),default=None),max_owned_RSS_gib=max((sum(p['rss_bytes'] for p in r['owned_processes'])/2**30 for r in tele),default=None),scope='Telemetry started during early CORE; earlier live resource snapshots and per-native-boundary RAM>=6GiB assertions are separate.'),native_steps_are_not_independent_learning_samples=True)
 put('RESOURCE_AND_ATTEMPT_ACCOUNTING.json',out);return out

def curves(allrows):
 D={r['id']:r for r in allrows};base=D.get('CORE_STRONG',D.get('RETIMED_STRONG'));out={};table=[]
 if base is None:return {},[]
 ev=[r for r in records() if r['event']=='START'];definitions={'A':lambda s:bool(re.fullmatch(r'CORE_A_\d+',s)),'B':lambda s:bool(re.fullmatch(r'CORE_B_\d+',s)),'C':lambda s:bool(re.fullmatch(r'CORE_C_\d+',s)),'PPO':lambda s:s.startswith('PPO_SCRATCH_TRAIN_') or s.startswith('PPO_SCRATCH_MEAN_')}
 for method,select in definitions.items():
  ids=[r['id'] for r in ev if select(r['id'])];best=base['JF'];bestmean=base['JF'];native=0;curve=[]
  for k,ident in enumerate(ids):
   r=D.get(ident);d=get('runtime/output/'+ident+'_DATA.json');p=get('runtime/output/'+ident+'_PARTIAL_COMPUTE.json');n=(d or {}).get('metric',p or {}).get('actual_new_native_physics_steps');native+=int(n or 0)
   if r and r.get('qualified'):
    best=min(best,r['JF'])
    if '_MEAN_' in ident:bestmean=min(bestmean,r['JF'])
   curve.append(dict(method=method,attempt=k+1,id=ident,native_cumulative=native,best_qualified_JF=best,PPO_best_evaluated_mean_JF=bestmean if method=='PPO' else None,complete=r.get('complete') if r else False,qualified=r.get('qualified') if r else False,JF=r.get('JF') if r else None,role='frozen_mean_evaluation' if '_MEAN_' in ident else 'training' if '_TRAIN_' in ident else 'optimization'))
  out[method]=curve
 for budget in [8,16,20,24,32,40,48,64]:
  for method,curve in out.items():
   if len(curve)<budget:continue
   r=curve[budget-1];table.append(dict(method=method,physical_branch_attempt_budget=budget,best_qualified_JF=r['best_qualified_JF'],best_evaluated_PPO_mean_JF=r['PPO_best_evaluated_mean_JF'],actual_new_native_steps=r['native_cumulative'],common_anchor_and_cold_parent_cost='separate shared engineering; not silently free',PPO_mean_evaluations_charged=True))
 nativebudgets=[]
 if out and all(out.values()):
  maxcommon=min(v[-1]['native_cumulative'] for v in out.values())
  for budget in np.arange(500000,maxcommon+1,500000,dtype=int):
   for method,curve in out.items():
    eligible=[r for r in curve if r['native_cumulative']<=budget]
    if eligible:nativebudgets.append(dict(method=method,native_budget=int(budget),physical_attempts=eligible[-1]['attempt'],best_qualified_JF=eligible[-1]['best_qualified_JF'],PPO_best_evaluated_mean_JF=eligible[-1]['PPO_best_evaluated_mean_JF']))
 put('MATCHED_BUDGET_RESULTS.json',dict(curves=out,fixed_attempts=table,fixed_new_native_steps=nativebudgets,base_JF=base['JF'],note='PPO complete-episode samples and frozen-mean performance separate. Actual evaluations consume physical attempts. Common anchors/parent, historical prior, secondary scouts and response tests remain in the full ledger.'))
 if table:
  with (P/'MATCHED_BUDGET_COMPARISON.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
 return out,table

def frozen_analysis(allrows):
 frozen=[r for r in allrows if r['id'].startswith('LOCKED_REPEAT_FAILURE_DOMAIN_') and r.get('prediction') and r['prediction'].get('predicted_outcome') is not None];out=dict(frozen_failure_domain=prediction_metrics(frozen) if frozen else dict(status='NOT_RUN'))
 paired=[]
 for k in [1,2]:
  a=next((r for r in allrows if r['id']=='LOCKED_REPEAT_CF%02d_LEARNED'%k),None);b=next((r for r in allrows if r['id']=='LOCKED_REPEAT_CF%02d_NOMINAL'%k),None)
  if a is None and b is None:continue
  winner='INCOMPLETE_PAIR'
  if a is not None and b is not None:
   winner='LEARNED' if a['qualified'] and (not b['qualified'] or a['JF']<b['JF']-1e-8) else 'NOMINAL' if b['qualified'] and (not a['qualified'] or b['JF']<a['JF']-1e-8) else 'TIE_OR_NEITHER_QUALIFIED'
  paired.append(dict(pair=k,learned=a,nominal=b,winner=winner,selection_rule='first two changed development C proposals; fixed before new diagnostic outcomes',new_native_cost=2))
 out['same_pool_native_counterfactuals']=paired
 lock=get('FROZEN_SELECTION.json',{});cross=[]
 for i in range(1,5):
  group='LOCKED_STATE_%d'%i;v=[r for r in allrows if r['id'].startswith(group+'_')];D={r['id']:r for r in v};base=D.get(group+'_STRONG');B=D.get(group+'_B');H=D.get(group+'_H150')
  if not v:continue
  methods={}
  for m,tag in lock.get('method_to_unique',{}).items():
   r=D.get(group+'_FROZEN_'+tag)
   if r is None:methods[m]=dict(status='NOT_RUN');continue
   methods[m]=dict(id=r['id'],complete=r['complete'],qualified=r['qualified'],JF=r.get('JF'),JM=r.get('JM'),gain_vs_qualified_strong=(base['JF']-r['JF']) if r['qualified'] and base and base['qualified'] else None,JF_prediction=(r.get('prediction') or {}).get('predicted_outcome',[None])[0],same_patient_new_legal_prefix=True)
  cross.append(dict(group=group,B_qualified=B['qualified'] if B else None,H150_qualified=H['qualified'] if H else None,strong_qualified=base['qualified'] if base else None,strong_JF=base.get('JF') if base else None,methods=methods,not_cross_patient=True))
 out['cross_state']=cross;put('FROZEN_VALIDATION_ANALYSIS.json',out);return out

def response_analysis(allrows):
 model=get('models/REFERENCE_RESPONSE_MODEL.json')
 if model is None:return dict(status='NOT_RUN')
 data=[]
 for r in allrows:
  if not (r['id'].startswith('RESPONSE_MODEL_') or r['id'] in ['RESPONSE_NOMINAL_COUNTERFACTUAL','RESPONSE_NATIVE_SCALAR_COUNTERFACTUAL']):continue
  p=r.get('prediction') or {};row=dict(id=r['id'],complete=r['complete'],qualified=r['qualified'],predicted_JF=p.get('predicted_JF'),predicted_JM=p.get('predicted_JM'),JF=r.get('JF'),JM=r.get('JM'),counterfactual=p.get('counterfactual_original_nominal_winner',False) or p.get('counterfactual_native_scalar_winner',False),native_scalar_counterfactual=p.get('counterfactual_native_scalar_winner',False),native_scalar_prediction=p.get('native_scalar_prediction'),identical_model_and_scalar_action=p.get('identical_model_and_scalar_action',False))
  if r['complete'] and p.get('predicted_reference_path'):
   with np.load(P/p['predicted_reference_path']) as z:t=z['time_s'];yp=z['predicted_reference']
   with np.load(R/'source/results'/r['id']/'trace.npz') as z:mask=z['stage']=='TASK';ta=z['time_s'][mask];ya=np.c_[z['reference_q_rad'][mask],z['reference_dq_rad_s'][mask],z['reference_ddq_rad_s2'][mask]]
   actual=np.column_stack([np.interp(t,ta,ya[:,j]) for j in range(6)]);row.update(reference_RMSE_per_component=np.sqrt(np.mean((yp-actual)**2,axis=0)),JF_error=p['predicted_JF']-r['JF'],JM_error=p['predicted_JM']-r['JM'])
  data.append(row)
 full=[r for r in data if r.get('JF_error') is not None];learned=[r for r in data if not r['counterfactual'] and r['qualified']];counter=next((r for r in data if r['counterfactual']),None);best=min(learned,key=lambda r:r['JF'],default=None)
 out=dict(status='EXECUTED' if data else 'NOT_RUN',model_training_tasks=17,new_native_forward_tests=len(data),engineering_overhead='new cold parent and B/H150/strong are charged in full ledger',rows=data,full_defined_JF_RMSE=float(np.sqrt(np.mean([r['JF_error']**2 for r in full]))) if full else None,best_learned_reference_candidate=best,nominal_same_pool_counterfactual=next((r for r in data if r['id']=='RESPONSE_NOMINAL_COUNTERFACTUAL'),None),native_scalar_same_pool_counterfactual=next((r for r in data if r.get('native_scalar_counterfactual')),None),no_new_true_Human_state_training_targets=True,calibrated_motion_or_uncertainty='NOT_ESTABLISHED',scope='fixed nominal context; actual forward predictions frozen before all four tests, model never updated on test feedback')
 put('REFERENCE_RESPONSE_LEARNING_RESULTS.json',out);return out

def figures(allrows,curves):
 os.environ.setdefault('MPLCONFIGDIR',str(R/'tmp/mpl'));import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 plt.rcParams.update({'figure.dpi':150,'axes.grid':True,'grid.alpha':.22})
 if any(curves.values()):
  fig,ax=plt.subplots(1,2,figsize=(12,4))
  for method,v in curves.items():
   if not v:continue
   ax[0].step([r['attempt'] for r in v],[r['best_qualified_JF'] for r in v],where='post',label=method)
   ax[1].step([r['native_cumulative']/1e6 for r in v],[r['best_qualified_JF'] for r in v],where='post',label=method)
   if method=='PPO':
    vv=[r for r in v if r['role']=='frozen_mean_evaluation'];ax[0].plot([r['attempt'] for r in vv],[r['JF'] if r['qualified'] else np.nan for r in vv],'kx',label='PPO evaluated mean')
  ax[0].set(xlabel='Real candidate attempts (mean evaluations charged)',ylabel='Best qualified full JF (N s)');ax[1].set(xlabel='New native steps (millions)',ylabel='Best qualified full JF (N s)')
  for a in ax:a.legend(fontsize=8)
  fig.tight_layout();fig.savefig(P/'figures/MATCHED_BUDGET_CURVES.png');plt.close(fig)
 mech=get('audit/REFERENCE_RESPONSE_MECHANISM.json')
 if mech:
  v=mech['rows'];x=np.arange(len(v));fig,ax=plt.subplots(figsize=(10,4));w=.25
  ax.bar(x-w,[r['delta_JF_actual'] for r in v],w,label='Actual native full-task delta');ax.bar(x,[r['delta_JF_pre_execution_approximation'] for r in v],w,label='Pre-execution rough proxy');ax.bar(x+w,[r['delta_JF_posthoc_actual_issued_reference'] for r in v],w,label='Posthoc actual-reference nominal load')
  ax.set(xticks=x,xticklabels=[r['id'].replace('RETIMED_','') for r in v],ylabel='Delta JF vs strong (N s)',title='Posthoc reconstruction diagnoses input error; it is not a forward score');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(P/'figures/REFERENCE_RESPONSE_DIAGNOSIS.png');plt.close(fig)
 nominal=[r for r in allrows if r.get('qualified') and not r['id'].startswith('LOCKED_') and 'JF' in r]
 if nominal:
  fig,ax=plt.subplots(figsize=(7,5));ax.scatter([r['JF'] for r in nominal],[r['JM'] for r in nominal],s=15,alpha=.55,label='Qualified development motions')
  for ident,label in [('INTERFACE_B','B'),('INTERFACE_H150','H150'),('INTERFACE_STRONG','Strong')]:
   r=next((r for r in nominal if r['id']==ident),None)
   if r:ax.scatter([r['JF']],[r['JM']],s=50,marker='*');ax.annotate(label,(r['JF'],r['JM']))
  ax.set(xlabel='Full JF (N s)',ylabel='Full JM (Nm s)',title='Qualified force / moment tradeoff');fig.tight_layout();fig.savefig(P/'figures/FORCE_MOMENT_TRADEOFF.png');plt.close(fig)

def motion_figures(allrows):
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 D={r['id']:r for r in allrows};nominal=[r for r in allrows if r.get('qualified') and r['action'].get('family','').startswith('modal8') and not r['id'].startswith('LOCKED_')]
 best=min(nominal,key=lambda r:r['JF'],default=None);ids=['INTERFACE_B','INTERFACE_H150','INTERFACE_STRONG']+([best['id']] if best else []);ids=list(dict.fromkeys(i for i in ids if i in D))
 if not ids:return
 fig,ax=plt.subplots(2,2,figsize=(12,8));phase_rows=[];strong=D.get('INTERFACE_STRONG')
 for ident in ids:
  r=D[ident];short=ident.replace('INTERFACE_','')
  with np.load(R/'source/results'/ident/'trace.npz') as z:
   ix=z['stage']=='TASK';t=z['time_s'][ix];t=t-t[0];q=np.degrees(z['evaluation_only_human_state_rad_rad_s'][ix,:2]);ax[0,0].plot(t,q[:,0],label=short);ax[0,1].plot(t,q[:,1],label=short);ax[1,0].plot(q[:,0],q[:,1],label=short)
  native=R/'motion_series'/(ident+'.npz')
  if native.exists():
   with np.load(native) as z:tn=z['time_s'];jerk=np.degrees(z['jerk_rad_s3'][:,1]);ax[1,1].plot(tn-tn[0],jerk,linewidth=.45,label=short)
  if strong:
   phase_rows.append(dict(id=ident,deltaJF=[r['phase_cost'][ph]['J_F_N_s']-strong['phase_cost'][ph]['J_F_N_s'] for ph in ['OUTBOUND','HOLD','RETURN']],deltaJM=[r['phase_cost'][ph]['moment_integral_Nm_s']-strong['phase_cost'][ph]['moment_integral_Nm_s'] for ph in ['OUTBOUND','HOLD','RETURN']]))
 ax[0,0].set(xlabel='Task time (s)',ylabel='Actual Human hip (deg)');ax[0,1].set(xlabel='Task time (s)',ylabel='Actual Human knee (deg)');ax[1,0].set(xlabel='Actual hip (deg)',ylabel='Actual knee (deg)');ax[1,1].set(xlabel='Task time (s)',ylabel='Raw native knee jerk (deg/s^3)',title='Every archived native sample; no endpoint deletion')
 for a in ax.flat:a.legend(fontsize=7);a.grid(alpha=.2)
 fig.tight_layout();fig.savefig(P/'figures/HUMAN_MOTION_AND_NATIVE_JERK.png',dpi=160);plt.close(fig)
 if phase_rows:
  fig,ax=plt.subplots(1,2,figsize=(11,4));x=np.arange(len(phase_rows));w=.24
  for j,ph in enumerate(['OUTBOUND','HOLD','RETURN']):
   ax[0].bar(x+(j-1)*w,[r['deltaJF'][j] for r in phase_rows],w,label=ph);ax[1].bar(x+(j-1)*w,[r['deltaJM'][j] for r in phase_rows],w,label=ph)
  for a in ax:a.set_xticks(x,[r['id'].replace('INTERFACE_','') for r in phase_rows],rotation=15);a.legend(fontsize=7);a.grid(alpha=.2)
  ax[0].set_ylabel('Delta phase JF vs strong (N s)');ax[1].set_ylabel('Delta phase JM vs strong (Nm s)');fig.tight_layout();fig.savefig(P/'figures/PHASE_FORCE_MOMENT_CHANGES.png',dpi=160);plt.close(fig)

def main():
 import acl2_exploration
 acl2_exploration.main()
 allrows=rows();account=accounting(allrows);c,table=curves(allrows);frozen=frozen_analysis(allrows);response=response_analysis(allrows);figures(allrows,c);motion_figures(allrows)
 put('ANALYSIS_COMPLETION.json',dict(utc=utc(),candidate_rows=len(allrows),physical_START=account['actual_physical_START'],fixed_budget_rows=len(table),frozen_cross_states=len(frozen['cross_state']),response_branch_status=response['status'],source_sha256=sha(__file__)))
 print('POST_ANALYSIS',len(allrows),'rows',account['actual_physical_START'],'physical START',flush=True)
if __name__=='__main__':main()
