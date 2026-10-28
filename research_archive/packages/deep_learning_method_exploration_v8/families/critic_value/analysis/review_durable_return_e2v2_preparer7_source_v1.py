"""独立AST/JSON/source SHA审查；不import被审模块，不读权重/raw/val。"""
from pathlib import Path
import ast,copy,hashlib,json,time
P=Path(__file__).resolve().parents[3];A=Path(__file__).resolve().parent;F='families/ppo_reward/continuous_scale_v1/';E='families/learning_assisted/common_out0_v2/'
checks=[];refs={}
def sha(rel):
 assert '/fits/' not in rel and '/fit_run' not in rel and not rel.endswith(('.gz','.npz'))
 refs[rel]=hashlib.sha256((P/rel).read_bytes()).hexdigest();return refs[rel]
def tree(rel):sha(rel);return ast.parse((P/rel).read_text(),filename=rel)
def load(rel):sha(rel);return json.loads((P/rel).read_text())
def dump(t):return ast.dump(t,include_attributes=False)
def check(n,v):checks.append({'check':n,'PASS':bool(v)})
def func(t,name):return next(n for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name==name)
def assigned(t,name):return next(n for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id==name for x in n.targets))
def reset_globals(new,old,names):
 for name in names:assigned(new,name).value=copy.deepcopy(assigned(old,name).value)
old=tree('source/v8_comparative_validation_candidate_v3.py');new=tree('source/v8_comparative_validation_candidate_v4.py')
normal=copy.deepcopy(new);call=func(normal,'call');oldcall=func(old,'call')
added=[n for n in call.body if (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='receipt_path' for t in n.targets)) or (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='save')]
check('core_exact_two_added_statements',len(added)==2);call.body=[n for n in call.body if n not in added]
receipt_removals=0
for node in ast.walk(call):
 if isinstance(node,ast.Dict):
  for i in range(len(node.keys)-1,-1,-1):
   if isinstance(node.keys[i],ast.Constant) and node.keys[i].value=='receipt':node.keys.pop(i);node.values.pop(i);receipt_removals+=1
check('core_one_RETURN_receipt_ref_added',receipt_removals==1)
check('core_entire_AST_equal_after_only_receipt_removal',dump(old)==dump(normal))
check('core_return_original_result',isinstance(func(new,'call').body[-1],ast.Return) and isinstance(func(new,'call').body[-1].value,ast.Name) and func(new,'call').body[-1].value.id=='result')
check('core_owner_save_unchanged',dump(func(old,'save'))==dump(func(new,'save')) and dump(func(old,'owner'))==dump(func(new,'owner')))
co=tree(F+'comparative_composer_v4_candidate_v4.py');cn=tree(F+'comparative_composer_v4_candidate_v5.py');reset_globals(cn,co,['V3','V3_SHA']);check('composer_only_core_path_SHA',dump(co)==dump(cn))
wo=tree('source/v8_comparative_validation_v6.py');wn=tree('source/v8_comparative_validation_v7.py')
for n in ast.walk(wn):
 if isinstance(n,ast.ImportFrom) and n.module=='comparative_composer_v4_candidate_v5':n.module='comparative_composer_v4_candidate_v4'
check('wrapper_only_composer_import',dump(wo)==dump(wn))
authority=load('audit/COMPARATIVE_DURABLE_API_RETURN_MAIN_SOURCE_REVIEW_V1.json')
for rel,h in authority['source_files_sha256'].items():check('durable_main_source_SHA:'+rel,sha(rel)==h)
eo=tree(E+'frozen_live_e2_candidate_v1.py');en=tree(E+'frozen_live_e2_candidate_v2.py');reset_globals(en,eo,['MANIFEST','CONTRACT'])
def normguard(t):
 return next(n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='need' and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value=='E2_LIVE_SAME_TRAIN_NORMALIZER')
