"""Reports reflect only completed evidence; intended final use after frozen queues finish."""
from pathlib import Path
import json,csv,datetime,time
P=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def write(n,s):(P/n).write_text(s.strip()+'\n')
def vec(a):return '/'.join(f'{x:.3f}' for x in a)
def result_table(rows):
 s='|身份|原motion|JF N·s|JM Nm·s|跨模板数|最小模型曲率 m/s²|native jerk RMS 髋/膝 °/s³|\n|---|---|---:|---:|---:|---:|---|\n'
 for r in rows:s+=f"|{r['id']}|{'PASS' if r['qualified'] else 'FAIL'}|{r['JF']:.9f}|{r['JM']:.9f}|{len(r['crossing_events'])}|{r['minimum_curvature_event']['guard']['model_curvature_m_s2']:.6f}|{vec(r['native_motion']['jerk_deg_s3']['rms'])}|\n"
 return s
A=read('ACTIVATION.json');S=read('analysis/RESULT_SUMMARY.json');account=read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json');branches={f.stem:json.loads(f.read_text()) for f in (P/'analysis/branches').glob('*.json')};ordered=[branches[a['id']] for a in account['attempts'] if a['id'] in branches];dev=[r for r in ordered if r['id'].startswith('DEV_')];local=[r for r in S['local_unseen']];stamp=datetime.datetime.now(datetime.timezone.utc);elapsed=stamp.timestamp()-A['t0_unix'];btime=datetime.timezone(datetime.timedelta(hours=8));host=sorted({r['axes']['HOST_EXECUTION_CAUSAL_VALID'] for r in ordered});hardpass=all(all(v is not False for v in r.get('original_hard_safety_checks',{}).values()) for r in ordered)
write('CAUSAL_PHYSICAL_COMPARISON.md',f'''# 实际物理比较与因果边界

新guard的P2-B/P2-C：**NOT_RUN**。所有本轮物理保留原clearance函数，只增加同次因果输入日志；没有新guard的jerk、force、任务失败率或安全资格结果。以下不是新旧guard对照。

开发固定候选共{len(dev)}条完整分支，冷父单独计账。同一live父地址空间fork；初始parent hash一致不等于后续Human状态相同。{account['groups'].get('DEV',{}).get('candidate_qualified',0)}/{len(dev)}通过完整原motion门。

{result_table(dev)}

六个未见微扰的分类事前冻结，已评价{len(local)}个，符合预测{sum(bool(r['match']) for r in local)}个。候选参数和历史因果估计是模型输入，未来Human/native只作标签。每条完整JF/JM均保留；motion FAIL不进入正式收益排名。当前强最佳为历史最佳精确重复，不能称本轮新降力成果。

原guard的巨大负曲率、加速度box角点、post-filter未满足标志和实际receipt/native冲击分开报告。完整指标见analysis/branches/*.json与FULL_RESULTS.csv；原始未滤波q/dq/a/jerk见runtime/motion_series/*.npz，完整native torque/contact和原scorer见runtime/source/results/*。新日志使双端点的gap/rate精确闭包，两个重建误差均0；解析单支曲率约2.15×10⁻⁵，双端点算术诊断correction为0。这仍未物理应用，不推断它实际会减少jerk。

实际物理安全/任务和科学receipt轴按原口径分别审计；host轴为{host}。guard内部约束未满足不自动等于实际碰撞，也不是安全证明。torque maxima由native receipt join单列；原trace实测为5ms并含terminal重复边界；clipping分量与实际task receipt逐条join、重建torque与覆盖率见audit/ALL_RECEIPT_NATIVE_IDENTITY.json，不能把20ms SAC wrapper当成trace采样周期。原安全检查结果全部保留。
''')
facttext='''# 协调权限对齐：固定坐标2×2因子

L=逐关节终点锁；D=新时长编译。L0不锁单独已到内部终点的关节，L1锁；整向量终点/HOLD规则始终保留。D0对修改后目标重算原scheduler minimum，按旧固定H150 RETURN槽1/4/5因子1.1/1.2/1.5编译，忽略新增局部time意图；D1使用ceil(max(parent duration,new minimum)×local factor/5ms)×5ms。x、legacy、原guard和物理均固定，不能同时改变它们再归因。

零物理相同请求映射见analysis/PERMISSION_FACTOR_MAPPING.json：时长D差异和endpoint L差异分别可见。最早的scheduler-only映射误将内部终点用作注册goal而被拒，修正为注册goal后重算，旧失败日志保留；不是物理失败或放宽阈值。

'''
for g in S['factors']:
 rr=[branches[r['id']] for r in g['rows'] if r.get('complete',True)];facttext+='## '+g['intent']+' 固定协调意图\n\n'+result_table(rr)+'\n'
 for r in [x for x in g['rows'] if x.get('complete',True)]:facttext+=f"{r['id']} 相对原同意图最大native q差={vec(r['vs_original']['max_abs_q_difference_deg'])}°，q/dq逐项相同={r['vs_original']['q_dq_exact_equal']}。\n\n"
