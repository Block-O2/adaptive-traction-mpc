# iHEAR Lab — 自主PPO三seed复现与性能就绪评估 v1

本轮结论：**NOT_READY_FOR_FINAL_CAMPAIGN**。精确50集预算只有2/3 seed复现；延长至80集后，未达到预注册3/3条件；只有0/3 seed达到初始失败→最终2/2成功；有2个seed由50集冻结2/2成功退回80集0/2，继续训练没有带来单调改进。B/H150原完整matched scorer仍NOT_READY，PPO未获FULL资格；Stage2状态为NOT_RUN。没有启动正式大规模训练。

T0为2026-10-20T17:03:00+08:00；报告时间2026-10-20T21:57:34.530478+08:00；当前累计294.6分钟。实验在独立目录进行，原ZIP、checkpoint、历史结果及414份原科学源码受hash保护。初次初始化缺vendor manifest而在任何物理/模型前退出，补齐原28资产manifest后恢复；失败记录保留。没有训练reward/算法修复分支。

## 1. 单seed学习能否在3个seed复现？

精确50集预算只有2/3 seed复现；延长至80集后，未达到预注册3/3条件；只有0/3 seed达到初始失败→最终2/2成功；有2个seed由50集冻结2/2成功退回80集0/2，继续训练没有带来单调改进。严格规则事先冻结为三个seed均从训练前冻结失败改善到最终冻结2/2原runtime成功；不能把一个或两个seed成功称为3-seed成功。三个初始冻结均失败；nominal重复不证明泛化。若从50延长至80，依据预注册全体延长门，复用已知nominal开发评价；不称未见最终测试，也不据此挑reward、超参数或seed。

## 2–3. 训练量、梯度更新与冻结完成率

|seed|训练成功/集数|RL decisions|native steps（含准备）|PPO epochs|Adam更新|初始冻结|最终冻结|
|---:|---:|---:|---:|---:|---:|---:|---:|
|1106823814|15/80|1065|6479800|320|468|0/1|0/2|
|1495656323|29/80|1261|7370360|320|528|0/1|0/2|
|1630784693|24/80|1081|6885240|320|492|0/1|0/2|

总Stage1训练attempt为240，Stage2为0，独立冻结评价为19。全部失败seed/episodes保留。PPO train call每已完成训练episode一次，epochs与真实Adam更新分开记录；所有训练transition进入更新。checkpoint保留于seeds/<seed>/<stage>/checkpoints，含model/Adam/RNG及SHA。详情见MULTISEED_PPO_RESULTS.json与PPO_CHECKPOINT_AUDIT.json。

## 4–6. 正式评价器、完整资格及性能比较

原ZIP450/450载荷核验通过；四历史包各414份source及真实差异已核对。现有唯一在线接口development合同不是B/H150 Master；缺原完整scorer、motion/fairness/dose语义、原基准raw与state身份。B/H150原条件复现NOT_RUN，正式匹配NOT_READY，不能近似替代。

RUNTIME_COMPLETE按原完整phase链/causal completion判定；19.030±.050仅是必要时长项；MATCHED_TASK_PASS和FULL_QUALIFIED未授予。G4_STRICT_PASS历史FAIL保持，本轮新增自然OUTBOUND/RETURN timeout证据（见G4_NATURAL_PATH_UPDATE），但自然HOLD失败、绝对安全触发及完整矩阵仍未闭合。每episode观测物理审计PASS不等于全动作安全或host实时/strict55资格。

