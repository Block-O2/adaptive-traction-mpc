"""Condition-split offline model comparison and SHORT/FULL action ranking."""
from pathlib import Path
from collections import defaultdict
import argparse, json, sys, time
import numpy as np
from scipy.stats import spearmanr
from value_models import fit_ridge, fit_mlp, save_model
from value_dataset import D,RAW,C,save,sha

def rank_metrics(y,p,groups,legacy=None):
 result=[]
 for g in sorted(set(groups)-{''}):
  ix=np.flatnonzero(groups==g)
  if len(ix)<2 or np.ptp(y[ix])<1e-6:continue
  actual=y[ix];pred=p[ix];selected=int(np.argmin(pred));best=float(np.min(actual));rank=np.argsort(pred)
  corr=None if np.ptp(pred)<1e-10 else float(spearmanr(actual,pred).statistic)
  if corr is not None and not np.isfinite(corr):corr=None
  row={'group':g,'candidate_count':len(ix),'true_return_range_n_s':float(np.ptp(actual)),'spearman':corr,
   'selected_return_n_s':float(actual[selected]),'best_candidate_return_n_s':best,'regret_n_s':float(actual[selected]-best),
   'top1':bool(actual[selected]<=best+1e-6),'top2_capture':bool(np.min(actual[rank[:2]])<=best+1e-6),
   'selected_row_index':int(ix[selected]),'best_row_index':int(ix[np.argmin(actual)])}
  if legacy is not None:row['legacy_regret_n_s']=float(actual[np.argmin(legacy[ix])]-best)
  result.append(row)
 return {'group_count':len(result),'mean_spearman':float(np.mean([r['spearman'] for r in result if r['spearman'] is not None])) if any(r['spearman'] is not None for r in result) else None,
  'mean_regret_n_s':float(np.mean([r['regret_n_s'] for r in result])) if result else None,
  'median_regret_n_s':float(np.median([r['regret_n_s'] for r in result])) if result else None,
  'top1_accuracy':float(np.mean([r['top1'] for r in result])) if result else None,
  'top2_capture_fraction':float(np.mean([r['top2_capture'] for r in result])) if result else None,
  'legacy_mean_regret_n_s':float(np.mean([r['legacy_regret_n_s'] for r in result])) if result and legacy is not None else None,'groups':result}
def evaluate(model,X,y,groups,legacy):
 p=model.predict(X);return {'MAE_n_s':float(np.mean(np.abs(y-p))),'RMSE_n_s':float(np.sqrt(np.mean((y-p)**2))),'ranking':rank_metrics(y,p,groups,legacy)}

