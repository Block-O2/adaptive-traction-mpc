"""Final Chinese answers; run after all finite physical queues and audits finish."""
from pathlib import Path
import json,time,datetime
P=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def write(n,s):(P/n).write_text(s.strip()+'\n')
A=read('ACTIVATION.json');S=read('analysis/RESULT_SUMMARY.json');C=read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json');rr=[json.loads(f.read_text()) for f in (P/'attempts').glob('*_RESULT.json')];complete=[r for r in rr if r['complete']];qualified=[r for r in complete if r['qualified']];same=[r for r in qualified if r['id'].startswith(('DEV_','FACT_'))];best=min(same,key=lambda r:r['JF']);old=next(r for r in rr if r['id']=='DEV_BEST');baseline=next(r for r in rr if r['id']=='DEV_B');elapsed=time.time()-A['t0_unix'];tz=datetime.timezone(datetime.timedelta(hours=8));start=datetime.datetime.fromtimestamp(A['t0_unix'],tz).isoformat();deadline=datetime.datetime.fromtimestamp(A['hard_stop_unix'],tz).isoformat();partials=[r for r in rr if not r['complete']];fails=[r for r in complete if not r['qualified']];dF=best['JF']-old['JF'];dM=best['JM']-old['JM'];local=S['local_unseen'];locked=S['locked'];locked_summary='；'.join(f"{g['group']}：完整候选{len(g['rows'])}、合格{sum(r['qualified'] for r in g['rows'])}" for g in locked)
newval=next((g for g in locked if g['group']=='VAL_C'),None);newvaltxt='NOT_RUN' if newval is None else '；'.join(f"{r['id']} {'PASS' if r['qualified'] else 'FAIL'}，JF={r['JF']:.6f}、JM={r['JM']:.6f}" for r in newval['rows'])
report=f'''# iHEAR Lab — Constraint Geometry & Learning Integration v4

状态：**STOP**。ACTIVATION `{A['id']}`。北京时间开始{start}，原硬截止{deadline}；报告生成时已用{elapsed/60:.2f}分钟，精确终态时间见END.json。未耗满十小时，不自动下一轮。

**主要结果：双端点的点态等价和局部解析导数成立，但尚不能提供完整采样间/实际actuator保护，因此未替换原guard。传统分支模型对六个预登记未见局部点预测6/6吻合；没有建立Learning或优化效率收益。权限消融另发现合格的force/moment取舍，独立prefix结果单列。**

## 数值参照

|同一开发条件身份|完整原门|JF N·s|JM Nm·s|
|---|---|---:|---:|
'''
for tag in ['DEV_B','DEV_H150','DEV_OLD_STRONG','DEV_BEST','FACT_BEST_L1_D0']:
 r=next((r for r in rr if r['id']==tag),None)
 if r and r['complete']:report+=f"|{tag}|{'PASS' if r['qualified'] else 'FAIL'}|{r['JF']:.9f}|{r['JM']:.9f}|\n"
