"""Freeze every contextual decision before outcomes; serial unique recipe execution."""
from pathlib import Path
import os,sys,json,time,hashlib,copy
P=Path(os.environ['ACL2_PACKAGE'])
sys.path.insert(0,str(P/'families/critic_value/source'))
sys.path.insert(0,str(P/'families/ppo_reward'))
from value_api import predict,to_context25
from controls_api import predict_control
from categorical_policy import select_out0
from acl2_shared import put,sha

def sequence(study,config):
    assert not study.metrics, 'SELECTION_MUST_PRECEDE_ANY_RESULT'
    for rel,digest in config['frozen_artifacts'].items():
        assert sha(P/rel)==digest,'FROZEN_ARTIFACT_CHANGED:'+rel
    bundle=json.loads((P/config['value_bundle']).read_text())
    controls=json.loads((P/config['simple_control_bundle']).read_text())
    ctx=to_context25(study.prefork_causal_context)
    menu=bundle['menu'];by_hash={m['recipe_sha256']:m for m in menu}
    decisions={}
    for method in bundle['methods']:
        for objective in ['JF_QUALIFIED','STRICT_JM']:
            decisions['A_'+method+'_'+objective]=predict(bundle,ctx,method=method,objective=objective)
    for control in ['BEST_FIXED_TRAIN','IF_STUMP_TRAIN','NEAREST_CONTEXT']:
        decisions[control]=predict_control(controls,ctx,control=control)
    for label,relative in config['policy_checkpoints'].items():
        policy=json.loads((P/relative).read_text())['policy']
        result=select_out0(policy,ctx['feature_names'],ctx['features'],qa_validated=True)
        h=result['full_recipe_sha256'];assert h in by_hash,'POLICY_RECIPE_NOT_IN_FROZEN_MENU'
        decisions[label]={**result,'choice_tag':by_hash[h]['tag'],'choice_recipe_sha256':h}
    # Bind exact frozen top-level proposal, resolved base candidate and planner hashes.
    for item in menu:
        recipe=copy.deepcopy(item['action_recipe'])
        candidate=copy.deepcopy(config['B'] if item['action']['family']=='B' else config['H150'])
        candidate.update(copy.deepcopy(item['action'].get('candidate_overrides',{})))
        candidate.pop('id',None)
        assert candidate==recipe['resolved_base_candidate'],'BASE_CANDIDATE_IDENTITY'
        assert sha(P/'runtime/FROZEN_18D.json')==recipe['frozen_18d_sha256']
        for rel,digest in recipe['planner_source_sha256'].items():assert sha(P/rel)==digest
        assert hashlib.sha256(json.dumps(recipe,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()==item['recipe_sha256']
    record={'created_unix':time.time(),'context25':ctx,'context_capture_sha256':study.prefork_causal_context['causal_payload_sha256'],'decisions':decisions,'before_any_candidate_outcome':True,'new_training':False,'selection_semantics':'Frozen policies select actual full recipe; same chosen recipe shares one actual matched execution, not multiple independent rollouts','value_primary':'A_ABS_25_JF_QUALIFIED','policy_primary':'B_PPO_RAW','traditional_fixed_controls':[m['tag'] for m in menu]}
    put('predictions/'+config['group']+'_FROZEN_CONTEXT_DECISIONS.json',record)
    selected={m['tag']:[] for m in menu}
    for label,d in decisions.items():
        tag=d.get('choice_tag')
        if tag is None:
            tag='B';d['actual_abstention_route']='B'
        assert tag in selected
        selected[tag].append(label)
    actions={a['tag']:a for a in config['actions']}
    order=['B']+[m['tag'] for m in menu if m['tag']!='B' and selected[m['tag']]]+[m['tag'] for m in menu if m['tag']!='B' and not selected[m['tag']]]
    put('predictions/'+config['group']+'_FROZEN_EXECUTION_PLAN.json',{'created_unix':time.time(),'order':order,'selected_by':selected,'unique_recipe_count':len(order),'case_or_future_result_used_for_selection':False})
    for tag in order:
        a=copy.deepcopy(actions[tag]);a['prediction']={'selected_by':selected[tag],'recipe_sha256':next(m['recipe_sha256'] for m in menu if m['tag']==tag),'all_decisions_frozen_before_B':True}
        yield a
        assert study.last_row['id']==config['group']+'_'+tag,'RESULT_IDENTITY'
        if tag=='B':assert study.last_row['qualified'],'B_ORIGINAL_QUALIFICATION_REQUIRED'
    put('analysis/'+config['group']+'_SELECTOR_EXECUTION_LINK.json',{'decisions':decisions,'rows_by_tag':{r['id'].removeprefix(config['group']+'_'):r['id'] for r in study.metrics},'no_outcome_based_reselection':True,'real_physical_attempts_saved':0,'shared_same_recipe_is_not_independent_replication':True})
