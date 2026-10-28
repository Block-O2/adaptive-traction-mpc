from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import ROOT,put
old=ROOT.parent/'rl_b_cloud_g4_repair_v1'
saved=json.loads((old/'audit/FINISHED_EPISODE_AUDITS.json').read_text())
items=[
 ('normal_full_task','NATURAL_PHYSICS_PASS','TEST_ONLY_PASS',['repair_reset_maximal_01','repair_random_01'],'完整phase与causal native commit；不由此授予matched资格。'),
 ('natural_TASK_and_phase_timeout','NOT_EVALUABLE','TEST_ONLY_PASS',['repair_outbound_TEST_ONLY_01','repair_return_TEST_ONLY_01'],'合法slow在9.820s先NO_FEASIBLE；零进度先reference-regression拒绝，不能冒充自然timeout。三phase各10s使global30s通常被phase bound覆盖；没有全动作不可达证明。'),
 ('HOLD_failure','NOT_EVALUABLE','TEST_ONLY_PASS',[],'HOLD候选与actor比例无关；无授权外扰，自然dwell失败未观察。源码只证明actor不能直接改HOLD目标，不证明所有合法入口均不可能失败。sensor-clock合成流清零dwell并10s timeout；旧HOLD exit-suppression的NO_FEASIBLE不是TIMEOUT_HOLD。'),
 ('zero_progress_stagnation','NATURAL_PHYSICS_PASS','TEST_ONLY_PASS',['repair_hold_01','repair_slow_01'],'合法零进度在0.005s原规则拒绝；慢动作最终NO_FEASIBLE。只覆盖这些被正确拒绝的停滞case，未声称存在新stagnation watchdog。'),
 ('consecutive_rejected_actions','NATURAL_PHYSICS_PASS','TEST_ONLY_PASS',['repair_slow_01'],'原slow最后两次request FAILED后NO_FEASIBLE；20次拒绝计数与fallback单元是TEST_ONLY，不等价于自然20次拒绝压力测试或独立REPEATED_REJECTION终止器。'),
 ('planner_failure','NATURAL_PHYSICS_PASS','TEST_ONLY_PASS',['repair_slow_01','repair_hold_01','repair_return_hold_01'],'真实无可行candidate/schedule异常保留，原fallback可用时继续，不可用时终止。'),
 ('legal_fallback','NATURAL_PHYSICS_PASS','TEST_ONLY_PASS',['repair_random_01','repair_reset_maximal_01'],'实际escape、brake/stop/hold、fresh resume与receipt/certificate链；不放宽准入。'),
 ('absolute_safety_trigger','NOT_EVALUABLE','TEST_ONLY_PASS',['repair_safety_TEST_ONLY_01'],'没有在合法动作和完整保护下观察自然超限；不绕过保护制造违规。旧MuJoCo测试只注入monitor acceleration字段；本轮6项原限值/安全优先协议测试。未证明全动作安全不变性。'),
 ('partial_episode_reward','NATURAL_PHYSICS_PASS','TEST_ONLY_PASS',['repair_hold_01','repair_slow_01','repair_return_hold_01'],'3个自然partial+3个TEST_ONLY partial的raw独立复算；失败progress归零、completion=-10、成本非正。'),
 ('terminated_truncated','NATURAL_PHYSICS_PASS','TEST_ONLY_PASS',['repair_hold_01','repair_slow_01','repair_return_hold_01','repair_reset_maximal_01'],'有限任务失败和成功最终transition terminated=True、truncated=False，吸收态为0且不能重复step；deadline专有分支只有TEST_ONLY。'),
 ('reset_cleanup_and_next_episode_independence','NATURAL_PHYSICS_PASS','TEST_ONLY_PASS',['repair_reset_maximal_01'],'同进程两真实episode清理4项检查通过，owner退出、计数/force/reward/队列不继承。跨进程checkpoint恢复不冒充同进程reset证据。')]
rows=[]
for key,nat,test,runs,reason in items:
 refs=[]
 for run in runs:
  refs.extend({'run':run,'episode':x['episode'],'category':x['category'],'status':x['status'],'task_s':x['task_s'],'reason':x['reason'],'saved_raw_audit_pass':x['case_audit_pass'] and x['force_audit_pass'],'path':str(old/'runs'/run/'physics'/f'env/episode_{x["episode"]:04d}')} for x in saved if x['run']==run)
 rows.append({'item':key,'natural':nat,'test_harness':test,'evidence':refs,'interpretation':reason})
unitnames=['G4_UNIT_RESULTS.json','REPAIR_BOUNDARY_TESTS.json','SAFETY_AUTHORITY_TESTS.json','EXECUTION_CONTRACT_TESTS.json']
units={n:json.loads((ROOT/n).read_text()) for n in unitnames}
put(ROOT/'G4_TEST_COVERAGE.json',{'G4_STRICT_PASS':'FAIL','G4_TEST_HARNESS_COVERAGE':'PASS' if all(x['pass'] for x in units.values()) else 'FAIL','natural_matrix_closed':False,'required_natural_gaps':['phase/TASK timeout','HOLD not established','absolute safety stop'],'items':rows,'units':units,'classification_rule':'TEST_ONLY_PASS never substitutes for NATURAL_PHYSICS_PASS','old_raw_reintegration':'audit/REUSED_FORCE_RECOMPUTATION.json','no_new_failure_physics_required_for_reuse':True})
lines=['# G4 严格验证\n','G4_STRICT_PASS=FAIL。G4_TEST_HARNESS_COVERAGE=PASS只证明逻辑/注入覆盖，不替代原严格自然失败门。\n','|项目|自然物理证据|测试harness|','|---|---|---|']
for r in rows:lines.append(f'|{r["item"]}|{r["natural"]}|{r["test_harness"]}|')
lines += ['\n原9个episode完整raw重积分本轮再次9/9通过（无新物理执行）；原实际Human motion、source age、receipt/native ownership审计以保护hash与明确源路径复用。新PPO episode另做独立raw审计，绝不把其正常运行当作缺失自然失败的证据。\n','## 可达性与正式审计路径\n']
for r in rows:lines.append(f'- {r["item"]}：{r["interpretation"]}')
lines += ['\n不存在自然失败证据并不自动等于保护逻辑失败，亦不证明边界不可达。对三类缺口，应先固定“合法动作+原保护+原模式”的可达状态集合，审计timeout与admission/fallback谁先触发；HOLD分析覆盖所有合法入口和连续sensor-clock条件；安全分析覆盖证书保守性、实际执行与monitor authority。若提出某边界结构性不可达，须提供相应证明和独立审查，原要求不能由本轮自行删除。若原合同明确要求自然物理矩阵，即使逻辑测试全部通过，仍应保留严格FAIL，直至取得合规自然证据或用户批准单独版本的正式资格规则。\n','原连续拒绝要求在可观察范围内通过：两次真实FAILED及合法fallback链。更强的固定次数拒绝压力试验只有TEST_ONLY；不声称覆盖任意连续拒绝长度。自然planner失败、停滞拒绝与自然timeout是不同终止原因。\n','所有partial保持真实累计力/运动成本；失败potential回到0、completion=-10，不因少动而赚成功奖。协议测试覆盖迟到deadline优先、安全优先、duplicate时钟、终态吸收和reset清理。\n','完整逐项直接证据、源路径和适用范围见 G4_TEST_COVERAGE.json。']
(ROOT/'G4_STRICT_VALIDATION.md').write_text('\n'.join(lines)+'\n')
print({'items':len(rows),'unit_checks':sum(len(u['tests']) for u in units.values()),'all_unit_pass':all(u['pass'] for u in units.values())})
