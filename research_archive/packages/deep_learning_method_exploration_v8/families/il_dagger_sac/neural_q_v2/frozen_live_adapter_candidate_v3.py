"""SOURCE_ONLY root generic extension：actual7role proof，当前0calls。"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys

ROOT='families/il_dagger_sac/neural_q_v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def doc(P,item):
    q=(P/item['path']).resolve();assert q.is_relative_to(P) and sha(q)==item['sha256'];return load(q)
def source(P,item,label):
    q=(P/item['path']).resolve();assert q.is_relative_to(P) and sha(q)==item['sha256']
    spec=importlib.util.spec_from_file_location(label,q);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);assert Path(m.__file__).resolve()==q;return m


def _predict_before_B(package,config,study,accounting):
    P=Path(package).resolve();mp=P/ROOT/'FROZEN_LIVE_SOURCE_MANIFEST_V3.json';manifest=load(mp)
    assert sha(__file__)==manifest['adapter_sha256']
    auth_item=config['comparative_validation']['neuralq_readonly_authorization'];auth=doc(P,auth_item)
    assert auth['scope']=='READ_ONLY_FROZEN_OUT0' and config['group'] in auth['authorized_groups']
    assert sha(Path(sys.executable).resolve())==auth['expected_binary_sha256']
    assert auth['source_manifest_sha256']==sha(mp) and auth['bundle_file_sha256']==manifest['bundle']['sha256']
    contract=doc(P,auth['readonly_contract'])
    assert contract['source_manifest_sha256']==sha(mp) and contract['bundle_file_sha256']==manifest['bundle']['sha256']
    document=doc(P,manifest['bundle']);a3=doc(P,manifest['proof_bundle'])
    proof_adapter=source(P,manifest['proof_adapter'],'_nq_actual_7role_proof')
    proof_adapter._menu_matches(P,config,a3['menu'])
    raw,proof,proof_audit=proof_adapter._actual_live_proof(P,config,study,a3)
    accounting['successful_frozen_proof_menu_logical_deepcopies']=11
    assert document['bundle']['action_contracts']==[m['action_recipe'] for m in a3['menu']]
    converter=source(P,manifest['converter'],'_nq_scoped_commission25');context=converter.to_context25(raw)
    api=source(P,manifest['api'],'_nq_readonly_fixed_api')
    restored=api.restore_fixed(document,authority=auth,expected_bundle_object_sha256=manifest['bundle_object_sha256'],expected_source_manifest_sha256=sha(mp),accounting=accounting)
    result=api.predict_fixed(restored,context['feature_names'],context['features'],qa_validated=True,authority=auth,accounting=accounting)
    decisions={}
    for label,pred in result['decisions'].items():
        item=a3['menu'][pred['action_index']]
        accounting['action_deepcopy_entry']=accounting.get('action_deepcopy_entry',0)+1
        decisions[label]={'choice_tag':item['tag'],'choice_recipe_sha256':item['recipe_sha256'],'choice_action':copy.deepcopy(item['action']),
                          'prediction_abstained':pred['prediction_abstained'],'execution_fallback_B_predeclared':pred['execution_fallback_B_predeclared'],
                          'original_qualification_granted':False,'detail':pred}
        accounting['action_deepcopy_completed']=accounting.get('action_deepcopy_completed',0)+1
    assert len(decisions)==68 and list(decisions)==manifest['selectors'] and not study.metrics and study.child is None and study.fork_done is True
    return {'schema':'v8.neuralq.pre_B_frozen_readonly_decisions.v3','decisions':decisions,'primary_labels':result['primary_labels'],
            'actual_source_proof':proof,'proof_audit':proof_audit,'all_model_values':result['all_head_values'],
            'API_calls':{'top_wrapper':1,'batch_restore':1,'logical_model_restore':63,'batch_predict':1,'head_or_ridge_forward':63,
                         'logical_model_deepcopies':63,'action_deepcopies':68,'inherited_proof_menu_deepcopies':11,
                         'parameter_array_constructions':195,'normalization_arrays':2},'forward_details':result['forward_counts'],
            'all_choices_before_any_B_result':True,'raw77_still_invalid':True,'same5physicalmenu_not68independentrollouts_or_savings':True,
            'training_authorization_not_used_or_extended':True,'readonly_authorization_sha256':auth_item['sha256'],
            'new_fit_initialize_physics':0,'adapter_manifest_sha256':sha(mp),'actual_nested_accounting':accounting}


def predict_before_B(package,config,study):
    accounting={'top_wrapper_entry':1}
    try:
        result=_predict_before_B(package,config,study,accounting)
        accounting['top_wrapper_completed']=1
        return result
    except BaseException as error:
        accounting['top_wrapper_failed']=1
        accounting['uncompleted_suboperation_work']='UNKNOWN_BOUNDED_NOT_ZERO; perAPI entry/completed counters retained'
        # Generic composer preserves str(error), so the paid prefix survives
        # even when no full extension result can be returned.
        raise RuntimeError('NEURALQ_READONLY_PAID_PREFIX:'+json.dumps(accounting,sort_keys=True)+'; cause='+repr(error)) from error
