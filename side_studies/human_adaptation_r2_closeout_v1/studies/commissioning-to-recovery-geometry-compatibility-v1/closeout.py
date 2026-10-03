"""Evidence-only closeout; no physics or source edits."""
import os,sys,json,gzip,hashlib,csv,time
from pathlib import Path
from datetime import datetime,timezone
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
W=Path('<SIDE_STUDIES_ROOT>/commissioning-to-recovery-geometry-compatibility-v1');L=W.parent/'lab-human-adaptation-contrast-v1';sys.path.insert(0,str(W))
import human_qualification_R2 as h
np=h.np;rt=h.rt
def load(p):return json.loads(p.read_text() if p.exists() else gzip.open(str(p)+'.gz','rt').read())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cf=load(W/'SAME_STATE_COUNTERFACTUALS.json');oa=load(W/'ORACLE_COMMISSIONING_ALIGNMENT.json');ow=load(W/'REFERENCE_OWNERSHIP_COUNTERFACTUALS.json')
pairs=[('A_reproduction',W/'baseline/C5_commissioning_only/runs/C5__commissioning_only',L/'runs_R2/C5__commissioning_only'),('B_reproduction',W/'baseline/C5_continual_adaptive/runs/C5__continual_adaptive',L/'runs_R2/C5__continual_adaptive'),('C_existing_oracle_reproduction',W/'baseline/C5_existing_oracle/runs/C5__fixed_population',L/'diagnostics_R2/D1_C5_TRUE_MODEL_FROM_START/runs/C5__fixed_population')]
rows=[];validation=[];consumption=[]
for label,p,old in pairs:
 r=load(p/'PRIMARY_RESULT.json');q=load(p/'qualification.json');s=load(p/'summary.json');r.update(path_label=label,path=str(p),scope='known-truth diagnostic' if 'oracle' in label else 'frozen commissioning-path reproduction',setup_status='PASS_FROZEN_STATIC_PARENT_SETUP',recovery_status=s['dev_a_recovery']['abort_reason'] if s['dev_a_recovery'].get('abort_reason') else ('COMPLETE' if s['dev_a_recovery']['succeeded'] else 'NOT_ENTERED'),commissioning_geometry=s['commissioning']['geometry_fit'],handoff_q_dq=s['dev_a_recovery']['start_estimated_state_rad_rad_s'],handoff_predicted_margins_m=cf['state_replacement_diagnostic']['oracle_at_oracle_state'] if 'oracle' in label else cf['rows'][0]['margins_m'],handoff_actual_clearance_evaluation_only_m=s['dev_a_recovery']['minimum_true_physical_clearance_m_evaluation_only'],resource=load(p.parent.parent/'RUN_RESOURCE.json'),mujoco_warnings=s['task']['mujoco_warning_counts'],short_trajectory_must_not_be_ranked_against_complete=True)
 with np.load(p/'trace.npz') as z:
  r['stage_metrics']={}
  for stage in np.unique(z['stage']):
   mask=z['stage']==stage;t=z['time_s'][mask];f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);m=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1)
   r['stage_metrics'][str(stage)]=dict(samples=len(t),duration_s=float(t[-1]-t[0]) if len(t)>1 else 0.,force_mean_n=float(np.mean(f)),force_RMS_n=float(np.sqrt(np.mean(f*f))),force_peak_n=float(np.max(f)),moment_peak_nm=float(np.max(m)),force_integral_n_s=float(f[:-1]@np.diff(t)),moment_integral_nm_s=float(m[:-1]@np.diff(t)))
 with np.load(p/'trace.npz') as a,np.load(old/'trace.npz') as b:
  mismatches=[]
  for key in a.files:
   if key not in b.files:continue
   equal=np.array_equal(a[key],b[key],equal_nan=True) if a[key].dtype.kind in 'fc' else np.array_equal(a[key],b[key])
   if not equal:mismatches.append(key)
  validation.append(dict(path_label=label,old_path=str(old),trace_keys_compared=len(set(a.files)&set(b.files)),all_compared_trace_arrays_exact=not mismatches,mismatched_trace_fields=mismatches))
 oldr=load(old/'PRIMARY_RESULT.json');fields=['status','physical_verdict','scientific_verdict','duration_s','J_F_task_n_s','force_peak_n','moment_peak_nm','minimum_clearance_m','minimum_true_clearance_m_evaluation_only','geometry_used']
 validation[-1]['frozen_endpoint_metric_exact_matches']={k:r.get(k)==oldr.get(k) for k in fields}
 events=[]
 for eventfile in p.glob('model_consumption_*.jsonl'):
  events.extend(json.loads(l) for l in eventfile.read_text().splitlines() if l.strip())
 counts={kind:{'calls':sum(e['kind']==kind for e in events),'PIDs':sorted({e['pid'] for e in events if e['kind']==kind}),'numeric_beta_residual_hashes':sorted({e['payload']['numeric_model_sha256'] for e in events if e['kind']==kind}),'geometry_hashes':sorted({e['payload']['geometry_sha256'] for e in events if e['kind']==kind})} for kind in ['execution','planner','mechanics']}
 consumption.append(dict(path_label=label,models=counts,handoff_envelope_record=load(p/'HANDOFF_EXACT.json')['envelope_record'],envelope_uses_same_geometry_object_as_accepted_belief=load(p/'HANDOFF_EXACT.json')['envelope_geometry_same_object_as_target'],target_beta=s['commissioning']['handoff_belief']['beta'],target_residual=s['commissioning']['handoff_belief']['state_residual_weights_nm'],target_geometry=s['commissioning']['handoff_belief']['effective_geometry'],recovery_active_model_at_end=s['dev_a_recovery'].get('active_model_at_end'),gaps_are_expected_for_preplanner_rejection='oracle' not in label,qualification_source_tags_for_oracle_overridden_by_explicit_known_truth_protocol='oracle' in label))
 rows.append(r)
