# iHEAR Lab — GitHub原评价器恢复与PPO稳定性诊断 v1

本轮结论：**原D01R/W1完整历史离线scorer已在云端从指定GitHub commit独立复现；云端代码差异已定位；050→080退化的执行链原因已确定，但唯一优化/奖励根因尚未识别。NEW_PPO_MATCHED_EVALUATION_READY、Stage2和正式campaign仍未就绪。**

T0：2026-10-21T02:08:05.854196+08:00；报告生成：2026-10-21T02:32:03.939162+08:00；当前elapsed约23.97min，硬上限T0+5h，最后45min不启动新长物理任务。全部新工作位于本目录；没有新PPO训练、backward或Adam更新。独立offline/CPU环境按GitHub hash locks安装。新增8次冻结MuJoCo开发评价已用尽上限，不再启动其他物理任务。

|独立结论|状态|直接证据|
|---|---|---|
|OFFLINE_SCORER_READY|PASS|audit/FIXTURE_CONTRACT_VERIFICATION.json、scorer/original-001/OFFLINE_SCORER_RESULT.json|
|HISTORICAL_MATCHED_REPRODUCTION|PASS|HISTORICAL_MATCHED_REPRODUCTION.json|
|CLOUD_SOURCE_DIFF_COMPLETE|PASS|source_diff/FILE_SHA256_COMPARISON.json、source_diff/CODE_LINEAGE_AND_CONFIG.json|
|PPO_STABILITY_CAUSE_IDENTIFIED|PARTIAL|stability/HISTORICAL_NATIVE_EXECUTION_AUDIT.json、CHECKPOINT_050_080_COMPARISON.json、stability/TRAINING_OPTIMIZATION_AUDIT.json、PHYSICAL_EVALUATION_RESULTS.json|
|NEW_PPO_MATCHED_EVALUATION_READY|NOT_READY|scorer/original-001/OFFLINE_SCORER_RESULT.json、physical/EVALUATION_PLAN.json|
|G4_STRICT_PASS|FAIL|/home/hank/ihear-lab/rl_b_autonomous_replication_v1/G4_NATURAL_PATH_UPDATE.json、/home/hank/ihear-lab/rl_b_autonomous_replication_v1/LEVEL_A.json|
|STAGE2_READY|NOT_READY|/home/hank/ihear-lab/rl_b_autonomous_replication_v1/STAGE2_GATE_DECISION.json、/home/hank/ihear-lab/rl_b_autonomous_replication_v1/STAGE2_RESULTS.json|
|FINAL_CAMPAIGN_READY|NOT_READY|NEXT_RESEARCH_DECISION.md、STATUS.json|

## 1–5. GitHub、原scorer、冻结指标与剩余缺口

1. **真正恢复指定commit：是。** 远端研究分支和独立detached checkout均为`1adb1de177d6f5f32de6d01c4e629cbfae9ce121`；没有在旧研究目录git pull。SSH主机信任缺失保留失败日志，后用HTTPS clone成功，无凭据/SSH配置更改。最终源码身份见`audit/GITHUB_FINAL_IDENTITY.json`。
2. **原完整离线scorer云端复现：是。** 23来源、16锚点、完整v6 1426项、九合同、32原native fixture和90模型身份先核验，再运行原measure/compare与独立recompute，全部原断言开启。原fixture直接来自此次clone，不取旧ZIP/TAR，也不新造scorer。
3. **parent/B/H150冻结指标一致：是。**

|历史输入|JF N·s|JM Nm·s|tracking RMS ° hip/knee|TASK s|raw jerk RMS °/s³ hip/knee|
|---|---|---|---|---|---|
|D01R_parent|1436.4564981450510|101.25369459130|0.473481/0.461755|19.030000000|305.077/714.727|
|D01R_B|1436.4564981450510|101.25369459130|0.473481/0.461755|19.030000000|305.077/714.727|
|D01R_H150|1402.6432114861727|107.07227190726|0.453090/0.522946|19.030000000|319.305/675.350|

