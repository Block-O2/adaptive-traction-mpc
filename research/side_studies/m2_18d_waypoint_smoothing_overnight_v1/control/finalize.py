"""Close a no-promotable-winner campaign, verify protections, and mirror review files."""
from pathlib import Path
import os,sys,json,hashlib,time,subprocess,shutil,datetime
P=Path(__file__).resolve().parents[1];L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
sys.path.insert(0,str(P/'control'))
from accounting import main as accounting
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
accounting();ac=read('ATTEMPT_ACCOUNTING.json');assert ac['physical_START']==ac['physical_END'] and not ac['active_owned'],'OWNED_PROCESSES_OR_UNCLOSED_ATTEMPTS'
review=read('SELECTION_REVIEW.json');assert not review['eligible'],'Eligible candidates require frozen independent validation before closeout'
rows=read('ALL_ANALYZED_RESULTS.json')['rows'];complete=[r for r in rows if r['status']=='COMPLETE'];plan=read('RUN_PLAN.json')
put('FROZEN_SELECTION.json',dict(status='NO_NEW_QUALIFIED_WINNER',PRIMARY=None,SECONDARY=None,frozen_unix=time.time(),selection_rule_sha256=sha(P/'RUN_PLAN.json'),development_review_sha256=sha(P/'SELECTION_REVIEW.json'),reason='No new intervention meets the predeclared full-task meaningful force or whole-task motion-improvement gate',historical_18D_not_renamed=True))
put('VALIDATION_RESULTS.json',dict(status='NOT_TRIGGERED_NO_NEW_ELIGIBLE_SELECTION',new_pairs=0,validation_START=0,reserved_STARTs_unused=30,historical_18D_motion_pass=0,historical_18D_denominator=4,no_reselection=True,scope='same-Human development only; deterministic repeats are not new-state validation'))
br=read('BASELINE_REPRODUCTION.json');br.update(status='ARCHIVAL_AND_NEW_PHYSICAL_REPRODUCTION_PASS',new_runs=[dict(id=r['id'],J_F=r['J_F'],motion=r['motion_pass']) for r in complete if r['candidate']['id'] in ['B0','E0']],all_archive_trace_gate_files=[str(f.relative_to(P)) for f in (P/'audit').glob('*_ARCHIVE_GATE.json')]);put('BASELINE_REPRODUCTION.json',br)
history=P/'HISTORICAL_18D_MECHANISM.md';text=history.read_text()
if 'COBYLA' not in text:text+='\n历史生成算法已按原源码核对：`overnight_runner.py`在NATIVE_SCALAR_18 seed附近做18维有界COBYLA，目标为完整J_F/B_J_F，约束为原motion/task/safety比较项；quality配置maxiter=52、rhobeg=0.15、tol=0.015、catol=0，参数在[-1,1]归一化盒内再按原scales映射。它不是平滑目标优化，也不是RL/Q。冻结_063是有限开发搜索中选出的合格候选；预算终止不等于收敛或全局最优。原报告/源码与完整参数分别保存于provenance和HISTORICAL_18D_PARAMETERS.json。\n'
history.write_text(text)
def tablerow(r):
 loc=r.get('local',[]);tv=' / '.join(f"{100*(x['candidate']['TV_v']/x['baseline']['TV_v']-1):+.3f}" for x in loc) or '—'
 return f"|{r['id']}|{r['J_F']:.9f}|{r['full_J_F_delta']:+.9f}|{tv}|{r['full_TV_v_change_percent']:+.4f}|{r['full_jerk_change_percent']:+.4f}|{'PASS' if r['motion_pass'] else 'FAIL'}|"
