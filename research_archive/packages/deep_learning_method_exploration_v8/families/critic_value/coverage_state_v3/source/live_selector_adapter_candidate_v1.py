"""SOURCE_ONLY: A1/A2/A3并列、原OUT0实际source证明；无physics dispatch。

Root调用时会发生冻结模型推理，应逐次计账。当前未调用；不是训练入口。
本文件不修改冻结API。私有namespace只重绑定其局部ImportFrom依赖名。
"""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import json
import sys
import types

MODULE_ROLES = {
    'capture':'v7_causal_context',
    'runtime':'traction_mpc_stage5.full3d_adaptive_integration_v1.runtime_coordination_residual_v2',
    'observer':'traction_mpc_stage5.controller_interface',
    'observation_contract':'traction_mpc_stage5.task_observation',
    'history_guard':'v6_features',
    'runtime_loader':'study_common',
}
ROOT_REL='families/critic_value/coverage_state_v3'
SELECTORS=['A1_ABS25','A2_ABS25','A3_ABS25_PARITY','A3_WRENCH39_PRIMARY',
    'A3_W39_CONSTANT_B','A3_W39_BEST_FIXED','A3_W39_IF_STUMP','A3_W39_NEAREST']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def bounded(package, relative):
    path=(package/relative).resolve()
    assert path.is_relative_to(package.resolve()),'ADAPTER_PATH_ESCAPES_V8'
    return path


def _private_modules(package, files, label):
    """保留API函数body，唯一变换是本地import的私有模块限定名。"""
    identity=digest({k:v['sha256'] for k,v in files.items()})[:20]
    namespace='_v8_'+label+'_'+identity
    if namespace not in sys.modules:
        module=types.ModuleType(namespace);module.__path__=[];sys.modules[namespace]=module
    loaded={};pending=dict(files)
    ordered=[]
    while pending:
        ready=[]
        for name,item in pending.items():
            path=bounded(package,item['path']);assert sha(path)==item['sha256']
            tree=ast.parse(path.read_text(),filename=str(path))
            deps={n.module for n in tree.body if isinstance(n,ast.ImportFrom) and n.level==0 and n.module in files}
            if deps.issubset(set(ordered)):ready.append(name)
        assert ready,'PRIVATE_DEPENDENCY_CYCLE_OR_MISSING_ORDER'
        for name in sorted(ready):ordered.append(name);pending.pop(name)
    for name in ordered:
        item=files[name]
        path=bounded(package,item['path']);assert sha(path)==item['sha256']
        fullname=namespace+'.'+name
        if fullname in sys.modules:
            module=sys.modules[fullname];assert Path(module.__file__).resolve()==path
        else:
            tree=ast.parse(path.read_text(),filename=str(path))
            for node in tree.body:
                if isinstance(node,ast.ImportFrom) and node.level==0 and node.module in files:
                    assert node.module in loaded,'PRIVATE_DEPENDENCY_ORDER'
                    node.module=namespace+'.'+node.module
            spec=importlib.util.spec_from_file_location(fullname,path)
            module=importlib.util.module_from_spec(spec);sys.modules[fullname]=module
            try:exec(compile(ast.fix_missing_locations(tree),str(path),'exec'),module.__dict__)
            except BaseException:
                sys.modules.pop(fullname,None);raise
        loaded[name]=module
    return loaded


def _actual_live_proof(package, config, study, bundle):
    """不收proof字符串；从当前job、原payload和实际loaded module取证。"""
    assert study.child is None and study.fork_done is True and not study.metrics,'ALL_SELECTIONS_REQUIRE_COLD_OUT0_BEFORE_B'
    assert config['fork_phase']=='OUTBOUND' and config['fork_slot']==0
    group=config['group'];config_path=package/'experiments'/(group+'.json')
    assert load(config_path)==config
    manifest_path=package/'jobs'/group/'SOURCE_MANIFEST.json';manifest=load(manifest_path)
    assert manifest['config_sha256']==sha(config_path)
    raw=copy.deepcopy(study.prefork_causal_context)
    payload_path=package/'history'/(group+'_PREFORK_CAUSAL_CONTEXT.json')
    assert load(payload_path)==raw,'NOT_EXACT_ORIGINAL_SAVED_PREFORK_PAYLOAD'
    choices=[(proof,paths) for proof,paths in zip(bundle['input_source_profiles'],bundle['input_source_profile_paths'])
             if paths['callback']=='source/'+config['worker']]
    assert len(choices)==1,'UNREGISTERED_OR_AMBIGUOUS_CALLBACK_SOURCE_PROFILE'
    expected,paths=choices[0];actual={};records={}
    callback_module=sys.modules.get(type(study).__module__)
    assert callback_module is not None
    callback_code=Path(study.decision_boundary.__func__.__code__.co_filename).resolve()
    for role, relative in paths.items():
        path=bounded(package,relative);actual_hash=sha(path)
        assert manifest['files'].get(relative)==actual_hash==expected[role],'ACTUAL_JOB_SOURCE_NOT_FROZEN_PROFILE:'+role
        module=callback_module if role=='callback' else sys.modules.get(MODULE_ROLES[role])
        assert module is not None and getattr(module,'__file__',None),'LIVE_MODULE_MISSING:'+role
        actual_loaded=Path(module.__file__).resolve()
        assert actual_loaded==path and sha(actual_loaded)==actual_hash,'LOADED_MODULE_PATH_NOT_JOB_SOURCE:'+role
        if role=='callback':assert callback_code==path,'ACTUAL_BOUND_CALLBACK_CODE_FILE'
        actual[role]=actual_hash;records[role]={'path':relative,'actual_file_sha256':actual_hash,'job_manifest_file_sha256':manifest['files'][relative],
            'actual_loaded_module_file':str(actual_loaded),'expected_profile_sha256':expected[role]}
    return raw,actual,{'job_source_manifest_sha256':sha(manifest_path),'config_sha256':sha(config_path),
        'prefork_payload_file_sha256':sha(payload_path),'prefork_payload_checksum':raw['causal_payload_sha256'],
        'roles':records,'current_task_B_or_candidate_result_used':False,'actual_in_memory_callback_code_checked':True}


