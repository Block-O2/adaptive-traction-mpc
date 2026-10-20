# 复现入口与冻结边界

环境：WSL Ubuntu-Research-Verify；Python /home/hank/envs/adaptive-online-rl-v1/bin/python；包 /home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_interface_v1。现有依赖/模型随闭包保存，无需修改主仓库或旧Side Studies。

本包已经STOP。**默认只重放/审核存档，不产生新的physical START。** own_physics/physical_runner都拒绝PHYSICS_STOP；不要在本包删除marker或重置ledger。若将来另行授权物理复现，应使用全新隔离输出、独立T0/截止/START预算，保留这里的原始证据，按FINAL protocol运行匹配B/zero/.02/repeat；不含force搜索。

```bash
P=/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_interface_v1
PY=/home/hank/envs/adaptive-online-rl-v1/bin/python
# 30项数学/接口测试，零physical START；会重写测试结果时间。
$PY -B "$P/tests/test_certification.py"
# 只读raw physics，独立系数/receipt/native/积分/运动统计复算；写本包审计输出。
$PY -B "$P/control/audit_physics.py"
# 存档数据生成五组科学图；不stepping physics。
$PY -B "$P/control/figures.py"
```

冻结包若需保持字节身份，先复制到全新审阅目录，再运行这些会刷新输出的脚本。物理入口是control/own_physics.py → physical_runner.py，最终实跑版本manifest在versions/interface2；首版在versions/interface1。START以manifest SHA绑定源码/模型/配置/权重，ATTEMPTS追加AUDIT补全实际reference/certificate/steps/结果，不篡改历史START/END。

审计代码只导入原raw JSON streaming parser，不导入planner/controller；独立normalized polynomial导数求值、SHA重建、receipt/native唯一时间区间及exact torque/步数、完整原积分、motion统计。当前certificate的完整内容未存档，因此独立重算仅限reference+worker certificate，current hash/状态准入由实际运行记录与保留源码验证。host timing原失败仍保留。

PACKAGE_MANIFEST包含最终文件SHA（排除它自身、STORAGE及临时cache）；CODE_MANIFEST保留最初来源SHA及最终两处原文件改动。原plant/FAST/allocator/任务等复制项逐文件与初始隔离副本SHA相同。key_traces的raw链接都只指向本包source/results；导出时需保留相对目录或解引用复制。Windows review是轻量审阅副本，完整原始证据以WSL包为准。
