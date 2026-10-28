"""独立只读已闭合JSON/SHA审查，不import/call任何builder或policy/helper。"""
from pathlib import Path
import hashlib,json,os,resource,time

P=Path(__file__).resolve().parents[3];D=Path(__file__).resolve().parent
F='families/ppo_reward/continuous_scale_v1/';R=F+'real_runs/GENUINE_BETA_V1/'
ARMS=['BETA_RF_RAW','BETA_PPO_RAW','BETA_RF_SCALED','BETA_PPO_SCALED']
refs={};pins={};checks=[];start=time.monotonic()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(d):return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def load(rel):
 assert rel.endswith('.json') and Path(rel).name!='CURRENT.json' and 'sampling' not in Path(rel).parts and 'pending_inputs' not in Path(rel).parts
 refs[rel]=sha(P/rel);return json.loads((P/rel).read_text())
def pin(rel,value=None):
 actual=sha(P/rel);assert value is None or actual==value,(rel,value,actual)
 assert rel not in pins or pins[rel]==actual;pins[rel]=actual;return actual
def refload(ref):pin(ref['path'],ref['sha256']);return load(ref['path'])
def check(name,value):checks.append({'check':name,'PASS':bool(value)})
inventory_path='freeze/BETA_COMMITTED_ENDPOINT_ACTUAL_INVENTORY_V2.json'
inv=load(inventory_path);check('main_reported_inventory_SHA',refs[inventory_path]=='8635b72b253dd6cf5e02f9a7fa7d56df1e200cd092851affd2f35f7090e27f58');pin(inventory_path)
review=refload(inv['root_endpoint_scope_review']);q=refload(inv['quarantine']);scope=review['endpoint_transaction_scope']
check('inventory_schema_status',inv['schema']=='v8.beta_committed_endpoint_inventory.v2' and inv['status']=='COMMITTED_G0_G1_ONLY_WITH_EXTERNAL_UNRESOLVED_QUARANTINE')
check('exact_roles_arms_policy_location',[x['role'] for x in inv['roles']]==['PARENT','FIRST_COMPLETED','LAST_COMPLETED'] and inv['arm_ids']==ARMS and inv['policy_location']==['policy'])
check('review_schema_status',review['schema']=='v8.beta_committed_endpoint_scope_review.v2' and review['status']=='SAFE_COMMITTED_ENDPOINT_SCOPE_EXTERNAL_BATCH02_UNRESOLVED')
check('global_UNKNOWN_not_globalFalse','true_hard_safety_violation' not in review and review['whole_training_hard_status']=='UNKNOWN_EXTERNAL_BATCH02_UNRESOLVED')
check('scope_safe_only',scope['generation_indices']==[0,1] and scope['true_hard_safety_violation'] is False and all(scope[k] is True for k in ['all_committed_checkpoints_have_no_pending','original_complete_receipts_raw_scorer_checks_reviewed','excludes_external_batch02_pending']))
check('no_outcome_selection_no_physics_authority',review['endpoint_selected_by_outcome_or_best_seed'] is False and review['physical_dispatch_authority_granted'] is False and review['quarantine']==inv['quarantine'])
for rel,h in review['metadata_evidence_files_sha256'].items():pin(rel,h);load(rel)
batch=refload(scope['committed_batch01_closure']);check('batch01_exact_SHA',scope['committed_batch01_closure']['sha256']=='9907d7853d6fadb6e1f83dec2bfa35cf2e1091507bc810b8f4013262a922de1e')
check('batch01_safe_closed',batch['status']=='READY_FULL_TWO_CASE_RECEIPTS_FOR_ALL_FOUR_ARMS' and batch['true_hard_safety_violation'] is False and all(batch[k] is True for k in ['all_started_children_joined','all_parent_prefixes_unchanged','all_started_attempts_hard_safety_reviewed']))
check('quarantine_schema',q['schema']=='v8.beta_external_unresolved_batch_quarantine.v1' and q['status']=='EXTERNAL_BATCH02_PENDING_UNRESOLVED_UNMODIFIED_NOT_ENDPOINT')
check('quarantine_no_cancel_no_commit',q['external_pending_proposal_count']==9 and q['published_updates_from_external_batch']==0 and q['disposition']=='KEEP_EXTERNAL_PENDING_NO_CANCEL_NO_COMMIT')
check('quarantine_UNKNOWN_unchanged',q['true_hard_safety_violation'] is None and q['hard_status']=='UNKNOWN_NOT_FALSE' and q['original_UNKNOWN_physical_guard_unchanged'] is True and q['pending_and_RNG_mutated_by_freeze'] is False and q['external_pending_in_endpoint_models'] is False)
records=q['external_pending_identity_inventory'];check('nine_distinct_proposals_and_attempts',len(records)==len({x['proposal_identity_sha256'] for x in records})==len({x['attempt_id'] for x in records})==9)
check('records_arm_snapshot_known_hardFalse',all(x['arm_id'] in ARMS and x['original_snapshot_sha256'] and x['snapshot_object_sha256'] and x['true_hard_safety_violation'] is False for x in records))
prefix=refload(q['original_prefix_review']);unknown=['human_acceleration','session_clearance','measured_sleeve_clearance']
check('exact_original_prefix_SHA',q['original_prefix_review']['sha256']=='d15d9d623fcda633530d7be702804dbce49ffb3d6ed63fb7188fcfa505b2113d')
check('original_three_unknowns',prefix['unresolved_gates']==q['unresolved_prefix_condition_names']==unknown and prefix['global_prefix_11hard_false_established'] is None and all(prefix['additional6_scope_review'][x]['value'] is None for x in unknown))
owners=refload(q['all_owner_closure_review']);check('owner_summary',owners['status']=='ALL_KNOWN_TRAINING_OWNERS_EXITED' and owners['survivors']==[] and owners['all_original_PID_startticks_exited'] is True)
check('four_owner_groups',set(x['group'] for x in owners['processes'])=={'V8BETA01H','V8BETA01L','V8BETA02H','V8BETA02L'})
for rel,h in owners['original_evidence_files_sha256'].items():pin(rel,h);load(rel)
owner_rows=[]
for x in owners['processes']:
 p=Path('/proc')/str(x['pid'])/'stat';tick=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
 check('owner_closed:'+x['group']+':'+str(x['pid']),x['original_closed'] is True and tick!=x['original_start_ticks']);owner_rows.append({'group':x['group'],'pid':x['pid'],'now_start_ticks':tick,'original_start_ticks':x['original_start_ticks']})
