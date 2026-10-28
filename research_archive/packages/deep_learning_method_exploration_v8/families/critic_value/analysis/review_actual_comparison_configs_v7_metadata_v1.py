"""独立config/auth注册核验；仅stdlib，不调用任何candidate/helper/model。"""
from pathlib import Path
import ast,hashlib,json,time

P=Path(__file__).resolve().parents[3];A=Path(__file__).resolve().parent
F='families/ppo_reward/continuous_scale_v1/';checks=[];refs={};opened=[]
expected={'V8FROZENENG02':'0b2c5cb44af40c172fed4da7edcd8454b7f58008f12a15edcb4fa96071471d74','V8VAL03':'1e47772d2c4118c2a1523cb304a7684f2c8437d44941cc049060c4862ad3f6f3','V8VAL04':'736b440db5d98fd71595662ca0f03a0b216d761140ee6e320594925459b673ff'}
def safe(rel):
 assert '/real_runs/' not in rel and '/onpolicy_runs/' not in rel and '/fit_run' not in rel and '/fits/' not in rel and not rel.endswith(('.npz','.gz'))
 assert 'high_rom_v8_val_' not in Path(rel).name
 return P/rel
def sha(rel):
 h=hashlib.sha256(safe(rel).read_bytes()).hexdigest();refs[rel]=h;return h
def load(rel):opened.append(rel);return json.loads(safe(rel).read_text())
def check(name,value):checks.append({'check':name,'PASS':bool(value)})
def getref(ref):check('actual_file_SHA:'+ref['path'],sha(ref['path'])==ref['sha256']);return load(ref['path'])
configs={g:load('experiments/'+g+'.json') for g in expected}
req=load('families/critic_value/analysis/BETA_FROZEN_SCOPE_REQUIRED_CONFIG_PINS_V1.json')['required_existing_pins']
iv=getref(configs['V8FROZENENG02']['beta_mean_extension']['inventory']);rv=getref(iv['root_endpoint_scope_review']);q=getref(iv['quarantine'])
axis=getref(iv['axis'])
ba=getref(configs['V8FROZENENG02']['beta_mean_extension']['deployment_authorization'])
activation=load('ACTIVATION.json');check('activation_global',activation['hard_stop_unix']==1793114740. and activation['clock_must_not_reset'] is True and sha('ACTIVATION.json')==ba['activation_sha256'])
check('beta_auth_v2',ba['schema']=='v8.beta_frozen_mean_deployment_authorization.v2' and ba['status']=='APPROVED_BY_MAIN_READ_ONLY_FROZEN_DEPLOYMENT' and ba['mean_policy_forward_only'] is True and ba['new_training_or_restore_authorized'] is False and ba['physical_dispatch_authority_from_endpoint_review'] is False and ba['authorized_job_groups']==list(expected) and ba['approved_unix']<ba['deployment_deadline_unix']<=1793114740.)
check('scope_quarantine_unknown',rv['whole_training_hard_status']=='UNKNOWN_EXTERNAL_BATCH02_UNRESOLVED' and 'true_hard_safety_violation' not in rv and rv['endpoint_transaction_scope']['true_hard_safety_violation'] is False and rv['endpoint_transaction_scope']['excludes_external_batch02_pending'] is True and q['true_hard_safety_violation'] is None and q['external_pending_proposal_count']==9 and q['disposition']=='KEEP_EXTERNAL_PENDING_NO_CANCEL_NO_COMMIT')
for rel,h in ba['source_files_sha256'].items():
 if rel.endswith('.py'):check('beta_auth_actual_source:'+rel,sha(rel)==h);ast.parse(safe(rel).read_text(),filename=rel)