def train(dataset=None):
 manifest=json.loads((D/'VALUE_DATASET_MANIFEST.json').read_text())
 if manifest['status']!='PASS':raise RuntimeError('dataset not validated')
 data_path=Path(dataset) if dataset else (D.parents[3]/manifest['dataset_path'])
 # Explicit absolute resolution avoids assumptions about checkout parent count.
 if dataset is None:
  from value_dataset import R
  data_path=R/manifest['dataset_path']
 with np.load(data_path/'data.npz',allow_pickle=False) as f:data={k:f[k] for k in f.files}
 X=data['X'];names=json.loads((D/'VALUE_DATASET_SCHEMA.json').read_text())['feature_names']
 train_mask=data['split']=='train';val_mask=data['split']=='validation';test_mask=data['split']=='test'
 report=[];times=[];models={};modeldir=D/'models';modeldir.mkdir(exist_ok=True)
 for target in ('full','short'):
  y=data['y_'+target]
  for kind in ('ridge','mlp'):
   candidates=[]
   settings=[.1,1.,10.,100.] if kind=='ridge' else [20260930,20260931,20260932]
   for setting in settings:
    t=time.perf_counter();metadata={'training_conditions':C['splits']['train'],'validation_conditions':C['splits']['validation'],'test_conditions_excluded':C['splits']['test'],'target':target,'dataset_sha256':sha(data_path/'data.npz')}
    model=fit_ridge(X[train_mask],y[train_mask],alpha=setting,feature_names=names,metadata=metadata) if kind=='ridge' else fit_mlp(X[train_mask],y[train_mask],validation=(X[val_mask],y[val_mask]),seed=setting,metadata=metadata)
    elapsed=time.perf_counter()-t
    evaluation=evaluate(model,X[val_mask],data['y_full'][val_mask],data['group'][val_mask],data['legacy'][val_mask])
    validation_target=evaluate(model,X[val_mask],y[val_mask],data['group'][val_mask],data['legacy'][val_mask])
    key=f'{kind}_{target}_{setting}';path=modeldir/(key+'.npz');hash_=save_model(path,model)
    candidate={'key':key,'kind':kind,'target':target,'setting':setting,'model_path':str(path),'sha256':hash_,'validation_full_action_ranking':evaluation['ranking'],'validation_target_prediction':validation_target,'training_wall_s':elapsed,'metadata':model.metadata}
    candidates.append((model,candidate));report.append(candidate);times.append({'model':key,'wall_s':elapsed,'stage':'offline_training','rows':int(np.sum(train_mask))})
    print(json.dumps({'trained':key,'wall_s':elapsed,'validation_regret_n_s':evaluation['ranking']['mean_regret_n_s'],'validation_spearman':evaluation['ranking']['mean_spearman']}),flush=True)
   # Fixed selection rule: validation full-return action regret, then target RMSE.
   best=min(candidates,key=lambda pair:(pair[1]['validation_full_action_ranking']['mean_regret_n_s'] if pair[1]['validation_full_action_ranking']['mean_regret_n_s'] is not None else float('inf'),pair[1]['validation_target_prediction']['RMSE_n_s']))
   models[(kind,target)]=best
 selected={}
 for (kind,target),(model,candidate) in models.items():
  test_prediction=evaluate(model,X[test_mask],data['y_'+target][test_mask],data['group'][test_mask],data['legacy'][test_mask])
  test_full_ranking=rank_metrics(data['y_full'][test_mask],model.predict(X[test_mask]),data['group'][test_mask],data['legacy'][test_mask])
  selected[kind+'_'+target]={**candidate,'test_target_prediction':test_prediction,'test_full_action_ranking':test_full_ranking}
 full_best=min([selected['ridge_full'],selected['mlp_full']],key=lambda x:(x['validation_full_action_ranking']['mean_regret_n_s'] if x['validation_full_action_ranking']['mean_regret_n_s'] is not None else float('inf'),x['validation_target_prediction']['RMSE_n_s']))
 rank=full_best['validation_full_action_ranking']
 meaningful=(rank['group_count']>=3 and rank['mean_spearman'] is not None and rank['mean_spearman']>0 and rank['mean_regret_n_s']<rank['legacy_mean_regret_n_s'])
 output={'schema':'offline_value_comparison_v1','selected_models':selected,'all_training_candidates':report,'best_full_model':full_best['key'],'ranking_gate':'PASS' if meaningful else 'FAIL','ranking_gate_rule':C['models']['gate'],'split':C['splits'],'test_used_for_model_selection':False,'interpretable_ridge':'linear plus state-action interactions; regularization selection on validation','MLP':'two 32-unit tanh hidden layers, trained in NumPy CPU; no cross-condition truth input','limitations':['Historical task conditions, not independent unseen Human subjects','Remaining cost dominated by phase/condition; branch ranking is more relevant than pooled prediction error','Declared continuation context conditions Q; policy improvement may change future behavior, requiring renewed returns']}
 save(D/'OFFLINE_VALUE_MODEL_COMPARISON.json',output)
 (D/'OFFLINE_VALUE_MODEL_COMPARISON.md').write_text('# Offline cost-to-go comparison\n\n'+json.dumps({k:v for k,v in output.items() if k!='all_training_candidates'},indent=2)+'\n')
 ablation={'schema':'short_vs_full_value_ablation_v1','short_horizon_s':1.5,'comparison_target':'actual remaining FULL repetition cost of selected branch action; same checkpoint/state/common continuation',
  'models':{kind:{t:selected[kind+'_'+t]['test_full_action_ranking'] for t in ('short','full')} for kind in ('ridge','mlp')},'selected_models_frozen_before_test':True}
 save(D/'SHORT_VS_FULL_VALUE_ABLATION.json',ablation)
 save(D/'TRAINING_UPDATE_LATENCY.json',{'offline_training':times,'repetition_boundary_updates':[],'units':'seconds','GPU':'not used; small models and scientific environment have NumPy CPU path; GPU optional'})
 save(D/'OFFLINE_MODEL_PROMOTION_GATE.json',{'status':'PASS' if meaningful else 'FAIL','chosen_model':full_best['model_path'],'ranking':rank,'pilot_training_conditions_exclusion_required':['sync_120'],'no_test_tuning':True})
 return output
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dataset');a=p.parse_args();train(a.dataset)