|seed / checkpoint|runtime|TASK s|JF N·s|JM Nm·s|tracking RMS °（hip/knee）|5ms jerk RMS °/s³（hip/knee）|
|---|---|---:|---:|---:|---|---|
|1106823814 / initial_deterministic|ABORTED|16.580|1260.614 partial|73.401 partial|[0.5817, 0.5987]|[522.999, 849.193]|
|1106823814 / checkpoint020|ABORTED|16.200|1218.506 partial|72.291 partial|[0.5605, 0.6337]|[472.017, 855.885]|
|1106823814 / checkpoint050_first|ABORTED|15.535|1097.199 partial|74.375 partial|[0.4734, 0.9066]|[336.735, 977.923]|
|1106823814 / checkpoint050_repeat|ABORTED|15.535|1097.199 partial|74.375 partial|[0.4734, 0.9066]|[336.735, 977.923]|
|1106823814 / checkpoint080_first|ABORTED|15.435|1131.390 partial|70.120 partial|[0.5018, 0.7201]|[354.434, 813.535]|
|1106823814 / checkpoint080_repeat|ABORTED|15.435|1131.390 partial|70.120 partial|[0.5018, 0.7201]|[354.434, 813.535]|
|1495656323 / initial_deterministic|ABORTED|16.575|1260.631 partial|73.334 partial|[0.5821, 0.6025]|[523.107, 853.266]|
|1495656323 / checkpoint020|ABORTED|16.755|1269.049 partial|75.492 partial|[0.538, 0.5917]|[416.005, 784.111]|
|1495656323 / checkpoint050_first|COMPLETE|19.030|1446.793|101.533|[0.4889, 0.555]|[336.701, 645.336]|
|1495656323 / checkpoint050_repeat|COMPLETE|19.030|1446.793|101.533|[0.4889, 0.555]|[336.701, 645.336]|
|1495656323 / checkpoint080_first|ABORTED|16.265|1222.538 partial|70.588 partial|[0.5007, 0.5242]|[324.088, 626.43]|
|1495656323 / checkpoint080_repeat|ABORTED|16.265|1222.538 partial|70.588 partial|[0.5007, 0.5242]|[324.088, 626.43]|
|1630784693 / initial_deterministic|ABORTED|16.625|1265.041 partial|73.857 partial|[0.5821, 0.6047]|[520.281, 851.432]|
|1630784693 / checkpoint020|ABORTED|15.885|1187.704 partial|69.888 partial|[0.5501, 0.6654]|[422.905, 868.394]|
|1630784693 / checkpoint050_first|COMPLETE|19.030|1437.054|102.749|[0.5057, 0.5804]|[328.023, 531.109]|
|1630784693 / checkpoint050_repeat|COMPLETE|19.030|1437.054|102.749|[0.5057, 0.5804]|[328.023, 531.109]|
|1630784693 / checkpoint080_first|ABORTED|15.580|1171.454 partial|60.870 partial|[0.4949, 0.4905]|[270.964, 570.289]|
|1630784693 / checkpoint080_repeat|ABORTED|15.580|1171.454 partial|60.870 partial|[0.4949, 0.4905]|[270.964, 570.289]|

80集最终checkpoint没有可用于完整性能比较的成功配对。 50集的相同时长完整执行则为：seed1495656323的JF -0.210%、JM +3.177%；seed1630784693的JF -0.882%、JM +4.413%。force略降伴随moment上升，详见FROZEN50_PERFORMANCE_DIAGNOSTIC.json/md，不能称完整性能优势。 只有相同TASK时长的完整执行才列相对百分比，时长不同只保留描述性原数值。这些比较的对象是固定合法[+1,+1]，不是B/H150。相对B/H150的JF、JM和motion均NOT_EVALUABLE。失败partial积分不可与完整任务积分宣称收益。完整native motion、terminal误差/overshoot、excursion、tracking、phase JF/JM见audit/ALL_SCIENTIFIC_METRICS.json及各评价raw。jerk没有新造通过门。

## 7–8. Stage2与任务完成代价

状态：NOT_RUN。原因/结果：Frozen gate failed: three_of_three_replication, parent_repeated_runtime_2_of_2。详见STAGE2_PERFORMANCE_STUDY.md与STAGE2_RESULTS.json。若启动，其身份只能是TASK_PRETRAINED_PPO_FINETUNING；父子完整配对与任务、安全、moment/jerk权衡单列。未运行时不能声称有优化收益或任务牺牲；父策略不被覆盖。

## 9. seed间差异