prior=load('families/critic_value/analysis/beta_committed_pending_metadata_v2/RESULT.json')
for rel,h in q['original_snapshot_files_sha256'].items():check('original_snapshot_identity_preserved_in_independent_142check:'+rel,prior['evidence_files_sha256'].get(rel)==h)
priorrows=[row for arm in ARMS for row in prior['batch2']['V8BETA02L']['arms'][arm]['pending']]
check('pending_identity_matches_independent_closed9',{x['attempt_id'] for x in records}=={x['attempt_id'] for x in priorrows})
txs={}
for item in inv['complete_committed_generation_transaction_inventory']:
 tx=refload(item['transaction']);idx=item['generation_index'];check('transaction:'+str(idx),tx['generation_index']==idx and tx['all_four_published_together'] is True and set(tx['checkpoints'])==set(ARMS));txs[idx]=tx
check('exact_two_committed_transactions',sorted(txs)==[0,1] and txs[0]['status']=='READY_ALL_FOUR_INITIALIZED' and txs[1]['status']=='READY_ALL_FOUR_UPDATED' and review['committed_generation_inventory_object_sha256']==digest(inv['complete_committed_generation_transaction_inventory']) and review['latest_actual_committed_generation_index']==1)
tip=refload(review['frozen_committed_pointer_snapshot']);tx1=next(x['transaction'] for x in inv['complete_committed_generation_transaction_inventory'] if x['generation_index']==1)
check('tip_new_basename_and_actual_bytes',Path(review['frozen_committed_pointer_snapshot']['path']).name!='CURRENT.json' and review['frozen_committed_pointer_snapshot']['sha256']==prior['CURRENT_original_sha256']=='32fad6c15976baa7f40f4391db9f1afe0472d452c3cad0afff54f3c866291161')
check('tip_exactG1',tip['generation_index']==1 and tip['transaction_sha256']==scope['reviewed_G1_transaction_sha256']==tx1['sha256'] and tip['checkpoints']==txs[1]['checkpoints'] and tip['status']=='READY_ALL_FOUR_UPDATED')
check('roles_no_best',review['role_generation_indices']=={'PARENT':0,'FIRST_COMPLETED':1,'LAST_COMPLETED':1})
axis=refload(inv['axis']);check('axis_object_SHA',digest(axis)==inv['axis_object_sha256'])
for rel,h in axis['source_files_sha256'].items():pin(rel,h)
norm=refload(inv['normalization_source'])['policy']['normalization'];check('norm_source_originalG0',inv['normalization_source']['path']=='families/ppo_reward/onpolicy_runs/GENUINE_V1/GENERATION_0000/RF_RAW.json')
models=[]
for role in inv['roles']:
 check('role_order:'+role['role'],[x['arm_id'] for x in role['checkpoints']]==ARMS and role['generation_index']=={'PARENT':0,'FIRST_COMPLETED':1,'LAST_COMPLETED':1}[role['role']])
 for item in role['checkpoints']:
  x=refload(item);pol=x['policy'];actual=txs[role['generation_index']]['checkpoints'][item['arm_id']]
  check('model_transaction_ref:'+role['role']+item['arm_id'],all(item[k]==actual[k] for k in ['path','sha256']))
  check('closed_policy_content:'+role['role']+item['arm_id'],x['schema']=='v8.continuous_beta_arm_checkpoint.v2' and x['execution_mode']=='GENUINE_ON_POLICY' and not x['pending'] and x['math_fixture_contract_sha256'] is None and x['algorithm']==('PPO' if item['arm_id'].startswith('BETA_PPO') else 'REINFORCE') and pol['schema']=='v8.scalar_beta_linear25.v1' and pol['arm_id']==item['arm_id'] and pol['gain']==(20. if item['arm_id'].endswith('SCALED') else 1.) and pol['normalization']==norm and x['frozen_axis_sha256']==inv['axis_object_sha256'] and pol['axis_contract']==axis and x['policy_behavior_sha256']==item['policy_behavior_sha256'])
  keys=['schema','feature_names','normalization','weights','axis_contract','axis_contract_sha256','seed','arm_id','gain','version'];check('policy_behavior_hash:'+role['role']+item['arm_id'],digest({k:pol[k] for k in keys})==item['policy_behavior_sha256'])
  if role['role']=='PARENT':check('parent_untrained:'+item['arm_id'],pol['version']==0 and pol['counters']['parameter_updates']==0)
  models.append({'role':role['role'],'arm_id':item['arm_id'],'version':pol['version'],'checkpoint_sha256':item['sha256']})