original55=load(F+'COMPARATIVE_ORIGINAL_55_CORE_LABELS_V1.json')
nqm=load('families/il_dagger_sac/neural_q_v2/FROZEN_LIVE_SOURCE_MANIFEST_V3.json')
a5m=load('families/critic_value/support_qualification_v5/LIVE_ADAPTER_MANIFEST_V1.json')
a5p='freeze/A5_FROZEN_OUT0_MAIN_SOURCE_APPROVAL_V2.json';a5auth=load(a5p)
e2contract='families/learning_assisted/common_out0_v2/FROZEN_LIVE_E2_CONTRACT_V2.json';e2c=load(e2contract)
mainp='freeze/FROZEN_COMPARISON_V4_MAIN_APPROVAL_V2.json';main=load(mainp)
counts={'original55':len(original55['labels']),'NQ':len(nqm['selectors']),'E2':9,'A5':len(a5m['selectors'])}
check('selector153',counts=={'original55':55,'NQ':68,'E2':9,'A5':21} and sum(counts.values())==153 and len(set(original55['labels']))==55 and len(set(nqm['selectors']))==68 and len(set(a5m['selectors']))==21 and e2c['approval_operation']=='FOUR_COST_PREDICTIONS_ONE_A3_RISK_NINE_SELECTORS')
check('main_counts_and_permissions',main['core_pre_B_decisions']==153 and main['fixed_original_core_subset']==55 and main['new_NeuralQ_decisions']==68 and main['new_E2_decisions']==9 and main['new_A5_decisions']==21 and main['Beta_mean_forwards']==12 and main['fixed_axis_maps']==5 and main['C_after_B_decisions']==5 and main['training']==0 and main['true_or_unknown_hard_safety_stops_all'] is True)
check('A5_readonly_auth',a5auth['schema']=='v8.a5.root_actual_out0_source_approval.v1' and a5auth['status']=='APPROVED_FROZEN_READONLY_OUT0_FOR_CONCRETE_JOBS' and a5auth['authorized_groups']==list(expected) and a5auth['training_authorized'] is False and a5auth['physics_authorized'] is False and a5auth['adapter_sha256']==a5m['adapter_sha256'] and a5auth['adapter_manifest_sha256']==sha('families/critic_value/support_qualification_v5/LIVE_ADAPTER_MANIFEST_V1.json'))
routes=load('freeze/ONPOLICY_V1_CASE_ROUTES.json');registrations=[]
for g,c in configs.items():
 f=c['frozen_artifacts'];cv=c['comparative_validation'];cp=c['comparative_composer_v4'];bp=c['beta_mean_extension']
 check(g+'.actual_config_SHA',sha('experiments/'+g+'.json')==expected[g]);check(g+'.192pins',len(f)==192)
 check(g+'.group_worker_identity',c['group']==c['condition']['name']==g and c['worker']=='v8_worker_v2.py' and c['algorithm']=='v8_comparative_validation_v7' and c['fork_phase']=='OUTBOUND' and c['fork_slot']==0)
 check(g+'.no_training_no_reselection',cv['status']==cp['status']=='APPROVED_BY_MAIN_AGENT' and all(cv[k] is True and cp[k] is True for k in ['no_training','no_outcome_reselection']) and cp['expected_core_pre_B_decision_count']==153 and cp['root_postclosure_raw_and_scorer_review_required'] is True)
 for rel,h in req.items():check(g+'.required49:'+rel,f.get(rel)==h)
 for rel,h in axis['source_files_sha256'].items():check(g+'.axis_source_pin:'+rel,f.get(rel)==h)
 for rel,h in ba['source_files_sha256'].items():check(g+'.beta_auth_source_pin:'+rel,f.get(rel)==h)
 for ref in [bp['inventory'],bp['deployment_authorization'],iv['root_endpoint_scope_review'],iv['quarantine'],rv['frozen_committed_pointer_snapshot'],q['all_owner_closure_review'],q['original_prefix_review']]:check(g+'.direct_metadata_pin:'+ref['path'],f.get(ref['path'])==ref['sha256'])
 for rel,h in rv['metadata_evidence_files_sha256'].items():check(g+'.closed_scope_evidence_pin:'+rel,f.get(rel)==h)
 for rel,h in main['dependencies_before_this_approval'].items():check(g+'.main_preapproval_pin:'+rel,f.get(rel)==h)
 check(g+'.beta_ref_and_schema',bp['schema']=='v8.beta_frozen_mean_extension_job.v2' and bp['inventory']==ba['inventory'] and bp['deployment_authorization']==configs['V8FROZENENG02']['beta_mean_extension']['deployment_authorization'])
 check(g+'.six_adapters_order',[x['label'] for x in cv['parallel_selector_adapters']]==['A4','SAC_V6','SAC_V7','NEURAL_Q_V3','E2_V2_SCHEMA_FIX','A5_V1'])
 for item in cv['parallel_selector_adapters']:check(g+'.adapter_actual_source_pin:'+item['label'],f.get(item['path'])==sha(item['path']))
 for rel,h in a5auth['required_frozen_artifacts'].items():check(g+'.A5_auth_dependency_pin:'+rel,f.get(rel)==h)
 check(g+'.A5_source_approval_pin',f.get(a5p)==sha(a5p))
 nr=cv['neuralq_readonly_authorization'];na=getref(nr);nc=getref(na['readonly_contract'])
 check(g+'.NQ_auth_ref_frozen',f.get(nr['path'])==nr['sha256'] and f.get(na['readonly_contract']['path'])==na['readonly_contract']['sha256'])
 check(g+'.NQ_readonly_auth',na['schema']=='v8.neuralq.readonly_fixed_models_authorization.v3' and na['status']=='APPROVED_BY_MAIN_AGENT_FOR_NEURALQ_READ_ONLY_FIXED_MODELS_V3' and na['scope']=='READ_ONLY_FROZEN_OUT0' and g in na['authorized_groups'] and na['training_or_physics_authorized'] is False and na['approved_unix']<na['expires_unix']<=1793114740.)
 check(g+'.NQ_manifest_bundle_identity',na['source_manifest_sha256']==sha('families/il_dagger_sac/neural_q_v2/FROZEN_LIVE_SOURCE_MANIFEST_V3.json')==nc['source_manifest_sha256'] and na['bundle_file_sha256']==nqm['bundle']['sha256']==nc['bundle_file_sha256'] and f.get(nqm['bundle']['path'])==nqm['bundle']['sha256'] and na['bundle_object_sha256']==nqm['bundle_object_sha256'])
 er=cv['e2_readonly_authorization'];ea=getref(er)
 check(g+'.E2_auth_ref_frozen',f.get(er['path'])==er['sha256'])
 check(g+'.E2_readonly_auth',ea['schema']=='v8.E2.frozen_live_inference_approval.v1' and ea['status']=='ROOT_APPROVED_FROZEN_E2_ACTUAL_OUT0_ONCE_V1' and ea['group']==g and ea['operation']==e2c['approval_operation'] and ea['physics_authorization'] is False and ea['real_fit_authorization'] is False and ea['original_global_stop_unix']==1793114740.)
 check(g+'.E2_manifest_contract_SHA',ea['source_manifest_sha256']==sha('families/learning_assisted/common_out0_v2/FROZEN_LIVE_E2_SOURCE_MANIFEST_V2.json') and ea['contract_sha256']==sha(e2contract))
 check(g+'.preserved_sourcepins',f.get(cp['preserved_v3']['path'])==cp['preserved_v3']['sha256']==sha(cp['preserved_v3']['path']) and f.get(cp['beta_mean_extension']['path'])==cp['beta_mean_extension']['sha256']==sha(cp['beta_mean_extension']['path']))
 check(g+'.wrapper_sourcepin',f.get('source/v8_comparative_validation_v7.py')==sha('source/v8_comparative_validation_v7.py'))
 check(g+'.main_actual_approval_pin',f.get(mainp)==sha(mainp))
 if g!='V8FROZENENG02':
  route=routes['sealed_validation'][{'V8VAL03':0,'V8VAL04':1}[g]];case='runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/'+route['case_key']+'.json'
  check(g+'.registered_case_seed_split',c['case_path']==case and c['case_sha256']==route['payload_sha256'] and c['condition']['seed']==route['seed'] and c['condition']['split']=='FROZEN_NEW_PARAMETER_VALIDATION' and c['mode']=='validation')
  check(g+'.registered_case_configpins',f.get(case)==route['payload_sha256'] and f.get(route['payload_relative_path'])==route['payload_sha256'])
  registrations.append({'group':g,'case_path':case,'case_sha256':route['payload_sha256'],'seed':route['seed'],'payload_opened':False})
 else:check(g+'.exposed_knownheavy_not_validation',c['case_sha256']=='44387b2b48a4d486d4fa5f7b980e698a3546365eea95bad2b1c2c50620342ccf' and c['condition']['seed']==2690 and c['mode']=='engineering' and c['condition']['split']=='ENGINEERING_EXPOSED_REPLAY')