原H150/B force改善2.353937394034738%，moment增加5.74653333830843%；全部motion/dose、任务/安全/科学执行/matched轴及receipt字段与冻结参考一致。原PHYSICAL_TASK_VALID、SCIENTIFIC_EXECUTION_CAUSAL_VALID、LEGACY_R2_MATCHED=PASS，HOST_EXECUTION_CAUSAL_VALID=NOT_EVALUABLE；保留原host-age失败记录，未换成实时通过。

4. **缺口：** 已运行离线scorer所需matcher、32fixture和九合同无缺失；完整可移植parent checkpoint与`D01R_parent_CAUSAL_STATE.json`仍缺失，历史native扩展ABI不作为3.12 live恢复PASS。FULL_FORK_REPLAY=NOT_RUN/UNVERIFIED，未构造替代父状态。
5. **新PPO完整matched评价：尚不可用。** 现有PPO nominal开发轨迹没有原同父prefix/B/H150匹配链。旧文档“scorer源码/fixture缺失”的阻碍已在本轮消除到离线层，不能因此给PPO授FULL资格，也不能把历史2.35%收益套给当前PPO。

详见`GITHUB_RECOVERY_AUDIT.md`、`FROZEN_SCORER_VALIDATION.md`和`HISTORICAL_MATCHED_REPRODUCTION.json`。

## 6–7. 真实云端源码及回流

实际240集由`rl_b_autonomous_replication_v1/replication_run.py`和447项冻结合同生成。414项科学闭包相对GitHub capsule为412相同+2修改；根Python为13相同+5修改+27新增+10GitHub独有。Python合计216个对照路径，172相同、7修改、27云端新增、10GitHub独有；不是仅按文件名或Git状态比较。active-main对应路径还缺capsule已有的rl_native_proposal.py。五个云端包证实两科学修复发生在早期g4_repair，其后414项源码树一致。

应优先审核回流：真实native区间force/moment积分修复、三phase期限优先级、相应独立审计；再抽取显式checkpoint合同/Adam/RNG、资源/gzip、训练与冻结证据工具。reward_v3 floor和单episode PPO属于需单独科学回归的研究版本；campaign/stage2/报告脚本保留历史特化身份。所有SHA与精确diff已交付，未自动覆盖、提交或推送。详见`CLOUD_GITHUB_SOURCE_DIFF.md`、`CLOUD_CODE_RETURN_PLAN.md`。

## 8–11. PPO为什么退化、训练/评价差异及证据边界

两个成功seed的050确定性冻结均2/2成功，080均0/2。相同准备native prefix、config和初始41D观测下，重新forward复现18次PPO历史确定性评价动作，另1次为固定合法[+1,+1]基线；51代actor/critic/model/Adam/RNG与原meta一致，无VecNormalize错配。050→080 mean漂移通过准入参考改变实际torque（TASK10ms已有分叉）及Human运动（15ms边界已有分叉），最终RETURN的候选进入原预测shank-table禁区，被拒绝并ABORTED。这是直接执行链证据，负mm不表示已经发生物理碰撞。

训练抽Gaussian sample再clip，冻结用mean再clip；两者不是同一个闭环目标。std约1且原动作常被clip，planner只评估单个候选，局部协调变化可以改变后续可行性。1495656323在51–80集随机训练19/30成功而最终mean失败，不能用训练曲线代替冻结完成率。两退化seed在共同causal观测上的mean绝对变化分别[.177006,.147412]、[.634878,.138427]；离线Gaussian KL分别.028598、.216017。

LR固定3e−4，继续120epochs/seed，target_kl=None；实际记录单次近似KL较小，clip fraction全为0，未见明确KL爆炸。value loss较大、解释力弱；65/240集只有1个transition，76/240有singleton minibatch，SB3对singleton跳过advantage标准化，是优先测试的高噪声/信用分配线索。日志KL只含最后epoch；梯度范数为裁剪后测量，缺裁剪前/分actor-critic梯度、精确minibatch历史，均标UNAVAILABLE，不伪造曲线。

