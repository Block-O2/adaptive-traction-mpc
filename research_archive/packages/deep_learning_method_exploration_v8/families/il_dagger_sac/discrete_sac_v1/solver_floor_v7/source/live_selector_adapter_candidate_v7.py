"""SOURCE_ONLY V7 extension：真实7role OUT0证明→冻结exact critic，当前0调用。"""
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT_REL='families/il_dagger_sac/discrete_sac_v1/solver_floor_v7'
PRIMARY='SACV7_EXACT_GAIN1_QGREEDY'
SELECTORS=['SACV7_EXACT_GAIN1_QGREEDY','SACV7_EXACT_GAIN20_QGREEDY','SACV7_EXACT_BALANCED_QGREEDY',
           'SACV7_EXACT_GAIN1_SOFTQ','SACV7_CONTROL_B','SACV7_CONTROL_BEST_FIXED','SACV7_CONTROL_IF_STUMP','SACV7_CONTROL_NEAREST']
METHODS=['EXACT_CRITIC_GAIN1_EMPIRICAL_ROWS','EXACT_CRITIC_GAIN20_EMPIRICAL_ROWS','EXACT_CRITIC_GAIN1_CASE_ACTION_BALANCED']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def document(P,item):
    path=(P/item['path']).resolve();assert path.is_relative_to(P) and sha(path)==item['sha256'];return load(path)
def source(P,item,label):
    path=(P/item['path']).resolve();assert path.is_relative_to(P) and sha(path)==item['sha256']
    spec=importlib.util.spec_from_file_location(label,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def predict_before_B(package,config,study):
    P=Path(package).resolve();mp=P/ROOT_REL/'LIVE_ADAPTER_MANIFEST_V7.json';manifest=load(mp)
    assert sha(__file__)==manifest['adapter_sha256'] and manifest['selectors']==SELECTORS and manifest['primary']==PRIMARY
    bundle=document(P,manifest['bundle']);a3=document(P,manifest['proof_bundle']);v6=document(P,manifest['controls_bundle'])
    assert bundle['primary']=='EXACT_CRITIC_GAIN1_EMPIRICAL_ROWS_QGREEDY'
    assert bundle['approved_contract_sha256']==manifest['fit_contract_sha256']
    source_manifest=document(P,manifest['fit_source_manifest'])
    assert bundle['source_manifest_sha256']==manifest['fit_source_manifest']['sha256']
    for rel,h in source_manifest['required_source_sha256'].items():assert sha(P/rel)==h,'FROZEN_FIT_DEPENDENCY_CHANGED:'+rel
    proof_adapter=source(P,manifest['actual_proof_adapter'],'_sacv7_actual_source_proof')
    proof_adapter._menu_matches(P,config,a3['menu'])
    raw,proof,proof_audit=proof_adapter._actual_live_proof(P,config,study,a3)
    converter=source(P,manifest['converter'],'_sacv7_context25_converter');context=converter.to_context25(raw)
    api=source(P,manifest['api'],'_sacv7_exact_critic_api');controls=source(P,manifest['controls'],'_sacv7_existing_control_api')
    recipes=[item['action_recipe'] for item in a3['menu']];hashes=[item['recipe_sha256'] for item in a3['menu']]
    predictions={}
    for name in METHODS:
        model=api.restore(bundle['models'][name],expected_source_sha256=manifest['fit_source_manifest']['sha256'],
                          expected_contract_sha256=manifest['fit_contract_sha256'],expected_recipe_sha256=hashes)
        assert model['action_contracts']==recipes
        predictions[name]=api.predict(model,context['feature_names'],context['features'],qa_validated=True)
    decisions={}
    def add(label,index,detail):
        abstained=index is None;index=0 if abstained else index;assert type(index) is int and index in range(5)
        item=a3['menu'][index]
        decisions[label]={'choice_tag':item['tag'],'choice_recipe_sha256':item['recipe_sha256'],'choice_action':item['action'],
                          'prediction_abstained':abstained,'execution_fallback_B_predeclared':abstained,
                          'original_qualification_granted':False,'detail':detail}
    for label,name in zip(SELECTORS[:3],METHODS):add(label,predictions[name]['action_index'],predictions[name])
    pred=predictions[METHODS[0]];add('SACV7_EXACT_GAIN1_SOFTQ',pred['same_Q_softmax_index'],pred)
    cb=v6['controls']['AGGREGATE64/ALL_DEVELOPMENT']
    for label,name in zip(SELECTORS[4:],['CONSTANT_B','BEST_FIXED','IF_STUMP','NEAREST']):
        cp=controls.predict_control(cb,context['features'],name);add(label,cp['action_index'],cp)
    assert list(decisions)==SELECTORS and study.child is None and study.fork_done is True and not study.metrics
    return {'schema':'v8.sacv7.exact_terminal_live_decisions.v7','decisions':decisions,'primary':PRIMARY,
            'actual_source_proof':proof,'proof_audit':proof_audit,'input_subset25_original_raw77_still_invalid':True,
            'API_calls':{'model_predict':3,'restore':3,'control_predict':4,'new_fit_initialize':0},
            'all_choices_before_any_B_result':True,'sameQ_reuse_not_independent_rollout_or_physics_savings':True,
            'support_permission':'all5 sameV6vanilla; current labels never mask','new_physics':0,
            'bundle_sha256':manifest['bundle']['sha256'],'adapter_sha256':manifest['adapter_sha256'],'manifest_sha256':sha(mp)}
