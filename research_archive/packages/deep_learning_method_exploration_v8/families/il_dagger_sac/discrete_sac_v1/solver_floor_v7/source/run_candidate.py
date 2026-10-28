"""V7 一次离线终末 critic 研究入口。无 import 时模型、训练或物理。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import resource
import sys
import time
import traceback

DEADLINE = 1793114740.0
ACTIVATION = 'deep_learning_method_exploration_v8_20261027T032540Z'
METHODS = ('EXACT_CRITIC_GAIN1_EMPIRICAL_ROWS','EXACT_CRITIC_GAIN20_EMPIRICAL_ROWS','EXACT_CRITIC_GAIN1_CASE_ACTION_BALANCED')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def module(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def bindings(package, approval_path):
    P=Path(package).resolve(); ap=(P/approval_path).resolve()
    assert ap.is_relative_to(P/'families/il_dagger_sac/discrete_sac_v1/solver_floor_v7')
    approval=load(ap)
    assert approval['status']=='APPROVED_BY_MAIN_AGENT_FOR_REAL_EXACT_TERMINAL_CRITIC_FIT'
    cp=P/approval['contract_path'];assert sha(cp)==approval['contract_sha256'];contract=load(cp)
    assert contract['status']=='FINAL_FROZEN_PENDING_MAIN_APPROVAL' and contract['activation']==ACTIVATION
    activation=load(P/'ACTIVATION.json')
    assert activation['activation_id']==ACTIVATION and activation['hard_stop_unix']==DEADLINE
    assert contract['global_deadline_unix']==DEADLINE and time.time()<DEADLINE
    assert contract['primary']=='EXACT_CRITIC_GAIN1_EMPIRICAL_ROWS_QGREEDY'
    assert sha(Path(sys.executable).resolve())==contract['interpreter']['binary_sha256']==approval['python_binary_sha256']
    assert sys.version_info[:3]==(3,12,3)
    mp=P/contract['source_manifest_path'];assert sha(mp)==contract['source_manifest_sha256'];manifest=load(mp)
    for rel,h in manifest['required_source_sha256'].items(): assert sha(P/rel)==h,'SOURCE_CHANGED:'+rel
    for key in ('dataset','dataset_manifest','old_bundle','old_predictions','proposal','existing_loss_audit'):
        item=contract['inputs'][key];assert sha(P/item['path'])==item['sha256'],'INPUT_CHANGED:'+key
    assert approval['dataset_file_sha256']==contract['inputs']['dataset']['sha256']
    return P,approval,contract


def evaluate(index, rows):
    matches=[r for r in rows if r['action_index']==index] if index is not None else []
    if not matches: return {'status':'UNKNOWN_MISSING_ACTION_LABEL' if index is not None else 'ABSTAIN','samples':0,'original_qualification':None,'reward':None}
    mean=lambda f:sum(f(r) for r in matches)/len(matches)
    return {'status':'OBSERVED_DEVELOPMENT_TABLE','samples':len(matches),
            'original_qualification':all(r['original_qualified'] for r in matches),
            'canonical_gain1_return':mean(lambda r:r['canonical_terminal_return']),
            'JF':mean(lambda r:r['JF_N_s']),'JM':mean(lambda r:r['JM_Nm_s']),
            'delta_JF':mean(lambda r:r['JF_N_s']-r['baseline']['JF_N_s']),
            'delta_JM':mean(lambda r:r['JM_Nm_s']-r['baseline']['JM_Nm_s']),
            'actual_original_qualified_and_JM_nonincreasing':all(r['original_qualified'] and r['JM_Nm_s']<=r['baseline']['JM_Nm_s']+1e-12 for r in matches),
            'not_independent_contexts':len(matches)>1}


def run(package, approval_path):
    P,approval,contract=bindings(package,approval_path)
    data=load(P/contract['inputs']['dataset']['path']);dm=load(P/contract['inputs']['dataset_manifest']['path'])
    assert digest(data)==dm['dataset_canonical_sha256'] and data['source_manifest_sha256']==contract['build_source_manifest_sha256']
    assert data['new_fit_or_forward']==0 and data['new_physics']==0 and data['sealed_reads']==0
    rows=data['cohorts']['AGGREGATE64'];cases=sorted({r['split_case_sha256_evaluation_only'] for r in rows})
    assert len(rows)==64 and len(cases)==12 and len({r['attempt_id'] for r in rows})==64
    assert len({(r['split_case_sha256_evaluation_only'],r['action_index']) for r in rows})==52
    old_bundle=load(P/contract['inputs']['old_bundle']['path']);old_records=load(P/contract['inputs']['old_predictions']['path'])['rows']
    saved=old_bundle['models']['AGGREGATE64/VANILLA_FIXED_ENTROPY'];reference=saved['model']
    assert digest(reference)==saved['snapshot_sha256'] and old_bundle['dataset_sha256']==contract['inputs']['dataset']['sha256']
    assert reference['configuration']['linear_weight_decay']==.001 and reference['configuration']['support_radius_RMS']==1.
    assert reference['configuration']['terminal_only'] is True and reference['mechanism']=='VANILLA_FIXED_ENTROPY'
    assert reference['actor']['feature_names']==data['feature_names'] and reference['actor']['action_contracts']==data['action_contracts']
    assert reference['actor']['action_sha256']==data['full_recipe_sha256']
    for row in rows:
        assert row['done'] is True and row['next_state'] is None and row['qa_validated'] is True
        assert row['feature_names']==data['feature_names'] and row['complete'] is True
        assert row['original_evidence']['hard_safety'] is False and row['original_evidence']['ownership_PASS'] is True
        assert digest(row['full_recipe'])==row['full_recipe_sha256']==data['full_recipe_sha256'][row['action_index']]
    old={}
    for item in old_records:
        if item['cohort']=='AGGREGATE64' and item.get('mechanism')=='VANILLA_FIXED_ENTROPY' and item['selector']=='ACTOR_ARGMAX':
            key=(item['fold'],item['case_sha256_evaluation_only']);assert key not in old;old[key]=item['prediction']
    assert len(old)==24
    out=P/contract['output_directory']
    assert out.is_relative_to(P/'families/il_dagger_sac/discrete_sac_v1/solver_floor_v7') and not out.exists(),'NO_OVERWRITE_NO_AUTOMATIC_RETRY'
    out.mkdir(parents=True)
    begin=time.time();initial=resource.getrusage(resource.RUSAGE_SELF)
    counters={'solve_attempts':0,'solve_completed':0,'scalar_rhs_attempts':0,'training_matrix_prediction_calls':0,
              'training_scalar_output_columns':0,'normal_equation_residual_products':0,'state_API_attempts':0,
              'state_API_completed':0,'state_Q_dot_calls':0,'actor_steps':0,'temperature_steps':0,
              'old_model_new_forward':0,'new_control_fits_or_API':0,'new_physics':0}
    error=None;diagnostics=[];predictions=[];models={};comparisons=[]
    save(out/'OWNER_START.json',{'initial_wall_unix':begin,'initial_CPU_user_s':initial.ru_utime,'initial_CPU_system_s':initial.ru_stime,
                               'initial_RSS_KiB':initial.ru_maxrss,'PID':os.getpid(),'approval_path':approval_path,
                               'approval_sha256':sha(P/approval_path),'contract_sha256':approval['contract_sha256']})
    try:
        def bounded(): assert time.time()<min(begin+60.,DEADLINE),'LOCAL_60S_OR_ORIGINAL_HARD_STOP'
        api=module(P/contract['api_path'],'_exact_terminal_critic_v7_api')
        fitter=module(P/contract['fit_source_path'],'_exact_terminal_critic_v7_fit')
        full_old={case:old[('ALL_DEVELOPMENT',case)] for case in cases}
        old_full_objectives=fitter.archived_objectives(rows,full_old,reference)
        for fold,holdout in [('ALL_DEVELOPMENT',None)]+[(c,c) for c in cases]:
            bounded();train=[r for r in rows if r['split_case_sha256_evaluation_only']!=holdout]
            test_cases=cases if holdout is None else [holdout]
            fitted,stats=fitter.fit_three(train,reference,approved_contract_sha256=approval['contract_sha256'],
                                          source_manifest_sha256=contract['source_manifest_sha256'],counters=counters,bounded=bounded)
            diagnostics.extend(dict(s,fold=fold) for s in stats)
            if holdout is None:
                models={name:api.snapshot(model) for name,model in fitted.items()}
                baseline=[x for x in old_full_objectives if x['gain']==1 and x['weighting']=='EMPIRICAL_ROWS']
                new=next(s['regularized_train_objective_own_target'] for s in stats if s['mechanism']==METHODS[0])
                assert all(new<=b['regularized_full_objective_from_archived_predictions']+1e-9 for b in baseline),'EXACT_GAIN1_OBJECTIVE_WORSE_THAN_ARCHIVED_SGD'
            for case in test_cases:
                bounded();held=[r for r in rows if r['split_case_sha256_evaluation_only']==case]
                features=held[0]['features'];assert all(r['features']==features for r in held)
                archived=old[(fold,case)]
                for name in METHODS:
                    counters['state_API_attempts']+=1
                    pred=api.predict(fitted[name],data['feature_names'],features,qa_validated=True)
                    counters['state_API_completed']+=1;counters['state_Q_dot_calls']+=5
                    predictions.append({'cohort':'AGGREGATE64','fold':fold,'case_sha256_evaluation_only':case,'mechanism':name,
                                        'prediction':pred,'actual_development':evaluate(pred['action_index'],held)})
                    errors=[(pred['Q_terminal_return'][r['action_index']]-r['canonical_terminal_return'])**2 for r in held]
                    old1=[(archived['Q1_terminal_return'][r['action_index']]-r['canonical_terminal_return'])**2 for r in held]
                    old2=[(archived['Q2_terminal_return'][r['action_index']]-r['canonical_terminal_return'])**2 for r in held]
                    cells=[]
                    for action in sorted({r['action_index'] for r in held}):
                        cell=[r for r in held if r['action_index']==action]
                        cells.append({'action_index':action,'actual_samples':len(cell),'qualified':all(r['original_qualified'] for r in cell),
                                      'gain1_targets':[r['canonical_terminal_return'] for r in cell],
                                      'new_Q':pred['Q_terminal_return'][action],
                                      'old_archived_Q1':archived['Q1_terminal_return'][action],'old_archived_Q2':archived['Q2_terminal_return'][action]})
                    comparisons.append({'fold':fold,'case_sha256_evaluation_only':case,'mechanism':name,
                                        'empirical_gain1_data_MSE':sum(errors)/len(errors),
                                        'old_archived_Q1_empirical_gain1_data_MSE':sum(old1)/len(old1),
                                        'old_archived_Q2_empirical_gain1_data_MSE':sum(old2)/len(old2),
                                        'observed_cells':cells,'old_fold_train_regularized_objective':'NOT_AVAILABLE_NOT_ARCHIVED',
                                        'old_forward_calls':0})
        assert counters['solve_attempts']==counters['solve_completed']==26 and counters['scalar_rhs_attempts']==39
        assert counters['training_matrix_prediction_calls']==26 and counters['normal_equation_residual_products']==26
        assert counters['training_scalar_output_columns']==39 and counters['state_API_completed']==counters['state_API_attempts']==72
        inherited=[r for r in old_records if r['cohort']=='AGGREGATE64' and (r.get('mechanism') is None or r.get('mechanism')=='VANILLA_FIXED_ENTROPY')]
        assert len(inherited)==168
        bounded()
        save(out/'FROZEN_EXACT_CRITIC_BUNDLE_V7.json',{'schema':'v8.exact_terminal_critic_bundle.v7','models':models,
             'primary':contract['primary'],'dataset_sha256':contract['inputs']['dataset']['sha256'],
             'source_manifest_sha256':contract['source_manifest_sha256'],'approved_contract_sha256':approval['contract_sha256'],
             'no_CV_best_selection':True,'BC_norm_prior_preexposed_development_only':True,'new_physics':0})
        save(out/'DEVELOPMENT_CASE_CV_AND_FULL_V7.json',{'rows':predictions,'inherited_V6_rows_reused_no_model_calls':inherited,
             'all_development_only':True,'missing_labels_unknown_not_imputed':True,'new_physics':0})
        save(out/'OBJECTIVE_AND_ARCHIVED_Q_COMPARISON_V7.json',{'new_training_diagnostics':diagnostics,
             'old_full_regularized_objectives_from_archived_Q':old_full_objectives,'same_state_comparisons':comparisons,
             'old_fold_train_weights_missing_no_train_objective_claim':True,'old_step100_logged_loss_was_preupdate':True,
             'V6_sameQ_greedy_softmax_worse_than_actor_remains_prior_evidence':True,'old_model_new_forward':0})
    except BaseException as exc:
        error={'error':str(exc),'traceback':traceback.format_exc()};raise
    finally:
        final=resource.getrusage(resource.RUSAGE_SELF)
        save(out/'RESOURCE_AND_OPERATIONS_V7.json',{'status':'FAILED_NO_RETRY' if error else 'COMPLETED','error':error,
             'initial_wall_unix':begin,'final_wall_unix':time.time(),'wall_s':time.time()-begin,
             'CPU_user_s':final.ru_utime-initial.ru_utime,'CPU_system_s':final.ru_stime-initial.ru_stime,
             'RSS_peak_KiB':final.ru_maxrss,'counters':counters,'completed_train_diagnostics':diagnostics,
             'auto_retry':False,'sealed_or_active_reads':0,'new_physics':0})
