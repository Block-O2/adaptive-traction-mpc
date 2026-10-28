"""仅原失败JSON/JSONL、源码和proc身份；不重跑推理、raw、trace或replay。"""
from pathlib import Path
import hashlib,json,os,resource,time

P=Path(__file__).resolve().parents[3];D=Path(__file__).resolve().parent/'v8frozeneng01_preb_failure_metadata_v1'
assert not D.exists();D.mkdir();started=time.monotonic();cpu=time.process_time();refs={};checks=[]
G='V8FROZENENG01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(rel):
 assert not rel.endswith(('.gz','.npz')) and '/real_runs/' not in rel and '/onpolicy_runs/' not in rel and '/fit_run' not in rel and '/fits/' not in rel
 p=P/rel;refs[rel]=sha(p);return json.loads(p.read_text())
def check(name,value):checks.append({'check':name,'PASS':bool(value)})
begin=read('owned/'+G+'_SUPERVISOR.json');end=read('owned/'+G+'_SUPERVISOR_END.json');exitrow=read('owned/'+G+'_EXIT.json');done=read('jobs/'+G+'/WORKER_DONE.json')
partial=read('runtime/output/'+G+'_parent_PARTIAL_COMPUTE.json');selector=read('analysis/'+G+'_SELECTOR_ERROR.json');composer=read('analysis/'+G+'_V4_COMPOSER_ERROR.json')
config=read('experiments/'+G+'.json');job=read('jobs/'+G+'/SOURCE_MANIFEST.json')
check('config_exact_original',refs['experiments/'+G+'.json']=='19b569452eef62f0e98d5419e0fc3d7802af87f4bc2e6e34465ab49d0571588c' and begin['config_sha256']==refs['experiments/'+G+'.json'])
check('closed_failed_original_owner',end['state']=='STOP' and end['worker_exit_code']==1 and end['survivors']==[] and exitrow['active_child'] is None and done['status']=='FAILED_PRESERVED' and done['rows']==[])
identities=list(end['known_owned'].values())+[begin['identity']];closures=[]
for ident in identities:
 if ident is None:continue
 p=Path('/proc')/str(ident['pid'])/'stat';ticks=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
 check('closed_original_PID:'+str(ident['pid']),ticks!=ident['start_ticks']);closures.append({'original':ident,'now_start_ticks':ticks,'original_closed':ticks!=ident['start_ticks']})
ep=P/'analysis'/f'{G}_INFERENCE_EVENTS.jsonl';refs[str(ep.relative_to(P))]=sha(ep)
events=[]
for n,raw in enumerate(ep.read_bytes().splitlines(),1):
 event=json.loads(raw);events.append({'line1':n,'rawline_sha256':hashlib.sha256(raw).hexdigest(),'record':event})