check('shared_exact_dependency_maps',configs['V8FROZENENG02']['frozen_artifacts']==configs['V8VAL03']['frozen_artifacts']==configs['V8VAL04']['frozen_artifacts'])
check('both_registered_distinct_val_cases',len(registrations)==2 and len({x['case_sha256'] for x in registrations})==2)
canary_metadata=[]
for g,c in configs.items():
 ea=getref(c['comparative_validation']['e2_readonly_authorization']);cr=ea['prerequisite_actual_bundle_canary'];canary=getref(cr)
 check(g+'.actual_weights_canary_PASS',canary['status']=='PASS_ACTUAL_BUNDLE_CANARY_NOT_LIVE_OUT0_APPROVAL' and canary['all_inputs_and_weights_unchanged'] is True and canary['selector_decisions_checked']==9 and canary['scalar_comparisons']==320 and canary['counters']['prediction_API_calls']==25 and canary['counters']['prediction_query_vectors']==85 and canary['counters']['fit']==canary['counters']['physics']==canary['actual_A3_predict_calls']==0)
 check(g+'.canary_not_actual_OUT0_proof',canary['actual_OUT0_source_proof_exercised'] is False and canary['actual_OUT0_wrapper_called'] is False and canary['deployment_eligible'] is False and canary['real_physical_qualification_granted'] is False)
 canary_metadata.append({'group':g,'canary':cr,'status':canary['status'],'direct_config_pin':c['frozen_artifacts'].get(cr['path'])==cr['sha256'],'indirect_pinning':'exactcanarypath/SHA in exactconfig-frozen E2readonlyauth; runtime E2doesnotreadcanaryfile'})
