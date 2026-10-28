"""A4 SOURCE_ONLY有限训练入口；当前不得运行/forward，需root另批final合同。"""
from pathlib import Path
import copy
import hashlib
import json
import os
import resource
import signal
import sys
import time
import traceback
ROOT=Path(__file__).resolve().parents[1];P=ROOT.parents[2]
HARD=1793114740.
OBJECTIVES=['JF_QUALIFIED','JM_QUALIFIED','STRICT_JM']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def put(p,d):
 with Path(p).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def evaluate(pred,test,method,cost_kind,objective,heldout):
 chosen=pred['choice_recipe_sha256'];abstain=chosen is None
 if abstain:chosen=next(r['action_recipe_sha256'] for r in test if r['action_recipe']['action']['family']=='B')
 row=next((r for r in test if r['action_recipe_sha256']==chosen),None);labels=row['labels_evaluation_only'] if row else None
 return {'heldout_parent_group':heldout,'development_context':test[0]['group_evaluation_only'],'method':method,'cost_kind':cost_kind,'objective':objective,'choice_recipe_sha256':chosen,'choice_id':row['id'] if row else None,'B_fallback_after_predictive_abstain':abstain,'actual_available':row is not None,'original_qualified':labels['original_qualified'] if labels else None,'JF_N_s':labels['JF_N_s'] if labels else None,'JM_Nm_s':labels['JM_Nm_s'] if labels else None,'delta_JF_vs_B_N_s':labels['delta_JF_N_s'] if labels else None,'delta_JM_vs_B_Nm_s':labels['delta_JM_Nm_s'] if labels else None,'motion_failed_requirements':labels['original_motion_failed_requirements'] if labels else None,'actual_min_original_margin':min(labels['signed_normalized_original_45_margin']) if labels else None,'prediction':pred,'evaluation_only_labels_not_selection_inputs':True}
