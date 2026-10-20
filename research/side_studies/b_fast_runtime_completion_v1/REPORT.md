# B FAST Runtime Completion & Conditional Frozen-Q Integration v1

**STATUS：研究工作包完成；B 未通过原始 R2，BEST_RUNTIME 未设立，冻结 M2/Q 未启用。**

本轮完成 FAST 实现、完整科学回归、真实时钟因果修复、独立冷启动/同解释器重复、合法偏离和有界故障注入。剩余阻塞是 HOLD 原生交接时长；工程服务节拍通过不能替代原 R2。没有训练、没有修改人体/控制律/安全条件/原生 dt/任务与 planner authority。

真实 t0：2026-10-07 05:53:58 UTC。派发截止15:08:58 UTC；硬结束15:53:58 UTC。本文生成时已运行 8.214 h，97/120 次实际物理启动（包括失败和双 plant 局部比较）；没有重置 t0 或为耗时重复不变失败。最终封存时刻见 STATE.json。

## 可重跑实现和入口

正式研究目录：`/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1`。环境：`/home/hank/envs/adaptive-online-rl-v1/bin/python`。

```powershell
.\b_fast_runtime_completion_v1\run_readonly.ps1 -Mode Check
.\b_fast_runtime_completion_v1\run_readonly.ps1 -Mode Review -TaskId 099_N13_S2_D2_C6_host_nominal
```

```bash
/home/hank/envs/adaptive-online-rl-v1/bin/python /home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1/code/reproduce.py --check
/home/hank/envs/adaptive-online-rl-v1/bin/python /home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1/code/reproduce.py --review 100_N13_S2_D2_C6_science_deviation
```

实际单任务内部入口是 code/run_one.py，预算执行入口是 code/fast_dispatch.py；不要绕过后者直接开启物理任务。reproduce.py 会检查固定 t0、代码 manifest 和已启动 ID。封存后允许只读恢复/复核，不自动重复物理运行。继续研究须新显式有界工作包；不能改写本轮时间和计数。

FAST 数学主线：N13/N12/N11 + V3/W1/A1，C1d/C2b 因果事务，S2 可重用流式导出；D2 双向 IPC warm 在真实物理 epoch 前完成。C6 将已激活 HOLD 末端服务与原 TASK socket 的有界可读通知组合。它是可审查候选，不是合格 BEST。

代码差异见 reports/R3_TO_FAST.patch 与 R3_TO_FAST_CHANGES.json；新增实现留在 code/、native/ 和 authoring/。FINAL_CODE_MANIFEST.json 记录实际交付文件。code/ 包含继承的历史诊断脚本，它们不是本轮入口；不要执行旧 campaign/closeout/training mains。

## 资格结果

|版本/运行|完整任务/物理/current/因果|HOLD s|服务 p50/p95/p99/max ms|backlog ms|FUNCTIONAL|LEGACY_STRICT|
|---|---|---:|---|---:|---|---|
|082_N13_S2_C5_host_nominal|PASS|1.025|5.006/5.448/6.444/28.012|14.238|FAIL|FAIL|
|088_N13_S2_C5b_host_nominal|PASS|1.030|5.007/5.400/5.978/32.998|17.527|FAIL|FAIL|
|095_N13_S2_D2_C5c_host_nominal|PASS|1.035|4.999/5.426/6.105/29.287|14.136|FAIL|FAIL|
|099_N13_S2_D2_C6_host_nominal|PASS|1.030|5.006/5.432/6.214/32.198|17.109|FAIL|FAIL|
|101_N13_S2_D2_C6_host_deviation|PASS|1.030|5.002/5.444/6.182/50.719|13.441|FAIL|FAIL|

所有最近完整非注入 host 的冻结功能失败项为 original_R2。最短观察到的 C5a HOLD1.025 s 仍超过原1.020 s，没有作为 BEST 或从重复中选出幸运通过。C6 名义14个 TASK 激活、12个真实有意义计划；合法偏离13个 TASK 激活。每个有意义计划的实际原生步和 receipt 对应保存在原资格证据。

C6名义 source→activation p50/p95/p99/max：44.291/49.849/51.505/51.919 ms；strict55 age miss=0。原 LEGACY_STRICT 仍因控制周期/command-gap/R2 等原口径 FAIL。合法偏离最大 age 86.645 ms，明确保留其 strict55 失败。55 ms 单项并非 M2 禁止的唯一理由；本轮实际原 R2 未过。