for g in S['factors']:
 for r in g['rows']:
  if not r.get('complete',True):facttext+=f"\n{r['id']}：TASK_FAIL/PARTIAL，{r['actual_new_native_steps']}新增native步；原中止={r.get('protected_task_failure',{}).get('abort_reason',r.get('error'))}。全任务JF/JM不排名，原硬安全项={r.get('protected_task_failure',{}).get('hard_safety_conditions')}。\n"
facttext+='''以上能识别两个compiler因素及其guard模式相互作用。L1D1是原新表示控制组；完整trace/native/receipt重现另行审计。D0恢复旧时长语义，但整个factor8仍使用modal目标提议，并没有恢复旧18D归一化目标域，因此L0D0不能冒称完整旧18D。旧18D与新8D非双向全族坐标变换；共同运动子族需逐请求target/pass/duration/certificate一致，x=0回到共同H150。尚未运行匹配完整权限后的旧18D/新坐标等预算优化，效率和性能创新均NOT_ESTABLISHED。
'''
write('REPRESENTATION_PERMISSION_ALIGNMENT.md',facttext)
cs='''# 独立冻结跨状态验证

两个新prefix在打开任何其物理结果前冻结，配置SHA见analysis/LOCKED_VALIDATION_FREEZE.json；没有依据验证结果选择候选或调参。新条件通过真实冷commissioning+合法prefix构造完整父状态，不用q/dq重建plant。Human仍是同一个nominal commissioned设定，没有跨患者参数研究或真实Trial1→Trial2→Trial3。

'''
for g in S['locked']:
 rr=[branches[r['id']] for r in g['rows']];cs+='## '+g['group']+'\n\n前缀：`'+json.dumps(g['condition']['prefix'])+'`。\n\n'+result_table(rr)+'\n'
 bb=next((r for r in rr if r['id'].endswith('_B')),None)
 if bb:
  for r in rr:
   if r['id']==bb['id']:continue
   cs+=f"{r['id']} 相对此条件B的JF变化={r['JF']-bb['JF']:.9f} N·s；完整原门={'PASS' if r['qualified'] else 'FAIL'}，未通过者不列正式收益。\n\n"
 for r in rr:
  pr=r.get('prediction') or {};naive=pr.get('naive_transfer_diagnostic')
  if naive:cs+=f"{r['id']}：域外模型正式ABSTAIN；冻结naive transfer预报motion={'PASS' if naive['predicted_motion_pass'] else 'FAIL'}，实际={'PASS' if r['qualified'] else 'FAIL'}。外推测试不赋予在线决策权限。\n\n"