starts=[x['record'] for x in events if x['record']['event']=='START'];returns=[x['record'] for x in events if x['record']['event']=='RETURN']
check('macro30started29returned',len(starts)==selector['counts']['API_started']==30 and len(returns)==selector['counts']['API_returned']==29)
check('macro_owner_identity',all(x['record']['owner_pid']==begin['worker']['pid'] for x in events))
check('NQ_return_E2_started_A5_not_reached','NEURAL_Q_V3' in [x['label'] for x in returns] and 'E2_V1' in [x['label'] for x in starts] and 'E2_V1' not in [x['label'] for x in returns] and 'A5_V1' not in [x['label'] for x in starts])
check('error_preserved_at_all_layers',selector['error']==composer['error']==done['error'])
prefix='E2_V3_THIN_WRAPPER_FAILED:';assert selector['error'].startswith(prefix)
outer=json.loads(selector['error'][len(prefix):]);receipt=outer['original_InferenceFailure_receipt'];c=receipt['counters']
check('outer_kind_schema_failure',outer['error_type']=='InferenceFailure' and outer['error']=="'kind'" and receipt['stage']=='FROZEN_E2_COSTS' and receipt['status']=='FAILED_NO_CHOICE_NO_RETRY' and outer['automatic_retry'] is False)
check('E2_actual_paid2API10vectors',c['prediction_API_calls']==2 and c['prediction_query_vectors']==10 and receipt['backend_kinds']=={'RIDGE_KNOT_MATRIX':{'API_calls':2,'query_vectors':10}})
check('E2_A3risk_Bpaired_not_reached',c['A3_predict_API_attempts']==c['A3_predict_API_returns']==c['completed_A3_risk_logits']==c['completed_A3_cost_dot_outputs']==c['shared_B_inference_forward_API_calls']==0)
check('no_method_fit_or_physics_in_E2',receipt['fit']==receipt['physics']==selector['counts']['new_fit']==0)
check('composer_beta_and_proposals_NOT_RUN',composer['counts']['beta_extension_entry']==composer['counts']['beta_extension_completed']==composer['counts']['physical_proposals_yielded_to_original_worker']==0 and composer['completed_tags']==[])
proof=receipt['proof_audit'];check('E2_actual_sourceproof_checked',proof['actual_in_memory_callback_code_checked'] is True and proof['current_task_B_or_candidate_result_used'] is False and proof['config_sha256']==refs['experiments/'+G+'.json'] and proof['job_source_manifest_sha256']==refs['jobs/'+G+'/SOURCE_MANIFEST.json'])
for role,row in proof['roles'].items():check('actual_E2_sourceproof_role:'+role,job['files'][row['path']]==row['actual_file_sha256']==row['expected_profile_sha256']==row['job_manifest_file_sha256'])
physical=[]
with (P/'runtime/ATTEMPTS.jsonl').open('rb') as f:
 for n,raw in enumerate(f,1):
  if ('"'+G+'_').encode() not in raw:continue
  record=json.loads(raw)
  if not str(record.get('id','')).startswith(G+'_'):continue
  physical.append({'line1':n,'rawline_without_newline_sha256':hashlib.sha256(raw.rstrip(b'\n')).hexdigest(),'record':record})
pstart=[x['record'] for x in physical if x['record']['event']=='START'];pend=[x['record'] for x in physical if x['record']['event']=='END']
check('only_parent_physical_START_END',len(pstart)==len(pend)==1 and pstart[0]['id']==pend[0]['id']==G+'_parent' and pend[0]['returncode']==1 and pend[0]['joined'] is True)
check('physical_START_source_identity',pstart[0]['config_sha256']==refs['experiments/'+G+'.json'] and pstart[0]['job_source_sha256']==refs['jobs/'+G+'/SOURCE_MANIFEST.json'])
check('partial_parent_paid40200',partial['actual_new_native_physics_steps']==partial['native_physics_steps']==40200 and partial['actual_new_main_model_inverse_dynamics_api_calls']==partial['main_model_inverse_dynamics_api_calls']==8131 and abs(partial['actual_new_simulation_seconds']-10.05)<1e-9 and partial['status']=='FAILED_UNRANKED' and partial['valid'] is False)
nqrel='families/il_dagger_sac/neural_q_v2/FROZEN_LIVE_SOURCE_MANIFEST_V3.json';nq=read(nqrel)
for rel in ['families/il_dagger_sac/neural_q_v2/frozen_live_adapter_candidate_v3.py','families/il_dagger_sac/neural_q_v2/frozen_live_api_candidate_v3.py','families/learning_assisted/common_out0_v2/frozen_live_e2_candidate_v1.py','source/v8_comparative_validation_candidate_v3.py']:
 refs[rel]=sha(P/rel);check('actual_failure_sourcepin:'+rel,job['files'][rel]==config['frozen_artifacts'][rel]==refs[rel])
