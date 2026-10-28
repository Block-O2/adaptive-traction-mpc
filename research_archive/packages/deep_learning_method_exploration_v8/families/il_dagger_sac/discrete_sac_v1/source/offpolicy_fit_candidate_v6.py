"""SOURCE_ONLY V6: 明确批准后一次执行；无CLI自动训练，无物理。"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import resource
import sys
import time
import traceback

DEADLINE=1793114740.0
MECHANISMS=('VANILLA_FIXED_ENTROPY','ADAPTIVE_TEMPERATURE','CONSERVATIVE_SUPPORT')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def save(path,obj):
    with Path(path).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def run(package,approval_path):
    P=Path(package).resolve();approval=load(P/approval_path)
    assert approval['status']=='APPROVED_BY_MAIN_AGENT_FOR_REAL_OFFLINE_SAC_FIT'
    contract_path=P/approval['contract_path'];assert sha(contract_path)==approval['contract_sha256'];contract=load(contract_path)
    assert contract['status']=='FINAL_FROZEN_PENDING_MAIN_APPROVAL' and contract['activation']=='deep_learning_method_exploration_v8_20261027T032540Z'
    assert contract['global_deadline_unix']==DEADLINE and time.time()<DEADLINE
    assert contract['primary']=={'cohort':'AGGREGATE64','mechanism':'VANILLA_FIXED_ENTROPY','selector':'ACTOR_ARGMAX'}
    source=P/contract['source_manifest_path'];assert sha(source)==contract['source_manifest_sha256'];manifest=load(source)
    for rel,h in manifest['required_source_sha256'].items():assert sha(P/rel)==h,'SOURCE_CHANGED:'+rel
    data_path=P/contract['dataset_path'];data_manifest=P/contract['dataset_manifest_path']
    assert sha(data_path)==contract['dataset_file_sha256']==approval['dataset_file_sha256']
    assert sha(data_manifest)==contract['dataset_manifest_file_sha256'];data=load(data_path);identity=load(data_manifest)
    assert digest(data)==identity['dataset_canonical_sha256'] and data['source_manifest_sha256']==contract['build_source_manifest_sha256']
    assert data['primary_cohort']=='AGGREGATE64' and data['new_physics']==0 and data['sealed_reads']==0
    parent_path=P/contract['bc3_parent_path'];assert sha(parent_path)==contract['bc3_parent_sha256'];parent=load(parent_path)['policy']
    assert len(data['cohorts']['AGGREGATE64'])==64 and len(data['cohorts']['FRESH16'])==16
    assert len({r['split_case_sha256_evaluation_only'] for r in data['cohorts']['AGGREGATE64']})==12
    assert len({r['split_case_sha256_evaluation_only'] for r in data['cohorts']['FRESH16']})==2
    out=P/contract['output_directory'];assert out.is_relative_to(P/'families/il_dagger_sac/discrete_sac_v1') and not out.exists(),'NO_OVERWRITE_OR_AUTOMATIC_RETRY'
    out.mkdir(parents=True)
    begin=time.time();cpu=resource.getrusage(resource.RUSAGE_SELF);counters={'init_attempts':0,'lift_calls':0,'step_attempts':0,'successful_steps':0,'SAC_predict_API_calls':0,'control_fits':0,'control_API_calls':0,'linear_forward_calls':0,'softmax_calls':0,'apply_calls':0,'SAC_snapshots':0}
    save(out/'OWNER_START.json',{'initial_wall_unix':begin,'initial_CPU_user_s':cpu.ru_utime,'initial_CPU_system_s':cpu.ru_stime,'initial_RSS_KiB':cpu.ru_maxrss,'python':sys.version,'python_binary_sha256':sha(Path(sys.executable).resolve()),'approval_path':approval_path,'approval_sha256':sha(P/approval_path),'contract_sha256':approval['contract_sha256'],'new_physics':0})
    predictions=[];fit_ledger=[];frozen={};control_bundles={};error=None
    try:
        resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_CPU,(180,180))
        sac=module(P/contract['sac_source_path'],'_sac_offpolicy_v2_approved');controls=module(P/contract['controls_source_path'],'_sac_controls_v2_approved')
        for key,counter in [('linear','linear_forward_calls'),('softmax','softmax_calls'),('_apply','apply_calls')]:
            original=getattr(sac,key)
            def wrap(*args,_original=original,_counter=counter,**kwargs):
                counters[_counter]+=1;return _original(*args,**kwargs)
            setattr(sac,key,wrap)
        counters['lift_calls']+=1;common=sac.lift_bc_three_to_five(parent,data['action_contracts'],approved_contract_sha256=approval['contract_sha256'])
        assert common['normalization']==parent['normalization']
        def bounded():assert time.time()<min(begin+180.,DEADLINE),'FINITE_WALL_OR_ORIGINAL_HARD_STOP'
        def replay(records,cohort):
            return {'schema':'v8.approved_terminal_sac_offpolicy_manifest.v2','approved_contract_sha256':approval['contract_sha256'],'cohort':cohort,'split':'DEVELOPMENT_ONLY','full_recipe_sha256':data['full_recipe_sha256'],'original_file_builder_verified':True,'dataset_file_sha256':contract['dataset_file_sha256'],'builder_manifest_file_sha256':contract['dataset_manifest_file_sha256'],'records_sha256':{r['attempt_id']:digest(r) for r in records}}
        def evaluate(pred,records):
            ai=pred.get('action_index');matches=[r for r in records if r['action_index']==ai] if ai is not None else []
            if not matches:return {'status':'UNKNOWN_MISSING_ACTION_LABEL' if ai is not None else 'ABSTAIN_NO_SUPPORT','samples':0,'original_qualification':None,'reward':None}
            return {'status':'OBSERVED_DEVELOPMENT_TABLE','samples':len(matches),'original_qualification':all(r['original_qualified'] for r in matches),'reward':sum(r['canonical_terminal_return'] for r in matches)/len(matches),'JF':sum(r['JF_N_s'] for r in matches)/len(matches),'JM':sum(r['JM_Nm_s'] for r in matches)/len(matches),'delta_JF':sum(r['JF_N_s']-r['baseline']['JF_N_s'] for r in matches)/len(matches),'delta_JM':sum(r['JM_Nm_s']-r['baseline']['JM_Nm_s'] for r in matches)/len(matches),'not_independent_contexts':len(matches)>1}
        for cohort in ('AGGREGATE64','FRESH16'):
            rows=data['cohorts'][cohort];cases=sorted({r['split_case_sha256_evaluation_only'] for r in rows})
            folds=[('ALL_DEVELOPMENT',None,contract['full_updates'])]+[(case,case,contract['fold_updates']) for case in cases]
            for fold,holdout,updates in folds:
                bounded();train=[r for r in rows if r['split_case_sha256_evaluation_only']!=holdout];test=[r for r in rows if holdout is None or r['split_case_sha256_evaluation_only']==holdout]
                test_cases=sorted({r['split_case_sha256_evaluation_only'] for r in test});rb=replay(train,cohort)
                counters['control_fits']+=1;cb=controls.fit_controls(train,common['normalization']);control_bundles[cohort+'/'+fold]=cb
                for mechanism in MECHANISMS:
                    attempt={'cohort':cohort,'fold':fold,'mechanism':mechanism,'updates_requested':updates,'completed_steps':0,'train_rows':len(train),'train_cases':len({r['split_case_sha256_evaluation_only'] for r in train}),'losses':[],'final_model_counters':None};fit_ledger.append(attempt)
                    bounded();counters['init_attempts']+=1;model=sac.initialize(copy.deepcopy(common),mechanism=mechanism,seed=contract['initial_Q_seed'],approved_contract_sha256=approval['contract_sha256'],module_source_sha256=sha(P/contract['sac_source_path']))
                    for step_index in range(updates):
                        bounded();counters['step_attempts']+=1;result=sac.step(model,train,rb,approved_contract_sha256=approval['contract_sha256']);counters['successful_steps']+=1
                        attempt['losses'].append({'step':step_index+1,'losses':result['losses'],'alpha':result['alpha_after'],'actor_states':result['actor_states']});attempt['completed_steps']+=1;attempt['final_model_counters']=copy.deepcopy(model['counters'])
                    if holdout is None:
                        counters['SAC_snapshots']+=1;frozen[cohort+'/'+mechanism]=sac.snapshot(model)
                    for case in test_cases:
                        held=[r for r in test if r['split_case_sha256_evaluation_only']==case];features=held[0]['features'];assert all(r['features']==features for r in held)
                        counters['SAC_predict_API_calls']+=1;pred=sac.predict(model,data['feature_names'],features,qa_validated=True)
                        # Qgreedy and softmax(Q/alpha) use this exact same Q; no extra fit.
                        allowed=pred['allowed_from_past_replay_only'];soft=pred['direct_softmax_Q_probabilities'];softchoice=max(allowed,key=lambda i:(soft[i],-i)) if allowed else None
                        for selector,ai in [('ACTOR_ARGMAX',pred['action_index']),('Q_GREEDY_SAME_Q',pred['direct_Q_greedy_index']),('SOFTMAX_Q_SAME_Q',softchoice)]:
                            predictions.append({'cohort':cohort,'fold':fold,'case_sha256_evaluation_only':case,'mechanism':mechanism,'selector':selector,'action_index':ai,'prediction':pred,'actual_development':evaluate({'action_index':ai},held)})
                for case in test_cases:
                    held=[r for r in test if r['split_case_sha256_evaluation_only']==case]
                    for name in ('CONSTANT_B','BEST_FIXED','IF_STUMP','NEAREST'):
                        counters['control_API_calls']+=1;pred=controls.predict_control(cb,held[0]['features'],name)
                        predictions.append({'cohort':cohort,'fold':fold,'case_sha256_evaluation_only':case,'selector':name,'prediction':pred,'actual_development':evaluate(pred,held)})
        assert counters['init_attempts']==48 and counters['successful_steps']==1650 and counters['SAC_predict_API_calls']==84 and counters['control_API_calls']==112
        save(out/'FROZEN_SAC_BUNDLE_V2.json',{'schema':'v8.terminal_offpolicy_sac_frozen_bundle.v2','models':frozen,'controls':{k:v for k,v in control_bundles.items() if k.endswith('/ALL_DEVELOPMENT')},'primary':contract['primary'],'common_actor_parent_sha256':digest(common),'dataset_sha256':contract['dataset_file_sha256'],'source_sha256':sha(P/contract['sac_source_path']),'approved_contract_sha256':approval['contract_sha256'],'no_CV_best_checkpoint_selection':True,'normalization_is_frozen_common_BC_parent_not_new_fold_fit':True,'BC_parent_historical_preexposure_means_LOCO_not_clean_independent_test':True,'new_physics':0,'physical_attempt_savings':0})
        save(out/'DEVELOPMENT_CASE_CV_AND_FULL_V2.json',{'rows':predictions,'all_development_only':True,'missing_labels_not_imputed':True,'first_completed_final_update_not_best':True})
    except BaseException as e:
        error={'error':str(e),'traceback':traceback.format_exc()};raise
    finally:
        final=resource.getrusage(resource.RUSAGE_SELF)
        save(out/'FIT_AND_COMPUTE_AUDIT_V2.json',{'status':'FAILED_NO_RETRY' if error else 'COMPLETED','error':error,'initial_wall_unix':begin,'final_wall_unix':time.time(),'wall_s':time.time()-begin,'CPU_user_s':final.ru_utime-cpu.ru_utime,'CPU_system_s':final.ru_stime-cpu.ru_stime,'peak_RSS_KiB':final.ru_maxrss,'counters':counters,'fits':fit_ledger,'forward_including_failed_attempts_counted_before_execution':True,'automatic_retry':False,'new_physics':0,'sealed_reads':0,'not_fresh_onpolicy_optimization':True})