m=refload(inv['A3_adapter_manifest']);pin('families/critic_value/coverage_state_v3/source/live_selector_adapter_candidate_v1.py',m['adapter_sha256'])
for ref in [m['bundles']['A3']]+list(m['api_files']['A3'].values()):pin(ref['path'],ref['sha256'])
for rel in [F+'beta_frozen_mean_extension_candidate_v2.py',F+'beta_policy.py',F+'axis_mapping.py']:pin(rel)
root_source='scripts/freeze_beta_committed_scope_v2.py';refs[root_source]=sha(P/root_source)
source_hashes={root_source:refs[root_source],F+'beta_frozen_mean_extension_candidate_v2.py':pins[F+'beta_frozen_mean_extension_candidate_v2.py']}
source_observations=[{'severity':'NO_BLOCKER_FOR_COMPLETED_EXACT_METADATA_FREEZE','lines':'freeze_beta_committed_scope_v2.py:36-70,93-111','finding':'固定CHAIN/PREFIX/CURRENT/G1哈希，非counter policy/optimizer/finished及parameter/score相同，forward/RNG允许增长；只新写自有freeze元数据，外部9pending和CURRENT不写；全局UNKNOWN与endpoint false分scope。'}, {'severity':'REQUIRED_PREDEPLOYMENT_FIX_ASSIGNED_ROOT_C','lines':'prepare_frozen_comparison_v4_v5.py:76 and beta_frozen_mean_extension_candidate_v2.py:178-180','finding':'preparerV5 refs(inventory)只pin axis JSON而不加载其source_files_sha256；已列base+9manifest缺10个runtime axis refs，meanV2会在Beta forward前拒绝。主已分派新preparerV6修，不需改meanV2。'}, {'severity':'NONBLOCKING_FIXED_INSTANCE_LIMIT','lines':'freeze_beta_committed_scope_v2.py:70 and beta_frozen_mean_extension_candidate_v2.py:131-134','finding':'源码显式检查9个proposal_identity唯一，未另断言attempt_id唯一；本次实际9attempt唯一且与独立142check结果完全同集。本审补证当前实例，不宣称任意输入安全。'}, {'severity':'NONBLOCKING_STANDALONE_API_CLOSURE_LIMIT','lines':'beta_frozen_mean_extension_candidate_v2.py:181-183','finding':'normalization_source有精确文件SHA/路径绑定，但独立API不额外assert其config pin；实际preparer refs(inventory)会pin，该pin仍列入最小闭包。本次不为hypothetical输入改源。'}, {'severity':'FAILURE_ACCOUNTING_COMPATIBLE','lines':'beta_frozen_mean_extension_candidate_v2.py:331-338 and comparative_composer_v4_candidate_v4.py:350','finding':'Beta异常属性beta_mean_extension_consumed_work由实际V4调用者存beta_failed_paid_work，不能按旧generic仅str(error)误报丢账。'}, {'severity':'FAILURE_PUBLICATION_LIMIT','lines':'freeze_beta_committed_scope_v2.py:88-129','finding':'5个新文件逐个open(x)，非原子组发布。当前实际END exit0和全部SHA闭合可用；若未来中途失败应保留partial，不自动覆盖/补成功。本builder已完成，不重跑。'}]
end=load('audit/BETA_COMMITTED_ENDPOINT_FREEZE_END_V2.json');check('root_actual_freeze_exit_evidence',end['status']=='METADATA_FROZEN_COMMITTED_ENDPOINTS_EXTERNAL_QUARANTINE_UNCHANGED' and end['external_pending']==9 and end['external_published_updates']==0 and end['whole_training_hard_status']=='UNKNOWN' and all(end[x]==0 for x in ['model_imports','forwards','fit','RNG_draws','new_physics']))
for rel,h in end['outputs'].items():check('root_actual_output_SHA:'+rel,sha(P/rel)==h)
out={'status':'ACTUAL_5JSON_METADATA_COMPATIBLE_WITH_MEAN_V2_DEPLOYMENT_CONFIG_NOT_YET_VALIDATED' if all(x['PASS'] for x in checks) else 'ACTUAL_METADATA_COMPATIBILITY_BLOCKED','created_unix':time.time(),'reviewed_source_hashes':source_hashes,'checks':checks,'failed_checks':[x for x in checks if not x['PASS']],'actual_model_metadata_only':models,'owner_identity_checks':owner_rows,'observations':source_observations,'required_existing_config_frozen_artifacts':pins,'future_required_auth_pin':'new deployment_authorization path/sha must also be config-frozen and approved separately','inference_budget_source_only':{'logical_mean_forwards':12,'policy_deepcopies':12,'fixed_maps':5,'mean_internal_maps':12,'A3_sevenrole_proof':1,'A3_context39_prepare':1,'projection25':1,'restore_init_fit_RNG_physics':0},'scope':'G0 parent/G1 first=last only; external9 identities/snapshotSHAs excluded from deployed models; parent prefix3unknown unchanged; no current/pending/raw/trace reads in this review','references_sha256':refs,'operations':{'builder_or_inventory_helper_calls':0,'model_import_init_forward_fit_physics':0,'mutable_CURRENT_pending_raw_trace_reads':0,'actual_state_mutation':0},'wall_s':time.monotonic()-start,'RSS_peak_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
for name,value in [('BETA_FROZEN_SCOPE_ACTUAL_COMPATIBILITY_REVIEW_V1.json',out),('BETA_FROZEN_SCOPE_REQUIRED_CONFIG_PINS_V1.json',{'status':'REVIEW_ONLY_NOT_APPROVAL_NOT_CONFIG','source_inventory_sha256':refs[inventory_path],'required_existing_pins':pins})]:
 with (D/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'status':out['status'],'checks':len(checks),'failures':out['failed_checks'],'review_sha256':sha(D/'BETA_FROZEN_SCOPE_ACTUAL_COMPATIBILITY_REVIEW_V1.json'),'pins':len(pins),'pins_sha256':sha(D/'BETA_FROZEN_SCOPE_REQUIRED_CONFIG_PINS_V1.json'),'operations':out['operations']},ensure_ascii=False))
