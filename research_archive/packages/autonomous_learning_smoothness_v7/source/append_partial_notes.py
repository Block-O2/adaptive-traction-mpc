from pathlib import Path
import json
P=Path(__file__).resolve().parents[1];parts=[json.loads(f.read_text()) for f in sorted((P/'analysis/partials').glob('*.json'))];body='\n\n## 全部受保护partial（不排名）\n\n'
for d in parts:body+=f"- {d['id']}：{d['protected_task_failure']['abort_reason']}；新增native={d['actual_new_native_steps']}；partial JF={d['partial_JF_unranked']} N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={d['protected_task_failure']['hard_safety_conditions']}。\n"
for name in ['CAUSAL_PHYSICAL_COMPARISON.md','REPRESENTATION_PERMISSION_ALIGNMENT.md','CROSS_STATE_VALIDATION.md']:
 f=P/name;s=f.read_text().split('\n\n## 全部受保护partial（不排名）')[0];f.write_text(s+body)
f=P/'LEARNING_DECISION_STUDY.md';s=f.read_text().split('\n\n## 四层结论')[0];s+='''\n\n## 四层结论\n\n1. 预测：六个预登记同父未见参数点6/6资格吻合；这不是随机总体准确率，未建立跨患者或一般state可靠性。\n2. 排序：没有证明比同信息传统成本规则排序更好；窄失败带预测与force排序分开。\n3. 决策：事后规则分析选同一点；不能称前瞻决策或因果策略改进。\n4. 完整运动：新的JF/JM取舍来自编译因子，不能记入Learning贡献。\n\n已执行的数据拟合明确为五条历史因果响应的传统线性拟合，并与解析min差分组合；独立Learning增量对照、神经网络、PPO新执行/训练均NOT_RUN。模型训练数据是历史同父物理fork，不等于五个患者或真实重复适应历史。\n''';f.write_text(s)
print('PARTIAL_NOTES',len(parts))