assert all(v['all_compared_trace_arrays_exact'] for v in validation),validation
assert all(all(v['frozen_endpoint_metric_exact_matches'].values()) for v in validation),validation
assert rows[0]['commissioning_geometry']==rows[1]['commissioning_geometry']
assert consumption[0]['target_beta']==consumption[1]['target_beta'] and consumption[0]['target_residual']==consumption[1]['target_residual']
assert all(x['envelope_uses_same_geometry_object_as_accepted_belief'] for x in consumption)
h.save(W/'REPRODUCTION_VALIDATION.json',dict(status='PASS',runs=validation,B_C_handoff_fit_beta_residual_exact_match=True,geometry_gauge_invariance_assertion=True,same_state_hash_identical_all_primary_counterfactuals=all(r['state_sha256']==cf['state_sha256'] for r in cf['rows']),source_is_unmodified=True))
h.save(W/'COMPARISON.json',dict(status='THREE_EXACT_REPRODUCTIONS_COMPLETE',runs=rows,interpretation='Failures have zero TASK intervals; task entry force/RMSE are not whole-task performance. Do not rank their zero integrals below the complete oracle.'))
with (W/'COMPARISON.csv').open('w',newline='') as f:
 fields=['path_label','status','physical_verdict','scientific_verdict','outbound_reached','hold_satisfied','true_return_satisfied','duration_s','J_F_task_n_s','force_peak_n','moment_peak_nm','minimum_clearance_m','minimum_true_clearance_m_evaluation_only','handoff_actual_clearance_evaluation_only_m']
 writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
