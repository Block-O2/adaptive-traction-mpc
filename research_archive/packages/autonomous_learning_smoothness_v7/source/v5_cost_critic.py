"""Small component-wise kernel cost critic. Training requires an observed myopia gate."""
from pathlib import Path
import os,sys,json,datetime,hashlib,time,resource
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
import numpy as np
from scipy.stats import spearmanr
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def selected(names):
 # All captured numeric fields are from the fixed causal whitelist; retain execution memory.
 # In particular include decision counts, previous executed delta, last applied command and pending request.
 return list(range(len(names)))
def kernel(a,b,length):return np.exp(-.5*np.mean(((a[:,None,:]-b[None,:,:])/length)**2,axis=2))
def fit(rows,phase,horizon=.5):
 use=[r for r in rows if r['complete'] and r['qualified'] and abs(r['horizon_s']-horizon)<1e-9 and phase==r.get('phase',phase)]
 assert len(use)>=6,'INSUFFICIENT_COMPONENT_COST_LABELS'
 names=use[0]['feature_names'];indices=selected(names);X=np.asarray([r['features'] for r in use])[:,indices]
 center=X.mean(0);scale=np.maximum(X.std(0),.001);Z=(X-center)/scale
 target_names=['tail_JF','tail_JM','remaining_time_s','motion_worst_ratio'];Y=[]
 for r in use:
  result=json.loads((P/'attempts'/(r['id']+'_RESULT.json')).read_text());Y.append([r['labels']['tail_JF'],r['labels']['tail_JM'],r['labels']['remaining_time_s'],result['worst_ratio']])
 Y=np.asarray(Y);yc=Y.mean(0);ys=np.maximum(Y.std(0),[.01,.001,.001,.001]);weights=[];lengths=[.5,1.,2.]
 for length in lengths:
  K=kernel(Z,Z,length)+np.eye(len(Z))*1e-4;weights.append(np.linalg.solve(K,(Y-yc)/ys).tolist())
 return dict(schema='v5.component_cost_kernel_ensemble.v1',phase=phase,horizon_s=horizon,gamma=1.,target_names=target_names,feature_names=[names[i] for i in indices],feature_indices=indices,x_center=center.tolist(),x_scale=scale.tolist(),train_x=Z.tolist(),target_center=yc.tolist(),target_scale=ys.tolist(),lengths=lengths,weights=weights,train_ids=[r['id'] for r in use],train_parent_groups=sorted(set(r['parent_group'] for r in use)),continuation_policy='original B rolling/replan after one candidate decision',failure_training_rows=[r['id'] for r in rows if not r['qualified']],failure_model='NOT_FIT; failed identities retained and evaluated; no calibrated eligibility model',uncertainty='ensemble disagreement only; not calibrated confidence interval')
def predict(model,row):
 names=row['feature_names'];lookup={n:i for i,n in enumerate(names)};x=np.asarray([row['features'][lookup[n]] for n in model['feature_names']]);z=(x-np.asarray(model['x_center']))/model['x_scale'];X=np.asarray(model['train_x']);out=[]
 for length,w in zip(model['lengths'],model['weights']):out.append(np.asarray(model['target_center'])+np.asarray(model['target_scale'])*(kernel(X,z[None,:],length).T@np.asarray(w))[0])
 out=np.asarray(out);distance=float(np.min(np.sqrt(np.mean((X-z)**2,axis=1))));return out.mean(0),out.std(0),distance