cs+='''结论只适用于已列合法prefix；有限无违规运行不是全局安全保证。未改变controller边界之外的Human参数，未做临床/硬件或host实时验证。冻结state结果与同父局部预测准确率不能合并成患者泛化准确率。
''';write('CROSS_STATE_VALIDATION.md',cs)
opt=(P/'OPTIMIZATION_IMPACT.md').read_text().split('## 实测结果')[0];menu=read('predictions/FROZEN_MENU_DECISION.json');opt+=f'''\n## 实测结果\n\n同父未见局部候选{len(local)}个，原门通过{sum(r['qualified'] for r in local)}，冻结分类命中{sum(bool(r['match']) for r in local)}。这是局部执行后果预测；未换guard，未提高同一候选的合格率。\n\n同历史数据规则分析：cost-only选{menu['cost_only_selection']['tag']}，branch-aware选{menu['branch_aware_selection']['tag']}；选点改变={menu['selection_changed']}。规则没有消费新标签，但记录晚于首个新结果，属于POSTHOC，不是前瞻优化或两独立臂。没有用一份共有物理菜单伪装两倍预算，也没有用预测精度代替实际低force收益。\n\n新旧执行处理、同optimizer、同累计physics checkpoint的P3-B指标（达到固定收益尝试数、拒绝率/搜索失败率、效率曲线）均NOT_RUN。上层planner拒绝与motion不合格不是同一概念，全部原issued/accepted/activated记录保留。不能依据本轮判定该机制是主要全局优化瓶颈，或已经排除它。\n''';write('OPTIMIZATION_IMPACT.md',opt)
# Audit-oriented CSV with full original motion and safety fields.
with (P/'FULL_RESULTS.csv').open('w',newline='') as z:
 fields=['id','qualified','original_motion_pass','legacy_R2_matched','JF','JM','physical_task','scientific_receipt','host','true_shank_clearance_m','measured_sleeve_gap_m','tracking_RMS_deg','velocity_peak_deg_s','acceleration_peak_deg_s2','jerk_peak_deg_s3','jerk_RMS_deg_s3','excursion_deg','endpoint_deg','force_peak_N','moment_peak_Nm','guard_crossing_count','guard_unsatisfied_samples','post_filter_unsatisfied_samples','native_steps','wall_s','actual_robot_torque_max_abs_nm','task_robot_torque_clipped_commands','task_clipping_log_coverage','guard_acceleration_box_saturated_samples'];w=csv.DictWriter(z,fieldnames=fields);w.writeheader()
 for r in ordered:
  torque=next((t for t in read('audit/ALL_RECEIPT_NATIVE_IDENTITY.json')['rows'] if t['id']==r['id']),{}) if (P/'audit/ALL_RECEIPT_NATIVE_IDENTITY.json').exists() else {};clip=torque.get('task_clipping_audit',{})
  cl=r.get('original_clearance_minima_m',{});w.writerow(dict(id=r['id'],qualified=r['qualified'],original_motion_pass=r['motion_vs_B']['acceptance_pass'],legacy_R2_matched=r['axes']['LEGACY_R2_MATCHED'],JF=r['JF'],JM=r['JM'],physical_task=r['axes']['PHYSICAL_TASK_VALID'],scientific_receipt=r['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID'],host=r['axes']['HOST_EXECUTION_CAUSAL_VALID'],true_shank_clearance_m=cl.get('minimum_true_shank_clearance_m',r['clearance']),measured_sleeve_gap_m=cl.get('minimum_measured_sleeve_gap_m'),tracking_RMS_deg=json.dumps(r['tracking_RMS_deg']),velocity_peak_deg_s=json.dumps(r['native_motion']['velocity_deg_s']['max_abs']),acceleration_peak_deg_s2=json.dumps(r['native_motion']['acceleration_deg_s2']['max_abs']),jerk_peak_deg_s3=json.dumps(r['native_motion']['jerk_deg_s3']['max_abs']),jerk_RMS_deg_s3=json.dumps(r['native_motion']['jerk_deg_s3']['rms']),excursion_deg=json.dumps(r['dose']['excursion_deg']),endpoint_deg=json.dumps(r['dose']['endpoint_deg']),force_peak_N=r['force_peak_N'],moment_peak_Nm=r['moment_peak_Nm'],guard_crossing_count=len(r['crossing_events']),guard_unsatisfied_samples=r['guard_unsatisfied_samples'],post_filter_unsatisfied_samples=r['post_filter_gap_unsatisfied_samples'],native_steps=r['actual_new_native_steps'],wall_s=r['physical_wall_s'],actual_robot_torque_max_abs_nm=json.dumps(torque.get('actual_torque_max_abs_nm')),task_robot_torque_clipped_commands=clip.get('task_robot_torque_clipped_commands'),task_clipping_log_coverage=clip.get('coverage'),guard_acceleration_box_saturated_samples=torque.get('guard_acceleration_box_saturated_samples')))
print('RESULT_REPORTS_WRITTEN',len(ordered),'rows','elapsed_h',elapsed/3600)