h.save(W/'MODEL_CONSUMPTION_EVIDENCE.json',dict(status='COMPLETE_WITH_EXPECTED_PREPLANNER_REJECTION_GAPS',runs=consumption,no_task_prediction_evidence_for_failed_paths=True,meaning='A/C labels here reproduce requested three paths, not the prior R2 A/B/C arms. Accepted belief/envelope consumption is distinct from activation/execution. Personalized belief never activates in the failed paths. Known-truth oracle source labels inherited from fixed-population implementation do not establish deployability.'))
prior=dict(role='Fixed structural conservative full knee-to-ankle shank length upper bound used to construct a worst-case distal cylinder endpoint; not cuff lever, fitted L2, measured registered individual bound or fit optimizer limit.',value_m=.46,additional_margin_m=.001,shank_radius_m=.045,bed_height_m=.012,source='SessionClearanceContract runtime.py:151-209 plus RigidTableReferenceEnvelopeV1 rigid_table_reference.py:46-47; development_v1_1.json registered same value.',estimator_bounds=dict(hip_x_m=[-.35,.35],hip_z_m=[-.05,.30],thigh_length_m=[.30,.56],knee_to_cuff_m=[.14,.48]),fit_identifies='hip world X/Z, thigh length, effective cuff lever only; explicitly does not split cuff lever=fraction*full_shank.',expression='min(knee_z, knee_z + .46*sin(q1-q2)) - .045 - .012 - .001',B_handoff_distal_m=cf['rows'][0]['margins_m']['distal_shank_m'],true_geometry_same_state_distal_m=cf['rows'][1]['margins_m']['distal_shank_m'],critical_full_shank_upper_at_B_m=cf['critical_full_shank_upper_m_at_B_handoff'],actual_full_shank_m_evaluation_only=.40076,excess_length_m=.05924,predicted_extra_downward_endpoint_displacement_m=.05924*(-np.sin(rows[0]['handoff_q_dq'][0]-rows[0]['handoff_q_dq'][1])),truth_bound_diagnostic_m=cf['rows'][8]['margins_m']['distal_shank_m'],same_prior_both_recovery_paths=True,same_zero_tool_reference_offset_both_recovery_paths=True,different_model_gauge_equivalent_in_world_hip=True,different_handoff_physical_state=True,why_conservative='A shorter cuff lever does not certify a shorter full shank. A .46m shank with the same identified lever remains in the admissible unmeasured geometry set. At this negative shank pitch its distal cylinder violates the certificate although the simulated .40076m shank does not.',commissioning_escape_note='The frozen commissioning path explicitly permits a narrow nonworsening distal-shank escape, guarded by monotonic geometric proof; its source explicitly forbids this exception in TASK/RECOVERY. No such bypass is enabled here.')
h.save(W/'SHANK_PRIOR_AUDIT.json',prior)
root=dict(status='DIAGNOSIS_COMPLETE_FIX_BLOCKED_UNDER_FROZEN_CONTRACT',categories=dict(A='Excluded as sufficient cause: true geometry at same state remains negative; fitted lever error 19.899um, pose residual RMS1.505um.',B='No frame mismatch sufficient to explain sign: world-hip gauge re-expression invariant; correctly inverse-mapping emitted pose still -0.527mm.',C='Supported domain interaction: individualized geometry exposes nominal commissioning terminal state outside unchanged conservative full-shank set.',D='No double counting in consumed recovery envelope: offsets reset to zero; keeping old offset worsens sleeve and leaves shank unchanged.',E='No evidence of erroneous physical reset or stale ownership; substituting old nominal q yields positive hypothetical reference but does not cover actual state.',F='No primary safety-envelope arithmetic/coordinate implementation bug demonstrated. Separate existing-oracle preload construction mixes patched control geometry with unpatched nominal setup frame, confounding physical robot initial state.',G='Supported: recovery refuses a continuous all-time certificate whose origin is already negative under intended full-shank prior.',H='Supported interaction of nominal commissioning trajectory with full-shank conservatism; oracle initialization/reference trajectory differs before the handoff.'),minimal_chain=['Accepted fitted geometry and q reconstruction are accurate at failed handoff.','Both accepted fit and exact geometry give approximately -1.83mm under the unchanged .46m full-shank prior, with physical truth +5.17mm.','Every continuation includes that origin; all46 path certificates reject before planner/mechanics/execution activation.','Correct world-hip gauge, cuff-origin semantics, ownership and emitted-pose re-expression do not produce a nonnegative actual-state certificate.','Only reducing unmeasured structural bound, double-counting a world hip lift, choosing fictitious reference origin or changing the physical trajectory can change that sign in these diagnostics. None is implemented.','The oracle reached different q/dq and positive +6.07mm conservative margin, with robot initial position changed47.75mm by its factory/preload path.'],oracle_success_causal_attribution_limit='Existing oracle success proves that its distinct initialized chain completes the task under same safety values; it does not isolate true model benefit at the failed commissioning state or establish same mechanical preload.',not_claimed=['No proof that rho=.60 is physically infeasible.','No proof all future causal commissioning protocols must fail.','No separated estimate of initialization-preload versus model/reference-trajectory contribution to oracle success.','No claim continual dynamics adaptation is the source of this preactivation failure.','No full physical safety proof from a geometry screen.'])
h.save(W/'ROOT_CAUSE_AUDIT.json',root)
fix=dict(status='BLOCKED_NO_DEPLOYABLE_LOCAL_FIX_DEMONSTRATED',implemented=False,source_patches=0,safety_thresholds_changed=False,conservative_checks_removed=False,reason='With frozen actual handoff and .46m full-shank set, the negative origin is a correctly computed intended certificate. Commissioning does not legally measure full L2 or rho separately. Tightening to .40076m would require hidden truth; changing origin to old nominal q or shifting hip would certify a different geometry/state. The separate oracle initialization inconsistency cannot causally repair the primary failed handoff.',regression_status='NOT_TRIGGERED_NO_FIX_IMPLEMENTED',requested_regressions_if_fix=['.60 commissioning_only','.60 continual_adaptive','.72 nominal','.66'],unmodified_parent_reference_results=[])
for cond in ['C0','C6']:
 p=L/'runs_R2'/(cond+'__commissioning_only')/'PRIMARY_RESULT.json';r=load(p);fix['unmodified_parent_reference_results'].append(dict(path=str(p),sha256=sha(p),rho=.72 if cond=='C0' else .66,status=r['status'],physical=r['physical_verdict'],scientific=r['scientific_verdict'],not_a_new_regression=True))