各seed训练完成率、失败阶段和原因、连续10集曲线及冻结结果全部公开。训练完成率分别为18.75%、36.25%、30.00%；50集冻结为0/2、2/2、2/2，80集冻结均0/2。两个已成功checkpoint在继续训练后回退，见LEARNING_STABILITY_AUDIT.json。仅三个训练seed、同一nominal物理初态，差异作描述性比较；不声称统计显著性或跨患者鲁棒性。学习reward不等于正式motion/force优化。

## 10. CPU样本成本与wall time

训练3407个RL decisions、20735400个native steps（TASK 11087400）；评价369个decisions、2041400个native steps。训练程序wall约250.23min（含独立审计与checkpoint），评价程序约25.88min；全研究包准备/审计/报告另计入总elapsed。native步与RL决策严格区分。

单物理环境、每环境单线程、CPU-only，最低可用RAM 28.31GiB，最低磁盘余量198.72GiB；未购买或调整Hetzner。资源样本、进程超时及退出检查保留。吞吐与条件估时见RESOURCE_USAGE.json/FINAL_CAMPAIGN_PLAN.json。

## 11–13. 阻碍、明日配置与下一优先项

主要阻碍：原B/H150完整scorer和state/基准身份缺失；G4的HOLD/绝对安全及完整矩阵未闭合（自然OUTBOUND/RETURN timeout已有新证据）；未见患者泛化未测试；没有完整资格支持的force/motion收益。另有三seed严格学习复现失败。

明日应先补齐原评价器与基准复现，再按FINAL_CAMPAIGN_READINESS.md的原PPO/reward配置和至少3 seed做已批准范围内的有界验证；正式campaign预算当前未批准，不应直接开百万decision训练。现有CPU未见扩容依据。若必须在reward/动作空间/算法/规模中排序，先补齐原scorer，再审计reward/rollout信用分配及随机采样与确定性均值执行差异；在有界开发中比较reward和动作分布/协调参数化，保持原物理、安全与任务门；不靠盲目增大规模弥补资格缺口。唯一下一步见NEXT_RESEARCH_DECISION.md。

## 复核、记录与停止边界

独立复核使用同一Agent的分离原始证据读取与积分代码；没有第二Agent/人工独立审稿。train/evaluation及失败/partial身份分开，未用真值/未来Human输入actor，未按测试反复挑配置。训练大raw在逐native与causal审计通过后按SHA记录去向；摘要/transition/receipt与周期checkpoint保留。关键评价保留完整无损raw，原始JF/JM和实际native运动可再计算。

冻结评价额外使用TASK前20ms真实native历史作锚，复核第一个TASK区间及所有native/5ms/20ms加速度窗口；jerk以TASK内全部结束点计算并保留原无锚窗口诊断数值。该补查不重定义原scorer。最终保护、START/END闭合、checkpoint身份、完整原始评价重算、所有owned进程退出、文件与manifest完整性以VALIDATION_RESULTS.json、ATTEMPT_ACCOUNTING.json、PROCESS_EXIT_AUDIT.json和PACKAGE_VERIFICATION.json为准。没有Git checkout；没有stage/commit/push/merge/reset/stash/clean，没有改正式控制器、物理或任务门。

本轮最终STOP。不得自动开始最终训练或下一研究包。

## 封包前最终核验

2026-10-20T22:01:07.171353+08:00，VALIDATION_RESULTS的23项核验全部通过，失败项为空。322个START/322个END闭合；259次真实物理尝试（240训练+19冻结评价），259个EPISODE_START/259个EPISODE_END闭合。51代checkpoint的model/RNG hash和跨进程恢复核对通过；19次冻结评价再次独立逐native核对ownership、实际torque及source-age，通过。4,827个历史保护文件与原ZIP/权重不变，414份科学源码及冻结执行合同不变。所有owned训练/仿真/观察器进程退出。

本轮Stage2没有启动，没有最终大规模训练或后续研究包。唯一下一步为恢复原B/H150完整scorer/fixture/state身份；稳定性诊断可在后续独立授权的有界研究中进行。本包STOP。归档及manifest校验见PACKAGE_VERIFICATION.json和同级外部ARCHIVE_VERIFICATION.json。
