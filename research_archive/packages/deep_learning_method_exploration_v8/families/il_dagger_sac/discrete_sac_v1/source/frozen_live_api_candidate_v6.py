"""SOURCE_ONLY: 冻结SAC三AGG机制+sameQ+强对照，actual OUT0 proof -> 选择。

当前未调用。不写文件/不派发物理，调用后root应计3 SAC API+4control API。
原失去支持的abstain保留，执行fallback B事前固定，不能授予资格。
"""
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT_REL='families/il_dagger_sac/discrete_sac_v1'
PRIMARY='SAC_AGG_VANILLA_ACTOR'
SELECTORS=['SAC_AGG_VANILLA_ACTOR','SAC_AGG_ADAPTIVE_ACTOR','SAC_AGG_CONSERVATIVE_ACTOR','SAC_AGG_VANILLA_QGREEDY','SAC_AGG_VANILLA_SOFTQ','SAC_CONTROL_B','SAC_CONTROL_BEST_FIXED','SAC_CONTROL_IF_STUMP','SAC_CONTROL_NEAREST']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def source(P,item,label):
 path=(P/item['path']).resolve();assert path.is_relative_to(P) and sha(path)==item['sha256']
 spec=importlib.util.spec_from_file_location(label,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def predict_before_B(package,config,study):
 P=Path(package).resolve();manifest_path=P/ROOT_REL/'FROZEN_LIVE_API_MANIFEST_V6.json';manifest=load(manifest_path)
 assert sha(__file__)==manifest['adapter_sha256'] and manifest['selectors']==SELECTORS and manifest['primary']==PRIMARY
 bundle_path=P/manifest['bundle']['path'];assert sha(bundle_path)==manifest['bundle']['sha256'];bundle=load(bundle_path)
 assert bundle['primary']=={'cohort':'AGGREGATE64','mechanism':'VANILLA_FIXED_ENTROPY','selector':'ACTOR_ARGMAX'}
 assert bundle['approved_contract_sha256']==manifest['fit_contract_sha256']
 proof_adapter=source(P,manifest['actual_proof_adapter'],'_sac_frozen_actual_source_proof')
 a3_path=P/manifest['actual_proof_bundle']['path'];assert sha(a3_path)==manifest['actual_proof_bundle']['sha256'];a3=load(a3_path)
 proof_adapter._menu_matches(P,config,a3['menu'])
 raw,proof,proof_audit=proof_adapter._actual_live_proof(P,config,study,a3)
 converter=source(P,manifest['converter'],'_sac_frozen_context25_converter');context=converter.to_context25(raw)
 learner=source(P,manifest['learner'],'_sac_frozen_offpolicy_learner');controls=source(P,manifest['controls'],'_sac_frozen_offpolicy_controls')
 recipe_hashes=[item['recipe_sha256'] for item in a3['menu']];predictions={};models={}
 for mechanism in ['VANILLA_FIXED_ENTROPY','ADAPTIVE_TEMPERATURE','CONSERVATIVE_SUPPORT']:
  saved=bundle['models']['AGGREGATE64/'+mechanism]
  model=learner.restore(saved,expected_source_sha256=manifest['learner']['sha256'],expected_contract_sha256=manifest['fit_contract_sha256'],expected_recipe_sha256=recipe_hashes)
  assert model['actor']['action_contracts']==[item['action_recipe'] for item in a3['menu']]
  models[mechanism]=model
  predictions[mechanism]=learner.predict(model,context['feature_names'],context['features'],qa_validated=True)
 decisions={}
 def add(name,index,detail):
  abstained=index is None;index=0 if abstained else index;item=a3['menu'][index]
  decisions[name]={'choice_tag':item['tag'],'choice_recipe_sha256':item['recipe_sha256'],'choice_action':item['action'],'prediction_abstained':abstained,'execution_fallback_B_predeclared':abstained,'original_qualification_granted':False,'detail':detail}
 for name,mechanism in [('SAC_AGG_VANILLA_ACTOR','VANILLA_FIXED_ENTROPY'),('SAC_AGG_ADAPTIVE_ACTOR','ADAPTIVE_TEMPERATURE'),('SAC_AGG_CONSERVATIVE_ACTOR','CONSERVATIVE_SUPPORT')]:add(name,predictions[mechanism]['action_index'],predictions[mechanism])
 pred=predictions['VANILLA_FIXED_ENTROPY'];add('SAC_AGG_VANILLA_QGREEDY',pred['direct_Q_greedy_index'],pred)
 allowed=pred['allowed_from_past_replay_only'];soft=pred['direct_softmax_Q_probabilities'];index=max(allowed,key=lambda i:(soft[i],-i)) if allowed else None;add('SAC_AGG_VANILLA_SOFTQ',index,pred)
 cb=bundle['controls']['AGGREGATE64/ALL_DEVELOPMENT']
 for name,control in [('SAC_CONTROL_B','CONSTANT_B'),('SAC_CONTROL_BEST_FIXED','BEST_FIXED'),('SAC_CONTROL_IF_STUMP','IF_STUMP'),('SAC_CONTROL_NEAREST','NEAREST')]:
  cp=controls.predict_control(cb,context['features'],control);add(name,cp['action_index'],cp)
 assert list(decisions)==SELECTORS and study.child is None and study.fork_done is True and not study.metrics
 return {'schema':'v8.sac.frozen_aggregate_live_selectors.v6','decisions':decisions,'primary':PRIMARY,'actual_source_proof':proof,'proof_audit':proof_audit,'input_subset25_original_raw77_still_invalid':True,'API_calls':{'SAC_predict':3,'control_predict':4,'restore':3,'new_fit_or_initialize':0},'all_choices_before_any_B_result':True,'sameQ_predictions_reused_not_extra_fit_or_independent_physics':True,'new_physics':0,'adapter_sha256':manifest['adapter_sha256'],'manifest_sha256':sha(manifest_path),'bundle_sha256':manifest['bundle']['sha256']}
