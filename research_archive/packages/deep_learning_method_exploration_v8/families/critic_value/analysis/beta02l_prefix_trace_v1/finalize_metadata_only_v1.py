"""只读已存结果/源码/JSON元数据；绝不读取raw或trace数组。"""
from pathlib import Path
import hashlib,json,os,time

D=Path(__file__).resolve().parent;P=D.parents[3]
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
r=load(D/'run_once_v1/RESULT.json');u=load(D/'run_once_v1/RESOURCE.json')
old=P/'families/critic_value/analysis/beta02l_parent_prefix_v1/PARENT_PREFIX_REVIEW_V1.json';v=load(old)
sump=P/'runtime/source/results/V8BETA02L_B/summary.json';s=load(sump)
jobp=P/'jobs/V8BETA02L/SOURCE_MANIFEST.json';job=load(jobp)
pid=u['END']['PID'];pp=Path('/proc')/str(pid)/'stat'
now_start=int(pp.read_text().rsplit(')',1)[1].split()[19]) if pp.exists() else None
closure={'PID':pid,'original_start_ticks':u['END']['start_ticks'],'now_start_ticks':now_start,'original_process_closed':now_start!=u['END']['start_ticks'],'tool_exit_code':0,'checked_unix':time.time()}
assert closure['original_process_closed']
save(D/'PID_CLOSURE_V1.json',closure)
scpath='runtime/source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py'
role_sources={}
for q in [scpath,'runtime/source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/fast_plant.py']:
 role_sources[q]={'actual_sha256':sha(P/q),'job_expected_sha256':job['files'][q]};assert role_sources[q]['actual_sha256']==role_sources[q]['job_expected_sha256']