原 strict、R2、物理安全、全部实际5 ms服务和新的冻结功能阈值在不同文件分别计算。RUNTIME_FUNCTIONAL_CHECKS.json 在000前冻结；没有后挑阈值。名义所有实际服务（含 commissioning/model publish/extra services）入统计。有限本机普通模式工程测量，不是硬实时数学证明。

## 控制、物理和同周期预算

保存因果输入的 N13完整控制重放：10种输入/120次调用，110次未 profile；所有命令数组逐位一致，p50/p95/p99/max=2.546/3.341/4.129/15.547 ms。它包含 observer/feedback/transform/safety/TRACK-BRAKE/loaded geometry，排除 IPC、异步 admission、receipt/actuator、物理与研究导出；不能替代闭环资格。

相同隐藏人体/初始支撑的原 N11单步成对比较：3000对、6000真实物理步、36000状态/力/历史数组比较逐位一致；原包装 p50=42.159 µs，N11=33.973 µs。更早原 R3包装约135 µs的 attribution 含不同包装开销，仅单列；不混用为匹配速度比。每个.25 ms子步保留两次 interface force 更新与原 MuJoCo顺序，没有20步合并。

GCC/CPython NumPy C API 唯一后端：MuJoCo3.10、float64、-O3 -fno-fast-math -ffp-contract=off。原 NumPy matmul、SciPy1.15.3 Markley/rotation顺序和原 pow/向外 nextafter/fsum 被保留；未支持输入走原实现。

|同一实际周期独占均值 ms|TASK045|HOLD103|
|---|---:|---:|
|TASK_packet_collect_and_proof_install|N/A|0.000|
|TASK_submit_snapshot_enqueue|N/A|0.001|
|belief_model_build|0.007|0.007|
|belief_snapshot|0.021|0.022|
|boundary_dataclass_copy|0.023|0.022|
|candidate_record_materialize|N/A|0.000|
|command_receipt|0.264|0.260|
|current_admission|0.003|0.008|
|decision_record_materialize|N/A|0.000|
|feedback_transform_filter|1.717|1.664|
|immutable_request_snapshot|0.001|0.003|
|measured_input|0.013|0.013|
|motion_authority|0.022|0.019|
|motion_monitor|0.089|0.079|
|observer_update|0.265|0.265|
|plant_native_wrapper|0.840|0.844|
|sensor_capture_observer|0.233|0.230|
|task_phase_transition|0.085|0.106|
|unwrapped_control_and_scheduling|1.258|1.240|
|wait|0.194|0.246|
|完整周期均值|5.037|5.027|

TASK045 3783 周期，HOLD103 206 周期；每个嵌套 span 从父项扣除，逐周期精确闭合。表为同一组周期均值，未相加独立 p50。103 为 attribution-only；其速度/失败不替代099/101无仪器评价。

## HOLD 阻塞及权限边界

原 SensorSupportedTaskClock 证明0.5 s连续有效样本 dwell；原 SACExpertEnv.transition_allowed 另要求1 s HOLD/9 s运动最小时长。之后原 reference_safe_task_transition 还要求实际激活参考段完整、原 terminal box、静止 dq/ddq。实际两次0.5 s HOLD段之间的提交、结果收取、当前验证和真实激活延迟使最后原生参考完成晚于1.020 s。

仪器运行103：完整 HOLD 1.035 s；sensor时钟先提议 RETURN，原交接仍延后。在调用 shared minimum 的原 previous phase_elapsed_s≥1 s 时还有 6 次真实拒绝交接。102 SCI逐位等价。详见 HOLD_ROOT_CAUSE.json 与原始逐服务事件。

该证据是当前实现的有限反例，不是所有合法架构不可能满足R2的证明。没有削短 HOLD、移除原最小时长、补记 dwell、放宽完成误差，或新增未来请求/预执行权。原1.035 s与整数4140原生格误差约4.94e-12 s，浮点记账不能解释额外15 ms。

19 ms研究提案预拒绝已检查：PrefixB 不调用该 Q/Native选择 headroom 路径；历史公式同时含原40 ms bridge与strict55 reserve，不是本轮 B HOLD原因。它保持原样，没有不确定职责下删除 guard。

## 科学等价、因果性及重复

保存的科学 gate 共34个；每版先局部回归再完整原 R3比较，要求≤1e-10。C4/C5/C5b/C5c/D2/C6以及最终102均逐位相同。N1、N4a、N13a的失败保留和来源限制详见 PROVENANCE_NOTES.json，不能把修正版覆盖成旧版通过。