def _menu_matches(package,config,menu):
    assert [m['tag'] for m in menu]==['B','LATE_H150','EARLY_H150','LATE_PHASE','EARLY_PHASE']
    assert len({m['recipe_sha256'] for m in menu})==5
    for item in menu:
        recipe=item['action_recipe'];action=item['action']
        assert recipe['action']==action and digest(recipe)==item['recipe_sha256']
        candidate=copy.deepcopy(config['B'] if action['family']=='B' else config['H150'])
        candidate.update(copy.deepcopy(action.get('candidate_overrides',{})));candidate.pop('id',None)
        assert candidate==recipe['resolved_base_candidate'],'LIVE_RESOLVED_BASE_CANDIDATE'
        assert sha(package/'runtime/FROZEN_18D.json')==recipe['frozen_18d_sha256']
        for relative,expected in recipe['planner_source_sha256'].items():assert sha(bounded(package,relative))==expected
    if config.get('actions'):
        assert [r['tag'] for r in config['actions'][:5]]==[m['tag'] for m in menu]
        assert all(r['action']==m['action'] for r,m in zip(config['actions'][:5],menu))


def _with_fallback(prediction, menu):
    choice=prediction.get('choice_recipe_sha256')
    item=next(m for m in menu if m['recipe_sha256']==choice) if choice else next(m for m in menu if m['tag']=='B')
    if choice:assert prediction['choice_action']==item['action']
    return {'choice_tag':item['tag'],'choice_recipe_sha256':item['recipe_sha256'],'choice_action':copy.deepcopy(item['action']),
        'fallback_B_after_predictive_abstain':choice is None,'prediction':prediction,'original_qualification_granted':False}


def predict_before_B(package, config, study):
    """Root在任何B结果前调用一次并存完整返回值；本函数不写/派发。"""
    package=Path(package).resolve();manifest_path=package/ROOT_REL/'LIVE_SELECTOR_ADAPTER_MANIFEST_V1.json'
    contract=load(manifest_path)
    assert sha(Path(__file__))==contract['adapter_sha256']
    assert contract['selectors']==SELECTORS and contract['primary']=='A3_WRENCH39_PRIMARY'
    bundles={}
    for family,item in contract['bundles'].items():
        path=bounded(package,item['path']);assert sha(path)==item['sha256'];bundles[family]=load(path)
    menu=bundles['A3']['menu'];assert all(b['menu']==menu for b in bundles.values())
    _menu_matches(package,config,menu)
    raw,proof,proof_audit=_actual_live_proof(package,config,study,bundles['A3'])
    apis={family:_private_modules(package,files,family) for family,files in contract['api_files'].items()}
    predictions={
        'A1_ABS25':apis['A1']['value_api'].predict(bundles['A1'],raw,'ABS_25','JF_QUALIFIED'),
        'A2_ABS25':apis['A2']['predict_api'].predict(bundles['A2'],raw,'ABS_25','JF_QUALIFIED','ON','MERGED'),
        'A3_ABS25_PARITY':apis['A3']['predict_api'].predict(bundles['A3'],raw,'ABS_25','JF_QUALIFIED','ON','MERGED',source_proof=proof),
        'A3_WRENCH39_PRIMARY':apis['A3']['predict_api'].predict(bundles['A3'],raw,'ABS_WRENCH39','JF_QUALIFIED','ON','MERGED',source_proof=proof),
    }
    for name,control in [('A3_W39_CONSTANT_B','CONSTANT_B'),('A3_W39_BEST_FIXED','BEST_FIXED'),('A3_W39_IF_STUMP','IF_STUMP'),('A3_W39_NEAREST','NEAREST')]:
        predictions[name]=apis['A3']['predict_api'].predict_control(bundles['A3'],raw,control,'JF_QUALIFIED','MERGED',representation='WRENCH39',source_proof=proof)
    assert list(predictions)==SELECTORS
    decisions={name:_with_fallback(pred,menu) for name,pred in predictions.items()}
    return {'schema':'v8.a3.frozen_live_parallel_selectors.v1','decisions':decisions,'actual_source_proof':proof,'proof_audit':proof_audit,
        'all_predictions_before_any_B_result':not study.metrics,'inference_API_calls':8,'new_fit_or_physics':0,
        'same_selected_recipe_sharing_is_not_independent_replication_or_savings':True,'primary':'A3_WRENCH39_PRIMARY',
        'A2_A3_25_same_permission_parity_control_not_independent_method_gain':True,
        'adapter_sha256':contract['adapter_sha256'],'adapter_manifest_sha256':sha(manifest_path),
        'loader_strategy':'private namespace; local import dependency names rebound, frozen API bodies unchanged'}