oldguard=normguard(eo);newguard=normguard(en)
check('E2_outer_only_normalizer_remains',isinstance(newguard.args[0],ast.Compare) and dump(newguard.args[0])==dump(ast.parse("paired_entry['normalizer'] == norm",mode='eval').body))
oldguard.args[0]=copy.deepcopy(newguard.args[0]);check('E2_entire_AST_same_after_allowed_schema_and_paths',dump(eo)==dump(en))
check('E2_inner_exact_checks_retained',"model['kind'] == 'MLP_PAIRED' and model['paired'] is True" in (P/E/'frozen_live_e2_candidate_v2.py').read_text() and "model['action_only'] is False" in (P/E/'frozen_live_e2_candidate_v2.py').read_text())
ew0=tree(E+'live_selector_e2_v3_wrapper_candidate_v1.py');ew1=tree(E+'live_selector_e2_v3_wrapper_candidate_v2.py');reset_globals(ew1,ew0,['SELF','MANIFEST','TARGET','TARGET_SHA']);check('E2_wrapper_only_identity_constants',dump(ew0)==dump(ew1))
c0=load(E+'FROZEN_LIVE_E2_CONTRACT_V1.json');c1=load(E+'FROZEN_LIVE_E2_CONTRACT_V2.json');a=copy.deepcopy(c0);b=copy.deepcopy(c1)
for k in ['schema','status','created_unix']:a.pop(k);b.pop(k)
for k in ['V2_minimum_schema_repair','actual_bundle_schema']:b.pop(k)
a['math_parity_plan'].pop('status');b['math_parity_plan'].pop('status');check('E2_contract_same_math_permissions_budgets_bundles',a==b)
m0=load(E+'FROZEN_LIVE_E2_SOURCE_MANIFEST_V1.json');m1=load(E+'FROZEN_LIVE_E2_SOURCE_MANIFEST_V2.json');wm=load(E+'LIVE_SELECTOR_E2_V3_WRAPPER_MANIFEST_V2.json')
for rel,h in m1['old_sources_preserved'].items():check('E2_old_bytes_preserved:'+rel,sha(rel)==h)
for rel,h in wm['files_sha256'].items():check('E2_new_wrapper_manifest_SHA:'+rel,sha(rel)==h)
for rel,h in m1['files_sha256'].items():
 if '/fits/' in rel or '/fit_run' in rel:check('E2_original_model_bundle_identity_map_unchanged:'+rel,m0['files_sha256'].get(rel)==h)
 else:check('E2_manifest_existing_source_metadata_SHA:'+rel,sha(rel)==h)
check('E2_original_predictor_source_identity',m0['files_sha256'][E+'e2_models_candidate_v1.py']==m1['files_sha256'][E+'e2_models_candidate_v1.py'])
check('E2_same_frozen_weight_ref',c0['bundles']==c1['bundles'] and c1['V2_minimum_schema_repair']['bundle_unchanged_sha256']==c0['bundles']['E2']['sha256'])
prep='scripts/prepare_frozen_comparison_v4_v7.py';pt=tree(prep);pub='scripts/publish_complete_prevalidation_freeze_v3.py';put=tree(pub)
check('preparer_source_SHA',refs[prep]=='c0c67f0c7a37826678260932430d44bd8b70df813203267fc58cba64cf96f3df')
check('publisher_source_SHA',refs[pub]=='17d579bd5bd889ffca9d7292aa905c9bc8c3536eaf22ced32e298da126437fd9')
check('preparer_new_unique_groups',ast.literal_eval(assigned(pt,'GROUPS').value)==['V8FROZENENG02','V8VAL03','V8VAL04'])
pt6=tree('scripts/prepare_frozen_comparison_v4_v6.py')
def route_body(t):
 return next(n.body for n in ast.walk(t) if isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=='index')
check('preparer_original_route_case_seed_assignment_AST_unchanged',all(dump(a)==dump(b) for a,b in zip(route_body(pt6),route_body(pt))) and len(route_body(pt6))==len(route_body(pt)))
ps=(P/prep).read_text();pubs=(P/pub).read_text()
for text in ['source/v8_comparative_validation_candidate_v4.py','source/v8_comparative_validation_v7.py','comparative_composer_v4_candidate_v5.py','FROZEN_LIVE_E2_SOURCE_MANIFEST_V2.json','live_selector_e2_v3_wrapper_candidate_v2.py','NEURALQ_FROZEN_OUT0_MAIN_AUTHORIZATION_V2.json','A5_FROZEN_OUT0_MAIN_SOURCE_APPROVAL_V2.json','expected_core_pre_B_decision_count=153','source_files_sha256','axis[\'source_files_sha256\']']:
 check('preparer_required_source_or_guard:'+text,text in ps)
for rel in ['freeze/NEURALQ_FROZEN_OUT0_MAIN_AUTHORIZATION_V2.json','freeze/A5_FROZEN_OUT0_MAIN_SOURCE_APPROVAL_V2.json']:
 doc=load(rel);check('new_main_auth_groups:'+rel,doc['authorized_groups']==['V8FROZENENG02','V8VAL03','V8VAL04'])