真实write使用 ceil .25 ms合法格；尚未模拟的过去由旧receipt命令推进，availability与最终owner commit分开。C6名义117006步、合法116966步逐步重建 command ID/torque/source/model/reference；没有 backdate、丢弃receipt或过期动作写入。quantization max分别249946/249939 ns，全部实际write源龄≤100 ms。初始active epoch之前的 validated support保留apply_ns=None，未伪装新命令。

053–056 四独立冷启动完整运行；063–066修复后的同一解释器四运行均完成。后者同一PID/ordinal0–3，全部物理/current/因果/service通过，但原R2全部FAIL。冷启动056另有1 s滚动平均6.068 ms越过冻结6 ms；没有选择性剔除。每轮新建plant并重新commission，这只是解释器可重用，不是同一人体持续适应。

057/058旧重用第二次因SERIALIZER_SOURCE_CHANGED在物理前失败；S1后的061在117k左右物理步骤后因inspect-source导出失败，不能称完整成功；S2用一次安装及逐轮显式状态恢复修复，旧失败证据保留。068/069及C4/C6额外合法偏离完整实跑。

## 有界故障与实际执行

|ID|注入位置/事件|实际结果|
|---|---|---|
|070|原COMMISSIONING req3 +30 ms|完整任务；等待有fresh feedback，R2仍FAIL|
|071|原COMMISSIONING req3 +120 ms|STALE_PLAN_MAXIMUM_AGE，workerFAILED，18745实际步；无过期写入|
|072|原COMMISSIONING req3显式reject|COMMISSIONING_NO_RIGID_TABLE_FEASIBLE_SEGMENT，workerFAILED，18277步|
|073|TASK req6 +30 ms|原结果ACTIVATED后完整任务，真实activation约81.64 ms|
|074|TASK req6 +120 ms|旧请求EXPIRED，原重试authority下完成；没有旧动作执行|
|075|TASK req6 proof identity mismatch|原 current model校验 exact-match=False/native recompute后激活并完成|
|076|TASK req6显式reject|LOW_LEVEL_EXECUTION:CURRENT_MODEL_ACTIVATION_REVALIDATION，任务ABORT；结果导出COMPLETE不是任务完成|
|085|TASK req7 moving +30 ms旧D1|尚未注入即首次send约133.68 ms、CPU133.62 ms而失败，不能报告注入已测试|
|092|D2 TASK req7 moving +30 ms|旧请求CANCELLED FALLBACK_COMMITTED，7个moving references/7 fresh services，原stop/new req8后完整任务|
|093|D2 TASK req7 moving +120 ms|旧请求先CANCELLED，旧packet到达源龄157.03 ms/stale；原stop/new req8完成，无过期执行|

原 commissioning req3没有versioned TASK proof identity接口，model mismatch原N/A明确保留；TASK6额外测试是 proof身份错配，不是 live human model publication变更。每个注入都登记于事前协议；正常科学等价不混入故障预期。

092/093负的旧 primary余量分别约-4.5/-7.5 ms，不授权无限外推。原先已经 admission 的40 ms bridge、35 ms分叉、240 ms braking reference为单独原权威；真实commit/stop/SAFE_FALLBACK_HOLD/新capture/replan/RESUME均保存。名义进度时长与实际wall/physical耗时分开，参见 MOVING_ORIGINAL_ESCAPE_AUDIT.json。没有BRAKE_INFEASIBLE；任何已见abort未被重标为qualification。

D2在host物理epoch前以identity0做一次65536B双向纯transport warm，随后TASK identity从1开始，一个原TASK worker且结束join；095首次send76.601 µs，warm不做模型/plant调用。085异常根因未擅称OOM或deschedule，D2有限测量不保证syscall永无长尾。

## M2/Q、收益与持续session

B真实原R2未过，M2条件未满足：没有Q smoke、没有M2非零动作执行、没有B/M2 J_F收益比较、没有在线更新、没有持久物理session。Q文件SHA256=3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9。Q-first、feature/slot/mask/shared context均保留原文件。仅产生proposal/ACTIVATED也不会被计作已执行学习残差。

## 关闭的分支与证据限制

N1手工matvec误差经闭环放大，改回原NumPy matmul；N4a pow²出现2.91e-11差异，改原pow；N13a Boolean scalar字节/repr为True但Python truth=False，改canonical np.True_/False_。其负binary和恢复反例保存。

R1大型模型pickle、R2整context、W2数值factor、GEO1、W3allocation等完整key的局部正确方案反而变慢，关闭；N7observer、N10mechanics及crossshape剩余空间微小，不安装。C3/C3b、C4、C5a/b/c/C6真实服务机会保留因果性但没有过原R2。

