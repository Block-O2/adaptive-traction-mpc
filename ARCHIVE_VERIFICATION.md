# 归档核验：远端干净克隆实际通过

**已列出的现代复现范围 PASS。** 这不是所有历史实验、真机或临床资格通过。仓库为 [https://github.com/Block-O2/adaptive-traction-mpc](https://github.com/Block-O2/adaptive-traction-mpc)，分支 `archive/research-closure-20261028`；完整动态验收的源码提交为 [`5586b946024c4a979aaa66287d9f2250a51dddb8`](https://github.com/Block-O2/adaptive-traction-mpc/commit/5586b946024c4a979aaa66287d9f2250a51dddb8)，起点为 `1adb1de177d6f5f32de6d01c4e629cbfae9ce121`。后续收尾提交只增加核验回执/文档/清单，不改变已测控制、模型、参数、评分或运行工具。

## 干净目录与依赖证明

实际从GitHub HTTPS独立clone到 `/tmp/ihear-archive-remote-20261028`，随后从远端fetch并checkout上述精确payload。`.git`为独立目录，无 `--reference`、本地clone、shared objects或alternates。使用另建 `/tmp/ihear-archive-clean-env`，通过官方pip引导程序、`--no-cache-dir --require-hashes`安装归档Linux CPython3.12 CPU锁文件；未使用原研究virtualenv。

Python3.12.3、NumPy2.2.6、SciPy1.15.3、MuJoCo3.10.0、Torch2.7.1+cpu、SB3 2.6.0。锁文件SHA256为 `e8008e3cf55f8af883c46887a976851783dd634f6173f7acb349689771cf09d3`。新OS安装未执行；本机缺ensurepip时默认install脚本曾失败，实际独立引导安装路径已验证，未来按指南先安装系统venv/GL依赖。

启用归档已有Python audit hook，禁止 `/home/hank/ihear-lab`、旧coding/envs和WSL盘路径读取；先实测原研究日志open被拒绝，再以新日志运行验收。正式验收 **0 次禁止目录访问事件**。该守卫不是OS级沙箱；原始路径重绑定、模型资产身份和真正远端来源也分别检查，不把守卫升级为全系统形式证明。

执行入口 `deployment/verify_fresh_archive.py`，`--timeout-s 900`只设host允许时长，不改19.03s科学任务。11项总wall为 **1011.46s**。机器原始unix开始/结束时间保留在回执，不改写为实验时间或计费测量。

## 实际执行结果

|检查|结果|wall秒|
|---|---|---:|
|选定文件SHA、源码语法、主文档/图片/源码链接及公开凭据审查|PASS|32.90|
|既有现代源码/冻结锚与资产引用身份|PASS|4.12|
|90项资产身份、6个robot XML静态编译|PASS|1.32|
|D01R原scorer与独立raw积分/原motion重放|PASS|19.53|
|现代B/组合完整历史scorer、ownership及native/wrench重放|PASS|16.95|
|已训练Value的真实25D接口推理|PASS|0.26|
|RL-B环境及5项原接口/安全合同单元检查|PASS|7.04|
|从归档原数组重建图、CSV与数值回执|PASS|2.52|
|无prefix原B完整闭环与原评分|PASS|114.22|
|B/phase/组合完整闭环、原门与冻结额外质量|PASS|481.45|
|D01R同父B/H150完整闭环与原门|PASS|331.14|

原B动态实际加载整套Human/robot/cuff环境，不只静态6个robot XML。三条现代动态入口均保留原certificate/admission、scheduler/governor、source age/lifecycle、guard/fallback、native receipt/owner及原task/motion门。所有运行均为 `SCIENTIFIC_SIMULATION`；`HOST_EXECUTION_CAUSAL_VALID=NOT_EVALUABLE`保持原值。

另实测三个动态launcher使用 `python -O` 均拒绝并不创建output，防止原assert资格门被优化移除，见 [优化模式回执](research_archive/verification/remote/OPTIMIZATION_MODE_REJECTION.json)。没有训练、参数搜索或硬件动作。

## 远端新动力学的关键数值

JF单位N·s，JM单位N·m·s，使用完整TASK、含HOLD的原5ms measured-wrench左积分；TASK时长由原phase时钟计。各组父状态/prefix不同，**不跨组做总排名**。

|实际条件 / ID|TASK秒|JF|JM|原资格|
|---|---:|---:|---:|---|
|原B / 无prefix / seed2026101303|19.030|1438.613498467|100.417251110|PASS|
|S1 / DEVPC02 / DEVPC02_B|19.030|1437.971420109|100.829733886|PASS|
|S1 / DEVPC02 / DEVPC02_V6PHASE|19.030|1405.990071056|105.481425332|PASS|
|S1 / DEVPC02 / DEVPC02_TRAD_COMBO|19.030|1405.935077633|105.464005963|PASS|
|D01R / D01R_B|19.030|1436.456498145|101.253694591|PASS|
|D01R / D01R_H150|19.030|1402.643211486|107.072271907|PASS|

COMBO对同父phase的ΔJF=-0.05499342256、ΔJM=-0.01741936853。原native脚本复算髋/膝jerk RMS比为 1.000621817564/1.000668301122，force norm-rate比为 0.999882919008；在原1.001/1.004冻结界内，额外质量及双成本对phase改进PASS。jerk并非全部下降，JM仍高于同父B；不宣称全局最优或所有指标支配。

完整原motion采用未滤波0.25ms native Human信号与原求导/比较器。历史D01R离线scorer还逐字段比较原数值和原motion数组；现代B/组合离线重放也检查原ownership/过期receipt及native/wrench指标。新动态只宣称原源码/任务/参数重执行与已列资格；没有把JF相同自动等同为所有旧raw逐字一致。

## Learning与训练范围

实际加载非零已训练 `VALUE_FAMILY_V1_FROZEN.json`，原25D API执行两次predict：JF_QUALIFIED选EARLY_PHASE，STRICT_JM选B。该输入是原EARLYN01训练context的无标签副本；不是独立泛化验证，不是新物理控制资格。RL-B的5项检查显式禁止physics step。**本轮Learning训练/Adam更新=0**。

## 尚未通过或未执行

|项目|实际状态与原因|
|---|---|
|legacy Stage1模型引用|旧静态核验单独报告40项缺失；不是现代B/H150依赖，未修补或冒称全部Stage可复现|
|完整旧m2磁盘镜像|原manifest38对象在旧快照位置缺失；其中22项在归档其它路径找到原SHA相同副本，见 [恢复映射](research_archive/manifests/historical_alias_recovery.json)。B执行所需3个JSON已按原SHA恢复；其余非本次B执行依赖不伪称完整恢复|
|更早History/ILC/BO完整训练重放|部分原权重/训练数据/raw本来缺档，保留机制、源与限制，未补造|
|全部历史变体与跨Human条件|未全部重新跑；early heavy H150/18D等部分只保留历史native/指标，不能从native-only重放全safety scorer|
|旧活父状态跨机器持久化恢复|NOT_RUN；新入口重新commission并现场fork，不把q/dq当完整checkpoint|
|旧41D PPO完整matched桥/新训练|本轮未执行，不消除原G4/评价缺口；无权重训练恢复承诺|
|硬实时、真实CR12/人体/临床|NOT_RUN / NOT_EVALUABLE，科学仿真PASS不外推|
|新OS、所有平台、未来依赖站可用性|未验证；已实际验证本Linux新venv在线hash安装，wheels未整包备份|

## 失败与修复没有被抹掉

准备阶段曾遇到必需动作合同位于output目录而被漏选、生成manifest自哈希覆盖、原v7报告输入漏选，以及缺ensurepip/初始Git认证。实际失败都发生在相应阶段，未当作成功TASK；部分原始小日志见 [manifest失败](research_archive/verification/preliminary_failures/manifest_self_hash.txt) 与 [scorer缺输入](research_archive/verification/preliminary_failures/v7_missing_report.txt)。修复仅补原对象、机械路径/manifest、安装或认证；未调控制参数、plant、task、阈值或评分。独立审查还纠正D01R无条件PASS和优化模式门风险，见 [审查记录](research_archive/verification/INDEPENDENT_ARCHIVE_REVIEW.md)。

## 回执与交付身份

[远端总回执](research_archive/verification/remote/RESULT.json)、[逐文件回执清单](research_archive/verification/remote/OUTPUT_MANIFEST.json)保留32项、约12.46MB真实输出，含原B完整native运动/5ms trace、原评分、PREPARATION路径/hash、组合额外门与学习输出。未上传所有新重复gzip raw；原B这些native/trace单独不能替代全raw ownership scorer。旧D01R全raw及现代B/组合两套全raw继续在仓库内。

文件/资料总范围见 [ARCHIVE_MANIFEST.md](ARCHIVE_MANIFEST.md)，删前损失见 [DELETION_IMPACT.md](DELETION_IMPACT.md)。最终收尾commit由 `git log -1 --format=%H -- FINAL_HANDOFF.md` 获取；本文件明确记录被实际完整验收的payload SHA，避免文档自引用哈希循环。