def run(config,stage):
 run_started=time.perf_counter();usage_started=resource.getrusage(resource.RUSAGE_SELF)
 assert stage in ['fit_only','evaluate_only'],'REQUIRE_EXPLICIT_FROZEN_TRAIN_OR_TEST_STAGE'
 cfg=json.loads((P/config).read_text());gates=[json.loads((P/'analysis/tail'/(g+'.json')).read_text()) for g in cfg['gate_groups']]
 assert any(g['critic_gate_triggered'] for g in gates),'NO_TRUE_MYOPIA_GATE_NO_TRAINING'
 assert not set(cfg['train_groups'])&set(cfg['test_groups']),'PARENT_GROUP_LEAKAGE'
 datasets={}
 for group in (cfg['train_groups'] if stage=='fit_only' else cfg['test_groups']):
  ds=json.loads((P/'models'/(group+'_TAIL_LABELS.json')).read_text());phase=json.loads((P/'experiments'/(group+'.json')).read_text())['fork_phase']
  for r in ds:r['phase']=phase
  datasets[group]=ds
 train=[r for g in cfg['train_groups'] for r in datasets[g]] if stage=='fit_only' else [];models={};results=[];horizon=cfg.get('horizon_s',.5)
 for phase in cfg.get('phases',['OUTBOUND','RETURN']) if stage=='fit_only' else []:
  use=[r for r in train if r['phase']==phase]
  if len([r for r in use if r['qualified'] and abs(r['horizon_s']-horizon)<1e-9])<6:continue
  model=fit(use,phase,horizon);models[phase]=model;put('models/CRITIC_'+cfg['id']+'_'+phase+'.json',model)
 if stage=='fit_only':
  assert models,'NO_COMPONENT_MODELS_FIT'
  fixed_regrets={}
  for group in cfg['train_groups']:
   candidates=[r for r in datasets[group] if r['qualified'] and abs(r['horizon_s']-horizon)<1e-9]
   best=min(r['labels']['full_remaining_JF'] for r in candidates)
   for r in candidates:fixed_regrets.setdefault(r['id'][len(group)+1:],[]).append(r['labels']['full_remaining_JF']-best)
  complete_fixed={tag:float(np.mean(vals)) for tag,vals in fixed_regrets.items() if len(vals)==len(cfg['train_groups'])}
  assert complete_fixed,'NO_COMMON_QUALIFIED_FIXED_ACTION'
  fixed_tag=min(complete_fixed,key=complete_fixed.get)
  freeze=dict(id=cfg['id'],fixed_training_action_tag=fixed_tag,fixed_training_mean_regret_N_s=complete_fixed,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),config_sha256=hashlib.sha256((P/config).read_bytes()).hexdigest(),models={ph:dict(path='models/CRITIC_'+cfg['id']+'_'+ph+'.json',sha256=hashlib.sha256((P/('models/CRITIC_'+cfg['id']+'_'+ph+'.json')).read_bytes()).hexdigest()) for ph in models},training_physical_attempts=len(set(r['id'] for r in train)),captured_horizon_rows=len(train),fitted_rows=sum(r['qualified'] and abs(r['horizon_s']-horizon)<1e-9 for r in train),train_parent_groups=cfg['train_groups'],test_parent_groups=cfg['test_groups'],test_labels_opened=False)
  usage=resource.getrusage(resource.RUSAGE_SELF);freeze['fit_resources']=dict(wall_s=time.perf_counter()-run_started,cpu_user_s=usage.ru_utime-usage_started.ru_utime,cpu_system_s=usage.ru_stime-usage_started.ru_stime,peak_process_rss_kib=usage.ru_maxrss,new_native_steps=0)
  put('models/CRITIC_'+cfg['id']+'_FROZEN.json',freeze);print(json.dumps(freeze,ensure_ascii=False),flush=True);return freeze
 freeze=json.loads((P/('models/CRITIC_'+cfg['id']+'_FROZEN.json')).read_text())
 assert freeze['config_sha256']==hashlib.sha256((P/config).read_bytes()).hexdigest(),'FROZEN_CRITIC_CONFIG_CHANGED'
 assert freeze['source_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'FROZEN_CRITIC_SOURCE_CHANGED'
 starts=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()]
 frozen_time=datetime.datetime.fromisoformat(freeze['frozen_utc']).timestamp()
 assert all(r['unix']>frozen_time for r in starts if r['event']=='START' and r.get('group') in cfg['test_groups']),'CRITIC_TEST_STARTED_BEFORE_MODEL_FREEZE'
 for phase,identity in freeze['models'].items():
  assert identity['sha256']==hashlib.sha256((P/identity['path']).read_bytes()).hexdigest(),'FROZEN_CRITIC_WEIGHTS_CHANGED'
  models[phase]=json.loads((P/identity['path']).read_text())
 for group in cfg['test_groups']:
  ds=[r for r in datasets[group] if abs(r['horizon_s']-horizon)<1e-9];phase=ds[0]['phase'];model=models[phase];pred=[]
  for r in ds:
   mean,std,distance=predict(model,r);actual=json.loads((P/'attempts'/(r['id']+'_RESULT.json')).read_text());pred.append(dict(id=r['id'],qualified=r['qualified'],short_JF=r['labels']['short_JF'],actual_full_task_JF=actual['JF'],actual_full_task_JM=actual['JM'],actual_motion_worst_ratio=actual['worst_ratio'],actual_tail_JM=r['labels']['tail_JM'],actual_tail_JF=r['labels']['tail_JF'],actual_full_remaining_JF=r['labels']['full_remaining_JF'],predicted_tail_components=dict(zip(model['target_names'],mean.tolist())),ensemble_std=dict(zip(model['target_names'],std.tolist())),nearest_training_distance=distance,critic_total_JF=r['labels']['short_JF']+float(mean[0]),future_truth_used_in_prediction=False))
  # Conditional offline ranking; hindsight qualification is shared and explicit.
  longer=[r for r in datasets[group] if abs(r['horizon_s']-1.)<1e-9];longer_choice=min(longer,key=lambda r:r['labels']['short_JF']) if longer else None
  short_all=min(pred,key=lambda r:r['short_JF']);critic_all=min(pred,key=lambda r:r['critic_total_JF']);offered=len(json.loads((P/'experiments'/(group+'.json')).read_text())['actions']);causal_menu_complete=len(pred)==offered
  fixed=next(r for r in pred if r['id']==group+'_'+freeze['fixed_training_action_tag']);valid=[r for r in pred if r['qualified']];short=min(valid,key=lambda r:r['short_JF']);critic=min(valid,key=lambda r:r['critic_total_JF']);actual=min(valid,key=lambda r:r['actual_full_remaining_JF']);err=np.array([r['predicted_tail_components']['tail_JF']-r['actual_tail_JF'] for r in pred]);rank=float(spearmanr([r['critic_total_JF'] for r in valid],[r['actual_full_remaining_JF'] for r in valid]).statistic)
  results.append(dict(group=group,phase=phase,horizon_s=horizon,rows=pred,offered_candidates=offered,all_offered_candidates_have_complete_short_and_tail_labels=causal_menu_complete,one_second_short_choice=None if longer_choice is None else longer_choice['id'],one_second_short_original_qualified=None if longer_choice is None else longer_choice['qualified'],one_second_short_actual_full_remaining_JF=None if longer_choice is None else longer_choice['labels']['full_remaining_JF'],unrestricted_short_choice=short_all['id'],unrestricted_short_qualified=short_all['qualified'],unrestricted_critic_choice=critic_all['id'],unrestricted_critic_qualified=critic_all['qualified'],unrestricted_actual_JF_improvement_vs_short_N_s=short_all['actual_full_remaining_JF']-critic_all['actual_full_remaining_JF'] if causal_menu_complete and short_all['qualified'] and critic_all['qualified'] else None,unrestricted_selection_inputs='actual short cost plus frozen critic(z_H) only; no future qualification mask; identifiable primary result only if the offered menu is fully observed',fixed_training_choice=fixed['id'],fixed_choice_original_qualified=fixed['qualified'],critic_improvement_vs_fixed_N_s=fixed['actual_full_remaining_JF']-critic['actual_full_remaining_JF'] if fixed['qualified'] else None,short_choice=short['id'],critic_choice=critic['id'],actual_tail_choice=actual['id'],critic_changed_choice=short['id']!=critic['id'],actual_JF_improvement_vs_short_N_s=short['actual_full_remaining_JF']-critic['actual_full_remaining_JF'],critic_regret_N_s=critic['actual_full_remaining_JF']-actual['actual_full_remaining_JF'],tail_JF_RMSE_N_s=float(np.sqrt(np.mean(err*err))),ranking_spearman=rank if np.isfinite(rank) else None,eligibility='OFFLINE CONDITIONAL ranking within same actual original-qualified set; uses hindsight qualification shared by all three arms, not deployment safety filtering',new_physical_attempt_savings_demonstrated=0))
 out=dict(id=cfg['id'],frozen_config=cfg,evaluated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),models=list(models),results=results,training_physical_attempts=freeze['training_physical_attempts'],captured_horizon_rows=freeze['captured_horizon_rows'],fitted_training_rows=freeze['fitted_rows'],model_weights_frozen_utc=freeze['frozen_utc'],primary_horizon_s=horizon,gamma=1.,new_physics_in_fit=0,real_attempt_savings='NOT_ESTABLISHED: all menu candidates fully executed for independent labels; no retrospective compute saving claim',method='Small three-lengthscale RBF kernel ensemble, component costs, whole-parent split; no MuJoCo gradients, world model or PPO training')
 usage=resource.getrusage(resource.RUSAGE_SELF);out['evaluation_resources']=dict(wall_s=time.perf_counter()-run_started,cpu_user_s=usage.ru_utime-usage_started.ru_utime,cpu_system_s=usage.ru_stime-usage_started.ru_stime,peak_process_rss_kib=usage.ru_maxrss,new_native_steps=0)
 put('analysis/CRITIC_'+cfg['id']+'_RESULTS.json',out);print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=='__main__':run(sys.argv[1],sys.argv[2])