table='|arm|完整 J_F N·s|相对匹配base ΔJ_F|support TV_v Δ%|完整TV_v Δ%|完整jerk RMS Δ%|原motion|\n|---|---:|---:|---:|---:|---:|---|\n'+'\n'.join(tablerow(r) for r in complete)
new=[r for r in complete if r['candidate']['base']=='E' and r['candidate'].get('changes') and not r['candidate']['id'].endswith('_zero')]
qualified=[r for r in new if r['motion_pass'] and r['safety'] and r['receipt']=='PASS'];best=min(qualified,key=lambda r:r['J_F']) if qualified else None
best_sentence='没有新的合格18D+S结果。' if best is None else f"新18D+S完整合格数值最低为 `{best['id']}`：J_F={best['J_F']:.9f} N·s，相对匹配18D变化{best['full_J_F_delta']:+.9f} N·s，完整velocity TV变化{best['full_TV_v_change_percent']:+.4f}%。这是描述性最小值，不是冻结PRIMARY。"
elapsed=(time.time()-plan['t0_unix'])/3600
report=f'''# iHEAR Lab — 18D + Waypoint smoothing overnight v1

本轮完成历史机制复核、原B/18D精确物理复现、零形状等价、四组有界干预及条件分支复核。没有达到预先冻结的“明确完整降力或保留18D力收益同时改善完整运动”晋级条件，因此PRIMARY/SECONDARY均为null，新合法prefix验证未触发。{best_sentence}

## 历史机制与组合接口

18D原始J_F=1400.697221153 N·s，B=1438.613498467 N·s，差37.916277314 N·s（2.635613%）。本轮两者从相同完整live父状态重新执行，全部trace字段与历史一致。原18参数、RETURN两个差分plateau、scheduler/bridge/current admission/receipt保留。零shape在B与18D均通过116320 native行、5817 receipts及完整trace等价，组合接口合法性在本开发条件有实证。

18D不是单一平滑机制：4–6 s和15–16 s合计贡献约53%的降力，但部分局部TV_a/jerk反而增加；全程moment也增加约7.03%。更早抬髋、降膝与模型重力/弹性需求变化一致，allocator通道变化有执行分量证据。不能把代数分解当独立物理因果中介比例。详见HISTORICAL_18D_MECHANISM、HISTORICAL_WINDOWS和原始来源hash。

## 完整结果

Δ以同一批次、同完整父状态的对应base（B或18D）为准；不同base的平滑形状分别按reference velocity TV设计，不是相同固定处理的纯2×2交互。support不同不做峰值对齐。force为原5ms采样左积分；0.25ms native只用于实际motion及ownership。所有phase和task均完整保存；partial不排名。

{table}

原task/safety/receipt结果、ROM、clearance、tracking、phase积分、moment、逐joint与combined TV_v/speed variation/TV_a/jerk、joint travel/excursion、torque分量及生命周期事件在ALL_ANALYZED_RESULTS、derived和原raw。velocity TV、speed variation、acceleration variation及jerk分别计算，不合并为临床舒适度。

## 科学判断

B+S复现了历史的小幅降力；18D+S的完整结果如表。局部reference与Human运动确实改变，但微小J_F下降不足以产生本轮新赢家。完整运动变化和下游响应必须一起评价，局部更平滑不保证完整更平滑。反向对照、被原速度证书拒绝的18D去程反向候选、所有motion失败和工程失败均保留。

本轮没有证明smoothness是独立原因，也没有证明18D与Waypoint存在明确可推广的互补收益。它也没有排除更广连续协调空间；结论只覆盖注册的两个窗口、固定内部dq/ddq、±0.05°位置偏移及有限条件分支。未进入RL/Q/Neural Q训练。

## 分母、边界与退出

T0=2026-10-17 02:12:56北京时间，实际截至本报告约{elapsed:.2f}小时。8–10小时是目标；在有限研究方向没有新的晋级信号后提前结束，没有为空耗时长继续physics。硬截止13:12:56未触及。物理START={ac['physical_START']}/120、END={ac['physical_END']}；含冷父及全部fork。实际新增native步={ac['actual_new_native_steps']}，继承前缀不重复计新步。30次验证预留未使用；新验证0对，历史18D合法prefix motion仍0/4。

仅PHYSICAL_LEVEL1 / same-Human development。正式Native LEVEL2、host-clock LEVEL3、硬实时、跨患者、真机与临床资格均未获得。原host/strict失败不被scientific模式PASS覆盖。

## 工程事件与保护

分析辅助函数保留旧包名，曾临时覆盖旧v3两份计划并写入四份新分析JSON；在任何physics前发现。两份旧计划从审阅镜像恢复，并与旧EXECUTION_CODE_MANIFEST的SHA逐字节一致；四份新文件移入本包。此事件明确保留于audit/ISOLATION_REPAIR，不声称全程零历史写入。正式B/plant/source语义未改变。另有控制台numpy布尔序列化、预检入口路径和模块名冲突的工程修复，均发生在physics前，不改变科学参数或门限。

源码闭包除了路径迁移保持语义一致；新增控制逻辑只在隔离control/campaign.py。原motion protocol字节一致。完整保护与退出复核见PACKAGE_VERIFICATION；它的PASS只代表审计合同，不代表科学假设成立。未commit/push/merge/reset/stash或删除历史失败。

## 图与复现

![历史共同时间轴](figures/18d_mechanism_timeline.png)

![B干预](figures/B_intervention_comparison.png)

![18D干预](figures/E_intervention_comparison.png)

canonical完整raw位于本WSL研究包source/results；Windows目录为审阅镜像，不伪称复制了全部raw。所有原始trace/native/receipt路径、identity、certificate、配置、START/END和代码hash均可追溯。见REPRODUCTION.md。下一步仅见NEXT_RESEARCH_DECISION，本轮STOP。
'''
(P/'REPORT.md').write_text(report,encoding='utf-8')
diagnostic='''# Force–motion diagnostic

本轮区分三层：reference变化、实际Human变化、完整force结果。新非零多段对象具有独立reference identity及worker/current certificate；逐receipt的q/dq由对象系数独立重建，实际native步唯一归属，command torque匹配。每例support之前与匹配base完全一致的negative control另存。

原allocator代数分解见derived/NEW_DEMAND_DECOMPOSITION.json：gravity、elastic、velocity terms、remainder与allocation geometry投影差精确闭合。remainder包含惯性、tracking、soft-limit、residual及安全修正，不是单独测得的acceleration项。模型beta差另存。模型需求与实测接触力差不同，后者仍受robot/contact及窗口边界响应影响。

实际tracking、command torque的base/position/velocity/allocator/clipping分量和request/activation/splice时序均保存；trace里的allocated_wrench_world是总command wrench，不能称纯allocator输出。原纯allocator输出只来自明确标注的代数重算。局部正负force差面积与完整净差分列，避免把局部低力或小净差误当全程改善。

所有完整候选的逐窗数值在ALL_ANALYZED_RESULTS.json，包含全程、OUTBOUND/HOLD/RETURN、4–6s、15–16s和各注册support。新组合的微小改善、恶化、证书拒绝和motion失败同等保留。无独立smoothness中介操纵，因此因果归因仍有限。
'''
(P/'FORCE_MOTION_DIAGNOSTIC.md').write_text(diagnostic,encoding='utf-8')
(P/'NEXT_RESEARCH_DECISION.md').write_text('''# Next research decision

本轮停止。没有新冻结PRIMARY/SECONDARY，不以同父确定性repeat冒充跨状态验证。

唯一建议：下一包优先以18D历史合法prefix的motion失败为对象，冻结合法配对与原门限，定位reference/allocator/tracking的远期响应；先建立跨prefix运动可靠性，再决定是否扩大平滑自由度。当前两个窗口的微小force信号不足以支持更密waypoint扫描或RL/Q训练。本轮不自动启动下一包。
''',encoding='utf-8')
(P/'REPRODUCTION.md').write_text(f'''# Reproduction

Canonical package: `{P}`. Runtime: `/home/hank/envs/adaptive-online-rl-v1/bin/python -B`; existing MuJoCo/NumPy/SciPy, single numerical thread. Windows mirror omits full raw/source; canonical raw remains under source/results with full native and receipt capture.

Do not rerun this stopped package in place or reset its attempts. Reproduce into a fresh versioned sibling after copying and rebasing the closure, preserving RUN_PLAN scientific criteria and a new explicit time budget. Prepare script is a historical bootstrap and must be adapted to a fresh path; its initial absolute-path-only rebase defect and repair are documented. No setup command here implicitly starts physics.

Completed physical commands: `python -B control/campaign.py` with default STUDY_GROUP=development1; if present, the second batch used STUDY_GROUP=development2. Each complete task arm is an os.fork of the full live parent, not a saved-state replay. The initial and follow-up executable plans and per-START manifest hashes are preserved.

Read-only calculation entries: control/analyze_batch.py, control/decompose_new.py, control/selection_review.py, control/accounting.py. They write only new-package diagnostics; the algebra script blocks mj_step/step1/step2. Original evaluation: code/analyze_matched.py. Safety contract tests: tests/test_certification.py (30 cases). Original runtime source and motion thresholds were preserved; all modifications and final hashes are in CODE_MANIFEST.

J_F uses original full TASK 5ms left quadrature with exact phase clipping. Native dq at0.25ms yields raw acceleration/jerk using original edge_order=2 gradients. Baseline archival trace gates, zero gates, current certificate reconstruction, native ownership and parent invariance have separate artifacts.
''',encoding='utf-8')
before=read('audit/PROTECTION_BEFORE.json');main=Path('/home/hank/coding/adaptive-traction-mpc-learning');git={}
for k,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('staged',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]:
 b=subprocess.check_output(['git','-C',str(main),*args]);git[k]=hashlib.sha256(b).hexdigest()==before['git'][k]['sha256']
