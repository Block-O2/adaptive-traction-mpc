"""SOURCE_ONLY V3: immutable首完整真实PG事务+已审48行 -> 明确offpolicy SAC replay。

不初始化模型，不forward/fit/physics，不自动寻找最新generation，不写文件。
Root须先批准具体闭合输入binding；build返回待root冻结的dataset+manifest。
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import math
import resource
import time

ACTIVATION='deep_learning_method_exploration_v8_20261027T032540Z'
DEADLINE=1793114740.0
ARMS=('RF_RAW','PPO_RAW','RF_SCALED','PPO_SCALED')
TAGS=('B','LATE_H150','EARLY_H150','LATE_PHASE','EARLY_PHASE')
HARD=('force','moment','torque','human_speed','human_acceleration','robot_speed','session_clearance','true_clearance','measured_sleeve_clearance','no_shank_table_contact','no_human_rom_violation')
HIST='families/critic_value/coverage_risk_v2/data/ACTUAL_COVERAGE_DATASET_V1.json'
HIST_SHA='e7a54dd7d3d39f0ab94cec45ceea284d6efec51d186ab74e46ff2335e82b79e0'
SCOPED='families/critic_value/coverage_state_v3/data/SCOPED_OUT0_STATES_V1.json'
SCOPED_SHA='7a1ba773b37686e13571d6c4aa4dfa31f180725e2ec7ee464170ef6258e3f68d'
CONVERTER='families/critic_value/coverage_risk_v2/source/causal_api.py'
BASE='runtime/source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/'
SOURCE_ROLES={'capture':'source/v7_causal_context.py','runtime':BASE+'full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py','observer':BASE+'controller_interface.py','observation_contract':BASE+'task_observation.py','history_guard':'source/v6_features.py','runtime_loader':'runtime/code/study_common.py'}


def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def require(test,reason):
    if not test:raise ValueError(reason)
def number(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def policy_identity(policy):
    fields=('schema','seed','version','action_sha256','feature_names','normalization','weights')
    return digest({**{k:policy[k] for k in fields},'representation':policy.get('representation','linear_commissioned25')})
def context_equal(a,b):
    return all(a[k]==b[k] for k in ('feature_names','features','quality','legacy77d_valid','subset_numeric_identity_sha256'))
def capture_proof(R,package,config):
    source=R.json(package/'jobs'/config['group']/'SOURCE_MANIFEST.json');proof={}
    for role,relative in {**SOURCE_ROLES,'callback':'source/'+config['worker']}.items():
        actual=R.sha(package/relative);require(source['files'][relative]==actual,'ACTUAL_CAPTURE_SOURCE_CHANGED:'+role);proof[role]=actual
    return proof


class Reader:
    def __init__(self,package):
        self.P=Path(package).resolve();self.repo=self.P.parent;self.files={};self.streams={};self.started=time.time()
    def bounded(self):require(time.time()<min(self.started+600.,DEADLINE),'READ_ONLY_BUILD_LOCAL_OR_GLOBAL_DEADLINE')
    def path(self,path):
        path=Path(path);path=(self.P/path).resolve() if not path.is_absolute() else path.resolve()
        require(path.is_relative_to(self.P) or path.is_relative_to(self.repo/'autonomous_learning_smoothness_v7'),'READ_OUTSIDE_APPROVED_PACKAGES')
        require(not any(s in str(path).lower() for s in ('_val_','/sealed/','validation_payload','validation_outcome')),'SEALED_PATH_FORBIDDEN')
        return path
    def sha(self,path):
        self.bounded()
        path=self.path(path);h=hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        value=h.hexdigest();relative=str(path.relative_to(self.repo))
        if relative in self.files:require(self.files[relative]==value,'SOURCE_CHANGED_DURING_BUILD:'+relative)
        self.files[relative]=value;return value
    def json(self,path):
        path=self.path(path);self.sha(path);return json.loads(path.read_text())
    def events(self,package,ids):
        package=self.path(package);found={};path=package/'runtime/ATTEMPTS.jsonl'
        # Only requested independent attempts are returned; full-file SHA is metadata identity.
        with path.open('rb') as f:
            for raw in f:
                ev=json.loads(raw)
                if ev.get('id') not in ids or ev.get('event') not in ('START','END'):continue
                key=(ev['id'],ev['event']);require(key not in found,'DUPLICATE_ORIGINAL_EVENT')
                found[key]={'record':ev,'raw_line_without_newline_sha256':hashlib.sha256(raw.rstrip(b'\r\n')).hexdigest(),'canonical_record_sha256':digest(ev)}
        require(set(found)=={(i,k) for i in ids for k in ('START','END')},'MISSING_INDEPENDENT_START_END')
        return found
    def module(self,relative,expected,label):
        path=self.path(relative);require(self.sha(path)==expected,'FROZEN_HELPER_SOURCE_CHANGED')
        spec=importlib.util.spec_from_file_location(label,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def closed(R,group):
    P=R.P;d=R.json(P/'jobs'/group/'WORKER_DONE.json');s=R.json(P/'owned'/(group+'_SUPERVISOR_END.json'))
    require(d['status']=='PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS' and d.get('all_children_joined') is True,'WORKER_NOT_CLEANLY_CLOSED')
    require(s['state']=='STOP' and s['worker_exit_code']==0 and s['survivors']==[],'OWNER_NOT_CLOSED')
    R.json(P/'owned'/(group+'_EXIT.json'))
    require(R.json(P/'audit'/(group+'_PARENT_RAW_GATE.json'))['status']=='PASS','PARENT_B_RAW_GATE')
    require(all(c['unchanged'] is True and c['child_exitcode']==0 for c in d['parent_checks']),'PARENT_MUTATED')
    return d


def full_physical(R,package,row,recipe,events):
    """原完整任务、实际binding/lineage/stream；不把recipe称为每个native step owner。"""
    ident=row['id'];require(row.get('complete') is True and row.get('error') is None,'PARTIAL_OR_ENGINEERING_ROW_EXCLUDED')
    require(type(row.get('qualified')) is bool,'MISSING_ORIGINAL_QUALIFICATION')
    require(all(number(row.get(k)) and row[k]>=0 for k in ('JF','JM')),'MISSING_FULL_COST')
    require(row['action']==recipe['action'],'RESULT_ACTION_NOT_FULL_RECIPE')
    binding=R.json(package/'attempts'/(ident+'_EXECUTION_BINDING.json'))
    candidate=copy.deepcopy(binding['candidate']);candidate.pop('id',None)
    require(binding['action']==recipe['action'] and candidate==recipe['resolved_base_candidate'] and binding['truth_used'] is False,'ACTUAL_BINDING_NOT_RECIPE')
    m=R.json(package/row['metrics_path']);require(m['id']==ident and m['J_F_N_s']==row['JF'] and m['moment_integral_Nm_s']==row['JM'],'MEASURED_RESULT_COST_IDENTITY')
    require(m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS','ORIGINAL_SCIENTIFIC_OWNERSHIP_FAIL')
    require(m['native_physical_audit']['pass_'] is True,'ORIGINAL_HARD_SAFETY_AUDIT_FAIL')
    common=m['native_physical_audit']['unchanged_evaluator']['physical_task_result']['scorer_v2_common_conditions']
    # True hard safety dominates unknown; both fail closed for replay.
    require(not any(common.get(k) is False for k in HARD),'HARD_SAFETY_STOP')
    require(all(common.get(k) is True for k in HARD),'HARD_SAFETY_UNKNOWN')
    lineage_path=R.path(m['execution_lineage_path']);require(lineage_path.is_relative_to(package),'LINEAGE_WRONG_PACKAGE')
    lineage=R.json(lineage_path);require(lineage['status']=='PASS' and lineage['ownership_error_count']==0,'APPLIED_LINEAGE_FAIL')
    require(number(m.get('actual_new_native_steps')) and isinstance(m['actual_new_native_steps'],int) and m['actual_new_native_steps']>0,'NO_REAL_NEW_NATIVE_INCREMENT')
    require(row['actual_new_native_steps']==m['actual_new_native_steps'],'NATIVE_INCREMENT_RESULT_MISMATCH')
    start,end=events[(ident,'START')],events[(ident,'END')]
    require(end['record'].get('joined') is True and end['record'].get('returncode')==0 and end['record'].get('parent_hash_equal') is True,'UNCLOSED_OR_PARENT_MUTATED')
    raw=package/'runtime/source/results'/ident/'runtime_artifacts.json.gz';rawsha=R.sha(raw)
    # Streaming helper is data-only and source-pinned; no simulator/model import.
    helper=R.stream_helper
    h=hashlib.sha256();count=positive=steps=0
    for receipt in helper.array_items(raw,'command_receipts'):
        h.update(json.dumps(receipt,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()+b'\n');count+=1
        if count%1024==0:R.bounded()
        if receipt.get('applied') is True and isinstance(receipt.get('native_steps'),int) and receipt['native_steps']>0:
            positive+=1;steps+=receipt['native_steps']
    require(count>0 and positive>0,'NO_ACTUAL_APPLIED_RECEIPT_STREAM')
    comp=row.get('motion_vs_B');require(isinstance(comp,dict) and isinstance(comp.get('failed_requirements'),list) and type(comp.get('acceptance_pass')) is bool,'ORIGINAL_MOTION_LABEL_MISSING')
    require(row['qualified']==(m['axes']['PHYSICAL_TASK_VALID']=='PASS' and m['axes']['LEGACY_R2_MATCHED']=='PASS' and comp['acceptance_pass'] is True),'ORIGINAL_QUALIFICATION_SEMANTICS_CHANGED')
    proof={'events_original_records_and_hash_scopes':{'START':start,'END':end},'result_source_sha256':R.sha(package/'attempts'/(ident+'_RESULT.json')),
      'measured_source_sha256':R.sha(package/row['metrics_path']),'actual_binding_sha256':R.sha(package/'attempts'/(ident+'_EXECUTION_BINDING.json')),
      'native_ownership_sha256':R.sha(lineage_path),'applied_reference_receipt_stream_sha256':h.hexdigest(),'raw_container_sha256':rawsha,
      'applied_stream_scope':{'receipt_count':count,'positive_step_receipts':positive,'archived_positive_native_steps_including_inherited_prefix':steps,'includes_inherited_prefix':True,'selected_recipe_not_owner_of_every_archived_step':True},
      'actual_new_native_steps':m['actual_new_native_steps'],'hard_safety':False,'ownership_PASS':True,'complete':True,
      'original_qualified':row['qualified'],'JF_N_s':row['JF'],'JM_Nm_s':row['JM'],'original_motion_failed_requirements':comp['failed_requirements'],
      'original_motion_comparison':comp}
    R.streams[ident]=proof;return proof


def common_record(*,ident,context,case_sha,parent,recipe,index,row,proof,base,origin,behavior=None):
    names=context['feature_names'];values=context['features'];feature_sha=digest({'names':names,'values':values})
    require(base['parent_fingerprint']==parent and base['causal_features_sha256']==feature_sha,'BASELINE_NOT_SAME_PARENT_CAUSAL_CONTEXT')
    require(base['complete'] is True and base['original_qualified'] is True,'BASELINE_NOT_FULL_QUALIFIED')
    reward=max(-.9,min(.9,(base['JF_N_s']-row['JF'])/max(base['JF_N_s'],1.))) if row['qualified'] else -1.
    return {'schema':'v8.sac_terminal_offpolicy_replay_record.v2','attempt_id':ident,'origin':origin,'data_use_semantics':'OFFPOLICY_TERMINAL_REPLAY',
      'split':'DEVELOPMENT_ONLY','split_case_sha256_evaluation_only':case_sha,'parent_fingerprint_evaluation_only':parent,
      'feature_names':names,'features':values,'causal_features_sha256':feature_sha,'qa_validated':True,
      'action_index':index,'full_recipe':copy.deepcopy(recipe),'full_recipe_sha256':digest(recipe),'done':True,'next_state':None,
      'complete':True,'original_qualified':row['qualified'],'JF_N_s':row['JF'],'JM_Nm_s':row['JM'],
      'canonical_terminal_return':reward,'failure':float(not row['qualified']),'baseline':base,'original_evidence':proof,
      'behavior':copy.deepcopy(behavior),'same_context_action_key_evaluation_only':digest({'case':case_sha,'parent':parent,'features':feature_sha,'recipe':digest(recipe)}),
      'behavior_missing_not_fabricated':behavior is None,'original_qualification_granted_to_future_action':False}


def build(package,binding_path,source_manifest_path):
    """调用需另批准；只返回JSON对象，不写任何CURRENT/checkpoint或结果。"""
    start=time.time();cpu_initial=resource.getrusage(resource.RUSAGE_SELF);R=Reader(package);P=R.P
    require(start<DEADLINE,'ORIGINAL_GLOBAL_HARD_STOP')
    activation=R.json(P/'ACTIVATION.json');require(activation['activation_id']==ACTIVATION and activation['hard_stop_unix']==DEADLINE,'ACTIVATION_RESET')
    binding=R.json(binding_path);require(binding['status']=='APPROVED_BY_MAIN_AGENT_FOR_READ_ONLY_DATA_BUILD','EXPLICIT_BUILD_APPROVAL_REQUIRED')
    sources=R.json(source_manifest_path);require(R.sha(source_manifest_path)==binding['build_source_manifest_sha256'],'BUILD_SOURCE_BINDING')
    for rel,expected in sources['required_source_sha256'].items():require(R.sha(rel)==expected,'SOURCE_CHANGED:'+rel)
    require(binding['activation']==ACTIVATION and binding['global_deadline_unix']==DEADLINE,'BUILD_CLOCK_IDENTITY')
    R.stream_helper=R.module('runtime/code/stream_runtime_evidence.py',sources['required_source_sha256']['runtime/code/stream_runtime_evidence.py'],'_sac_replay_stream_only')
    converter=R.module(CONVERTER,sources['required_source_sha256'][CONVERTER],'_sac_replay_context25_only')
    run=R.path(binding['run_directory']);require(run==P/'families/ppo_reward/onpolicy_runs/GENUINE_V1','ONLY_GENUINE_V1_RUN')
    identity=R.json(run/'RUN_IDENTITY.json');require(R.sha(run/'RUN_IDENTITY.json')==binding['run_identity_sha256'],'RUN_IDENTITY_SHA')
    require(identity['activation']==ACTIVATION and identity['global_deadline_unix']==DEADLINE and identity['initialization_count']==1,'RUN_CLOCK_OR_INIT_RESET')
    approval_path=P/identity['approved_contract_path'];approval=R.json(approval_path)
    require(approval['status']=='APPROVED_BY_MAIN_AGENT' and R.sha(approval_path)==identity['approved_contract_sha256']==binding['onpolicy_contract_sha256'],'ROOT_ONPOLICY_APPROVAL')
    require(approval['activation']==ACTIVATION and approval['global_deadline_unix']==DEADLINE,'ONPOLICY_CLOCK_CHANGED')
    correction=R.json(binding['engineering_correction_approval_path'])
    require(R.sha(binding['engineering_correction_approval_path'])==binding['engineering_correction_approval_sha256'] and correction['status']=='APPROVED_BY_MAIN_AGENT','JSON_IDENTITY_CORRECTION_NOT_APPROVED')
    require(correction['corrected_adapter_sha256']==binding['receipt_adapter_sha256'] and correction['run_identity_and_local_deadline_must_not_reset'] is True,'CORRECTION_SCOPE_CHANGED')
    menu=R.json(P/approval['menu_path']);require(R.sha(P/approval['menu_path'])==binding['menu_sha256'],'MENU_DOCUMENT_CHANGED')
    recipes=menu['action_contracts'];hashes=[digest(r) for r in recipes]
    require(menu['action_names']==list(TAGS) and hashes==menu['full_recipe_sha256'] and len(set(hashes))==5,'EXACT_COMPLETE_FIVE_MENU')
    for recipe in recipes:
        require(R.sha(P/'runtime/FROZEN_18D.json')==recipe['frozen_18d_sha256'],'FROZEN18D_CHANGED')
        for relative,expected in recipe['planner_source_sha256'].items():require(R.sha(P/relative)==expected,'RECIPE_PLANNER_CHANGED')
    pointer_path=P/binding['immutable_completed_pointer_path']
    require(pointer_path==P/'freeze/GENUINE_FIRST_COMPLETED_POINTER_V1.json','NO_MUTABLE_CURRENT_OR_LATEST_POINTER')
    current=R.json(pointer_path);require(R.sha(pointer_path)==binding['immutable_completed_pointer_sha256'],'IMMUTABLE_POINTER_EXACT_BYTES')
    freeze=R.json(binding['early_pointer_freeze_audit_path'])
    require(R.sha(binding['early_pointer_freeze_audit_path'])==binding['early_pointer_freeze_audit_sha256'],'EARLY_COPY_AUDIT_IDENTITY')
    require(freeze['status']=='FIRST_COMPLETED_ALIGNED_UPDATE_FROZEN_NOT_BEST' and freeze['source_pointer_bytes_sha256']==freeze['immutable_exact_copy_sha256']==binding['immutable_completed_pointer_sha256'],'NOT_EXACT_ORIGINAL_CURRENT_BYTES_COPY')
    require(freeze['immutable_exact_copy_path']==binding['immutable_completed_pointer_path'] and freeze['transaction_sha256']==current['transaction_sha256'],'FROZEN_COPY_ORIGINAL_TRANSACTION_BINDING')
    require(current['transaction_sha256']==binding['transaction_sha256'],'EXACT_FIRST_TRANSACTION_IDENTITY')
    require(current['status']=='ALL_FOUR_GENUINE_UPDATES_ATOMICALLY_COMMITTED','CANCELLED_OR_UNCOMPLETED_GENERATION_FORBIDDEN')
    index=current['generation_index'];require(index==binding['completed_generation_index'],'NO_AUTOMATIC_LATEST_OR_BEST_CHECKPOINT')
    transaction=R.json(P/current['generation_directory']/'TRANSACTION.json')
    require(R.sha(P/current['generation_directory']/'TRANSACTION.json')==current['transaction_sha256'] and current['checkpoints']==transaction['checkpoints'],'CURRENT_TRANSACTION_BINDING')
    computation_path=P/transaction['durable_computation_output_path'];computation=R.json(computation_path)
    require(R.sha(computation_path)==transaction['durable_computation_output_sha256']==binding['computation_sha256'],'DURABLE_COMPUTATION_BINDING')
    require(computation['schema']=='v8.completed_private_four_arm_computation.v1' and computation['generation_index']==index,'WRONG_COMPUTATION')
    meta=computation['metadata'];require(meta['status']==current['status'] and meta['all_arms_committed_together'] is True,'NOT_ATOMIC_COMPLETED')
    for key,value in meta.items():require(transaction[key]==value,'COMPUTATION_VS_PUBLISHED_METADATA_CHANGED:'+key)
    require(computation['created_unix']<=min(identity['local_stop_unix'],DEADLINE),'COMPUTATION_AFTER_ORIGINAL_CLOCK')
    intent_path=run/('TRANSACTION_ATTEMPT_'+str(index).zfill(4)+'.json');intent=R.json(intent_path)
    require(R.sha(intent_path)==computation['intent_sha256'] and intent['current_pointer']==computation['previous_pointer'],'DURABLE_INTENT_OR_PREVIOUS_POINTER_CHANGED')
    # No earlier completed update is silently skipped. Cancellation generations remain excluded.
    for prior in range(index):
        old=R.json(run/('GENERATION_'+str(prior).zfill(4))/'TRANSACTION.json')
        require(old['status']!='ALL_FOUR_GENUINE_UPDATES_ATOMICALLY_COMMITTED','NOT_FIRST_COMPLETED_FOUR_ARM_UPDATE')
    groups=binding['expected_closed_sampling_groups'];require(len(groups)==2 and len(set(groups))==2 and set(meta['closed_jobs'])==set(groups),'EXACT_TWO_CLOSED_JOBS_REQUIRED')
    require('V8OP01H' not in groups,'CANCELLED_G0001_ENGINEERING_GROUP_EXCLUDED')
    for arm in ARMS:
        checkpoint=current['checkpoints'][arm];require(R.sha(P/checkpoint['path'])==checkpoint['sha256'],'CHECKPOINT_BYTES_CHANGED')
        require(R.json(P/checkpoint['path'])==computation['snapshots'][arm],'PRIVATE_COMPUTATION_VS_PUBLISHED_SNAPSHOT')
    pending_envelope=R.json(P/meta['pending_input_path']);require(R.sha(P/meta['pending_input_path'])==meta['pending_input_sha256'],'PENDING_ENVELOPE_CHANGED')
    pending_path=P/pending_envelope['original_final_pending_path'];pending=R.json(pending_path)
    require(R.sha(pending_path)==pending_envelope['original_final_pending_sha256']==meta['original_final_pending_sha256'],'FINAL_PENDING_BYTES_CHANGED')
    require(pending_envelope['root_expected_sampling_groups']==groups,'ROOT_TWO_JOB_BINDING_CHANGED')
    proposals=[];configs=[];contexts={};baseline_receipts={};raw_receipts={};rows=[]
    for group in groups:
        closed(R,group);config=R.json(P/'experiments'/(group+'.json'));configs.append(config);spec=config['onpolicy_sampling']
        require(meta['closed_jobs'][group]['worker_done_sha256']==R.sha(P/'jobs'/group/'WORKER_DONE.json') and meta['closed_jobs'][group]['supervisor_end_sha256']==R.sha(P/'owned'/(group+'_SUPERVISOR_END.json')),'COMMITTED_CLOSED_OWNER_PROOF_CHANGED')
        require(config['mode']=='development' and config['fork_phase']=='OUTBOUND' and config['fork_slot']==0,'NOT_DEVELOPMENT_OUT0')
        require(spec['approved_contract_sha256']==identity['approved_contract_sha256'] and config['local_stop_unix']==identity['local_stop_unix'],'SAMPLING_CONTRACT_OR_CLOCK_RESET')
        source=R.json(P/'jobs'/group/'SOURCE_MANIFEST.json');require(source['config_sha256']==R.sha(P/'experiments'/(group+'.json')),'ACTUAL_JOB_CONFIG_SHA')
        require(spec['menu_sha256']==binding['menu_sha256'] and spec['menu_path']==approval['menu_path'],'SAMPLING_MENU_CHANGED')
        require(R.sha(P/spec['receipt_adapter_path'])==spec['receipt_adapter_sha256']==binding['receipt_adapter_sha256'],'APPROVED_RECEIPT_ADAPTER_CHANGED')
        require(source['files'][spec['receipt_adapter_path']]==spec['receipt_adapter_sha256'],'ACTUAL_JOB_ADAPTER_PROFILE')
        route=R.json(P/spec['case_route_manifest']);case=route['development_routes'][spec['development_context_id']]
        require(case['case_sha256']==config['case_sha256']==R.sha(P/config['case_path']),'EXACT_DEVELOPMENT_CASE_ROUTE')
        raw_path=P/'history'/(group+'_PREFORK_CAUSAL_CONTEXT.json');raw=R.json(raw_path);context=converter.to_context25(raw);contexts[group]=context
        capture_proof(R,P,config)
        baseline=R.json(P/spec['output_directory']/'B_BASELINE_RECEIPT.json');baseline_receipts[group]=baseline
        require(baseline['result_path']=='attempts/'+group+'_B_RESULT.json' and R.sha(P/baseline['result_path'])==baseline['result_source_sha256'],'ORIGINAL_BASELINE_RESULT_SHA')
        expected_ids=[group+'_B']+[group+'_OP_'+arm+'_'+str(i).zfill(2) for arm in ARMS for i in (1,2)]
        events=R.events(P,set(expected_ids+[group+'_parent']))
        require(set(meta['closed_jobs'][group]['attempt_ids'])==set(expected_ids+[group+'_parent']),'COMMITTED_ACTUAL_ATTEMPTS_CHANGED')
        for ident in expected_ids:
            require(events[(ident,'START')]['record']['config_sha256']==source['config_sha256'],'START_NOT_CONFIG')
            require(events[(ident,'END')]['record']['unix']<=min(identity['local_stop_unix'],DEADLINE),'PHYSICS_AFTER_ORIGINAL_CLOCK')
        B=R.json(P/baseline['result_path']);baseproof=full_physical(R,P,B,recipes[0],events)
        parent=B['branch']['full_hash'];feature_sha=digest({'names':context['feature_names'],'values':context['features']})
        require(baseline['causal_features_sha256']==feature_sha and baseline['complete'] is True and baseline['original_qualified'] is True,'B_CONTEXT_OR_QUALIFICATION')
        base={**baseline,'parent_fingerprint':parent,'full_recipe_sha256':hashes[0],'original_evidence':baseproof}
        for arm in ARMS:
            for i in (1,2):
                ident=group+'_OP_'+arm+'_'+str(i).zfill(2);tag=ident.removeprefix(group+'_')
                proposal_path=P/spec['output_directory']/(tag+'_PROPOSAL.json');proposal=R.json(proposal_path)
                require(proposal['physical_result'] is None and proposal['attempt_id']==ident and proposal['arm_id']==arm,'NOT_PRESAMPLED_ORIGINAL_PROPOSAL')
                original=copy.deepcopy(proposal);identity_sha=original.pop('proposal_identity_sha256');require(digest(original)==identity_sha,'PROPOSAL_CANONICAL_IDENTITY')
                require(proposal['approved_contract_sha256']==identity['approved_contract_sha256'] and proposal['features']==context['features'] and proposal['feature_names']==context['feature_names'],'PROPOSAL_CAUSAL_INPUT_CHANGED')
                require(proposal['causal_features_sha256']==feature_sha and proposal['baseline_evaluation_only']==baseline,'PROPOSAL_SAME_PARENT_B')
                ai=proposal['action_index'];require(type(ai) is int and ai in range(5) and proposal['proposal_recipe']==recipes[ai] and proposal['proposal_recipe_sha256']==hashes[ai],'PROPOSED_FULL_RECIPE_NOT_MENU')
                pred=R.json(P/'predictions'/(ident+'.json'));require(pred['proposal_file_sha256']==R.sha(proposal_path) and pred['proposal_identity_sha256']==identity_sha,'PREDICTION_PROPOSAL_SHA')
                require(pred['collection_policy_sha256']==proposal['collection_policy_sha256'] and pred['created_unix']<=events[(ident,'START')]['record']['unix'],'PROPOSAL_NOT_BOUND_BEFORE_PHYSICS')
                require(number(proposal['old_logprob']) and proposal['old_logprob']<=0 and type(proposal['collection_policy_version']) is int,'BEHAVIOR_PROVENANCE_MISSING')
                row=R.json(P/'attempts'/(ident+'_RESULT.json'));require(row['branch']['full_hash']==parent,'INDEPENDENT_ATTEMPT_NOT_SAME_ACTUAL_FORK_PARENT')
                proof=full_physical(R,P,row,recipes[ai],events);receipt=R.json(P/spec['output_directory']/(tag+'_PHYSICAL_RECEIPT.json'));raw_receipts[ident]=receipt
                require(receipt['engineering_complete'] is True and receipt['ownership_and_causality_audit_pass'] is True and receipt['true_hard_safety_violation'] is False,'ENGINEERING_OR_UNKNOWN_SAFETY_SAMPLE_EXCLUDED')
                for key in ('attempt_start_sha256','attempt_end_sha256'):
                    kind='START' if key=='attempt_start_sha256' else 'END';require(receipt[key]==proof['events_original_records_and_hash_scopes'][kind]['canonical_record_sha256'],'RECEIPT_EVENT_CANONICAL_SHA')
                for key in ('result_source_sha256','native_ownership_sha256','applied_reference_receipt_stream_sha256','actual_new_native_steps','complete','original_qualified','JF_N_s','JM_Nm_s'):
                    require(receipt[key]==proof[key],'RECEIPT_NOT_ORIGINAL:'+key)
                require(receipt['applied_stream_scope']['container_sha256']==proof['raw_container_sha256'] and receipt['events_original_records_and_hash_scopes']==proof['events_original_records_and_hash_scopes'],'RAW_OR_EVENT_HASH_SCOPES_CHANGED')
                require(receipt['attempt_id']==ident and receipt['arm_id']==arm and receipt['selected_full_recipe_sha256']==hashes[ai] and receipt['proposal_identity_sha256']==identity_sha,'RECEIPT_IDENTITY_MISMATCH')
                behavior={'policy_sha256':proposal['collection_policy_sha256'],'version':proposal['collection_policy_version'],'old_logprob':proposal['old_logprob'],'arm_id':arm,'proposal_file_sha256':R.sha(proposal_path),'physical_receipt_file_sha256':R.sha(P/spec['output_directory']/(tag+'_PHYSICAL_RECEIPT.json'))}
                rows.append(common_record(ident=ident,context=context,case_sha=config['case_sha256'],parent=parent,recipe=recipes[ai],index=ai,row=row,proof=proof,base=base,origin='GENUINE_PG_PHYSICAL_SAMPLE_NOW_REUSED_OFFPOLICY',behavior=behavior));proposals.append(proposal)
    require(len(rows)==16 and len({r['attempt_id'] for r in rows})==16,'EXACT_SIXTEEN_FRESH_ACTUAL_ATTEMPTS')
    # Bind first/final pending and the 16 originals without model restore/forward.
    first_config=configs[0];first_path=P/first_config['onpolicy_sampling']['output_directory']/'PENDING_CHECKPOINTS.json';first=R.json(first_path)
    require(R.sha(first_path)==meta['first_job_pending_sha256'],'FIRST_PENDING_ORIGINAL_SHA')
    for arm in ARMS:
        arm_pending=pending['snapshots'][arm]['pending'];require(arm_pending[:len(first['snapshots'][arm]['pending'])]==first['snapshots'][arm]['pending'],'FIRST_PENDING_PREFIX_CHANGED')
        originals=[p for p in proposals if p['arm_id']==arm];require(len(arm_pending)==len(originals)==4,'ARM_REAL_PENDING_COUNT')
        previous=computation['previous_pointer']['checkpoints'][arm];require(R.sha(P/previous['path'])==previous['sha256'],'PRIOR_CHECKPOINT_SHA')
        prior=R.json(P/previous['path']);previous_rng=prior['rng'];policy_sha=policy_identity(prior['policy'])
        require(policy_identity(pending['snapshots'][arm]['policy'])==policy_sha,'SAMPLING_POLICY_CHANGED')
        for saved,original in zip(arm_pending,originals):
            detached=copy.deepcopy(saved);attached=detached.pop('physical_result');expected=copy.deepcopy(original);expected.pop('physical_result')
            require(detached==expected and attached['driver_receipt_errors']==[],'PENDING_NOT_ORIGINAL_OR_DRIVER_ERROR')
            require(attached=={**raw_receipts[original['attempt_id']],'driver_receipt_errors':[]},'PENDING_ATTACHED_RECEIPT_NOT_EXACT_ORIGINAL_FILE')
            require(original['collection_policy_sha256']==policy_sha and original['collection_policy_version']==prior['policy']['version'],'BEHAVIOR_NOT_PRIOR_SAMPLING_POLICY')
            require(digest(original['rng_before'])==digest(previous_rng),'ORIGINAL_SAMPLING_RNG_CHAIN_BROKEN');previous_rng=original['rng_after']
        require(digest(previous_rng)==digest(pending['snapshots'][arm]['rng']),'FINAL_PENDING_RNG_CHANGED')
        require(meta['preflights'][arm]['admissible'] is True,'NONADMISSIBLE_COMMITTED_ARM')
    fresh=copy.deepcopy(rows)
    require(R.sha(P/HIST)==HIST_SHA and R.sha(P/SCOPED)==SCOPED_SHA,'HISTORICAL_DATA_IDENTITY_CHANGED')
    old=R.json(P/HIST);scoped=R.json(P/SCOPED);require(len(old['rows'])==48 and [m['action_recipe'] for m in old['menu']]==recipes,'HISTORICAL_NOT_EXACT_SAME_FIVE_RECIPES')
    scoped_by_group={r['group_evaluation_only']:r for r in scoped['records']}
    groups_old={r['group'] for r in old['rows']}
    for group in sorted(groups_old):
        source_rows=[r for r in old['rows'] if r['group']==group];Brow=next(r for r in source_rows if r['action_recipe_sha256']==hashes[0]);package_old=(R.repo/Brow['source_result']).parents[1]
        context_path=R.path(scoped_by_group[group]['source_payload_path']);require(R.sha(context_path)==scoped_by_group[group]['source_payload_file_sha256'],'HISTORICAL_RAW_PAYLOAD_SHA')
        context=converter.to_context25(R.json(context_path));require(context_equal(context,Brow['context']),'HISTORICAL_CONTEXT25_QA_IDENTITY')
        capture_proof(R,package_old,R.json(package_old/'experiments'/(group+'.json')))
        events=R.events(package_old,{r['id'] for r in source_rows});B=R.json(R.repo/Brow['source_result']);baseproof=full_physical(R,package_old,B,recipes[0],events)
        parent=Brow['parent_evaluation_only']['snapshot_full_hash'];feature_sha=digest({'names':context['feature_names'],'values':context['features']})
        require(B['branch']['full_hash']==parent,'HISTORICAL_BASELINE_PARENT')
        base={'complete':True,'original_qualified':B['qualified'],'JF_N_s':B['JF'],'JM_Nm_s':B['JM'],'result_source_sha256':baseproof['result_source_sha256'],'parent_fingerprint':parent,'full_recipe_sha256':hashes[0],'causal_features_sha256':feature_sha,'original_evidence':baseproof}
        protocol=R.json(package_old/'runtime/MOTION_ACCEPTANCE_PROTOCOL.json');require(digest(protocol)==digest(R.json(P/'runtime/MOTION_ACCEPTANCE_PROTOCOL.json')),'HISTORICAL_PROTOCOL_CHANGED')
        for oldrow in source_rows:
            ai=hashes.index(oldrow['action_recipe_sha256']);require(oldrow['action_recipe']==recipes[ai] and context_equal(oldrow['context'],context),'HISTORICAL_RECIPE_OR_CONTEXT_CHANGED')
            row=R.json(R.repo/oldrow['source_result']);labels=oldrow['labels_evaluation_only']
            require(row['branch']['full_hash']==parent and row['JF']==labels['JF_N_s'] and row['JM']==labels['JM_Nm_s'] and row['qualified']==labels['original_qualified'],'HISTORICAL_ORIGINAL_LABEL_PARENT_CHANGED')
            require(row['motion_vs_B']['failed_requirements']==labels['motion_failed_requirements'],'HISTORICAL_ORIGINAL_MOTION_CHANGED')
            proof=baseproof if row['id']==B['id'] else full_physical(R,package_old,row,recipes[ai],events)
            rows.append(common_record(ident=row['id'],context=context,case_sha=oldrow['identity_evaluation_only']['case_sha256'],parent=parent,recipe=recipes[ai],index=ai,row=row,proof=proof,base=base,origin='AUDITED_HISTORICAL_PHYSICAL_TABLE_OFFPOLICY',behavior=None))
    require(len(rows)==64 and len({r['attempt_id'] for r in rows})==64,'AGGREGATE_ROW_IDENTITY')
    # Metadata-only grouping; no fabricated outcome for missing case/action.
    audit={}
    for cohort,records in [('AGGREGATE64',rows),('FRESH16',fresh)]:
        cases={r['split_case_sha256_evaluation_only'] for r in records};keys={r['same_context_action_key_evaluation_only'] for r in records}
        audit[cohort]={'actual_rows':len(records),'independent_case_groups':len(cases),'unique_context_action_keys':len(keys),'repeated_actual_samples':len(records)-len(keys),'action_counts':{tag:sum(r['action_index']==i for r in records) for i,tag in enumerate(TAGS)},'split_group':'case_sha256; duplicates of same case never cross fold','missing_actions_not_imputed':True}
    require(time.time()<DEADLINE,'GLOBAL_DEADLINE_AFTER_READ_ONLY_BUILD')
    dataset={'schema':'v8.audited_sac_offpolicy_dataset.v2','cohorts':{'AGGREGATE64':rows,'FRESH16':fresh},'primary_cohort':'AGGREGATE64','feature_names':rows[0]['feature_names'],'full_recipe_sha256':hashes,'action_contracts':recipes,'audit':audit,'all_development_exposed':True,'sealed_reads':0,'new_physics':0,'physical_attempt_savings':0,'new_fit_or_forward':0,'source_binding_sha256':R.sha(binding_path),'source_manifest_sha256':R.sha(source_manifest_path)}
    final=resource.getrusage(resource.RUSAGE_SELF)
    manifest={'schema':'v8.audited_sac_offpolicy_dataset_manifest.v2','dataset_canonical_sha256':digest(dataset),'row_canonical_sha256':{r['attempt_id']:digest(r) for r in rows},'files_sha256':R.files,'binding_sha256':R.sha(binding_path),'build_wall_s':time.time()-start,'CPU_user_s':final.ru_utime-cpu_initial.ru_utime,'CPU_system_s':final.ru_stime-cpu_initial.ru_stime,'RSS_peak_KiB':final.ru_maxrss,'new_fit_or_forward_or_physics':0,'excluded_groups':[{'group':'V8OP01H','generation':'GENERATION_0001','reason':'CANCELLED_ENGINEERING_PARTIAL_BATCH; original physics retained, not replay'}],'historical_behavior_logprob_not_fabricated':True,'source_receipt_reuse_is_not_new_onpolicy_or_saved_physics':True}
    return dataset,manifest
