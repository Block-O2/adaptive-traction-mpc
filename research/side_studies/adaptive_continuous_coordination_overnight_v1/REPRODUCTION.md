# 复现与证据口径

Canonical包：Ubuntu-Research-Verify:/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_overnight_v1。Windows同名目录仅为轻量review镜像，完整raw在canonical。全部新增代码/输出归本包。

只读/无physics重算（只写本包派生结果）：

```bash
PY=/home/hank/envs/adaptive-online-rl-v1/bin/python
PKG=/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_overnight_v1
$PY -B $PKG/control/diagnose.py
$PY -B $PKG/control/math_validate.py
$PY -B $PKG/control/schema_gate.py
$PY -B $PKG/control/independent_verify.py
```

这些脚本不调用plant stepping，schema_gate仅import原schedule类型/公式。未来重算不属于本轮截止内新证据，勿覆盖最终记录冒称本轮交付；如要重算，先复制到新的授权分析目录并保留最终版本。

本轮实际physics由control/own_baseline.py唯一owner管理，命令/开始/退出见control/BASELINE_OWNER.json，日志logs/baseline.log。baseline_runner在既有科学模式下合法冷父与三fork，原seed=2026101303；4 START硬cap与本轮绝对时间防止自动重启。PHYSICS_STOP.allow_restart=false。不要运行复制的历史campaign脚本，它们保留旧用途/协议，不是本包新授权入口。

source选择：历史ihear_overnight_research_retrospective_v1/CODE_MANIFEST，1376源文件核验后复制；所有路径迁移记录CODE_MANIFEST。模型/配置/compiled native/权重见audit/MODEL_CONFIG_NATIVE_WEIGHT_HASHES。指定Python存在并解析到既有基础环境，实际版本和module闭包见audit/IMPORT_PREFLIGHT。无依赖安装或更新。

历史raw位于key_traces，来源路径与SHA见audit/HISTORICAL_TRACE_MANIFEST；新raw位于source/results/baseline_*，新metrics在reports，dense Human在motion_series。历史reported验证、独立重算历史证据、新full physical rollout三类严格分开。新B/18D历史raw逐native和receipt一致见audit/INDEPENDENT_RAW_VERIFICATION。

原成本完整TASK5ms边界左积分；各phase按真实转移时间裁切区间。0.25ms真实dq连续两次gradient(edge_order=2)，端点不删，SG5/21敏感性诊断分列。reference解析ddq和actual数值导数不混用。评价阈值保留MOTION_ACCEPTANCE_PROTOCOL，不按结果调低。

静态代码定位见CURRENT_ACTION_AUTHORITY_AUDIT；原型精度、首次失败和修复见prototype/MATH_PROTOCOL及prototype/repairs；非零接口最小反例见PHYSICAL_INTERFACE_PREFLIGHT。完整科学结论与未做项见REPORT。不要把零修改折回成功当新多段物理权限。