for token in ["integration['group']=='V8FROZENENG02'","integration['all_owned_closed'] is True","integration['read_only_model_identity_and_inference_review_pass'] is True","integration['new_parameter_outcome_used_for_repair_or_selection'] is False",'source/v8_comparative_validation_candidate_v4.py','source/v8_comparative_validation_v7.py','comparative_composer_v4_candidate_v5.py','frozen_live_e2_candidate_v2.py','live_selector_e2_v3_wrapper_candidate_v2.py','UNRESOLVED_PREFIX_UNKNOWN_NO_CANCEL_NO_COMMIT_NO_ENDPOINT_UPDATES','physics_dispatch_authorized=False']:
 check('publisher_required_scope:'+token,token in pubs)
draft=load('families/history_conditioned/audit/DRAFT_ROOT_MASTER_INVENTORY_REFERENCES_V2.json');check('draft_7_model_containers',len(draft['model_inventory'])==7)
check('publisher_explicit_no_new_parameter_START_before_master','NEW_PARAMETER_PHYSICS_ALREADY_OPENED' in pubs and "parameter_shas={item['payload_sha256'] for item in routes}" in pubs)
check('metadata_builders_no_candidate_or_numeric_imports',all(not any((n.module or '').startswith(('numpy','torch','mujoco','beta_policy','frozen_live')) for n in ast.walk(t) if isinstance(n,ast.ImportFrom)) and all(not any(a.name.startswith(('numpy','torch','mujoco','beta_policy','frozen_live')) for a in n.names) for n in ast.walk(t) if isinstance(n,ast.Import)) for t in [pt,put]))
notes=[{'scope':'durable_return','conclusion':'PASS_SCOPED_SOURCE_ONLY','detail':'每成功call先owner-save原return和counts，再fsync RETURN事件并绑定path/SHA；函数结果仍原对象返回，原数值/调用顺序/动作/安全AST一致。不能回填ENG01丢失payload，不新增推理。'}, {'scope':'IO_durability_boundary','detail':'acl2.put=tmp.write_text(close)+replace，无receipt文件fsync/目录fsync；append有fsync。覆盖后继普通adapter异常；不承诺掉电事务、任意I/O错误或强杀精确尾部工作。写入失败时API_returned已加，仍必须保留失败/未知，不能自动重跑。'}, {'scope':'E2_V2','conclusion':'PASS_MINIMUM_SOURCE_SCHEMA_REPAIR_CANARY_NOT_RUN_BY_REVIEWER','detail':'只移除outer缺字段访问；normalizer与inner model三项约束及预测后端完全保留。原weight refs不变，不称真实schema已实测；旧approval不能复用，新manifest/contract SHA需要新授权。'}, {'scope':'preparer_V7','conclusion':'PASS_SOURCE_ONLY_NEW_UNIQUE_GROUPS_ORIGINAL_ROUTES','detail':'ENG02/VAL03/VAL04新名称，原route index-1/seed/case赋值AST不变；core4/composer5/wrapper7/E2V2/readonlyauthV2及axis闭包保留；canary后E2三个新group auth尚由root另写，未执行本preparer。'}, {'scope':'publisher_V3','conclusion':'PASS_SCOPED_SOURCE_ONLY_NOT_PUBLISHED','detail':'依赖ENG02只读推理/owner closed审查、五份配置、未开原两个parameter case、7族draft及C4模板精确SHA；保留Beta全局UNKNOWN，source/metadata不派发物理。'}, {'scope':'operative_contract_documentation','detail':'publisher新procedure显式加入E2V2两个py，V2contract/manifest经新config进入frozen_artifacts；draft旧E2 V1合同仍是generic provenance行而非新operative行。可另补V2 contract/manifest operative引用提高可读性，当前runtime闭包不会用旧合同，无确定执行阻塞。'}, {'scope':'metadata_publication_limits','detail':'preparer/publisher open(x)顺序写入非整组原子事务；若未来失败保留partial，不覆盖/自动补成功。新文件/主权限实际存在性、canary PASS、integration PASS、master/C4闭包须由root后续实际检查，本审不生成它们。'}]
result={'status':'SOURCE_ONLY_AST_DIFF_PASS_NO_DETERMINISTIC_BLOCKER' if all(x['PASS'] for x in checks) else 'SOURCE_REVIEW_HAS_BLOCKERS','created_unix':time.time(),'checks':checks,'failed_checks':[x for x in checks if not x['PASS']],'source_and_metadata_sha256':refs,'notes':notes,'operations':{'candidate_or_fixture_or_helper_calls':0,'model_import_restore_forward_fit_physics':0,'weights_raw_trace_or_newval_payload_reads':0,'config_source_master_or_permission_mutations':0}}
dest=A/'DURABLE_RETURN_E2V2_PREPARER7_SOURCE_REVIEW_V1.json'
with dest.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'status':result['status'],'checks':len(checks),'failed_checks':result['failed_checks'],'review_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'operations':result['operations']},ensure_ascii=False))