def run(approval_path):
 approval=load(approval_path);contract_path=ROOT/'contracts/FIT_CONTRACT_FINAL_V1.json';manifest_path=ROOT/'SOURCE_CANDIDATE_MANIFEST_V1.json';contract=load(contract_path)
 assert approval['status']=='APPROVED_BY_MAIN_AGENT' and approval['contract_sha256']==sha(contract_path)
 assert approval['source_manifest_sha256']==sha(manifest_path)==contract['source_manifest_sha256']
 data_path=P/contract['data_path'];assert sha(data_path)==approval['dataset_sha256']==contract['data_sha256']
 activation=load(P/'ACTIVATION.json');assert activation['activation_id']==contract['activation_id'] and activation['hard_stop_unix']==contract['global_deadline_unix']==HARD
 assert time.time()<HARD
 for relative,h in load(manifest_path)['source_files_sha256'].items():assert sha(P/relative)==h,'A4_SOURCE_CHANGED:'+relative
 for relative,h in contract['frozen_reference_files_sha256'].items():assert sha(P/relative)==h,'A4_REFERENCE_CHANGED:'+relative
 for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:assert os.environ.get(name)=='1'
 assert os.environ.get('PYTHONDONTWRITEBYTECODE')=='1'
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});run_path=ROOT/contract['output_directory'];assert not run_path.exists(),'NO_AUTOMATIC_RETRY_OR_OVERWRITE';run_path.mkdir(parents=True)
 started=time.time();before=resource.getrusage(resource.RUSAGE_SELF);deadline=min(started+175.,HARD)
 put(run_path/'OWNER_START.json',{'PID':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'start_unix':started,'local_stop_unix':deadline,'original_hard_stop_unix':HARD,'approval_sha256':sha(approval_path),'contract_sha256':sha(contract_path),'data_sha256':sha(data_path),'affinity':sorted(os.sched_getaffinity(0)),'new_physics':0})
 def stop(_sig,_frame):raise TimeoutError('A4_EXTERNAL_FINITE_TIMEOUT')
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGXCPU,stop)
 ledger=[];cv=[];parity=[];cache={};infer_calls=0;dot_calls=0;reference_cost_dot_calls=0;error=None;status='FAILED';versions=None
 try:
  resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_CPU,(180,180))
  import numpy as np
  import scipy
  import predict_api as api
  from fit_candidate import fit,check
  from causal_api import to_context_full
  original_dot=api.dot
  def counted_dot(a,b):
   nonlocal dot_calls
   dot_calls+=1;return original_dot(a,b)
  api.dot=counted_dot
  data=load(data_path);rows=data['rows'];assert len(rows)==48 and len({r['split_parent_group_evaluation_only'] for r in rows})==10
  a3=load(P/contract['A3_bundle_path']);old_cv=load(P/contract['A3_LOCO_path']);menu=a3['menu'];profiles=data['input_source_profiles'];parents=sorted({r['split_parent_group_evaluation_only'] for r in rows})
  assert profiles==a3['input_source_profiles'] and all(len(r['labels_evaluation_only']['signed_normalized_original_45_margin'])==45 for r in rows)
  names=[d['name'] for d in rows[0]['labels_evaluation_only']['component_descriptors']];assert len(set(names))==45
  for row in rows:assert [d['name'] for d in row['labels_evaluation_only']['component_descriptors']]==names
  old_diagnostics={(d['heldout_parent'],d['method'],d['tag']):d['predicted'] for d in old_cv['prediction_diagnostics'] if d['method'] in ['ABS_WRENCH39','DELTA_WRENCH39']}
  def base_bundle(model):return {'schema':'v8.a4.original_component_margin_bundle.v1','model':model,'menu':menu,'component_names':names,'input_source_profiles':profiles,'input_source_profile_paths':data['input_source_profile_paths'],'minimum_support_contexts':2,'distance_limit':3.,'risk_threshold':.5,'primary':{'cost_kind':'ABS','eligibility':'ENSEMBLE45_002','objective':'JF_QUALIFIED'},'classifier_original_threshold':.5,'development_only':False}
  def fitted(records):
   key=tuple(r['id'] for r in records)
   if key not in cache:cache[key]=fit(records,menu,profiles,ledger,deadline)
   return cache[key]
  parity_keys=['predicted_JF_component','predicted_JM_component','ridge_spread_JF','ridge_spread_JM','predicted_delta_JF_vs_B','predicted_delta_JM_vs_B']
  for heldout in parents:
   check(deadline);train=[r for r in rows if r['split_parent_group_evaluation_only']!=heldout];test=[r for r in rows if r['split_parent_group_evaluation_only']==heldout];model=fitted(train);bundle=base_bundle(model)
   context=to_context_full(test[0]['context'],profiles)
   risk={m['recipe_sha256']:old_diagnostics[(heldout,'ABS_WRENCH39',m['tag'])]['qualification_failure_score'] for m in menu}
   assert all(risk[m['recipe_sha256']]==old_diagnostics[(heldout,'DELTA_WRENCH39',m['tag'])]['qualification_failure_score'] for m in menu)
   bundle.update(development_only=True,diagnostic_context_vector_sha256=digest(context['features']),frozen_A3_LOCO_risk_by_recipe=risk,frozen_A3_LOCO_source_sha256=sha(P/contract['A3_LOCO_path']))
   for cost_kind,old_method in [('ABS','ABS_WRENCH39'),('DELTA_B','DELTA_WRENCH39')]:
    for eligibility in api.ELIGIBILITY:
     for objective in OBJECTIVES:
      check(deadline);pred=api.predict(bundle,test[0]['context'],cost_kind,eligibility,objective);infer_calls+=1;cv.append(evaluate(pred,test,eligibility,cost_kind,objective,heldout))
      if eligibility=='CLASSIFIER39':
       old_choice=next(r for r in old_cv['rows'] if r['heldout_parent_group']==heldout and r['method']==old_method+'/RISK_ON' and r['objective']==objective)
       assert pred['choice_recipe_sha256']==old_choice['prediction']['choice_recipe_sha256'],'A4_A3_CLASSIFIER_CHOICE_PARITY'
       parity.append({'scope':'LOCO_ORIGINAL_CLASSIFIER_CHOICE','parent':heldout,'method':cost_kind,'objective':objective,'exact_choice_equal':True})
      if eligibility=='CLASSIFIER39' and objective=='JF_QUALIFIED':
       for value in pred['predictions']:
        old=old_diagnostics[(heldout,old_method,value['tag'])];differences={k:abs(value[k]-old[k]) for k in parity_keys};assert max(differences.values())<=1e-6,'A4_A3_LOCO_COST_MEAN_SPREAD_PARITY'
        assert value['qualification_failure_score']==old['qualification_failure_score'] and value['supported']==old['supported']
        parity.append({'scope':'LOCO_MEAN_SPREAD','parent':heldout,'method':cost_kind,'tag':value['tag'],'absolute_difference':differences,'max_abs_difference':max(differences.values()),'source_A3_fold_lambda_weights_unavailable':True,'per_lambda_normal_equation_residuals':model['normal_equation_residuals']})
   for value in old_cv['rows']:
    if value['heldout_parent_group']==heldout and value['method'] in ['CONSTANT_B/WRENCH39','BEST_FIXED/WRENCH39','IF_STUMP/WRENCH39','NEAREST/WRENCH39']:
     cv.append({**copy.deepcopy(value),'method':'INHERITED_A3/'+value['method'],'reuse_frozen_A3_control_prediction':True,'new_model_forward':0,'frozen_source_sha256':sha(P/contract['A3_LOCO_path'])})
  full=fitted(rows);a3spec=a3['cohorts']['MERGED']['models']['WRENCH39']
  for key in ['indices','center','scale','numeric_constant_positions','train_parent_groups','support_train_z']:assert full[key]==a3spec[key],'A4_A3_FULL_NORMALIZATION_OR_SUPPORT_PARITY:'+key
  full['risk_weights']=copy.deepcopy(a3spec['risk_weights'])
  for kind in ['ABS','DELTA_B']:
   h,ref=full['cost_heads'][kind],a3spec['cost_heads'][kind]
   for key in ['target_center','target_scale']:assert np.max(np.abs(np.asarray(h[key])-np.asarray(ref[key])))<=1e-9
   for i,penalty in enumerate([.1,1.,10.]):
    difference=float(np.max(np.abs(np.asarray(h['weights'][i])-np.asarray(ref['weights'][i]))));assert difference<=1e-8,'A4_A3_FULL_EACH_LAMBDA_WEIGHT_PARITY'
    parity.append({'scope':'FULL_EACH_LAMBDA_WEIGHTS','method':kind,'lambda':penalty,'max_abs_difference':difference})
  frozen=base_bundle(full)
  proxy={'schema':a3['schema'],'menu':menu,'cohorts':{'MERGED':{'models':{'WRENCH39':copy.deepcopy(a3spec)},'controls':{'WRENCH39':copy.deepcopy(a3['cohorts']['MERGED']['controls']['WRENCH39'])}}},'input_source_profiles':profiles,'distance_limit':3.,'minimum_support_contexts':2,'risk_threshold':.5}
  frozen.update(inherited_A3_control_bundle=proxy,fit_contract_sha256=sha(contract_path),data_sha256=sha(data_path),source_manifest_sha256=sha(manifest_path),frozen_unix=time.time(),all_parent_contexts_are_development=True,sealed_validation_read=False,new_physics=0,physical_attempt_savings=0)
  for parent in parents:
   test=next(r for r in rows if r['split_parent_group_evaluation_only']==parent)
   for kind in ['ABS','DELTA_B']:
    pred=api.predict(frozen,test['context'],kind,'ENSEMBLE45_002','JF_QUALIFIED');infer_calls+=1
    context=to_context_full(test['context'],profiles);z=api.transform(a3spec,context);h=a3spec['cost_heads'][kind]
    for index,value in enumerate(pred['predictions']):
     vector=api.design(z,index,5)
     for li,penalty in enumerate([.1,1.,10.]):
      estimates=[]
      for output in range(2):
       reference_cost_dot_calls+=1;estimates.append(sum(a*b[output] for a,b in zip(vector,h['weights'][li]))*h['target_scale'][output]+h['target_center'][output])
      difference=max(abs(a-b) for a,b in zip(estimates,value['cost_estimates_by_lambda'][li]));assert difference<=1e-6,'A4_A3_FULL_EACH_LAMBDA_PREDICTION_PARITY'
      parity.append({'scope':'FULL_EACH_LAMBDA_PREDICTION','parent':parent,'method':kind,'tag':value['tag'],'lambda':penalty,'max_abs_difference':difference})
  assert len(cache)==11 and len(ledger)==33 and infer_calls==320 and reference_cost_dot_calls==600
  assert len([r for r in cv if r.get('reuse_frozen_A3_control_prediction')])==120
  put(run_path/'A4_FROZEN_BUNDLE_V1.json',frozen);put(run_path/'DEVELOPMENT_LOCO_V1.json',{'rows':cv,'independent_test':False,'original_qualification_mask_used':False,'primary_was_fixed_before_fit':True});put(run_path/'A3_THREE_LAMBDA_COST_PARITY_V1.json',{'rows':parity,'full_all_three_lambda_weights_and_predictions_direct_parity':True,'LOCO_all_actions_mean_spread_direct_parity':True,'LOCO_per_lambda_evidence':'normal-equation residual, same training state and target normalization rule; original individual-lambda fold weights were not archived','no_additional_reference_ridge_solves':True})
  status='COMPLETED_FROZEN_NO_SEALED_VALIDATION';versions={'numpy':np.__version__,'scipy':scipy.__version__}
 except BaseException as failure:error={'error':str(failure),'traceback':traceback.format_exc()};raise
 finally:
  after=resource.getrusage(resource.RUSAGE_SELF);put(run_path/'FIT_RESOURCE_AND_OPERATIONS_V1.json',{'status':status,'error':error,'wall_s':time.time()-started,'initial_wall_unix':started,'final_wall_unix':time.time(),'CPU_user_s':after.ru_utime-before.ru_utime,'CPU_system_s':after.ru_stime-before.ru_stime,'RSS_peak_KiB':after.ru_maxrss,'ridge_ledger':ledger,'ridge_49_RHS_solves':len(ledger),'prediction_API_calls':infer_calls,'scalar_predict_dot_calls_including_constants_skipped':dot_calls,'A3_reference_cost_head_dots':reference_cost_dot_calls,'inherited_A3_control_CV_rows_reused_no_forward':120,'new_classifier_fits':0,'automatic_retry':False,'versions':versions,'python':sys.executable,'new_physics':0,'sealed_or_active_H2_read':False})
 print(json.dumps({'status':status,'bundle_sha256':sha(run_path/'A4_FROZEN_BUNDLE_V1.json'),'prediction_API_calls':infer_calls}))