g=r['remaining6']
scope={
 'torque':{'full_fast_prefix_observations':True,'value':g['torque']['value'],'native_continuous_guarantee':False},
 'human_speed':{'full_fast_prefix_observations':True,'value':g['human_speed']['value'],'native_continuous_guarantee':False},
 'robot_speed':{'full_fast_prefix_observations':True,'value':g['robot_speed']['value'],'native_continuous_guarantee':False},
 'human_acceleration':{'full_fast_prefix_observations':False,'value':None,'observed_valid_only_formula_pass':g['human_acceleration']['value'],'ACTIVE_RECOVERY_valid_rows':605,'COMMISSIONING_invalid_or_unrecorded_rows':1406,'original_source':'ACTIVE row实际记录split.human_motion_valid；COMMISSIONING row未记录acceleration，序列化默认False/NaN，不能按False视为物理无越限'},
 'session_clearance':{'full_fast_prefix_observations':False,'value':None,'ACTIVE_RECOVERY_finite_rows':605,'COMMISSIONING_missing_rows':1406,'original_source':'session shank contract在commissioning fit后才创建；COMMISSIONING trace缺字段，序列化NaN；不存在同定义全session指标'},
 'measured_sleeve_clearance':{'full_fast_prefix_observations':False,'value':None,'ACTIVE_RECOVERY_missing_rows':605,'COMMISSIONING_finite_rows':1406,'COMMISSIONING_observed_min_m':g['measured_sleeve_clearance']['original_finite_only_formula_observed_min'],'original_source':'COMMISSIONING写实际sleeve gap，ACTIVE_RECOVERY row不写此字段，不能以参考桥sleeve证书替代实际物理观测'}
}
refs={str(p.relative_to(P)):sha(p) for p in [sump,jobp,P/'experiments/V8BETA02L.json',old,D/'audit_prefix_trace_once_v1.py',D/'run_once_v1/RESULT.json',D/'run_once_v1/RESOURCE.json',D/'PID_CLOSURE_V1.json',Path(__file__)]}
result={
 'status':'PREFIX_UNCHANGED_AND_8_OBSERVED_HARD_GATES_WITH_3_SCOPE_UNKNOWNS_NOT_PARENT_PASS',
 'authority':'root明确批准一次新prefix-trace审计≤60s/CPU1/AS1GiB；原stream失败不重扫不重跑',
 'raw_prefix_source':'第一审计FAILED_PAID_PREFIX成功部分与PARENT_PREFIX_REVIEW_V1冻结证据，本次large raw读取0',
 'parent_accounting':v['parent_accounting'],
 'original5_native_session_checks':v['prefix_original_hard_checks'],
 'additional6_scope_review':scope,
 'global_prefix_11hard_false_established':None,
 'unresolved_gates':['human_acceleration','session_clearance','measured_sleeve_clearance'],
 'observed_violation':False,
 'observation_not_continuous_guarantee':True,
 'N_A_or_UNKNOWN':'原TASK scorer对非TASK前缀不适用；六项额外核验仅原阈值观测。缺失stage不能改为N/A从而令all11=True；对取消所需全prefix安全保留UNKNOWN。',
 'parent_original_scorer':'PARTIAL_NOT_RANKED','parent_full_task_qualification':None,
 'summary_original_recovery_metadata':{k:s['dev_a_recovery'].get(k) for k in ['entered','succeeded','abort_reason','start_time_s','end_time_s','duration_s','executed_interval_count','minimum_session_clearance_m','minimum_true_physical_clearance_m_evaluation_only','shank_bed_contact_physical_steps_evaluation_only']},
 'summary_commissioning_has_no_missing3_fullprefix_metrics':True,
 'summary_reference_guard_not_substitute':'stationary emitted q/dq/ddq和reference bridge continuous clearance是参考/模型证书，不是缺失物理人加速度、旧session contract或实际sleeve全prefix观测',
 'source_formula_lines':{'TASK_scorer':'summarize_phase_b.py:31,40-47','ACTIVE_state_clearance_acceleration':'runtime_coordination_residual_v2.py:1517-1556','COMMISSIONING_row_omissions_and_sleeve':'runtime_coordination_residual_v2.py:2249-2275','session_contract_created_after_commissioning_fit':'runtime_coordination_residual_v2.py:2344-2367','missing_field_serialization':'runtime_coordination_residual_v2.py:4015-4031','recovery_after_commissioning':'runtime_coordination_residual_v2.py:2426-2437'},
 'trace_binding':r['binding'],'trace_sha256':r['trace_sha256'],'source_bindings':r['source_bindings'],'additional_role_sources':role_sources,
 'receipt_trace_row_count_caveat':'相等计数不是逐row双射：commissioning terminal零步trace与初始化零步receipt分别存在；实际native来自原receipt总和40200，trace末ACTIVE观测40180后执行20步，末尾TASK boundary不推进parentTASK。',
 'fork_actual_snapshot_hash': '06d5fe51c735e3d4a9b84a2fd62b4a72fc54a181eef2ea903ad3024a76448e2a',
 'early_fork_audit_hash_equal_actual':False,
 'actual_fork_and_events_reference':str(old.relative_to(P)),
 'L_owner_closure':v['L_owner_closure'],
 'resource':{'wall_s':u['END']['unix']-u['START']['unix'],'CPU_s':u['END']['CPU_user_s']+u['END']['CPU_system_s']-u['START']['CPU_user_s']-u['START']['CPU_system_s'],'RSS_peak_KiB':u['END']['RSS_peak_KiB'],'affinity':u['END']['affinity'],'AS_bytes':u['AS_bytes'],'external_timeout_s':60,'python_identity':{k:u['END'][k] for k in ['python','binary_sha256']},'PID_closure':closure},
 'operations':r['ledger'],'raw_rereads':0,'model_init_forward_fit_physics':0,
 'new_physical_estimation_or_guard_redefinition':False,
 'cancel_publish_or_run_mutation':False,'active_PHAPP_or_Beta_or_sealed_outcomes_read':False,
 'references_sha256':refs,
}
save(D/'PREFIX_TRACE_REVIEW_V1.json',result)
md='''# V8BETA02L 父前缀独立补充审计

原父 raw 的40200个native记录、2011条回执与L_B继承前缀逐字段完全相等，实际父增量40200，不重复计子任务继承前缀。父无任何TASK native推进，任务原状态仍PARTIAL_NOT_RANKED。

新增trace审计只执行一次：10个数组各读取1次，6项reduce；仅读ACTIVE_RECOVERY/COMMISSIONING的2011条fast观测。末观测10.045s、physics_steps40180，原末回执再执行20步至10.05s/40200。TASK cutoff节点仅核时间/计数元数据，不读取其物理指标。原raw没有重扫。

原session原生监测已覆盖force/moment/true clearance/contact/ROM五门。新增torque、人速度、机器人速度三门在完整fast前缀上均符合原阈值；没有观测到越限。

剩余三门保持UNKNOWN：

- 人加速度：ACTIVE_RECOVERY的605条有效观测max=[22.9313118,51.1492020]deg/s²，低于[300,600]；COMMISSIONING 1406条未记录，序列化valid=False，不能因此判安全。
- session clearance：ACTIVE_RECOVERY 605条有限；COMMISSIONING 1406条缺失。相同session contract在commissioning fit后才构建，不可反向补算。
- measured sleeve clearance：COMMISSIONING 1406条有限，min=.002802109066m；ACTIVE_RECOVERY 605条缺失。参考桥的sleeve clearance证书不等于实际物理间隙观测。

因此可说“8门有相应前缀观测证据、3门范围未知”，不能声称原scorer prefix PASS、全部11门hardFalse或完整parent资格。原TASK scorer对前缀不适用；此N/A不能用作消除缺失后令取消门成立。原始RESULT里的acceleration valid-only公式PASS仅覆盖605条，最终scope review明确保留COMMISSIONING UNKNOWN。

源manifest/模型XML/scorer阈值全部精确绑定。两个子任务实际SNAPSHOT/START/PARENT_CHECK/END使用相同06d5fe51…48e2a且parent unchanged；早期FORK_CONTEXT c89d7f7f…3467在quiesce/gc之前，不能宣称等于实际snapshot。原始失败审计及其格式错误均完整保留。

资源：wall {wall:.6f}s、CPU {cpu:.6f}s、RSS峰值{rss}KiB、affinity[0]、AS1GiB；外部timeout60s。PID {pid}原进程已闭合。0模型初始化/forward/fit/physics，无取消、发布或Beta/run状态写入。未读取其它活动physics结果。
'''.format(wall=result['resource']['wall_s'],cpu=result['resource']['CPU_s'],rss=u['END']['RSS_peak_KiB'],pid=pid)
with (D/'PREFIX_TRACE_REVIEW_V1.md').open('x') as f:f.write(md)
items=[p for p in D.rglob('*') if p.is_file()]
save(D/'OUTPUT_MANIFEST_V1.json',{'status':'IMMUTABLE_EVIDENCE_MANIFEST','files':{str(p.relative_to(D)):sha(p) for p in sorted(items)}})
print(json.dumps({'review_sha256':sha(D/'PREFIX_TRACE_REVIEW_V1.json'),'md_sha256':sha(D/'PREFIX_TRACE_REVIEW_V1.md'),'manifest_sha256':sha(D/'OUTPUT_MANIFEST_V1.json'),'result_sha256':sha(D/'run_once_v1/RESULT.json'),'resource':result['resource'],'unresolved':result['unresolved_gates']},ensure_ascii=False,indent=2))
