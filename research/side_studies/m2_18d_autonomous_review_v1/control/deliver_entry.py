"""Install new analysis-only scripts, finish diagnostics and close the package."""
from pathlib import Path
import shutil,json,hashlib,subprocess,sys,time
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1');L=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
assert (P/'SEQUENCE_DECISION.json').exists(),'Wait for research sequence to exit first'
frozen=dict(read('EXECUTION_CODE_MANIFEST.json')['files']);frozen.update(read('ORCHESTRATION_AND_ANALYSIS_MANIFEST.json')['files'])
for f in (L/'control').glob('*.py'):
 target=P/'control'/f.name;rel=str(target.relative_to(P))
 if rel in frozen:assert sha(f)==frozen[rel] and sha(target)==frozen[rel],('FROZEN_CONTROL_CHANGE',rel)
 else:shutil.copy2(f,target)
def run(n,*args):subprocess.run([sys.executable,'-B',str(P/'control'/n),*args],cwd=P,check=True)
historical=P/'control/historical_recompute.py';assert 'control/historical_recompute.py' not in frozen
shutil.copy2(P.parent/'m2_18d_baseline_qualification_v1/control/historical_recompute.py',historical)
for n in ['parameter_representation_audit.py','historical_compatibility.py','historical_recompute.py','waypoint_recheck.py','causal_features.py','future_contract.py']:run(n)
groups=[g for g in ['reproduction','N2','development','U1','U2','U3'] if (P/(g+'_DONE.json')).exists()]
for g in groups:
 assert read('audit/INDEPENDENT_'+g+'.json')['status']=='PASS'
 run('diagnostic.py',g);run('tracking_chain.py',g)
run('intent_execution_audit.py');run('candidate_diagnosis.py');run('terminal_contract_diagnostic.py')
(P/'audit/ENGINEERING_EVENTS.json').write_text(json.dumps(dict(rows=[dict(stage='before physical START',event='Windows directory is a review mirror, git command could not find the actual WSL repository; switched to documented canonical WSL main and Side Studies without modifying Git.'),dict(stage='before physical START',event='Sandbox denied WSL enumeration; approved WSL execution used for authorized isolated study.'),dict(stage='analysis',event='Supplemental analysis and orchestration manifests explicitly distinguish original pre-physics execution closure from later diagnostic scripts. No scientific thresholds or raw data changed.')],physics_implementation_failure=False),indent=2,ensure_ascii=False)+'\n')
run('summarize.py')
(P/'MINIMAL_NEXT_STUDY.md').write_text('''# 下一阶段最小研究设计（本轮不执行）

核心问题：能否先把18D中相对独立的RETURN降力能力冻结为更保守的协调方法，并定位OUTBOUND终末响应缺口，而不是继续给每个状态调参。

第一步只做表示合同：增加Side Study的phase-local零意图身份。若某phase的全部位置/速度偏置与native residual为零，必须走原B原调用路径；当前RichFreePlanner只在整向量为零时短路，RETURN参数非零时OUTBOUND全零仍可能重新_evaluate，不能未经测试就声称等价。该改变需零phase数学/调用身份测试和完整新物理B等价检查，仍不改变原B控制模块。

机制臂事前固定为B、原冻结18D、RETURN-only 18D，后者OUTBOUND严格原B，RETURN参数与两个plateau原样。同一个已暴露N2合法活父状态完整配对；RETURN-only一次确定性重复。它只是下一实验候选，不是本轮新方法或物理结果。现有phase积分提示RETURN保留较大收益，不能把分phase加和预测冒充真实完整闭环执行。

若开发门通过，冻结RETURN-only，再从两个或三个本轮未执行的合法prefix条件串行完整验证；不得按验证更换参数。预算预留：开发父+四子约5 START，新prefix每个父+B/E/候选约4 START，总量约13–17；额外失败停止门预先写定，禁止消耗验证预算开发搜索。所有原task/safety/motion/receipt门不变，完整JF包括prefix。再用历史失败V1–V4的明确来源补适用范围，不能只选择容易状态。

若RETURN-only也不稳定，则保持诊断性结论，优先研究接近单关节goal时的边界连续意图与原native末段制动/闭环响应。只有被原证书接纳、实际motion通过且有新prefix证据，才进入第二轮18D+Waypoint联合优化。Waypoint平顺性作为独立目标，不作为force代理。Q-learning此时只准备schema与区间credit assignment，不训练。

本轮完成后STOP；该文档不是自动启动下一包的授权或结果。\n''')
rows=read('EXPERIMENT_RESULTS.json')['rows'];n2=[r for r in rows if r['group']=='N2'];table='\n'.join(f"|{r['arm']}|{r['phase_cost']['phases']['OUTBOUND']['J_F_N_s']:.9f}|{r['phase_cost']['phases']['HOLD']['J_F_N_s']:.9f}|{r['phase_cost']['phases']['RETURN']['J_F_N_s']:.9f}|{r['full_duration_s']:.6f}|{'PASS' if r['absolute_safety'] else 'FAIL'}|{r['receipt']}|" for r in n2)
with (P/'REPORT.md').open('a') as f:
 f.write('''\n## 8. 相位积分、边界结构与停止理由

|N2臂|OUTBOUND JF|HOLD JF|RETURN JF|完整TASK s|绝对安全|causal receipt|
|---|---:|---:|---:|---:|---|---|
'''+table+'''\n
N2原E与C的末段结构见MECHANISM_FINDINGS.md：在hip已到goal、knee尚未到goal时，额外协调意图被原范围门拒绝，原B继续在改变后的状态上选目标、通过速度与终末时长。C去除显式去程速度偏置后，下一native膝通过速度反而从约8.862增至10.036°/s；全程issued膝加速度峰下降，实际膝峰却上升。它支持继续研究目标饱和/末段停止几何与闭环响应，不能唯一归因于任一分量。参考C2与certificate PASS并不自动保证逐状态motion非劣等。

![N2完整物理比较](figures/N2_full.png)

已按预注册有限分支完成或触发停止门，因此未为填满3–4小时目标继续低信息量physics。实际耗时另见PACKAGE_VERIFICATION；四小时是绝对上限，不将提前结束伪称达到时长目标。未触发的新prefix没有消耗，也没有宣称其验证通过。失败记录与未见验证状态均保留。
''')
run('closeout.py')
