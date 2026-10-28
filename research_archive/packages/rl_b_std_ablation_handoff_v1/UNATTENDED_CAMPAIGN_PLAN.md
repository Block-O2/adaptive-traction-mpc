# 7–8小时无人值守开发计划

状态：FINAL_PREPARED_NOT_STARTED。本轮零训练、零梯度；本文件和模板不会自动启动下一轮。全部模型身份见 NEXT_PARENT_CHECKPOINTS.json。

方法：['CHECKPOINT_STD', 'STD_INIT_0p2']。若本轮B在两个父均提高完整完成数且无A-only配对，下一轮比较原STD与初始化可学习STD=.2；否则比较H2 aggregate64/128，保持R1。这个规则用于计算分配，不是显著性或训练效果证明。

|阶段|训练episode上限|冻结评价上限|目的|
|---|---|---|---|
|稳定性10集screen|40|8|2方法×2父；每端点mean/sample|
|共同延长至30|80|8|仅保留两父mean且至少一次sample成功的方法|
|R1/R4同父分叉10集|40|8|固定已选PPO，检验moment价格|
|先锁候选再评价|0|12|每父6条未使用保留动作流|
|合计|160|36|有限清单；未通过的分支不无限追加|

历史实测训练吞吐 1401.30、评价 1280.64 native steps/s，来自390训练/52评价完整job wall（含保存/审计）。按历史实际失败混合平均step估算约3.89小时计算；所有196次都用165000 native预算、分别按对应实测吞吐估算约6.52小时，再留45分钟复核/恢复。不是保证，成功任务比例升高会改变episode时长。33M native、8小时硬限独立生效。

单物理环境；Torch/BLAS单线程、单核亲和；至少6GiB可用RAM、10GiB空闲磁盘；单attempt300秒/165000 native/128 RL decisions，单job外层超时、输出上限60GiB。6小时后不启动新训练，并在训练job准入时预留其最坏wall；7小时45分不启动新物理；7小时50分failsafe开始独立关闭；8小时前watchdog终止仍活着的owned PGID。12次最终评价的1.98M native始终保留，直到锁定最终候选后使用。

隔离机制复用：不可变447文件runtime、原checkpoint全状态恢复、内容地址worker bundle、逐attempt START/END与native预留/结算、PID+start_ticks/PGID监督、独立watchdog、deadline failsafe。新增代码修复旧status重复参数收尾错误；实际控制器已用fake jobs测试普通分支FAIL后继续、全局完整性STOP、最大episode/评价数、先锁候选后12条保留流。没有本轮训练端到端验证，见 readiness。

训练STD实验必须生成新policy身份：完整加载原policy/critic/Adam/RNG后，在pending为空时只初始化log_std；actor mean与critic继承，Adam继承。此后用实际新分布采样raw动作、保存其log_prob，clip仅用于执行；每次更新前独立evaluate_actions检查old log_prob属于当前采样policy且初始ratio≈1。不得修改std后沿用旧policy日志概率或跨分布pending。

原子checkpoint：zip和RNG分别写临时文件后replace，metadata为generation commit marker；下一阶段wrapper额外fsync三个payload与目录。每次完整更新前保存before_update_checkpoint和完整rollout。普通续跑只接受完整metadata/SHA/空pending或已验证完整pending；partial Adam不自动恢复，不重复已有attempt。保留损坏generation及分支证据。

断线后已启动的有限清单依靠独立campaign/watchdog/failsafe继续或有界关闭，不依靠聊天存活。后台不会生成新权重网格、Reward或无界实验。普通ABORTED是科研结果，失败screen保留后继续下一方法；已确认local branch fault可跳过其后续；未知worker异常、实际安全/receipt/身份/资源控制失败整体停机。

状态入口：未来包内 `python3 scripts/status.py`，读取 RESEARCH_STATE/LEDGER/PROGRESS_REPORT/JOB_RESULTS。连接中断但PID身份仍活着时不要再启动第二个campaign。若进程真正退出：先查owned PGID、未结算预留和checkpoint metadata/SHA；deadline保持原值，不能重置8小时时钟；partial-Adam generation须显式离线恢复或跳过分支，禁止自动猜测。

本轮只提供inactive launcher：`python3 unattended/next_launch.py --inspect`。下一轮获得明确训练授权后才可执行 `python3 unattended/next_launch.py --prepare-authorized --start-authorized`；它创建新的独立rl_b_training_stability_reward_v1包并使用新的时间/PID/状态/队列。目录存在即拒绝，须人工选择新版本或依恢复指南继续。不得复制旧STOP、PID、时间戳或账本。

科学边界：即使开发mean/sample及保留动作流都成功，仍仅为两个成功父的nominal开发研究。G4严格安全、原B/H150同链live matched、独立合法物理初态和Stage2仍不具备。正式Campaign、Stage2、服务器升级均不在此启动器范围。
