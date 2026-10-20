# Early RETURN Repair v1 — 物理前冻结协议

RETURN1选后suffix duration倍率1.10/1.20，原规则向上5ms对齐；同活态原目标与通过速度保持。18D参数、RETURN plateau、T1.5选后规则、D RETURN2/3 [+0.3,-0.3]°冻结。每条新quintic重做原certificate、mechanics、escape、40ms桥接与current admission；没有复用旧曲线证书或改变正式接口。

{
  "full_gates": "Every original task, safety, complete motion/fairness vs matched B, actual intervention acceptance, causal/native ownership",
  "meaningful_gain_percent": 1.0,
  "major_gain_retention_fraction": 0.8,
  "eligibility": "all original gates; J_F gain>=1% vs same matched B; retain>=80% of matched frozen D saving",
  "selection": "Among eligible prefer smaller duration factor; no minimum-force search. Freeze before any validation.",
  "bounded_repair": "At most one subsequent development revision, prospectively registered after mechanism analysis; no validation-based reselection.",
  "stop": "Original task/safety/causal fail stops all physics. New failed metric vs D, >10% raw acceleration max or jerk RMS vs D, or tracking RMS>D+0.5deg pauses remaining candidates for mechanism review.",
  "validation": "Reserve11 START; selected same-W1 cold parent B/T/D/primary/repeat (6); one never-used legal prefix B/T/D/primary (5). If no eligible primary, no validation. All serial."
}

开发条件W1，真实完整commissioning及合法OUTBOUND0父状态后serial live fork。B/T/D须逐字段复现旧W1；全部候选完整19.030s任务及各phase合同不变。先原始dense统计，再SG5/21敏感性；完整matched-B相对门不改变。单因子虽保留D规则，后续实际选定duration/目标可因果响应，须记录。所有失败/partial保留。

最多24 START（父/子/失败/重复/验证均计），开发最多13保留11验证。T0 2026-10-18 14:36:39+08，18:36:39硬截止，17:51:39后无新START，另保留900s完成在途运行。禁止Human真实状态赋值/回放、RL、gain/plant/ROM/阈值修改、Git提交或分支操作。具体参数和预检见CANDIDATE_PLAN.json、audit/OFFLINE_PRECHECKS.json。