historical=read('../representation_execution_v3/attempts/MATCH_JOINT_FIT_RESULT.json')
report+=f"|历史v3完整18D联合近似（本轮未新重复）|{'PASS' if historical['qualified'] else 'FAIL'}|{historical['JF']:.9f}|{historical['JM']:.9f}|\n"
report+=f'''
同开发条件新最佳为`{best['id']}`：相对原最佳ΔJF={dF:.9f} N·s、ΔJM={dM:.9f} Nm·s。这是本轮固定因子搜索的一个局部点，不是同预算optimizer优势，也不归功于guard或Learning。其他prefix只与各自B比较。

## 十八个问题

1. **实际耗时、规模、终态？** 报告时{elapsed/3600:.3f}小时；物理START/END={C['physical_START']}/{C['physical_END']}，新增native={C['actual_new_native_steps']:,}，dt=.25ms。{len(partials)}个受保护任务partial、{len(fails)}个完整motion失败全部计账；所有START有独立身份/END。END封包后STOP。新物理、失败与继承prefix计数见RESOURCE_AND_ATTEMPT_ACCOUNTING.json，候选支路wall中位数（含partial）{C['physical_wall_median_s']:.2f}s。模型拟合/归档/核算耗时见analysis/FRESH_SERVER_TIMINGS.json。

2. **clearance跨分支真实机制？ CONFIRMED。** 连续非光滑包络`g=smooth−L|axis_z|`的10μs方向差分跨端点，产生大负曲率；原shortfall、加速度box投影、filter/allocator和实际robot torque接续进入Human瞬态。几何不可微、数值曲率、离散模式、饱和与真实运动五层分开。C19原函数和真实原执行均精确复现；不是gap跳变或数千m/s²真实加速度。见CLEARANCE_GEOMETRY_ANALYSIS.md。

3. **双光滑端点保护关系？** **CONFIRMED：同一估计接口几何的点态等价**，2,437个检查点差0、解析导数吻合；竖直轴仍有径向退化。**NOT_ESTABLISHED：闭环安全等价。** 已给出原时域末端条件不能保证5ms间隔的标量反例，并推导条件性全间隔下界；仍缺KV observer误差、最终饱和torque响应误差与可行backup。见DUAL_ENDPOINT_CONSTRAINT_STUDY.md。

4. **哪些替代真正执行？** 双端点只执行离线解析/半空间投影和精确因果输入算术重放，**物理替代NOT_RUN**。实际物理使用原clearance函数，新增诊断返回相同correction；六条历史trace/native/receipt逐项复现。另执行独立L/D compiler因子，不能混同guard替代。见ISOLATED_GUARD_IMPLEMENTATION.md。

5. **与原guard真实运动比较？** 诊断组与原历史逐raw一致，没有新guard的轨迹。六个未见上层微扰在原guard下得到不同motion结果；全部请求时钟与时长未变，实际反馈q/dq可以不同，比较记录没有声称全过程状态相同。权限因子的原生轨迹差另见REPRESENTATION_PERMISSION_ALIGNMENT.md和analysis/CAUSAL_REQUEST_PAIR_COMPARISON.json。

6. **是否减少jerk、拒绝、任务失败？** **未证明新执行处理减少这些指标。** 同父六点3通过/3失败可被传统显式模型预测，原分支失败带仍存在。曲率幅度变化后box饱和使失败点jerk接近平台，不能按曲率下降比例推断运动收益。开发合格率8/12是冻结菜单结果，不是总体失败率。新增compiler失败按原门中止而没有放宽规则。

7. **新的安全/可行性问题？** 因子去掉终点锁产生{len(partials)}个任务partial，原因与原硬安全布尔值逐条保留；不将partial费用排名。所有新增物理沿用原硬安全检查，未发现被隐藏或放宽的违规。原guard局部constraint_satisfied=false与全任务硬安全PASS分开；有限运行不构成全局安全保证。host实时、硬件、临床资格均NOT_TESTED。

8. **JF/JM及其他代价变化？** 同开发条件最佳相对原最佳ΔJF={dF:.9f}、ΔJM={dM:.9f}；原低force最佳不是所有cuff负担同时下降的证明。FULL_RESULTS.csv及每条analysis/branches保留tracking、真实native速度/加速度/jerk、excursion、endpoint、force/moment峰值、clearance与torque信息。原积分、任务时长、HOLD和motion门保持。

9. **真实优化效率、合格率是否提高？ NOT_TESTED。** guard未晋级，P3-B新旧guard同optimizer/同预算复测NOT_RUN。已执行固定候选前瞻资格预测；离线cost-only与branch-aware规则选同一点，但选点记录晚于首个新结果，明确POSTHOC，不能当作前瞻优化实验或两独立臂。不能用预测6/6或一个新低force点声称搜索效率优势。见OPTIMIZATION_IMPACT.md。

10. **旧18D与新表示权限对齐？** 终点锁和时长编译已固定坐标独立2×2执行。终点锁在本modal提议的参考合法性上有直接作用；新时长下限并非所有局部低force点必需，恢复旧H150时长可形成另一取舍。D0恢复时长语义，整个factor8仍不是完整旧18D归一化域；不能将无锁partial写成旧18D方法必然失败。共同运动子族与完整旧/新族等预算效率仍未建立。

11. **Learning是否受益？** **没有独立价值证据。** 数据拟合与解析分支组合已执行，称传统局部线性响应模型；独立Learning辅助对照、网络/残差/value训练NOT_RUN。六点预测吻合不等于排序更准、决策改变或完整合格运动更好。未见prefix正式ABSTAIN，naive transfer诊断结果保留，不能把5条历史同父fork当成少数患者真实适应。

12. **PPO新证据？** 只复用第9次历史causal标量做原函数重放；没有新冻结策略物理、scratch或继续训练。未建立PPO主要受该机制限制，不把PPO失败当物理最优证明，不复用旧rollout到新接口。

13. **跨状态结果？** {locked_summary}。这些是三个冻结合法prefix、同nominal Human，未覆盖其他commissioned参数。新时长候选的独立复核：{newvaltxt}。各状态有自己的B分母；原motion失败与partial保留。见CROSS_STATE_VALIDATION.md。

14. **潜在研究贡献？ SUPPORTED。** 可复核的真实闭环稀疏失败带、精确因果输入重放、解析分支加传统局部响应预测、独立compiler因素与force/moment取舍及合法prefix边界。不是新min/max理论，不是已合格的新guard，亦非广泛Learning优势。

15. **相对已有安全控制方法缺什么？** [非光滑barrier组合](https://par.nsf.gov/servlets/purl/10057932)、[ZOH/不确定性控制](https://arxiv.org/abs/2005.06418)与[近似离散模型的采样安全](https://arxiv.org/abs/2203.11470)已有方法。本系统缺最终actuator层误差/可达集界、采样间不变性与可行backup、广泛状态和患者覆盖；见带原论文链接的RELATED_WORK.md。不能将保留原scorer的LEVEL1仿真结果升级为形式、硬件或临床保证。

16. **下一阶段优先？** 先建立KV observer与最终robot torque→cuff/Human端点响应的可验证下界和采样间backup合同，再决定双端点guard是否晋级；并在匹配compiler权限下评估传统搜索与状态相关motion余量。新增force/moment取舍按独立prefix结果限定。只有显式模型留下可部署决策缺口，再做最小Learning对照，不默认增加PPO episode。见NEXT_RESEARCH_DECISION.md。

17. **长期日志？** 根RESEARCH_DECISION_JOURNAL.md开始/结束append-only，旧前缀SHA核验；详细假设→证据→决策记录在RESEARCH_DECISIONS.jsonl。启动、导出、队列恢复、scheduler注册goal修正、保护快照路径误替换的可逆修复和POSTHOC时间边界均保留。

18. **owned任务与保护审计？** 五个物理job的父/子进程均join、有限队列结束、scorer服务停止；源码/历史SHA、原scorer独立重算与全native receipt归属见PACKAGE_VERIFICATION.json。未commit/push/merge，未改正式历史控制器，未启动Stage2、硬件、扩容或下一轮。精确封包终态见END.json。

## 证据级别

CONFIRMED：点态代数等价、局部解析导数、原函数/原执行重放、预登记六点结果、实际L/D因子和冻结prefix结果。

SUPPORTED：分支数值项与饱和反馈是局部motion失败的重要来源；compiler权限存在可执行性及force/moment取舍。

HYPOTHESIS：采样安全双端点处理能提高一般优化效率；状态相关残差/历史对少数重复患者运动可能有额外价值。

NOT_TESTED / NOT_ESTABLISHED：新guard物理/保护资格、同权限等预算优化优势、独立Learning/PPO增量、跨患者与临床/硬件资格。

![未滤波局部预测与物理结果](figures/LOCAL_BRANCH_VALIDATION.png)

文件导航：[几何](CLEARANCE_GEOMETRY_ANALYSIS.md) · [双端点](DUAL_ENDPOINT_CONSTRAINT_STUDY.md) · [物理](CAUSAL_PHYSICAL_COMPARISON.md) · [优化](OPTIMIZATION_IMPACT.md) · [权限](REPRESENTATION_PERMISSION_ALIGNMENT.md) · [Learning](LEARNING_DECISION_STUDY.md) · [跨状态](CROSS_STATE_VALIDATION.md) · [账本](RESOURCE_AND_ATTEMPT_ACCOUNTING.json)。
'''
write('REPORT.md',report)
write('NEXT_RESEARCH_DECISION.md',f'''# 下一阶段研究决策 — 未自动启动

本轮STOP。先读取本包实际独立prefix结果，再拟定下一份有界合同。

1. 优先补齐采样安全合同：名义KV界面observer的因果误差界、最终饱和robot torque到Human两端点加速度下界、5ms ZOH整个间隔下界与空集backup。单纯把min换成两个smooth Hessian不足以晋级。
2. 保留分支显式诊断；局部六点预测已成立，但域外必须拒绝自信外推。跨prefix的state-conditional参考编译/闭环响应与实际motion余量，比继续拟合已知abs差分更值得收集数据。
3. {best['id']}在开发条件JF={best['JF']:.9f}、JM={best['JM']:.9f}，独立VAL_C结果见REPORT第13项。它是一项力/力矩取舍，不当作跨患者最优。先在相同端点/时长权限、共同运动子族和相同真实物理预算下比较传统18D/新坐标搜索，再决定表示价值。
4. 只有预测→排序→决策→完整合格运动链中的实际缺口得到识别，才开展同信息/预算的Learning增量。PPO不默认长程继续训练；必须冻结接口及on-policy合同。

本轮没有启动以上任何下一轮任务、Stage2、Campaign、服务器扩容或真机。
''')
print('MAIN_REPORT',best['id'],best['JF'],best['JM'],'partial',len(partials),'motion_fail',len(fails))
