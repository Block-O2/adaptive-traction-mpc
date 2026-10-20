"""Record a development-stage choice before model freeze and any test START."""
from pathlib import Path
import time,json,shutil,hashlib
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
assert not (P/'models/VALUE_FREEZE.json').exists()
assert not any(json.loads(s)['id'].startswith('U') for s in (P/'ATTEMPTS.jsonl').read_text().splitlines())
entry=dict(unix=time.time(),status='DEVELOPMENT_RULE_CLARIFICATION_BEFORE_TRAINING_AND_TEST',evidence_seen=['D01R','D02','D03'],motivation='D03 ZERO passes while H150/HIP/KNEE fail excursion; qualification first requires allowing predicted qualification recovery even when force is higher than unqualified H150.',rule='If supported and H150 conservative predicted margin is not positive, choose minimum cost among candidates with all conservative margins positive. If none, keep H150 as unqualified reference fallback. Otherwise require force advantage greater than empirical error. Original safety/admission always rechecks.',test_conditions_changed=False,motion_limits_changed=False,force_gain_and_qualification_recovery_reported_separately=True)
entry['files']={str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [R/'learning/value_model.py',R/'control/frozen_selector.py',R/'control/feedback_selector.py']}
(P/'audit/SELECTION_RULE_DEVELOPMENT_CLARIFICATION.json').write_text(json.dumps(entry,indent=2)+'\n')
f=P/'LEARNING_PROBLEM_DEFINITION.md'
with f.open('a') as out:out.write('\n## 开发阶段的资格优先澄清\n\nD03完成后、训练与全部U测试之前，明确：若H150预测余量下界不为正而其他候选有正下界，可选择预测成本最低的合格候选，即使其力积分高于不合格H150。若没有可信候选仍保持H150研究参考，但不宣称实际资格。若H150本身预测合格，则保持原force优势误差门。资格恢复与对合格H150的降力收益分开报告。详见audit/SELECTION_RULE_DEVELOPMENT_CLARIFICATION.json。\n')
print('DEVELOPMENT_SELECTION_CLARIFIED',flush=True)
