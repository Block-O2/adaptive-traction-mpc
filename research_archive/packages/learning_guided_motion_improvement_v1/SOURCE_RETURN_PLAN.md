# 源码回流计划

本轮不自动Git提交或推送。先review新包，再由用户确认是否纳入长期仓库。

建议审查：source/nominal_proxy.py中的明确模型/ROM/residual身份与causal输入allowlist；source/optimizers.py中的同权限直接/名义/残差臂、整轨迹监督与模型身份；source/study_worker.py中的预算、full-live fork与per-arm反馈隔离；独立积分/receipt审计及append-only研究决策日志。

历史runtime/source、code、control、deps是可定位的版本复制，仅做已登记路径与资产恢复，不应整包覆盖正式B或与PPO云端修复混合。数据、实验决策、参数域与脚本路径特化部分留在research包；模型预测有效范围、失败、held-out纪律与原scorer保护须一起保留。

回流前检查零参数与H150 raw等价、完整state fork与RNG、原安全/40ms bridge/100ms生命周期、未来真值防火墙、相同预算计数、旧raw保护及独立积分。仅新增身份明确的研究模块，不能因此给host实时/Stage2/硬件资格。

应单独修正并测试继承Campaign的RETURN-slot operational logger：当前按H150 recipe id写入可变诊断文件，回流时应绑定unique attempt id；本轮科学证据使用独立per-attempt raw、causal history和prediction，见audit/OPERATIONAL_LOG_SCOPE.json。