check('successful_NQ_count_manifest',nq['per_context_counts']['logical_model_restores']==63 and nq['per_context_counts']['named_total_model_forwards']==63 and nq['per_context_counts']['matrix_products']==105 and nq['per_context_counts']['scalar_outputs']==315)
output_missing=not (P/'predictions'/f'{G}_FROZEN_CONTEXT_DECISIONS.json').exists()
check('no_complete_preB_selection_artifact',output_missing)
paid={'evidence_grade_A_original_events_and_failure_receipt':{'top_API_started':30,'top_API_returned':29,'E2_backend_API_entries':2,'E2_backend_query_vectors':10,'E2_backend_kinds':receipt['backend_kinds'],'E2_A3_risk_API_attempts':0,'E2_paired_shared_B_forward':0,'A5_top_API_entries':0,'Beta_extension_entries':0,'child_physical_START':0,'parent_new_native_steps':40200,'parent_new_main_model_inverse_calls':8131},'evidence_grade_B_fixed_return_path_reconstruction_not_perhead_original_ledger':{'NQ_return_event_present':True,'NQ_per_context_counts':nq['per_context_counts'],'basis':'冻结adapter返回路径已完成restore_fixed、predict_fixed和68选择断言，原macro RETURN落盘；generic在整组成功前不保存extension payload，故无独立逐head实际counter对象/预测值副本。未重跑。'},'explicit_unknowns':{'other_successful_macros_complete_nested_numeric_total':'UNKNOWN_IN_THIS_METADATA_AUDIT_NOT_ZERO; 29RETURN的原API工作保留，不能把composer restore0看成全job restore0','unpersisted_NQ_predicted_values_or_choices':'NOT_RECOVERED_NO_REPREDICTION','parent_full_task_qualification':'PARTIAL_NOT_RANKED_NOT_PASS','parent_hard_safety_all11':'UNKNOWN_NOT_REPLAYED'},'NOT_RUN':{'A5':'无START，调用/dots均0','Beta_mean_and_grid':'composer entry0，0mean/0fixedmap','C_history_afterB':'无B child START，未到达'}}
result={'status':'FAILED_ENGINEERING_SCHEMA_PRESERVED_OWNERS_CLOSED_PAID_PREFIX_ACCOUNTED','checked_unix':time.time(),'checks':checks,'failed_checks':[x for x in checks if not x['PASS']],'original_error_type':"KeyError 'kind' wrapped InferenceFailure/RuntimeError",'failure_location':'frozen_live_e2_candidate_v1.py paired_entry outer kind check after D4 two knot predictions; not learned cost/motion failure','original_file_references_sha256':refs,'inference_event_evidence':events,'scoped_original_physical_events':physical,'other_job_ATTEMPTS_rows_not_parsed':True,'owner_closure':closures,'original_supervisor_wall_s':end['wall_s'],'partial_compute_original':partial,'paid_work':paid,'task_native_steps':{'value':0,'basis':'OUT0 callback在B前异常，0child START/0proposal yielded；原parent终止于10.05/40200，不推进TASK continuation。非新trace统计。'},'E2_original_failure_receipt':receipt,'thin_wrapper_owner_proof':outer['thin_wrapper_owner_proof'],'metadata_pass_does_not_validate_real_model_schema':True,'prior_1181check_review_not_overwritten':'只检SHA/注册/auth，未执行真实模型结构；本次actual integration暴露其不覆盖的outer schema错误','no_method_family_failure_claim':True,'no_automatic_retry_or_new_physics_authority':True,'audit_operations':{'new_candidate_or_helper_calls':0,'model_restore_forward_fit_physics':0,'raw_trace_or_replay_reads_calls':0,'actual_config_or_permission_mutations':0},'audit_resource':{'PID':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'wall_s':time.monotonic()-started,'CPU_s':time.process_time()-cpu,'RSS_peak_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}}
with (D/'RESULT.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'status':result['status'],'checks':len(checks),'failed_checks':result['failed_checks'],'result_sha256':sha(D/'RESULT.json'),'original_owners_checked':len(closures),'paid':paid['evidence_grade_A_original_events_and_failure_receipt'],'audit_operations':result['audit_operations'],'audit_resource':result['audit_resource']},ensure_ascii=False))