所有240份reward及GAE再次重算通过。172失败总回报约−11.5，没有失败正总回报漏洞；107失败含正中间reward、48含正raw advantage，只能作为局部信用分配证据。原执行准入、source-age、bridge及实际native审计没有显示非法放行；G4全矩阵未闭合仍不能授予严格资格。最可能的解释是**未保护的累计策略漂移在高随机训练分布/均值部署差异和局部信用噪声下，破坏了RETURN协调可行性**；优化层归因置信中等，不能宣布唯一根因或catastrophic forgetting已证实。

本轮8次预注册随机冻结评价：seed1495656323/cp050=1/2；seed1495656323/cp080=0/2；seed1630784693/cp050=2/2；seed1630784693/cp080=2/2；seed1630784693的080为mean 0/2而sample 2/2，seed1495656323的080两种均0/2；这不是单一模式解释。仅两个共同RNG、同一已知nominal。新run全部独立物理/奖励审计PASS、原weights/Adam/checkpoint文件不变；0梯度更新。各次完整/partial JF/JM、实际动作与失败见`PHYSICAL_EVALUATION_RESULTS.json`。不同TASK时长不列相对force收益；随机一次成功也不是稳定性结论。

详见`PPO_STABILITY_DIAGNOSIS.md`、`TRAIN_EVAL_SEMANTICS_AUDIT.md`和两份PNG/PDF科学图。PPO_STABILITY_CAUSE_IDENTIFIED=PARTIAL，执行原因高置信，唯一优化根因未定。

## 12–14. 下一优先项、独立初态、正式资格

优先训练策略而非先换算法或reward：唯一下一步是审阅后单独授权H1的小学习率paired continuation；其次才考虑H2完整episode聚合/消除singleton。每个方案都有明确180训练episode/3seed上限、父checkpoint、对照、成功/失败门和独立初态要求，均只设计未执行，见`NEXT_RESEARCH_DECISION.md`。保留成功checkpoint，但不改写原3-seed/80集失败结论。

需要真正新增独立合法初态评价；reset seed变化不改变现有nominal物理，不能冒称泛化。初态族生成和工程准入须先冻结，接口不支持则该部分BLOCKED。患者泛化仍未测试。

**Stage2_NOT_RUN、STAGE2_READY=NOT_READY；FINAL_CAMPAIGN_READY=NOT_READY。** 原三seed/父策略重复门失败、G4 HOLD/绝对安全矩阵未闭合、新live matched链和独立初态稳定性缺口均保留。没有买算力或调整Hetzner。

## 审计、保护与STOP

原五研究包、checkpoint/raw/414科学源码、原ZIP及历史归档共13,683文件（15,484,480,779 bytes）在工作前记录SHA，封包后逐项重算，结果见`audit/HISTORICAL_PROTECTION_END.json`。GitHub checkout及原D01R合同保持不变。所有实际计算job、8个物理attempt和episode均有START/END；lossless raw压缩前后SHA相同，未丢弃新失败证据。CPU/RAM/磁盘/wall见`RESOURCE_USAGE.json`；最终身份、manifest、进程退出与封包验证见`PACKAGE_VERIFICATION.json`。

复核由同一Agent采用分离证据读取/原独立算术完成，没有第二Agent或人工独立审稿。没有Git stage/commit/push/merge/rebase/reset/stash/clean；只有新clone和指定detached checkout。没有修改历史控制器、任务、物理、安全、reward或权重；原执行闭包仅按hash复制到本轮隔离运行目录。新budget只配置资源/时间guard，不改变任务期限或物理参数。

**本轮最终STOP。不得自动启动训练、Stage2、后续研究包或大规模campaign。**