H1 loaded-equilibrium full-key局部184 hits/8misses、480命令数组对比精确，median仅46.894 µs收益，未装入物理候选。N14 Boolean scope六TASK输入/144对照调用math/proof精确，但两个HOLD中位收益0.334/53.245 µs，关闭于离线，不进行整任务重复。

PROVENANCE_NOTES.json披露：直接cross probe456 API在OFFLINE_LEDGER外；原未profile控制重放JSON保留，但原030 profile文本被instrumented probe覆盖，保留覆盖版本且不称原profile；N4a原gate JSON在修复时覆盖，恢复counterexample不是原时间戳gate。早期commission/model import/warm计数及CPU/PSS覆盖不完整。

## 资源、计算和保留

实际启动97/120，未扩240；9,657,488测得原生步骤，2414.37200 aggregate模拟秒（局部双plant都计入）。六个早期完整记录最终catch-up合计补58步；原TASK_LEDGER保持原值，修正账本单列；三次startup null指标按发生在plant初始化前的拒绝解释为0。中断/局部测试仍依靠其记录指标，完整ownership信息见每个receipt。

计得main inverse-dynamics API下界1,885,305，TASK worker下界244,482，OFFLINE_LEDGER模型API 102,647，另直接cross replay至少456。未宣称这些覆盖所有早期import/warm/commissioning调用；native公式调用与Python API计数分开。所有physics尝试START/END各一次、输入配置/版本/code/native hash均留存，失败计数不免除。

数据记得4,406,004,808 B（4.103 GiB），目标≤10 GiB；最终以FULL_PACKAGE_MANIFEST/FINAL_DATA_ACCOUNT及目录实际字节为准。89份gzip逐流CRC验证；没有旧raw库复制或关键失败删除。

资源样本344；最低WSL available 4.652 GiB；最低Windows commit余量4.797 GiB；最低C盘余量8.247 GiB；最大owned PSS 2.323 GiB；OOM增量0。系统swap in/out页增量见FINAL_RESOURCE_ACCOUNT，未归因为本任务独占。分析阶段资源日志最大间隔1008.2 s明确披露。

压力pause/5-10-20分钟退避及60分钟不可自动恢复规则已作fake-resource测试；真实未触发资源停止。普通/安静模式、线程1保持。未kill未知进程、重启WSL、改内存/swap/内核/实时优先级。最终只回收并join本任务worker与monitor。

主仓库branch/HEAD/status/index/staged diff以及原R3报告/manifest/source/action/Q关键hash最终一致，详见 preservation/FINAL_PRESERVATION.json。既有source/deps差异仅路径迁移，原数学文件未修改；新的adapter作用范围见科学gate与源码。

## 唯一后续建议

开启一个普通有界的 HOLD交接关键路径工作包，沿本轮同周期预算减少真实源到激活及原参考完成的串行延迟，并首先以原R2 HOLD≤1.020 s复验。保留原0.5 s sensor dwell、1 s shared最小时长、.25 ms事件和完整current admission；如果方案需要未来请求/新authority，单列权限问题，不绕过它，也不先开M2。

## 交付索引

- REPORT.md：本文；RESUME.md：只读恢复与不可重复派发规则。
- FINAL_CODE_MANIFEST.json：实际交付代码/native closure；FULL_PACKAGE_MANIFEST.json：本轮完整文件hash。
- reports/RESULTS_OVERVIEW.json：所有主机资格与科学gate紧凑索引。
- reports/FINAL_EXCLUSIVE_BUDGET.json、HOLD_ROOT_CAUSE.json：完整同周期和HOLD交接归因。
- reports/R3_TO_FAST.patch、R3_TO_FAST_CHANGES.json：原R3代码差异。
- reports/FINAL_COMPUTE_ACCOUNT.json、FINAL_ARCHIVE_AND_RECEIPT_VERIFICATION.json：预算/模型scope与原生步对账。
- reports/FINAL_RESOURCE_ACCOUNT.json、FINAL_DATA_ACCOUNT.json：资源和数据账。
- reports/PROVENANCE_NOTES.json、MOVING_ORIGINAL_ESCAPE_AUDIT.json：限制与故障权限证据。
- preservation/FINAL_PRESERVATION.json：原仓库/历史/action/Q保护核验。
- TASK_LEDGER.json、ATTEMPTS.jsonl、OFFLINE_LEDGER.jsonl、queue/、versions/、output/、source/results/：可恢复全部实际记录。
