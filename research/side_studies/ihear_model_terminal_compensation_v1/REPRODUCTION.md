# 证据导航与只读复核

主报告为REPORT.md。完整冻结代码、19个完整运行的raw、两个失败/partial、注册方案、版本修复、独立重算及保护审计都在本包内。Windows目录是完整科学证据镜像，canonical执行根在 `/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_model_terminal_compensation_v1`。

## 关键路径

|内容|位置|
|---|---|
|原始5ms trace及summary|`source/results/<run>/trace.npz`、`summary.json`|
|完整native、receipt、请求及激活证据|`source/results/<run>/runtime_artifacts.json.gz`|
|原0.25ms人体状态及导数|`motion_series/<run>.npz`|
|原资格逐项结果|`reports/<run>_MEASURED.json`、`EXPERIMENT_RESULTS.json`|
|四种辅助每周期因果输入、修正、过滤结果|`output/Ctrl_<arm>_CONTROL_INTENT.json`|
|原始START/END|`ATTEMPTS.jsonl`；闭合账本为`ATTEMPT_ACCOUNTING.json`|
|候选参数与源代码绑定|`CANDIDATE_PLAN.json`、各组`*_PLAN.json`、`CANDIDATE_LEDGER.json`|
|执行v1/v2全部源码SHA|`EXECUTION_CODE_MANIFEST.json`、`EXECUTION_CODE_MANIFEST_v2.json`|
|冻结与验证|`NEW_FROZEN_SELECTION.json`、`REPEAT_VERIFICATION.json`、`HOLDOUT_REGISTRATION.json`、`VALIDATION_RESULTS.json`|
|历史与Git保护|`audit/HISTORY_PROTECTION.json`、`audit/GIT_LOGICAL_STATE.json`及BEFORE/AFTER快照|
|最终证据与交付|`EVIDENCE_MANIFEST.json`、`PACKAGE_VERIFICATION.json`、`DELIVERY_VERIFICATION.json`|

物理步长0.00025s；控制trace名义0.005s。5ms force积分使用TASK完整区间左端求积；jerk从native真实dq连续两次gradient得到，不删端点。原注册RETURN目标[5°,10°]，合法issued终点[5.5°,9.5°]。主overshoot以issued膝9.5°为基准。

最终图依次为`01_historical_terminal.png`至`09_controller_intents.png`（中间编号对应文件名中的主题）。原先的`01_terminal_reference_actual.png`保留为探索性绘图，最终参考/实际对照请用`01_historical_terminal.png`；推荐从REPORT中的图5、7、8及诊断报告中的图4阅读。

Dev、Ctrl为同一暴露W1条件；Ctrl含新的完整cold parent及H150确定性重复。W2为冻结后消费的新prefix，同一Human。父native序列与fork共享前缀；物理预算/计算量只计fork新增steps，不重复计继承部分。

## 分析程序

`analysis/historical_prediction.py`、`diagnosis_details.py`和`prediction_decision.py`读取历史数据做因果预测及诊断。`analyze_experiments.py`计算完整对照与辅助receipt绑定；`causal_native_proof.py`逐body证明干预前一致；`verify_repeat.py`比较全trace/native及科学receipt字段。`independent_all.py`使用独立算术实现，单独进程、不导入plant/controller，重算原始积分、运动量与逐步ownership。

分析代码中的源根为已记录的canonical路径，所用Python为 `/home/hank/envs/adaptive-online-rl-v1/bin/python`。只读独立算术入口为 `analysis/independent_all.py Dev Ctrl W2`；它重读raw并写复核JSON，不调用物理。最终图生成顺序为`analyze_experiments.py`之后再运行`final_figures.py`。

本包已封存。不要在本包内再次运行bootstrap、prepare或owner，也不要删除STOP文件、修改冻结manifest或重用W2作为盲测。分析重跑会更新派生文件与manifest一致性；如需进一步研究，应另行获得授权，复制新的版本化包并另注册开发/验证协议。本说明不启动下一研究包。