prior=load('families/critic_value/analysis/ACTUAL_COMPARISON_V6_METADATA_REVIEW_V1.json')
for g,h in prior['config_sha256'].items():check('old_config_preserved:'+g,sha('experiments/'+g+'.json')==h)
oldsource=load('families/critic_value/analysis/DURABLE_RETURN_E2V2_PREPARER7_SOURCE_REVIEW_V1.json')
for rel,h in oldsource['source_and_metadata_sha256'].items():
 if rel.endswith('.py'):check('reviewed_old_and_new_source_bytes_preserved:'+rel,sha(rel)==h)
out={'actual_bundle_canary_metadata':canary_metadata,'status':'PASS_METADATA_CONFIGS_AUTH_CLOSURE_153_AND_TWO_VAL_REGISTRATIONS' if all(x['PASS'] for x in checks) else 'METADATA_CONFIG_BLOCKERS','created_unix':time.time(),'config_sha256':expected,'pin_count_per_config':192,'required49_all_covered':True,'axis11_all_covered_previous10_missing_fixed':True,'selectors':counts,'core_logical_selector_count':153,'Beta_separate_mean_forward_and_fixed_maps':{'mean_forwards':12,'fixed_maps':5},'C_post_B_logical_selectors':5,'val_registration_metadata_only':registrations,'checks':checks,'failed_checks':[x for x in checks if not x['PASS']],'references_sha256':refs,'documents_opened':sorted(set(opened)),'operations':{'candidate_helper_or_model_calls':0,'model_restore_forward_fit_physics':0,'original_run_CURRENT_pending_or_raw_trace_reads':0,'case_payload_reads_or_outcomes':0,'actual_config_or_approval_mutations':0},'scope_limits':['这仅核metadata/sourceSHA与map；原模型run字节本轮未重新读取，沿用前次闭合身份和config中精确SHA','actual七角色loadedmodule/sourceproof、worker/supervisor身份、环境binary/numpy、实时期限与callback行为仍须actual integration gate；本审无forward','153是逻辑core selector数，NQ63forward/68selector等嵌套账分列；另12Beta mean与5grid，C仅B后','本审不授权新val或FMEAN job prepare/physics，仍等master+C4builder及root独立派发批准']}
dest=A/'ACTUAL_COMPARISON_V7_METADATA_REVIEW_V1.json'
with dest.open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'status':out['status'],'checks':len(checks),'failed_checks':out['failed_checks'],'review_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'operations':out['operations']},ensure_ascii=False))