h.save(W/'FIX_DECISION.json',fix)
# Keep exact failures/oracle trajectory; compact only lossless own event logs after evidence extraction.
compact=[]
for p in (W/'baseline').glob('*/runs/*/*.jsonl'):
 if p.name.startswith(('model_consumption_','prediction_updates_')) or p.name=='TASK_PREDICTION_SAMPLES.jsonl':
  original=sha(p);dest=Path(str(p)+'.gz')
  with gzip.open(dest,'wb',compresslevel=3) as f:f.write(p.read_bytes())
  assert hashlib.sha256(gzip.open(dest,'rb').read()).hexdigest()==original
  compact.append(dict(path=str(dest.relative_to(W)),original_content_sha256=original,lossless=True));p.unlink()
h.save(W/'RETENTION.json',dict(whole_history_copied=False,original_R2_untouched=True,full_unique_new_three_traces_retained=True,own_logs_losslessly_compressed=compact))
resources=[json.loads(l) for l in (W/'RESOURCE_SAMPLES.jsonl').read_text().splitlines()]
launches=[load(p.parent.parent/'RUN_RESOURCE.json') for _,p,_ in pairs]
res=dict(sample_count=len(resources),sampling_policy='At launch, completion and cooperative callback at >=30s; no high-frequency polling. VmHWM covers parent serialization/scorer peak at completion.',Windows_min_available_GiB=min(r['Windows_available_GiB'] for r in resources),WSL_min_available_GiB=min(r['WSL_available_GiB'] for r in resources),swap_max_KiB=max(r['swap_used_KiB'] for r in resources),oom_kills_delta=max(r['oom_kill_count'] for r in resources)-min(r['oom_kill_count'] for r in resources),parent_peak_RSS_GiB=max(x['parent_peak_RSS_KiB'] for x in launches)/1048576,sampled_planner_child_HWM_GiB=max(x['peak_rss_KiB'] for r in resources for x in r['side_workers'] if 'multiprocessing.spawn' in x['command'])/1048576,child_peak_limitation='Sampled planner VmHWM is a lower bound on exact lifetime peak; rusage CHILDREN also includes Windows interop forks and is retained separately, not mislabeled as physics planner peak.',sampled_aggregate_RSS_GiB=max(r['side_aggregate_RSS_KiB'] for r in resources)/1048576,total_run_and_scorer_wall_seconds=sum(x['wall_seconds'] for x in launches),SAC_workers_observed=any(r['SAC_workers'] for r in resources),SAC_heavy_observed=any(r['SAC_heavy_workers'] for r in resources),max_physics_owners=1,threads=1,GPU=False,RL_steps=0,parallel_intervals=[dict(path_label=label,start_utc=resources[i]['utc'],SAC_workers_observed=False,clean_performance_benchmark=False) for i,(label,_,_) in zip([0,3,6],pairs)],SAC_phase_evidence=dict(thread_id='01a0fd54-f393-7283-9225-06c0ee2dc3d0',cursor='8f368a34-88be-4d01-bc32-3663619b3b0f:8',status='idle latest turn completed Seed1 diagnosis and STOP',main_STATE_file_stale_not_used_to_override_live_evidence=True))
h.save(W/'RESOURCE_OVERLAP_LOG.json',res)
# All evidence in original parent and our snapshot must still match.
parent=load(W/'PARENT_PRESERVATION_MANIFEST.json');assert all(sha(L/r['path'])==r['sha256'] for r in parent['files'])
prov=load(W/'SOURCE_PROVENANCE.json');assert all(sha(W/'snapshot'/p)==r['sha256'] for p,r in prov['source_files'].items())
h.save(W/'PRESERVATION_VERIFICATION.json',dict(status='PASS',parent_files_unchanged=len(parent['files']),snapshot_files_unchanged=len(prov['source_files']),main_repo_writes=0,git_operations=0,environment_changes=0,production_source_changes=0))
state=load(W/'STATE.json');now=datetime.now(timezone.utc)
state.update(status='COMPLETE_DIAGNOSIS_FIX_BLOCKED',phase='CLOSEOUT_STOP',finished_utc=now.isoformat(),finished_local=now.astimezone().isoformat(),study_elapsed_since_preparation_seconds=(now-datetime.fromisoformat(state['started_utc'])).total_seconds(),reproductions_completed=3,dynamic_runs=3,static_counterfactuals=len(cf['rows'])+len(ow['rows']),fixes=0,new_regression_runs=0,regression_reason='Conditional on a deployable fix; no such fix found or implemented.',SAC_affected=False,next_action='STOP. Preserve exact blocker. No combined/height/SAC/RL/hardware. Further protocol or registered structural information would require a separately authorized study.')
h.save(W/'STATE.json',state)
report=f"""# Commissioning-to-Recovery Geometry Compatibility v1

STATUS: COMPLETE_DIAGNOSIS_FIX_BLOCKED. 三条原路径精确复现；没有实现控制、接口或阈值修改。完成后 STOP。

## 结论与最小证据链

主因属于 **C/G/H**：名义模型 commissioning 到达的真实状态，与保留完整小腿保守上界的 recovery certificate 不兼容；certificate 按既有规则正确拒绝该状态。没有找到在冻结 handoff 和当前合法辨识信息下可部署的局部软件修复。

1. B/C 的 fit、beta、residual、handoff q/dq 和全部数值轨迹，与原 R2 精确一致。有效 knee-to-cuff=0.240475899 m，对模拟 truth 的误差19.899 µm；拟合位置残差 RMS1.505 µm、最大17.154 µm，352样本。完整小腿长度与 rho 未分别辨识。
2. 两个失败路径 handoff 的估计 q=[5.338567°,11.150913°]，dq=[0.004908307,0.012384048] rad/s；真实 q/dq 见 HANDOFF_EXACT 与 RECOVERY_EXACT。拟合 world hip=[0.000039235,0,0.062115336] m、L1=0.436819886 m。旧 emitted joint reference=[5.5°,9.5°]、dq/ddq=0；新 recovery candidate origin 使用 fitted causal observation。没有物理状态或历史 reset。
3. 在完全相同 handoff 下，fitted geometry 的 distal-shank margin=-1.827095 mm；exact true effective geometry=-1.836838 mm；真实物理 clearance=+5.170123 mm。几何拟合误差不是负号的充分原因。
4. 首条 continuation 连续证书下界=-1.840858 mm；46条候选全部拒绝，执行0个 recovery interval。没有 planner/mechanics task-model 消费；已接受个体模型未激活，不能用版本号或拟合成功替代执行证据。
5. 正确 world-hip gauge 变换、oracle recovery origin 语义、ownership 标签均不改变负号。旧 commissioning cuff translation=(-46.9264,-0.00146,-5.1910) mm，只作用于 tool/sleeve reference；带入 fitted recovery 后 shank gap不变而 sleeve变负。当前 recovery 已使用 fresh zero offset，没有 offset 双计。
6. 重用旧名义 q 作为新 geometry 的 candidate origin 能得到假想 +13.894689 mm，但对应 emitted pose 位置差5.684 mm，实际 handoff gap仍为负。正确反解旧 emitted robot pose 后 origin gap仍为-0.527015 mm，且存在1.182 mm投影位置差。它们均未实施。
7. 保留 fitted geometry、仅在诊断中换成 oracle 到达的 q，gap变为+6.073567 mm；oracle geometry 在其自身状态为+6.066522 mm。决定局部符号差异的是状态与 prior 的组合。

## 为什么 existing oracle 可以通过

既有 oracle 完整成功，但不是 failed handoff 的 SAME-STATE oracle。它从初始化注入 true effective geometry，经另一条 commissioning/加载链到达 q=[7.927032°,15.206532°]，具有正的 conservative margin。两条 recovery 均使用同样 .46 m full-shank upper、1 mm margin、零 cuff translation 和相同 conservative checks。

还发现此前 oracle 描述需要限定：在 runtime.py:264 以被替换的 control geometry 求 loaded equilibrium 后，runtime.py:267–269 仍用未替换 STAGE5_GEOMETRY 的 nominal cuff frame 重表达 preload。两者初始 Human q相同，但机器人 attachment 实际位置相差 **47.747426 mm**，robot q、初始支撑动作及 startup alignment 不同。此初始化差异在 handoff 之前已存在。它是明确的 oracle setup/reference 消费不一致，不能把 oracle 成功归因于同机械初态下的几何辨识，也不能据此宣布 commissioning handoff 有 arithmetic bug。本研究没有进一步分离 preload 与后续 model/reference trajectory 对 oracle 成功的各自贡献。

## 0.46 m prior 的角色

这是固定的 **完整 knee-to-ankle shank 长度保守上界**，用于最坏情况 ankle/cylinder 构造；不是 knee-to-cuff 距离、不是估计器参数上界，也不是已测得的个体安装长度。配置和两个 clearance dataclass 一致。估计器 knee-to-cuff 上界是0.48 m，与0.46 m不同。

本 handoff shank pitch向下，公式为
\[
\min(z_{{knee}},z_{{knee}}+0.46\sin(q_1-q_2))-0.045-0.012-0.001.
\]
模拟 full shank=0.40076 m，其与prior的59.24 mm差异导致约5.9993 mm额外向下延伸；加上1 mm保守margin，解释物理正clearance与certificate负值。要令该 handoff 的 fitted shank certificate非负，需要 full-shank upper≤0.441958296 m；当前 commissioning 没有合法测量依据支持这个收紧。只在静态 hidden-truth diagnostic 中改为0.40076 m会得到+4.172179 mm，未用于控制或修复。

Frozen commissioning 允许明确受限的 nonworsening shank escape，源码明确禁止该例外用于 TASK/RECOVERY。把例外复制到 recovery、删掉起点、选择虚构 ownership 状态，都属于改变既有 certificate 行为，未实施。

## 复现结果与模型消费

| 路径 | COMPLETE | physical/scientific | OUT/HOLD/true RETURN | TASK时间 | TASK J_F |
|---|---|---|---|---:|---:|
| rho=.60 commissioning-only | ABORTED | FAIL/PASS | 否/否/否 | 0 intervals | 不适用完整任务比较 |
| rho=.60 continual-adaptive | ABORTED | FAIL/PASS | 否/否/否 | 0 intervals | 不适用完整任务比较 |
| existing known-truth oracle | COMPLETE | PASS/PASS | 是/是/是 | 15.49 s | 1187.608929 N·s |

Oracle TASK peak force109.239931 N、peak moment13.148696 Nm、deployable minimum clearance6.654246 mm、actual diagnostic clearance12.044649 mm。完整 mean/RMS/integrals/各阶段peak/tracking/update/prediction与数值消费hash在 COMPARISON.json 和 MODEL_CONSUMPTION_EVIDENCE.json。两个失败路径仅有TASK入口节点，force80.981402 N、moment9.482749 Nm；它们的零积分不能与完整成功任务排名。

Oracle 的 planner/mechanics/execution 数值消费均有逐PID记录；B/C在certificate前置拒绝，因此planner/mechanics缺项如实保留。失效路径没有TASK预测质量数据。Scientific PASS仅说明此冻结仿真记录的状态/来源/消费与评价模式一致，不等于physical成功或deployable oracle。

## FIX 与回归决定

**FIX: BLOCKED_NO_DEPLOYABLE_LOCAL_FIX_DEMONSTRATED；实际patch=0。**
降低未测 full-shank upper需要hidden truth，不能实施。当前没有证据支持通过合法几何表示变换使同一实际起点被原certificate接受；也没有证明任何未来causal commissioning设计都不可能成功。

rho=.66/.72没有新修复回归，因为未实现修复。FIX_DECISION.json保留原R2对应 commissioning-only COMPLETE/PASS/PASS的只读引用，明确不是本轮新回归。不能声称本轮满足“修复后四项回归”。所有140冻结源码hash与原670证据hash保持一致，阈值、task、prior、算法均未改变，故也没有宣称 envelope 被整体放宽或修复已经通过。

## 资源、保留与停止

严格单physics owner、CPU/nice19、数值线程1、无GPU/RL/渲染。三次run连同scorer wall总计{res['total_run_and_scorer_wall_seconds']:.2f}s；包括独立准备和静态审计的目录记录elapsed约{state['study_elapsed_since_preparation_seconds']/60:.1f}min。Host wall用于characterization，不是干净性能benchmark。
Parent含序列化/scorer lifetime RSS peak={res['parent_peak_RSS_GiB']:.3f}GiB；sampled planner-child VmHWM={res['sampled_planner_child_HWM_GiB']:.3f}GiB（不是精确生命周期峰值）；sampled aggregate={res['sampled_aggregate_RSS_GiB']:.3f}GiB。采样Windows minimum available={res['Windows_min_available_GiB']:.3f}GiB、WSL minimum={res['WSL_min_available_GiB']:.3f}GiB，swap0、OOM0、MuJoCo warnings空。SAC处于idle/STOP，未观察到SAC worker，未修改或影响SAC。

仅复制冻结最小源码、三条新关键轨迹；own event logs lossless压缩，未复制历史结果库。原R2与主repo只读，无git操作/环境变更/sharedSTOP写入。没有后续生产纳入文件；这些是独立诊断证据。NEXT: STOP，保留exact blocker；任何新的commissioning protocol或registered anatomy信息需另行授权与版本化研究。
"""
(W/'REPORT.md').write_text(report)
(W/'SHANK_PRIOR_AUDIT.md').write_text('# 0.46 m structural prior audit\n\n'+json.dumps(rt._jsonable(prior),indent=2)+'\n')
# Manifest hashes every study file except itself.
files=[dict(path=str(p.relative_to(W)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(W.rglob('*')) if p.is_file() and p.name!='MANIFEST.json']
h.save(W/'MANIFEST.json',dict(status='COMPLETE_STOP',utc=now.isoformat(),files=files,total_bytes=sum(x['bytes'] for x in files),self_excluded=True))
print('CLOSEOUT',state['status'],'files',len(files),'MiB',sum(x['bytes'] for x in files)/1048576,'resources',res['parent_peak_RSS_GiB'],res['swap_max_KiB'])
