from pathlib import Path
import os,json,shutil,copy,time
P=Path(__file__).resolve().parents[1];O=P.parent/'representation_execution_v3'
def put(n,d):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
# Independent copied scorer utilities, all output roots relocated to this package.
shutil.copytree(O/'legacy_source',P/'legacy_source',dirs_exist_ok=True)
for f in (P/'legacy_source').rglob('*.py'):
 s=f.read_text();f.write_text(s.replace(str(O),str(P)).replace(str(P.parent/'autonomous_coordination_learning_v2'),str(P)))
s=(P/'source/v3_worker.py').read_text();s=s.replace('from acl2_modal_retimed import RetimedModalPlanner','from acl2_modal_retimed import RetimedModalPlanner\nimport branch_diagnostics\nbranch_diagnostics.install()');s=s.replace("'acl2_modal_retimed.py']","'acl2_modal_retimed.py','branch_diagnostics.py']")
# Keep inherited scoring; add task and native caps already checked at every boundary.
(P/'source/v4_worker.py').write_text(s)
p1=json.loads((O/'experiments/P1.json').read_text());p2=json.loads((O/'experiments/P2.json').read_text());cfg=copy.deepcopy(p2);cfg.update(group='DEV',historical_repeats={},actions=[])
actions={a['tag']:a['action'] for a in p1['actions']};c19=next(a['action'] for a in p2['actions'] if a['tag']=='C19');neg=next(a['action'] for a in p2['actions'] if a['tag']=='NEG')
for tag in ['B','H150','OLD_STRONG','BEST']:cfg['actions'].append(dict(tag=tag,action=actions[tag],category='fixed_candidate'))
cfg['actions'].append(dict(tag='C19',action=c19,category='fixed_candidate'))
for delta in [-.0008,-.0004,-.0002,.0002,.0004,.0008]:
 a=copy.deepcopy(c19);a['x'][3]+=delta;cfg['actions'].append(dict(tag=('LOCAL_M' if delta<0 else 'LOCAL_P')+str(abs(delta)).replace('.','p'),action=a,category='unseen_local_validation',local_delta=delta))
cfg['actions'].append(dict(tag='NEG',action=neg,category='fixed_candidate'))
put('experiments/DEV.json',cfg);put('runtime/DEV_TEST_PLAN.json',cfg)
(P/'EXPERIMENT_CONTRACT.md').write_text('''# 研究合同\n\nACTIVATION固定于ACTIVATION.json，十小时硬截止，恢复不重置。全部物理串行、完整地址空间合法父fork、父状态散列核验。历史包只读；原plant、任务、阈值、scorer、HOLD、端点和积分口径保持。\n\n## 门控与实际执行\n\nP1双端点解析/零物理检查已经执行。点态等价不提供采样间与实际actuator保护；缺少误差界，候选不晋级物理。所有新增物理保留原guard，只添加原输入的因果诊断记录，返回相同correction。P2-B/C新旧guard对照NOT_RUN；P3改按预授权备选，评价分支感知预测与上层搜索，不能称guard改进或Learning贡献。\n\n## 冻结候选与预算\n\nDEV冻结B、H150、旧强固定、新最佳、C19、NEG和六个未见C19微扰。原motion与硬安全分别判定；失败不进入正式JF排名。DEV共12分支加1冷父。新候选在运行前写下预测，训练数据仅历史因果估计/候选。随后最多两臂各8次传统优化；冻结后保留至少12个验证attempt，独立prefix不得用于调参。全局物理START硬上限120，native上限14,000,000，单次180,000且300秒，RAM至少6GiB、磁盘18GiB，距硬截止40分钟进入封包。任何预算扩展先登记。\n\n## 因果边界\n\nguard当前采样的精确代数诊断与上层执行前预测分开。原始Human truth只作评价标签。相同父/初始动作不意味着后续反馈轨迹相同。记录issued/accepted/activated/receipt、torque和native Human q/dq/contact；同任务原JF/JM积分。host实时资格单列，不继承正式安全资格，无硬件或Stage2。\n\n## 停止与恢复\n\n每组worker有独立配置、源码SHA和PID/starttime记录；局部截止与全局ALARM、native计数、串行锁。中断时封存partial，不重跑同ID。无需常驻服务器外客户端；已启动有限队列可继续，但本研究不假设推理会话断线后会继续思考。终态STOP，不自动下一轮。\n''')
print('PREPARED',len(cfg['actions']))
