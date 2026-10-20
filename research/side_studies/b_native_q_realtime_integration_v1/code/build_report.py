"""Source-grounded 13-part report assembled from authoritative audit outputs."""
from task_bootstrap import *
from datetime import datetime,timezone,timedelta
from collections import Counter

WIN='C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1/delivery'
def read(name,default=None):
 p=STUDY/name
 return json.loads(p.read_text()) if p.exists() else default
def link(name,label=None):return f'[{label or Path(name).name}](<{WIN}/evidence/{name}>)'
def fig(name):return f'![{name}](<{WIN}/figures/{name}.png>)'
def fmt(value,d=3):return 'N/A' if value is None else f'{value:.{d}f}'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(str(x) for x in r)+' |' for r in rows])

def main():
 final='--final' in sys.argv
 if final:
  assert read('reports/CLOSEOUT_STATUS.json',{}).get('status')=='STOPPED_AND_RECONCILED','FINAL_REQUIRES_ORDERLY_CLOSEOUT'
 timing=read('reports/REQUEST_TIMING_RECONCILIATION.json');host=read('reports/HOST_QUALIFICATION_SUMMARY.json');receipt=read('reports/HOST_FAILURE_FORENSICS.json');trade=read('reports/SCIENTIFIC_CANDIDATE_TRADEOFF_SUMMARY.json');continuous=read('reports/CONTINUOUS_FROZEN_STABILITY_SUMMARY.json');q=read('reports/Q_CURRENT_COUNTERFACTUAL_AUDIT.json');compute=read('reports/AUDIT_COMPUTE_RECONCILIATION.json');resource=read('reports/RESOURCE_COMPUTE_DATA_SUMMARY.json');preserve=read('reports/PRESERVATION_AUDIT.json');queue=read('reports/QUEUE_CHARACTERIZATION.json');wide=read('reports/WIDE_CAUSAL_EQUIVALENCE.json');legal=read('reports/LEGAL_PREFIX_STABILITY_SUMMARY.json',{});suffix=read('reports/SUFFIX_LABEL_AUDIT.json');close=read('reports/CLOSEOUT_STATUS.json',{});data=read('reports/TOTAL_DATA_ACCOUNTING.json',{});retention=read('delivery/ACTOR_SOURCE_RETENTION_MANIFEST.json',{})
 raw=read('reports/RAW_PHYSICS_PROVENANCE_AUDIT.json',{});deferred=read('versions/E7_DEFERRED_FULL_NATIVE_EQUIVALENCE_GATE.json',{});selection=read('reports/FROZEN_SELECTION_INTEGRITY.json',{});closure=read('reports/SOURCE_CLOSURE_AUDIT.json',{});headroom=read('reports/ADMISSION_HEADROOM_AUDIT.json',{});idle=read('reports/RESOURCE_QUIESCENCE_AUDIT.json',{})
 raw_grid_runs=sum(r.get('actual_wall_new_command_steps_on_grid_before_host_write',0)>0 for r in raw.get('rows',[]));raw_grid_steps=sum(r.get('actual_wall_new_command_steps_on_grid_before_host_write',0) for r in raw.get('rows',[]));raw_grid_max=max([r.get('actual_wall_max_grid_start_lead_ms',0) for r in raw.get('rows',[])] or [0])
 now=time.time();stamp=datetime.fromtimestamp(now,timezone(timedelta(hours=8))).isoformat(timespec='seconds')
 b=read('output/002_T0_science_B_RESULT.json')['metric'];m=read('output/231_E6_LEAN_science_M2_RESULT.json')['metric'];dev=read('output/232_E6_LEAN_science_deviation_RESULT.json')['metric']
 version_rows=[]
 for p in sorted((STUDY/'versions').glob('*_FULL_NATIVE_EQUIVALENCE_GATE.json')):
  v=json.loads(p.read_text());version_rows.append([v['version'],v['status'],','.join(str(r.get('native_step_counts')) for r in v['rows']),all(r.get('full_native_step_signature_exact',False) for r in v['rows'])])
 latency=read('reports/ACCELERATION_LATENCY_SUMMARY.json',{});latencyrows=[[r['version'],fmt(r['baseline']['coordinator_ms']['p50']),fmt(r['optimized']['coordinator_ms']['p50']),fmt(r['optimized']['fast_prefix_ms']['p50'])] for r in latency.get('rows',[])]
 hostrows=[]
 for key,g in host['groups'].items():hostrows.append([key,g['attempts'],g['full_valid'],g['TASK_reached'],g['TASK_activated'],g['activated_over55'],g['learned_executions']])
 methodtotals={method:sum(r['method']==method for r in host['rows']) for method in ('M0','M2')}
 outcome=host['task_request_outcomes'];ages=[r for r in timing['rows'] if r['id']=='117_host_cold_pair3_accelerated' and r['request_id'] in (6,7)]
 deadline_rows=[['Physical bridge','40 ms','原生 scheduler reference_period 5 ms × 8；从合法 handoff 的物理 bridge 起点计时','保留旧合法动作/bridge；不能当作所有 request 的统一 source-age 截止'],['严格资格 evaluator','<55 ms','独立 scorer 对保存的真实 conservative activation age 作严格比较','ACTIVATED 且年龄 <100 仍可能不合格'],['Generic expiry','100 ms','原始 worker lifecycle：source age >=100 ms expired，当前状态重验后仍再次检查','未过期只满足生命周期的一项条件，不等于完整实时资格']]
 timeline_rows=[]
 for row in timing['rows']:
  if (row['id'],row['request_id']) not in [('000_T0_wall_B',6),('000_T0_wall_B',7),('001_T0_wall_M2',6),('117_host_cold_pair3_accelerated',6),('117_host_cold_pair3_accelerated',7)]:continue
  pieces=' + '.join(f"{s['start']}→{s['end']}={s['ms']:.3f}" for s in row['event_intervals'])
  timeline_rows.append([row['id']+'/'+str(row['request_id']),row.get('outcome'),fmt(row.get('age_ms')),fmt(row.get('request_available_to_actual_terminal_ms')),pieces])
 texts=[]
 texts.append(f'''# B-Native Q Real-Time Integration & Conditional Repetition Adaptation v1

状态：**{'FINAL' if final else 'DRAFT — 工作仍在进行'} / EXACT SCIENTIFIC EQUIVALENCE PASS / HOST-CLOCK NOT QUALIFIED / ADAPTATION NOT RUN**。生成时间：{stamp}。从保守登记起点 2026-10-07 01:19（上海）计时，当前 {((now-START)/3600):.3f} h。没有训练或更新 Q。

科学收益得到保留，实际执行链仍未达到原始实时要求。公共 B 已在 commissioning、当前状态重验及物理 catch-up 中出现失拍；M2 增加的主要成本是同一边界重复上下文与原生证书，而 Q 推理本身约 0.016–0.096 ms。已用两版有依据的公共 B 工程修复完成回归和复测，未派发第三版控制修复。

原始轨迹、失败和历史报告保留在 WSL：`{STUDY}`。本 Windows 目录是可审阅的 compact 导出；完整 native trace 没有重复导出到 Windows。{link('USER_REQUEST.txt','用户授权和冻结范围')}；[冻结源码行索引](<{WIN}/SOURCE_GUIDE.md>)。

## 1. Exact B/M2 timing timeline

{table(['规则','数值','原始计时与判定','含义'],deadline_rows)}

上述三个时钟作用不同。原始 request source timestamp 一直保持不可变；实际activation使用原始command receipt的conservative时间，记录真实host write，未重写已经积分的物理轨迹。wall physics在planner运行期间按固定epoch追赶，期间保留已持有命令；原fixed-grid模拟滞后局限见第6节，不能据此宣称连续实时部署。

100ms边界也保留原始比较符：PlanLifecycle.expired使用age>=100ms，low-level WallPhysicsSession.apply写前及写后检查使用>100ms。没有把两个stage的比较符统一或放宽；恰好55ms仍不符合独立严格资格，恰好100ms的理论边界差异不能视为实时通过。

source_capture_ns是原physical sensor sample映射到固定wall epoch的source stamp；原artifact另有host_materialized_ns，二者不能混成同一个真实host采集完成时刻。request_ns是native modifiable request实际创建时刻。表格同时列source-age与request实际可用→activation/处置耗时；原55/100判定仍按原source stamp，不重新定义年龄。源码带原行号审阅链接见 [SOURCE_GUIDE.md](<{WIN}/SOURCE_GUIDE.md>)。

{fig('actual_activation_timeline')}

图中 40 ms 虚线仅表示 bridge 的时长尺度。bridge 的物理起点和 source-age 的起点不同，不能据图把 40 ms 解释为所有 request 的年龄截止。

{table(['实际 request','处置','原source年龄 ms','请求可用→实际终点 ms','不重叠原始事件区间 ms'],timeline_rows)}

本轮 {timing['request_count']} 条原始 request 的事件区间均可与最终 disposition/activation age 对齐，审计问题数 {len(timing['issues'])}。基线M2/001/request6的request→snapshot=315.526469ms，包含同步research coordinator，不能全部归因于pickle；worker69.683975ms之后，到TASK_PHASE_CHANGED/CANCELLED disposition还有647.042876ms。该请求没有记录main collect或command activation；1039.964128ms是source→最终处置年龄，不是activation latency，末段也不能全部称为queue等待。图只画实际ACTIVATED的B/E5实例，表另保留这个baseline M2取消实例。22 个保存状态的原生 B payload 序列化 p50={fmt(queue['payload_stats']['snapshot_ms']['p50'])} ms，decode p50={fmt(queue['payload_stats']['decode_ms']['p50'])} ms，payload p50={fmt(queue['payload_stats']['bytes']['p50'],0)} bytes。

证据：{link('reports/REQUEST_TIMING_RECONCILIATION.json')}；{link('reports/SOURCE_EVIDENCE_INDEX.json')}。''')
 texts.append(f'''## 2. Bottleneck attribution

**原生 B**：TASK process worker 已在物理 epoch 开始前预热，首次 TASK 的 66.44 ms 不是冷解释器启动；后续原始 B worker p50 约 38.84 ms。还需支付采集、结果传回/调度、当前状态模型重验及命令构造，示例真实 ACTIVATE 为 99.33/74.21 ms。commissioning 同步 planner 约 1–8 ms，其validation/command窗口约8–20ms包含原生命令检查/构造及receipt物理追赶，不能全部称为TASK模型重验；这些总成本已超过5ms feedback周期，追赶仍持有旧命令。

原profile与validation窗口的独立交叉核对共167窗。原B/TASK 7个窗：model revalidation p50=7.457ms、receipt_prepare旧命令追赶p50=8.206ms、其余原检查/构造p50=3.012ms；窗口总p50=18.625ms，各项p50不相加冒充总p50。commissioning 33个窗中没有TASK revalidation wrapper事件：receipt_prepare p50=4.654ms，其他原检查/构造p50=3.651ms，整体窗口p50=8.830ms。E5两个TASK窗model revalidation p50=3.090ms，receipt_prepare p50=5.770ms；不同state及样本量不作为配对速度因果结论。wrapper嵌套区间先union再partition，mechanics包含在model revalidation内不重复加账；关闭profile的E6/E7不写成0耗时。{link('reports/ACTIVATION_CHAIN_COMPONENTS.json')}。

原fixed-ready源码顺序为：当前model activation validator/phase检查→suffix splice guard→原reference-motion/velocity检查→prepare_apply积分旧command到已冻结ready目标→effective reference-motion复核→原lifecycle expiry/真实write。prepare之后的reference复核不是第二次全model certificate；本轮保留这个原始顺序及全部检查，未通过重排或重新打时间戳缩短记录年龄。

**M2 增量**：旧adapter在主线程同步构造context，再为候选重复执行原生B nominal选择与完整检查；这些工作落在source-age内。内部B的S用于选取certified nominal，必须保留。原HumanWaypointFeedbackMPC按(total_cost,label)排名；S含goal error、waypoint change、completion及原future-value hook项。native residual先取得原B，再做当前残差的完整_evaluate及fallback。原先约185ms的“validation/S”混合计时不能全部解释成S scalar计算。B2源码检查未发现可独立删除的重型performance-only外层S：native_local仍记录float(e.total_cost)，M2原本就不以S作最终排名；没有删除S、原生证书或声称S移除带来提速。减少的是同一request重复nominal/context计算、候选validation数量和重复已认证snapshot执行。E5将当前causal context / Q / candidate certificate移入既有原生TASK worker，保留原始source和当前状态重验；实际coordinator p50约34.76ms，但worker仍约44.58–49.19ms，真实ACTIVATE为75.46–77.66ms，而且late guard丢弃了学习proposal。

**公共执行链限制**：独立 evaluator 还要求 control_cycle_misses=0、任一命令 receipt native_steps≤20，以及没有 HOST_LATENCY fallback。{receipt['with_receipt_gaps']}/{receipt['attempts']} 个实际 active epoch 都存在 >20-step receipt，且 {receipt['with_initial_support_gap']} 个在初始已验证 support receipt 上已出现间隙。这些包含 TASK 前的真实持有；不能凭 TASK 的平均 compute 更快通过完整实时资格。

初始support已在离线组装/预载阶段按原contract验证，不是晚到proposal。73个epoch的首个native integration相对epoch p50=2.291ms；72个initial support receipt的网格持有超过5ms，网格p50=12.750ms。71个观察到实际首个write的epoch全部超过5ms，实际write p50=16.213ms、p95=113.873ms；另外2个没有首个write，单列censored。首个write与其effective grid的差p50=3.646ms。未把整段时间归因于解释器启动：原process prewarm在epoch前，sensor/observer/reference history和commissioning command工作仍在epoch后。{link('reports/INITIAL_SUPPORT_ATTRIBUTION.json')}。

**实际物理计算预算**：原host_step_start/finish只覆盖plant.step_native与少量receipt bookkeeping；native状态/接触复制、monitor、sensor capture及循环在其外。E7 quiet cold组的原始窗口里 B/M2的run-level catch-up计算/物理时长比p50分别0.774/0.793，每个5ms反馈周期已需约3.87/3.97ms物理追赶处理，尚未加planner/current-model validation。该比值是不同状态的描述性观测，不是E6与E7的配对因果速度差；全部群组在原report保留。{link('reports/NATIVE_WALL_UTILIZATION.json')}。

**queue / 传回成本**：4 个独立预热 process × 6 个保存状态、4 个条件共 96 次有限请求，原始完整 native decision 均在 1e-10 内一致。无竞争 T0 process 首次 worker p50=64.84 ms，enqueue→collect=77.94 ms；C2 首次为 38.72 /49.10 ms，后续为 21.77 /29.78 ms。C2 process 加父进程同状态重复规划后，首次 enqueue→collect=58.53 ms，后续39.12 ms；C2 thread 与同状态重复规划首次160.37 ms，后续99.10 ms。thread 条件下全局 C2 安装也作用于父线程，这个测试表示重复 certified planner 竞争；不是实际 MuJoCo 的 substitute，也不是资格通过证据。进程 worker 的结果传回本身有约8–12 ms成本，不能把它全部记成 OS scheduler 等待。

证据：{link('reports/HOST_FAILURE_FORENSICS.json')}；{link('reports/QUEUE_CHARACTERIZATION.json')}；{link('reports/ASYNC_TIMING_DETAILS.json')}。''')
 texts.append(f'''## 3. Optimization versions

| 版本 | 实质变化 | 处理与边界 |
| --- | --- | --- |
| T0 | 原始 B 和 frozen M2 | 新测冻结基线；历史 8/8 不重跑 |
| E1 | 同 request 共享 certified nominal context | 状态/引用/belief/ownership/request 限定生命周期；跨边界失效 |
| E2 → E2r1 | Q-first complete-native-validation排序，保留原S | 未发现可独立删去的heavy外层S；E2 legal deviation出现UnboundLocalError，保留失败；r1显式调用NativeInterface.choose修复 |
| E3 / process C1 / parent C2 | 尝试证书复用、process、batch | 原 worker 已是 process，父进程 monkeypatch 未进入子进程，部分路径 NO-OP；未伪称有效提速 |
| E3T | 同一数学语义的 thread 证书复用 | 公共 B 修复1；SCI 等价，actual cold 失败 |
| E3T_C2 / C2A | 原始 21 mechanics 样本批处理并保证最终 payload | 公共 B 修复2；标量 shadow ≤1e-10；靠近阈值返回原标量路径 |
| E5_NATIVE_WORKER / HOST_v1 | 当前上下文和 frozen Q 在既有原生 TASK worker 内运行 | 原始当前状态重验和 safe_fallback.prepare 保留；晚 proposal 恢复原合法 carry 并重验 |
| E6_LEAN | 关闭 research-only 嵌套 profiling/锁包装 | 原 lifecycle、全轨迹、provenance、import firewall、safety 保留；SCI exact，quiet actual 在 TASK 前失败 |
| E7_DEFERRED | 原生每步复制 evaluation-only monitor 输入，事后按原式同序聚合 | source 证实 observer 不参与控制/估计/安全；原每步采样不丢弃，评分 JSON bit-exact；不是第三个公共 scheduling 修复 |
| CONSECUTIVE_r1 | 同父进程有限 run 生命周期 | 最小 metadata 修复；历史 SCI 字面 mode 改为实际 summary mode，不改 evaluator |

SCI 中留有 full-validation shadow，所以 SCI coor 或 fast prefix 是研究计时，不能直接当部署端到端延迟。E6 的 SCI 运行时与 O10 有已记录的 CPU 并行，quiet host 复测是在 O10 全部结束后独立派发。

最终cache lifetime只读审计覆盖259个nominal boundary和90个certificate事件：65次exact-byte/same-request命中、20次hash miss、5次原generic expiry拒绝，0项ownership/source/hash/expiry违规。没有把miss或expired当命中。E5/E6/E7的worker-local字典每个execute重新建立，关闭profile后不宣称逐事件import/cache attestation；轨迹等价由完整native gate另证。{link('reports/CACHE_LIFETIME_AUDIT.json')}。

各nominal SCI exact gate对应的延迟记录如下，均为p50；coordinator含full-validation shadow，fast prefix在proposal submission之前结束、排除shadow，不是完整command activation。相同科学轨迹不意味着相同host timing epoch，各版后期research/CPU压力不同，因此不宣称随机化的因果速度比。

{table(['版本','T0 SCI coordinator ms','该版 SCI coordinator ms','该版 SCI fast prefix ms'],latencyrows)}

实际E5保留2条request：coordinator p50=34.763ms、activation source-age p50=76.561ms，p95=77.554ms，max=77.664ms；两条晚proposal均丢弃、learning execution=0。数据见{link('reports/ACCELERATION_LATENCY_SUMMARY.json')}。

precompute/pipeline范围复核：静态candidate模板、固定transforms与epoch前process/import warm-up可以提前准备；原PlanRequest冻结、capture write-once、lifecycle单outstanding request，residual authority仅在当前OUTBOUND/RETURN非terminal边界。当前causal observation/Q、candidate certificate和activation current-model重验不能由未来state或旧boundary替代。E5利用既有worker执行当前immutable snapshot，没有创建未来request；它没有解决5ms物理feedback与admission路径的阻塞。上述结论只限已检查接口，不声称不存在未来架构扩展。{link('reports/PREPARATION_SCOPE_REVIEW.json')}。

未推广的离线方案：完整 clearance memo 没有 full-cert hit；多项式缓存约 10% 更慢，纯 roots 小缓存约 2.71% 小收益；原数学 C++ interval 11.62% 更慢、trig 1.61% 更慢；纯 derivative 中间量缓存仅约 1.25% 收益。均保留原证据，未凭微小收益更换正式控制路径或新增 deployment 声明。

证据：{link('reports/EVIDENCE_CATALOG.json')}；`evidence/versions` 保存每版 preregistration、source hash、冻结 manifest 和 gate。''')
 texts.append(f'''## 4. Scientific equivalence gates

每个正式实质版本比较 original B / frozen M2 / legal deviation；既有容差 1e-10 未放宽。涵盖 selected identity、全部 candidate acceptance/rejection、fallback、实际激活决策、q/dq/ddq、5 ms trace、每0.25 ms native qpos/qvel/torque/contact、J_F/峰值/moment/tracking/clearance 和 phase timing。

{table(['版本','完整 gate','B / M2 / deviation native count pairs','完整 native array/contact bit exact'],version_rows)}

E2 初版 FAIL 保留，E2r1 后才推广；CONSECUTIVE 初版记录了两个完整物理运行后的 metadata 失败，修复后重新通过 gate。所有失败和修复均计 physical attempts。

B4 拓展离线审计：{wide['comparisons']} 个不重复同状态候选池、{wide['native_validation_calls']} 次 full certificate 调用，scalar 原始与 C2/shared-context acceptance 完全一致，target 在1e-10内一致，含 conservative roundoff fallback 的 Q-first selected identity 一致，{len(wide['errors'])} 个错误。22个保存状态、最多512候选种子，不优化物理结果、不做 E 搜索、不增加 physics；有限状态覆盖不能推断连续空间证明。

E7 的 original true_physics 评分记录在 B/M2/legal deviation 三组均 bit-exact；每组保留116,320个native样本及2个原boundary样本，事后仍调用原 observe/record 数学。postprocess约0.775–0.865s，明确在物理阶段之外执行。source-grounded observer隔离审计PASS；无原control/safety consumer被移出链。

额外基线入口隔离：original runtime B与B-native PrefixBInterface的empty residual入口，在同一seed下116,320个native步、全部reference/decision/fallback/R2及原true_physics JSON精确一致。不是新的优化或第三个公共B修复。随后原生零Q入口4个cold run仍0/4 VALID：2个在commissioning触发原20ms acceleration-envelope，2个到TASK后ROLLING_SUFFIX_STALE_AT_APPLY；6次TASK activation全≥55ms。该实验直接隔离没有Q的B-native执行链，不把相同scalar cost当入口等价证明。{link('reports/BASELINE_RUNTIME_ROUTE_EQUIVALENCE.json')}。

证据：{link('reports/WIDE_CAUSAL_EQUIVALENCE.json')}；{link('reports/EVIDENCE_CATALOG.json')}。''')
 texts.append(f'''## 5. Host-clock qualification

真实 wall physics 尝试 **{host['valid_complete_tasks']}/{host['attempts']} 完整任务 VALID**。M0 B={methodtotals['M0']} 次，M2各版本={methodtotals['M2']} 次；均未取得资格。完成原 B / baseline M2 / accelerated 各4+冷启动及同父进程连续 run；连续 timing run 每次新建 plant/commissioning/native worker，并不等于同一 Human 会话 personalization。

{table(['分组','尝试','完整VALID','到达TASK run','TASK ACTIVATED','ACT年龄≥55','非零学习执行'],hostrows)}

总 request：TASK {host['task_request_count']}，pre-TASK {host['pre_task_request_count']}。TASK outcome={json.dumps(outcome,ensure_ascii=False)}。TASK ACTIVATED 中 {host['task_activated_over55_count']}/{host['task_activated_count']} 年龄≥55 ms，严格年龄失败比例={100*host['task_activated_over55_count']/host['task_activated_count']:.3f}%；denominator 只含实际激活，未激活请求不混入。学习 proposal late discard={host['late_discard_count']}。失败在 TASK 前的组，Q/coordinator/候选预算 actual latency 被 censor，不能写0 ms或0%late。

E6_LEAN 四组 balanced B/M2 cold pairs 各4次全部在 TASK 前失败：backlog、20 ms waypoint acceleration-envelope、commissioning timeout。没有把旧 B timing blocker 归因于 Q，也没有进入第三个公共 B 修复或放宽控制/安全时钟。

E7_DEFERRED 四组 balanced B/M2 quiet cold pairs：B 0/4、M2 0/4 完整 VALID；B 2次、M2 2次到达 TASK。M2 7个TASK activation中6个年龄≥55ms，7个晚学习proposal均被丢弃；唯一低于55ms的activation仍是原合法carry，非零学习执行证明为0。该组观察到更多到达TASK的run，仍有原始5ms反馈链、当前状态重验及旧计划持有的限制；不同seed的到达率不构成匹配的因果加速证据。

E7另登记B/M2各4次同父进程连续host检查，测试新增observer registry/logging的有限生命周期。每次仍重新commission/new plant/new worker；没有改变E7 actor或增加公共scheduling修复。该组最终结果列在上表，全部失败/中断均计数。

证据：{link('reports/HOST_QUALIFICATION_SUMMARY.json')}。''')
 texts.append(f'''## 6. Actual learned-action execution evidence

**实际非零学习动作执行证明数={host['learning_execution_proven_count']}；及时执行证明数={host['timely_learning_execution_proven_count']}。** Q proposal、plan_changed、native ACTIVATED 和非零 K3 的真正物理执行是不同事件。

E5/E7的19ms=min(40,55−36)是预登记的research proposal-return guard，36ms为下游预留；它不是原生evaluator的第四个截止条件。原生40ms physical bridge、严格<55ms年龄、100ms expiry仍分别保留。晚carry重新certify和recording约4.36–8.07ms，不能从旧carry的实测activation直接扣去这些时间，就断言未执行learning plan本可以及时。

唯一冷启动<55ms的request是296/request12，实际年龄53.569475ms。其OUTBOUND coordinator count=6，原五槽mask将当次动作映射为[0,0,0]，即使Q选中含未来RETURN动作的negative graph；因此它本身不提供非零学习执行证明。{link('reports/ADMISSION_HEADROOM_AUDIT.json')}。

全部73个actual run中，共5个TASK activation年龄<55ms：上述296/request12零carry；300/B的request11/12为原HOLD；311/M2的request12/13同样是原HOLD，原worker evidence的selection_row为空、Q_calls累计保持30。HOLD没有residual动作authority；33.7605/45.641053ms不能计作Q命令按时执行。逐条original decision/learning record关联见{link('reports/TIMELY_ACTIVATION_COVERAGE.json')}。ADMISSION_HEADROOM的23条只含已保存async worker且存在selection的记录，其23/23晚丢弃不替代所有实现的31条总late记录。

原frozen coordinator的count在choose/apply构造proposal时增加，发生在native activation之前；E5晚guard恢复carry，却未事务式回滚count。实际失败prefix中的cancelled/expired尝试可能消耗coordinator计数，因此count不代表已经物理执行的学习槽。SCI exact gate及Q重建保留原feature定义，这项actual bookkeeping局限单列，不以改mask/candidate authority修饰失败结果。{link('reports/NATIVE_COUNT_AUTHORITY_AUDIT.json')}。

执行审计连接原始 request owner、原始 conservative actual activation timestamp 或 native learning-record 的半开 active segment，再核对 applied command receipt 的 native_steps>0、当次 nonzero K3 与 late admission surviving。117 E5 的两个 request 虽原生 ACTIVATED，但丢弃了晚 learning proposal，恢复零 carry；因此不能数成学习控制执行。SCI 的动作确实产生科学轨迹，但 planner 计算期间免费冻结 host 模式，不能计入 actual wall qualification。

审计数据逐 request 保存 applied K3、late_discard、native outcome、实际 age、receipt index、原始连接依据及积分步数。证据：{link('reports/117_host_cold_pair3_accelerated_LEARNING_EXECUTION_AUDIT.json')}；{link('reports/HOST_QUALIFICATION_SUMMARY.json')}。''')
 texts[-1]+=f'''

全原始物理provenance审计：{raw.get('status','PENDING')}，覆盖{raw.get('attempts_audited',0)}次尝试、{raw.get('native_steps_audited',0):,}个native步，receipt持有命令、step数、qpos/qvel有限性、原0.25ms网格及原TASK积分均核对。实际host integration在对应command write之前的违规为0。

必须保留的模拟时钟限制：{raw_grid_runs}个actual epoch、{raw_grid_steps:,}个新命令步的fixed wall-grid起点早于真实host write，最大lead={raw_grid_max:.6f}ms；这些步本身是在真实write之后才计算，属于单owner catch-up的模拟滞后。没有改写已积分state，也没有用grid time伪造activation；conservative actual activation保持真实write下界。这个provenance PASS不能证明硬件连续实时部署，所有实时资格仍按原evaluator失败。证据：{link('reports/RAW_PHYSICS_PROVENANCE_AUDIT.json')}。

冻结Q的独立selection审计={selection.get('status','PENDING')}，覆盖{selection.get('runs',0)}个run、{selection.get('native_selection_rows',0)}次selection；当前特征/原Q/valid-subset或all-Q计算、完整池排名及late carry一致。partial fast pool不假装全部候选已validation。{link('reports/FROZEN_SELECTION_INTEGRITY.json')}。'''
 texts.append(f'''## 7. Scientific benefit after acceleration

完全同轨迹 gate 的 nominal matched seed：B J_F={b['J_F']:.6f} N·s，E6 frozen6 M2={m['J_F']:.6f} N·s，下降 {100*(b['J_F']-m['J_F'])/b['J_F']:.3f}%；moment integral {b['moment_integral']:.6f}→{m['moment_integral']:.6f} N·m·s。原匹配 legal deviation E6 J_F={dev['J_F']:.6f} N·s；这是和原 frozen M2 对照的 exact regression，不能把单个 favorable seed 的9.25%替代历史8-pair7.177%。

新6/4/2 study 的4组 exposed nominal/合法 deviation（见第10节）全部 SCI VALID；6候选平均 paired力积分下降 {trade['aggregate']['6']['mean_paired_reduction_percent']:.3f}%，nominal {trade['aggregate']['6']['nominal_mean_paired_reduction_percent']:.3f}%，deviation {trade['aggregate']['6']['deviation_mean_paired_reduction_percent']:.3f}%，moment增幅 {trade['aggregate']['6']['mean_paired_moment_increase_percent']:.3f}%。保持原科学收益，但尚不能称 host-qualified Phase C。

CASE4另预登记8组不同合法prefix/8个新候选种子：状态={legal.get('status','RUNNING / not yet summarized')}，有效pair={legal.get('valid_pairs','pending')}/8，正向pair={legal.get('positive_pairs','pending')}，平均paired下降={fmt(legal.get('mean_paired_reduction_percent'))}%，平均moment增幅={fmt(legal.get('mean_paired_moment_increase_percent'))}%。这是 labels不足情况下的冻结Q科学稳定性补充；没有 new-Human 或 multi-Human泛化含义。预学习 OUT prefix 与 commissioning 的每个 native state/command/contact 及 reference 在首个 Q source boundary 前做配对审计，之后学习导致的分歧是预期的。RETURN prefix 可在不同起点被实现，不宣称其物理效果匹配。

{fig('legal_prefix_stability')}

证据：{link('reports/SCIENTIFIC_CANDIDATE_TRADEOFF_SUMMARY.json')}；{link('reports/LEGAL_PREFIX_STABILITY_SUMMARY.json')}；{link('versions/LEGAL_PREFIX_STABILITY_PROTOCOL.json')}。''')
 texts.append(f'''## 8. Q structure / state-dependence audit

**{q['status']}**。冻结 linear Q 特征维度120：state58（原55D causal observation+3D prior residual）、candidate U30、carry30、coordinator counts2（OUT/5、RETURN/5）；无 state×plan interaction，mixed derivative=0。实数等价形式为`Q = bias(state58) + w_U·mask(U30) + w_C·mask(carry30) + w_n·counts2 + constant`，固定scaling可吸收进系数。实际部署先做float32 feature/normalization，再用float64 linear weights/output；没有在本轮改算术顺序。

对于同一native边界的不同 U，state/carry/count 是公共输入。实数算术中的 Q差由固定计划系数产生；原coordinator计数mask清除已尝试的位置，计数变化可改变剩余计划特征及排序。actual失败prefix的count不等于已物理提交的学习动作数。候选生成器的c参数未被使用：池直接依赖carry、count、seed与固定historical design，而不直接依赖当前state/phase/progress。phase在native_local中决定当前实际动作槽；原55D observation内的phase one-hot属于共同state bias。当前state影响native feasibility/realization，也可通过执行历史间接改变carry/count；这些不表示 linear Q 学会了 state-conditioned candidate preference。独立AST及22个保存状态、330次有限pool检查通过；只改变phase label且保持observation/carry/count时，feature与Q保持bit-exact。该代数probe不作为合法物理状态或新Human实验。{link('reports/Q_POOL_DEPENDENCY_AUDIT.json')}。

22个当前保存状态的 same-state feature counterfactual：输入公共特征字节相同；由于 native scaling/dot有限精度，候选差值对代数分解最大误差约3.01e-6 N·s，公共state-bias扰动的 pair差漂移约4.55e-13 N·s。初版把共同 contribution 的 dot 当成严格bit-exact而触发断言，失败保留，r1改为检查公共输入字节相同且报告真实 roundoff；未改变 Q 或部署容差。nominal/deviation结果中的Q候选偏好在这个模型中只能来自固定masked-plan系数，仍结合原生state-dependent可行子集与控制实现产生轨迹；已有证据没有做收益的因果分解，不能量化“固定排序贡献了多少百分比”，也不能把7%左右的收益解释为学得个体化状态偏好。

{fig('linear_Q_plan_coefficients')}

当前 force 收益仍有效，但不将其解释成新Human个体化能力。Q文件SHA-256：`{q['weights_sha256']}`。

证据：{link('Q_STRUCTURE_AUDIT.json')}；{link('reports/Q_CURRENT_COUNTERFACTUAL_AUDIT.json')}。''')
 rep_rows=[[r['repetition'],r['B_valid'],r['frozen_valid'],fmt(r['B_J_F']),fmt(r['frozen_J_F']),fmt(r['paired_force_reduction_percent']),fmt(r['B_moment']),fmt(r['frozen_moment'])] for r in continuous['rows']]
 labelrows=[[r['id'],r['eligible_complete_labels'],r['censored_replacement_labels'],r['labels_used_for_training']] for r in suffix['rows']]
 texts.append(f'''## 9. Conditional repetition adaptation / frozen stability

**Adaptation pilot NOT RUN；frozen vs adaptive=N/A；Q updates=0。** Scientific gate PASS，但实际 wall qualification和学习动作执行 gate未通过，因此不触发自动训练。当前会话 gate 也不能由 SCI 的positive结果替代。

真实 persistent SCI 两组保留同一plant、updater、measurement filter、RNG和 commissioned belief sequence351：Rep1均纯B，Rep2起另一组用frozen M2。Rep1两组完整 native轨迹均与原B bit-exact。它与“同父解释器新plant”的host consecutive测试分开。

{table(['Rep','B VALID','frozen VALID','B J_F','frozen J_F','力下降 %','B moment','frozen moment'],rep_rows)}

{fig('persistent_repetition_stability')}

Rep4两组物理完成、原 safety/physical audit PASS，但HOLD=1.030 s超过原R2 upper1.020 s；failed cost只保留unranked，Rep5未派发。原reference governor对每个0.5s hold用1e-12完成容差；Rep4绝对物理时钟的elapsed短缺约1.18234e-11 s，两段hold各多等1个5ms tick，累计+10ms。read-only重建确认schedule duration仍是0.5s，且原trace决策commit恰好在下一control tick。没有reset physical clock、放宽1e-12或R2阈值。原persistent native接口只支持SCI，不能侵入式改成actual continuous来伪造资格。

当前重复/合法结果的suffix标签审计：

{table(['run','兼容完整remaining-cost label','被后续plan替换而censored','用于training'],labelrows)}

标签只使用当前rep当前native state后的 measured-force left quadrature；rolling controller替换剩余图后不把最终fullcost当早期candidate的committed标签。审计不是新certified训练集；censored cost未用于完整Qtarget。训练没有发生。

扩大到所有有trace的M2 selection后，{suffix.get('aggregate',{}).get('runs',len(suffix['rows']))}个run共找到{suffix.get('aggregate',{}).get('eligible_complete_labels',0)}个图级兼容完整suffix标签，{suffix.get('aggregate',{}).get('censored_replacement_labels',0)}个实际执行后发生剩余图替换的censored记录。完整标签来自SCI合法prefix，不能解除actual gate，且未作为训练数据使用。

证据：{link('reports/CONTINUOUS_FROZEN_STABILITY_SUMMARY.json')}；{link('reports/R2_CLOCK_RECONSTRUCTION.json')}；{link('reports/SUFFIX_LABEL_AUDIT.json')}。''')
 budgetrows=[[k,fmt(v['B_mean_J_F']),fmt(v['M2_mean_J_F']),fmt(v['mean_paired_reduction_percent']),fmt(v['nominal_mean_paired_reduction_percent']),fmt(v['deviation_mean_paired_reduction_percent']),fmt(v['mean_paired_moment_increase_percent'])] for k,v in trade['aggregate'].items()]
 texts.append(f'''## 10. Candidate-count compute–performance tradeoff

{table(['候选数','B均值 J_F','M2均值 J_F','paired力下降 %','nominal %','deviation %','moment增幅 %'],budgetrows)}

{fig('candidate_budget_scientific')}

6候选是冻结科学reference；4/2候选明确是 **COMPUTE–PERFORMANCE TRADEOFF，不是 EXACT_EQUIVALENT**。所有预算同一Q、安全、Human，16个SCI尝试均VALID。另6个actual6/4/2尝试均未到TASK，所以真实预算-dependent coordinator latency、late rate无法从该组估计，不能用SCI shadow或0分母冒充实际速度。

证据：{link('reports/SCIENTIFIC_CANDIDATE_TRADEOFF_SUMMARY.json')}。''')
 texts.append(f'''## 11. Resource / compute / attempt ledger

新增physics尝试={compute['attempts']}，END={compute['ended']}，VALID={compute['valid_physics_attempts']}，failed/invalid={compute['failed_or_invalid_attempts']}；当前active={compute['active_ids']}。所有failure/retry、metadata失败、冷启动、同进程子rep、连续rep都逐次计数；没有漏掉fullphysics后报告失败的任务。绝对160上限未超过。

实际新增物理时间下界={compute['total_actual_new_physics_seconds_lower_bound']:.6f} s；native步数下界={compute['total_actual_new_native_steps_lower_bound']:,}；disjoint top-level physics-owner inclusive wall={compute['disjoint_top_level_physics_owner_wall_seconds']:.3f} s。main model API和native-worker API分别列账，不因thread可能重叠而相加成unique总数。并行offline wall不加到package elapsed；parent inclusive wall不再加其child wall。

最终原始计数验证完成={compute.get('raw_count_verification_complete',False)}；authoritative新增物理时间={compute.get('authoritative_total_actual_new_physics_seconds',compute['total_actual_new_physics_seconds_lower_bound']):.6f}s，native步数={compute.get('authoritative_total_actual_new_native_steps',compute['total_actual_new_native_steps_lower_bound']):,}。{compute.get('raw_verified_additional_terminal_native_steps',0)}个终端尾部步原先位于最后control/partial snapshot之后，经逐步状态、receipt和original wall record三重核对补入；原下界与append-only日志保留。上述总数另将inter-rep 120步计入一次，未把absolute clock累计重复相加。

原COMPUTE_LEDGER只追加而未改写；发现consecutive child metrics缺漏、absolute plant time重复计数和main API累计计数后，以AUDIT_COMPUTE_RECONCILIATION为总账。连续rep使用真正起点差分，原inter-rep settle/hold物理时间和步数另计。未发现compute来源缺失：{compute['missing_compute_ids']}。独立离线账簿闭合检查覆盖81条已登记job、58个声明source版本，全部源码可恢复；4条非零返回记录原样保留。各区间和zero-physics scope通过，离线wall sum/union均不加到package elapsed；未单独登记的短时报告helper由最终source/export manifest表示，不宣称账簿覆盖全部维护调用。原wrapper在completion记录source SHA，不等同于逐module import attestation。{link('reports/NONPHYSICS_LEDGER_CLOSURE.json')}。

资源：WSL MemAvailable最小 {resource['WSL_mem_available_min_bytes']/2**30:.3f} GiB，owned PSS最大{resource['owned_PSS_max_bytes']/2**30:.3f} GiB；Windows commit headroom最小{resource['Windows_commit_headroom_min_bytes']/2**30:.3f} GiB，available最小{resource['Windows_available_min_bytes']/2**30:.3f} GiB，C盘最小可用{resource['Windows_disk_C_min_bytes']/2**30:.3f} GiB。swap amount稳定{resource['swap_used_max_bytes']/2**20:.3f} MiB，swap-in={resource['swap_in_delta_pages']}pages，swap-out={resource['swap_out_delta_pages']}pages，OOM delta={resource['oom_kill_delta']}。未触发持续危险退避；未杀未知进程、未重启WSL、未修改RAM/swap或dropcache。

常规采样cadence为45s；首次durable task-owned row相对保守START延迟{fmt(resource.get('initial_task_owned_sample_delay_seconds'))}s，setup至首样本区间不假装具有45s记录。早期runner缺少compute模块崩溃后恢复，原采样最大gap={resource['runner_max_sample_gap_s']:.3f}s明确保留，不插值造样。极值/PSS限于记录过的scope/window：routine涵盖runner/physics descendants；offline sweep样本涵盖自身及已验证runner后代，两种scope在图中分开。graceful join之后最后一次resource row的owner另标FINAL_POST_RUNNER_JOIN_READ_ONLY_REVIEW，PSS仅为当时的final sampler helper，不表示runner/physics仍在运行。短时Windows available下降只记录。

物理任务全部END后的runner范围观察：{idle.get('samples','pending')}个idle样本、跨度{fmt(idle.get('recorded_span_seconds',0)/60)}min；runner及其验证后代PSS p50={fmt(idle.get('idle_runner_and_descendant_PSS_GiB',{}).get('p50'))}GiB，进程数max={idle.get('idle_owned_process_count',{}).get('maximum','pending')}；这段swap-in/out={idle.get('swap_in_delta_pages','pending')}/{idle.get('swap_out_delta_pages','pending')}pages，OOM delta={idle.get('oom_kill_delta','pending')}。短时独立read-only helper不属于runner ancestry；共享可用内存也受其他进程影响，不把有限观察当成普遍无泄漏证明。{link('reports/RESOURCE_QUIESCENCE_AUDIT.json')}。

{fig('resources')}

WSL新增task目录含startup/source/deps copy={resource['study_total_bytes']/2**30:.3f} GiB；Windows authoring+compact delivery及合计见TOTAL_DATA_ACCOUNTING。测量Unix时点={data.get('measured_unix','pending')}，两处logical file bytes合计={fmt(data.get('total_added_bytes_conservative',0)/2**30) if data else '待最终审计'} GiB，含两份导出/源码重复copy，目标<10GiB；不是allocated disk blocks。少量后续report/accounting/export manifest会再增加metadata字节，raw physics在159 END之后冻结。无需重新计算旧study历史费用。

证据：{link('reports/AUDIT_COMPUTE_RECONCILIATION.json')}；{link('AUDIT_TASK_LEDGER.json')}；{link('ATTEMPTS.jsonl')}；{link('NONPHYSICS_JOBS.jsonl')}；{link('reports/RESOURCE_COMPUTE_DATA_SUMMARY.json')}；{link('reports/TOTAL_DATA_ACCOUNTING.json')}。''')
 texts.append(f'''## 12. Source / Git preservation

Preservation={preserve['status']}；原study受保护文件{preserve['old_protected_files_checked']}个，差异{len(preserve['old_protected_mismatches'])}；新副本原控制source{preserve['relocated_frozen_control_sources_checked']}个，差异{len(preserve['relocated_control_source_mismatches'])}。只重定位旧study path literal，并将工程adapter/observer放在本新工作包；未编辑原frozen控制、Human、R2、安全/clearance/force/moment限值、K3、J_F和Q定义。

受核对的primary为WSL目录`{ROOT}`：其dirty Git branch、HEAD、status、index hash和staged diff bytes前后相同；未commit/reset/stash/rebase。初始没有完整primary unstaged-file hash，所以不宣称未复制的全部unstaged字节已逐文件证明相同，也不将这个WSL Git snapshot外推为Windows authoring目录的完整Git验证。旧结果/权重保留。Q SHA匹配={preserve['Q_weights_equal']}，且文件哈希一直为`{preserve['Q_weights_sha256']}`。

source/版本manifest记录原源码、辅助actor、network文件以及关键运行输入。运行source hashes在每个task登记；后期只读报告helper变更存入code_history，不把其新hash说成旧version当时执行的hash。Windows DELIVERY_MANIFEST对每个导出文件SHA逐一校验；完整raw gzip及NPZ留在WSL。

独立source closure={closure.get('status','PENDING')}。输入bytes、RESULT与直接/首个子episode配置、Q登记哈希、CODE_MANIFEST可恢复性及{closure.get('top_level_owners',0)}个top-level owner时段均审计；owner重叠为{len(closure.get('top_level_overlap_rows',[]))}。所有声明actor bytes均可恢复，未找到的声明source={closure.get('unretained_declared_sources','pending')}。两个B科学wrapper的通用CODE_MANIFEST早于直接worker安装，和更细的version-registration worker哈希不同；这项局限保留，未篡改历史登记。{len(retention.get('files',[]))}个声明actor字节版本、{len(retention.get('attempt_references',[]))}条per-attempt引用另在historical_code及ACTOR_SOURCE_RETENTION_MANIFEST中提供。matching retained bytes证明可复现来源，不等于逐module import-time attestation。

source_manifest_sha256字段由原enqueue定义为CODE_MANIFEST文件哈希；它不等于SOURCE.json哈希。首版只读closure脚本混淆两者及wrapper/首子episode，产生审计FAIL，原报告保留；根据原enqueue/consecutive contract修正审计后运行数据无需修改。{link('reports/SOURCE_CLOSURE_AUDIT.json')}。

证据：{link('reports/PRESERVATION_AUDIT.json')}；{link('SOURCE.json')}；{link('GIT_BEFORE.json')}；{link('CODE_MANIFEST.json')}。''')
 texts.append(f'''## 13. Resume / closeout state

当前closeout状态：{close.get('status','WORKING — all registered physics joined; read-only diagnosis and delivery verification continue')}。Final报告在已登记任务结束、START/END平衡、队列无未解释pending、已知本任务runner/controller/offline children全部join及最终preservation/resource/compute核对后生成；导出完成后独立DELIVERY_VALIDATION逐文件检查SHA、本地链接、准确fig QA字节/inputs及关闭状态。dispatch marker：{link('STOP_DISPATCH') if close.get('status')=='STOPPED_AND_RECONCILED' else '7h目标到达时由graceful closeout写入，当前不提前关闭runner'}。

恢复证据：{link('RUN_PLAN.json')}；{link('CHECKPOINT.json')}；{link('PROGRESS.md')}；{link('RESUME.md')}；{link('reports/CLOSEOUT_STATUS.json')}；{link('reports/KNOWN_PROCESS_CLOSEOUT_AUDIT.json')}。后者核对原verified-owner ancestry采样记录中的PID+exact cmd，包括命令行未含study path的multiprocessing IPC worker；没有用PID相同就终止任何进程，原采样无start-time identity的局限保留。恢复前检查ATTEMPTS中的START/END、runner.lock实际PID及source hashes，不能覆盖活runner的TASK_LEDGER，不能把失败id当未执行而重复派发；只能新id继续并计数。原始root空RESOURCE_LOG不是数据源，authoritative记录在output/RESOURCE_LOG，Windows导出在evidence/RESOURCE_LOG.jsonl。

条件pilot未获资格；后续若再次授权，唯一建议是：**先把公共B commissioning及当前模型命令重验的阻塞从5ms反馈线程隔离，并在原时钟、原阈值和真实物理推进下独立验证完整B实时资格，再接M2。** 这需要新的明确工程范围；本轮没有以第三版公共B修复继续侵入式改写。

当前结论保持：科学exact加速有效，实时不合格，adaptation未运行，frozen/adaptive差值不适用。''')
 folder=STUDY/'delivery';folder.mkdir(parents=True,exist_ok=True);text='\n\n'.join(texts)+'\n';path=folder/'REPORT.md';path.write_text(text)
 save(STUDY/'reports/REPORT_BUILD_STATUS.json',dict(status='FINAL' if final else 'DRAFT',generated_unix=now,report_sha256=sha(path),bytes=path.stat().st_size,sections=13,scientific_equivalence='PASS',actual_host_qualification='NOT_QUALIFIED',adaptation='NOT_RUN'))
 print(json.dumps(dict(status='FINAL' if final else 'DRAFT',sections=13,report=str(path),bytes=path.stat().st_size)))
if __name__=='__main__':main()
