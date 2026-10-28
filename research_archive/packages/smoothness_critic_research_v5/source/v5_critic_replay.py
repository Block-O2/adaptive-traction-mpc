"""Independent frozen-model/data binding and prediction replay; no refitting or physics."""
from pathlib import Path
import os,sys,json,hashlib,datetime
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def get(n):return json.loads((P/n).read_text())
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
events=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];out=[];errors=[]
for result_file in sorted((P/'analysis').glob('CRITIC_*_RESULTS.json')):
 result=json.loads(result_file.read_text());mid=result['id'];frozen=get('models/CRITIC_'+mid+'_FROZEN.json');cfg=get('experiments/CRITIC_'+mid+'.json');bad=[];freeze_time=datetime.datetime.fromisoformat(frozen['frozen_utc']).timestamp()
 if frozen['source_sha256']!=sha(P/'source/v5_cost_critic.py'):bad.append('SOURCE_CHANGED')
 if frozen['config_sha256']!=sha(P/'experiments'/('CRITIC_'+mid+'.json')):bad.append('CONFIG_CHANGED')
 if set(cfg['train_groups'])&set(cfg['test_groups']):bad.append('PARENT_SPLIT_LEAK')
 test_starts=[x['unix'] for x in events if x['event']=='START' and x.get('group') in cfg['test_groups']]
 if not test_starts or min(test_starts)<=freeze_time:bad.append('TEST_NOT_AFTER_FREEZE')
 train_ends=[x['unix'] for x in events if x['event']=='END' and x.get('id','').split('_')[0] in cfg['train_groups']]
 if not train_ends or max(train_ends)>freeze_time:bad.append('TRAINING_NOT_FINISHED_BEFORE_FREEZE')
 data={r['id']:r for group in cfg['train_groups'] for r in get('models/'+group+'_TAIL_LABELS.json') if abs(r['horizon_s']-cfg['horizon_s'])<1e-9};max_fit_residual=0.;max_prediction_error=0.;max_uncertainty_error=0.;n=0
 for phase,identity in frozen['models'].items():
  if identity['sha256']!=sha(P/identity['path']):bad.append('WEIGHT_SHA_CHANGED')
  model=get(identity['path']);train=[data[i] for i in model['train_ids']];names=model['feature_names']
  def vector(row):
   index={name:k for k,name in enumerate(row['feature_names'])};return np.array([row['features'][index[name]] for name in names])
  x=np.vstack([vector(r) for r in train]);z=(x-np.array(model['x_center']))/np.array(model['x_scale']);stored=np.array(model['train_x'])
  if not np.allclose(z,stored,atol=1e-12,rtol=0):bad.append('TRAIN_X_LABEL_BINDING')
  y=np.array([[r['labels']['tail_JF'],r['labels']['tail_JM'],r['labels']['remaining_time_s'],get('attempts/'+r['id']+'_RESULT.json')['worst_ratio']] for r in train]);yn=(y-model['target_center'])/model['target_scale']
  if not all(r['qualified'] for r in train):bad.append('FAILED_COST_LABEL_USED_AS_SUCCESS')
  for length,weights in zip(model['lengths'],model['weights']):
   difference=stored[:,None,:]-stored[None,:,:];K=np.exp(-np.mean(difference*difference,axis=-1)/(2*length*length))+1e-4*np.eye(len(stored));max_fit_residual=max(max_fit_residual,float(np.max(abs(K@np.array(weights)-yn))))
  for group_result in result['results']:
   if group_result['phase']!=phase:continue
   testdata={r['id']:r for r in get('models/'+group_result['group']+'_TAIL_LABELS.json') if abs(r['horizon_s']-cfg['horizon_s'])<1e-9}
   for reported in group_result['rows']:
    r=testdata[reported['id']];query=(vector(r)-model['x_center'])/model['x_scale'];predictions=[]
    for length,weights in zip(model['lengths'],model['weights']):
     kernel=np.exp(-np.mean((stored-query)**2,axis=1)/(2*length*length));predictions.append(np.array(model['target_center'])+np.array(model['target_scale'])*(kernel@np.array(weights)))
    mean=np.mean(predictions,axis=0);std=np.std(predictions,axis=0);saved=np.array([reported['predicted_tail_components'][name] for name in model['target_names']]);uncertainty=np.array([reported['ensemble_std'][name] for name in model['target_names']]);max_prediction_error=max(max_prediction_error,float(np.max(abs(mean-saved))),abs(reported['critic_total_JF']-r['labels']['short_JF']-mean[0]));max_uncertainty_error=max(max_uncertainty_error,float(np.max(abs(std-uncertainty))));n+=1
 if max_fit_residual>1e-7:bad.append('FROZEN_WEIGHTS_NOT_BOUND_TO_ACTUAL_TRAIN_LABELS')
 if max_prediction_error>1e-8 or max_uncertainty_error>1e-8:bad.append('FROZEN_PREDICTION_REPLAY_MISMATCH')
 out.append(dict(model=mid,status='PASS' if not bad else 'FAIL',fitted_real_branch_labels=frozen['fitted_rows'],independent_test_rows_replayed=n,fit_equation_max_abs_residual=max_fit_residual,prediction_max_abs_error=max_prediction_error,ensemble_std_max_abs_error=max_uncertainty_error,errors=bad));errors.extend([mid+':'+b for b in bad])
result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS' if out and not errors else 'REVIEW_REQUIRED',rows=out,errors=errors,scope='Separate arithmetic from JSON frozen weights and actual training/test labels. Source/config/weights SHA, train/test chronology, complete parent split and actual cost binding checked. No model is selected/refit on test.',new_physical_START=0)
(P/'audit/CRITIC_FROZEN_PREDICTION_REPLAY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('CRITIC_REPLAY',result['status'],'models',len(out),'errors',errors);assert out and not errors,errors
