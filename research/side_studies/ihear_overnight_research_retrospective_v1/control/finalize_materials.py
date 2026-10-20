"""Finalize Chinese prose and evidence; no model/runner import or physics."""
from pathlib import Path
import json,time,hashlib,csv,datetime,re,shutil
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def block(path,name,text):
    start='<!-- '+name+'_START -->';end='<!-- '+name+'_END -->';p=S/path;s=p.read_text();new=start+'\n'+text+'\n'+end
    s=re.sub(re.escape(start)+'.*?'+re.escape(end),lambda _:new,s,flags=re.S) if start in s else s+'\n\n'+new+'\n';p.write_text(s)
r=load(S/'EXPLORATION_RESULTS.json');selection=r['frozen_selection'];v=load(S/'VALIDATION_RESULTS.json');best=selection['best'];bad=selection['diagnostic'];mech=load(S/'MECHANISM_ANALYSIS.json')
assert v['primary_condition_count']==4 and not r['open_attempt_ids']
night=f'''## 本轮夜间探索的最终补充（2026-10-14）

本轮未训练学习器。保留原机器人、被动Human、接触和执行约束，在隔离研究中将原10维意图扩为18维：两方向的共同进度倾斜/曲率、差分进度曲率、髋膝速度倾斜。参数仍经原quintic与原筛选/准入，再由六轴robot实际执行。

同完整开发父状态，冻结最好`{best['id']}`下降{best['comparison']['gain_percent']:.6f}%，全部冻结motion规则PASS；相对旧2.457489%增加{best['comparison']['gain_percent']-2.457488974523768:.6f}个百分点。这是一项有限开发改进，不是全局最优。16个±0.4新轴probe和后续三个区域的有限COBYLA结果保留；joint optimum不能把增益简单分摊为某一自由度的贡献，详见MECHANISM_ANALYSIS.json。

冻结primary在四个预注册合法prefix条件中合格{v['primary_pass']}/4、完整任务{v['primary_complete_task_count']}/4。四条件都来自同一已暴露Human；仅未消费suffix被测试，共享prefix不属于未见完整原策略。失败保留且不从分母移除，secondary事先冻结而没有用测试改选primary。VALIDATION_RESULTS.json记录完整candidate身份、冻结文件hash和先后时间、配对初态及干预前物理/控制相等。

最低force代表下降{bad['comparison']['gain_percent']:.6f}%，motion {'PASS' if bad['comparison']['acceptance_pass'] else 'FAIL'}，失败项{bad['comparison']['failed_requirements']}。它保留为负结果，不能称优质teacher。实际START/END={r['physical_attempt_start_count']}/{r['physical_attempt_end_count']}，包含两次包装失败和真实commissioning，不把数学拒绝当physics。全部科学结论最多LEVEL1，未新增原B接口、host、硬件或临床资格。

与教授的关键问题仍是：允许多少中间姿态变化、怎样评价平顺与治疗剂量、何时迁移最小参考接口，以及何时才具备few-repetition学习值得使用的state/action/label证据。
'''
for path in ['DETAILED_RESEARCH_HISTORY.md','MILESTONES_AND_EVIDENCE.md','RESEARCH_TIMELINE.md']:block(path,'OVERNIGHT_FINAL',night)
p=S/'MILESTONES_AND_EVIDENCE.md';text=p.read_text();text=text.replace('这里只承接本轮已完成的实际结果，不预写收益。REPORT.md与EXPLORATION_RESULTS.json会在候选冻结、合法条件验证和独立审计后更新。当前数据状态必须以这些文件的generation/status字段为准。','本轮冻结、合法条件验证与独立核验已完成。最终数字列在下节、REPORT.md和EXPLORATION_RESULTS.json；数据版本以这些文件的generation/status字段为准。');p.write_text(text)
short=f'''## 本轮冻结后的结论

原完整动力学中18D开发最好下降{best['comparison']['gain_percent']:.6f}%，新合法prefix条件合格{v['primary_pass']}/4；事先冻结secondary开发下降{selection['secondary']['comparison']['gain_percent']:.6f}%，新条件合格{v['secondary_pass']}/4。未用测试改选primary；这是同一Human剩余策略的LEVEL1证据，未迁移原B接口或完成host/临床资格。

下一步仍应先确认治疗允许的中间姿态和motion依据；新状态的速度/加速度/阶段端点失败说明名义开发优化不能直接当可靠teacher。完整逐条件结果见REPORT与VALIDATION_RESULTS，接口变化与负担修复诊断见MECHANISM_ANALYSIS。本轮已停止，不继续训练或自动开启下一包。
'''
for path in ['CURRENT_SYSTEM_EXPLAINED.md','ARCHITECTURE_EVOLUTION.md','OPEN_PROBLEMS_AND_DECISIONS.md']:block(path,'OVERNIGHT_CONCLUSION',short)
p=S/'DETAILED_RESEARCH_HISTORY.md';s=p.read_text();s=s.replace('Phase3 waypoint正式claim限定80°/100°','Phase3接口沿用80°/100°默认domain；对应正式科学claim属于Phase2');p.write_text(s)
p=S/'PROFESSOR_BRIEF.md';s=p.read_text();marker='## 第4页｜B现在做到什么、还不能做到什么（约2分钟）'
insert='当前研究使用1.72m/75kg名义Human、shank的72%cuff、120°/120°目标；双方0–125°hard ROM是工程假设，未来自患者测量。实际模型与历史80°/100°默认domain分开。'
if insert not in s:s=s.replace(marker,marker+'\n\n'+insert)
p.write_text(s)
ledger=load(S/'EVIDENCE_LEDGER.json');ledger['records']=[x for x in ledger['records'] if not x['id'].startswith('NIGHT_')]
claims=[('ZERO','ZERO_EXTENSION_REPRODUCTION_GATE.json','新扩展零调整原B全数据精确复现','1 pair'),('PRIOR','reports/PRIOR_RAW_INDEPENDENT_GATE.json','旧10维teacher嵌入18维的完整native/receipt/积分独立精确复现','1 pair; 116320 native rows'),('BEST','FROZEN_SELECTION.json',f'开发合格最好力积分下降{best["comparison"]["gain_percent"]:.6f}%；最低力代表motion失败另列',f'{r["physical_attempt_start_count"]} actual total physical START; development same complete parent'),('VALIDATION','VALIDATION_RESULTS.json',f'冻结primary合格{v["primary_pass"]}/4；完整任务{v["primary_complete_task_count"]}/4，失败留在分母','4 preregistered same-Human legal prefix conditions; remaining unconsumed suffix'),('MOTION','INDEPENDENT_SELECTED_METRIC_CHECKS.json','关键B/最优/强失败完整raw导数与force/moment全任务/phase独立闭合','3 representatives'),('ACTUATION','ACTUATOR_CONTACT_EVIDENCE.json','原6 robot motors/torque范围、完整native与actual receipts归属核验','3 representatives; full native arrays')]
for ident,source,claim,denom in claims:
    ledger['records'].append(dict(id='NIGHT_'+ident,stage=9,claim=claim,source=str(S/source),source_sha256=sha(S/source),lines='complete JSON',revision='frozen isolated package',classification='SUPPORTED' if ident in ['BEST','VALIDATION'] else 'CONFIRMED',denominator=denom,limitations='LEVEL1 scientific simulation; not cross-Human/host/hardware/clinical',verification='new actual data and independent read-only checks; no new simulation from analysis',record_origin='overnight_final',research_question='原完整动力学中更自由参考能否降低力且保留运动质量',then_architecture='18D bounded offline intent + unchanged quintic/physical plant',change_trigger='old 10D limited gain and motion failures',technical_change='eight added spatial/velocity shape coordinates; source unchanged except allowed path relocation',retained_or_abandoned_reason='retain qualified candidate and negative results; no automatic interface migration',causal_context_grade='INFERRED narrative linkage',numerical_result=claim,verified_degree=denom))