now_files={str(f.relative_to(main)):[f.stat().st_size,f.stat().st_mtime_ns] for f in main.rglob('*') if f.is_file() and '.git' not in f.relative_to(main).parts}
source_bad=[n for n,h in before['source_files'].items() if not Path(n).exists() or sha(Path(n))!=h]
old=P.parent/'force_mechanism_waypoint_v3';oldman=json.loads((old/'EXECUTION_CODE_MANIFEST.json').read_text());restored=sha(old/'CANDIDATE_PLAN.json')==oldman['original_plan_sha256'] and sha(old/'EXECUTABLE_PLAN.json')==oldman['executable_plan_sha256']
execution=read('EXECUTION_CODE_MANIFEST.json');execution_bad=[n for n,h in execution['files'].items() if sha(P/n)!=h]
required=['REPORT.md','HISTORICAL_18D_MECHANISM.md','FORCE_MOTION_DIAGNOSTIC.md','INTERVENTION_PROTOCOL.md','EXPLORATION_RESULTS.jsonl','ATTEMPT_ACCOUNTING.json','FROZEN_SELECTION.json','VALIDATION_RESULTS.json','NEXT_RESEARCH_DECISION.md']
checks=dict(git_unchanged=all(git.values()),main_metadata_unchanged=now_files==before['main_files'],historical_source_hashes_unchanged=not source_bad,temporarily_written_historical_plans_restored_hash_exact=restored,execution_manifest_unchanged=not execution_bad,starts_ends_closed=ac['physical_START']==ac['physical_END'],native_steps_exact=ac['native_steps_exact'],owned_physics_zero=not ac['active_owned'],budget_ok=ac['physical_START']<=90,storage_ok=ac['package_bytes']<8*2**30,deadline_ok=time.time()<plan['hard_stop_unix'],required_files=all((P/n).exists() for n in required))
put('PACKAGE_VERIFICATION.json',dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,source_hash_mismatches=source_bad,execution_hash_mismatches=execution_bad,git=git,qualification_scope='package integrity and stop only, not scientific hypothesis or deployment',historical_temporary_write_disclosed=True,closed_unix=time.time(),starting_git=before['git']))
assert all(checks.values()),checks
put('PHYSICS_STOP.json',dict(unix=time.time(),reason='registered bounded study completed, no new eligible winner; validation not triggered'))
put('STATE.json',dict(status='STOP',phase='CLOSEOUT_COMPLETE',physics_START=ac['physical_START'],physics_END=ac['physical_END'],owned_pids=[],next_action='none; no automatic next campaign',elapsed_hours=(time.time()-plan['t0_unix'])/3600))
manifest={str(f.relative_to(P)):dict(sha256=sha(f),bytes=f.stat().st_size) for d in ['source','code','deps','weights','control','tests'] for f in (P/d).rglob('*') if f.is_file() and 'results' not in f.relative_to(P).parts and '__pycache__' not in f.parts}
put('CODE_MANIFEST.json',dict(files=manifest,git_mutation=False,original_execution_manifest='audit/development1_EXECUTION_CODE_MANIFEST.json',final_execution_manifest='EXECUTION_CODE_MANIFEST.json'))
for f in P.iterdir():
 if f.is_file() and f.suffix in ['.md','.json','.jsonl','.txt']:shutil.copy2(f,L/f.name)
for d in ['figures','derived','series','reports','audit','evidence','output','provenance','control','logs']:
 shutil.copytree(P/d,L/d,dirs_exist_ok=True)
put('REVIEW_MIRROR_MANIFEST.json',dict(canonical=str(P),mirror=str(L),full_raw_mirrored=False,files={str(f.relative_to(L)):sha(f) for f in L.rglob('*') if f.is_file()}));shutil.copy2(P/'REVIEW_MIRROR_MANIFEST.json',L/'REVIEW_MIRROR_MANIFEST.json')
print('CLOSED',ac['physical_START'], 'STARTS', 'hours', (time.time()-plan['t0_unix'])/3600)
