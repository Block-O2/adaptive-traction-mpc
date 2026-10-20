# 身份与复核

canonical目录：`/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_control_learning_transition_v1`。Python：`/home/hank/envs/adaptive-online-rl-v1/bin/python`；MuJoCo/NumPy版本见ENVIRONMENT及源manifest。所有本轮新源文件位于control/analysis/learning或provenance/authoring。

执行层由EXECUTION_CODE_MANIFEST_v2.json冻结，v3增加在线Q及预注册早期QE选择，v4增加真实持续重复及反馈选择，v5/v6仅修复序列化恢复和独立启动日志；原B/物理/准入实现未更改。START记录携带执行manifest与group plan SHA。训练身份见models/TRAINING_CODE_MANIFEST.json、VALUE_FREEZE.json及EARLY_VALUE_FREEZE.json。测试plan添加Q、QE分支，原条件、种子和五个固定动作不变。相应测试START必须晚于两个模型的权重冻结。

只读复核算法入口：control/independent_recompute.py（不导入runner/plant）；analysis/audit_raw.py逐组重算原始完整积分、native平顺性与receipt；learning/evaluate_value.py根据冻结权重和记录状态复核策略。它们的输出仅能写新研究目录，若复算已封包结果，应复制到新的独立审计目录并保存原SHA，避免修改本包最终manifest。

实际物理启动命令完整保存在*_OWNER.json的command与logs，环境STUDY_GROUP/STUDY_MODE由owner设置。主测试入口为control/owner_v3.py；成功的连续重复入口为control/repetition_owner_v6.py，调用repetition_runner_v6.py。v4保留为失败证据，v5未启动worker。

所有physics已STOP，不应删除STOP标志后在本目录重跑。需要新物理复现时，创建新版本目录，复制冻结代码、权重及科学配置，在新包登记路径、T0/硬截止、预算和唯一运行ID等管理信息，冻结新的manifest并明确列出这些差异。保留原seed/prefix/控制参数/任务门，使用新的空输出目录保存新运行，不覆盖或删除本包证据；通过同父raw比较后才评估新结论。禁止从raw设置/回放Human状态。

P1 START=83，P2=0。parent完整轨迹含commissioning/prefix，fork继承全live地址空间但只计新增native后缀，父进程等待children，不并行推进physics。边界及persistent bootstrap额外成本在ATTEMPT_ACCOUNTING.json解释。报告图来自raw/numeric结果，没有绘制虚构RL训练曲线。