ledger.update(generated_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),source_history_only=False,interpretation='Historical and tonight evidence preserve distinct per-study denominators and levels; no clinical or few-repetition success.')
(S/'EVIDENCE_LEDGER.json').write_text(json.dumps(ledger,indent=2,ensure_ascii=False)+'\n')
fields=sorted(set().union(*(x.keys() for x in ledger['records'])))
with (S/'EVIDENCE_LEDGER.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
    for x in ledger['records']:writer.writerow({k:json.dumps(value,ensure_ascii=False) if isinstance(value,(list,dict)) else value for k,value in x.items()})
captions=[('01_ARCHITECTURE_BEFORE_AFTER.png','两次转变：固定参考→Goal torque→online waypoint','结构图来自历史源码；不能追认早期已具有后期lifecycle。'),('02_PROBLEM_DRIVEN_EVOLUTION.png','问题推动结构变化','日期与分母见timeline/ledger；教授上次实际边界未确认。'),('03_CAPABILITY_BOUNDARIES.png','科学、原接口、host与临床能力分开','图中旧2.457489%/1of2是历史结果，本轮结果另见第7图。'),('04_FORCE_MOTION_TRADEOFF.png','同完整父开发集force与冻结motion权衡','完整候选保留；FAIL低力不能升级为优质运动。'),('05_ACTUAL_HUMAN_MOTION.png','真实Hip/Knee角与速度、发出参考分别显示','原0.25ms native真实q/dq，每16点显示，所有统计用全部点；无滤波。'),('06_CUMULATIVE_FORCE_AND_PHASES.png','全TASK原左积分及实际phase收益','共享任务/HOLD；不因小幅变化称治疗等效。'),('07_FROZEN_VALIDATION.png','四条件固定分母和真实prefix状态','同一Human合法前向生成状态，仅验证剩余suffix，不改选primary。')]
(S/'FIGURES.md').write_text('# 图表阅读与来源\n\n'+''.join(f'## {i+1}. {title}\n\n![{title}](FIGURES/{name})\n\n{note}\n\n' for i,(name,title,note) in enumerate(captions))+'数据来源：EXPLORATION_RESULTS、各_MEASURED/trace/native motion、VALIDATION_RESULTS；绘图不新增physics。图片显示抽样不用于验收统计。\n')
helpers=['analyze_overnight.py','analyze_validation.py','analyze_mechanisms.py','actuation_evidence.py','verify_package.py','build_final_report.py','finalize_materials.py','plot_structure.py','plot_physical.py','plot_validation.py','pin_freeze.py','launch_phase.py','run_frozen_validation.py','record_delivery_qa.py','close_campaign.py']
for name in helpers:shutil.copy2(W/name,S/'control'/name)
for directory in ['history_early','history_learning','audit']:
    for p in (W/directory).glob('*'):
        if p.is_file() and (p.suffix in ['.md','.json']) and (directory=='audit' or p.name.startswith('FINAL')):shutil.copy2(p,S/'reports'/p.name)
shutil.copy2(W/'PACKAGE_LOCATION.json',S/'control/PACKAGE_LOCATION.json')
(S/'control/ANALYSIS_MANIFEST.json').write_text(json.dumps({name:sha(S/'control'/name) for name in helpers},indent=2)+'\n')
(S/'REPRODUCTION.md').write_text('''# 最小复现与只读重算

canonical包保存code/source/build/native/weights及冻结参数，原主Git未写入。Python为`/home/hank/envs/adaptive-online-rl-v1/bin/python`，WSL为Ubuntu-Research-Verify，用户hank。PACKAGE_LOCATION指定canonical路径。

已完成同父zero/prior/repeat实测。完整关键raw、dense motion、trace、receipts及输出可重新核验；普通中间raw已在原核验完成后报告化，不能声称所有候选均可重新raw复验。

数据重算（不仿真，但会更新派生JSON）：从control依次运行`analyze_overnight.py`、`analyze_validation.py`、`analyze_mechanisms.py`、`actuation_evidence.py`。它们读取numpy/raw/json并写派生报告，不训练或调用plant。重算前应保留最终交付副本，或另设独立分析输出，不能把晚于deadline的重算当本次交付。verify_package会核验来源与实际资源，但09:30历史绝对deadline过后不应期待final时限PASS；final文件是本次实际关闭证据。

原physics启动命令由control/LAUNCH_*完整记录；runner在code/overnight_runner.py。launch/runner保留本次绝对时限与attempt账，不应覆盖旧目录或删除截止保护后重跑。本包已STOP，未来物理复现需另行授权、独立新目录/新时间预算合同、原模型与零调整复现；不能将现有结果当新unseen验证或续跑冻结搜索。

CODE_MANIFEST保护执行源码与复用文件；control/ANALYSIS_MANIFEST另列分析/绘图脚本。初始Git/复用源hash与晚捕获主工作区字节证据的边界见PACKAGE_VERIFICATION，不混称完整t0镜像。
''')
r.update(status='COMPLETE',registered_campaign_finished=True,scientific_global_optimum_proven=False,primary_all_registered_motion_conditions_passed=v['primary_pass']==4,all_registered_validation_conditions_classified=v['status']=='COMPLETE',finalized_unix=time.time(),physics_STOP=True)
(S/'EXPLORATION_RESULTS.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
(S/'control/DELIVERY_GENERATION.json').write_text(json.dumps(dict(generated_unix=time.time(),selection_sha256=sha(S/'FROZEN_SELECTION.json'),validation_sha256=sha(S/'VALIDATION_RESULTS.json'),primary_pass=v['primary_pass'],secondary_pass=v['secondary_pass'],registered_primary_denominator=4),indent=2)+'\n')
print('FINAL_MATERIALS_UPDATED',len(ledger['records']),v['status'])
