"""Historical raw diagnosis only; writes exclusively to this new package."""
from pathlib import Path
import os,json,sys,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1];Q=P.parent/'m2_18d_baseline_qualification_v1'
def put(n,x):
 def clean(v):
  if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
  if isinstance(v,(list,tuple)):return [clean(x) for x in v]
  if isinstance(v,np.ndarray):return v.tolist()
  if isinstance(v,np.generic):return v.item()
  return v
 (P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False)+'\n')
rows=[]
for g in ['reproduction','N1','N2','N3','N4']:
 arms={}
 for arm in ['B','E']:
  ident=g+'_'+arm;folder=Q/'source/results'/ident
  with np.load(folder/'trace.npz') as z:
   task=z['stage']=='TASK';t=z['time_s'][task];f=np.linalg.norm(z['physical_cuff_force_world_n'][task],axis=1);jf=float(f[:-1]@np.diff(t))
  with np.load(Q/'motion_series'/(ident+'.npz')) as z:
   a=np.rad2deg(z['acceleration_rad_s2']);i=int(np.argmax(abs(a[:,1])));peak=dict(task_s=float(z['time_s'][i]-z['time_s'][0]),value_deg_s2=float(a[i,1]),phase=str(z['phase'][i]))
  report=json.loads((Q/'reports'/(ident+'_MEASURED.json')).read_text());assert abs(jf-report['J_F_N_s'])<1e-8
  arms[arm]=dict(J_F_N_s=jf,knee_acceleration_peak=peak,full_max_abs_acceleration_deg_s2=np.max(abs(a),axis=0))
 rows.append(dict(group=g,arms=arms,gain_percent=100*(arms['B']['J_F_N_s']-arms['E']['J_F_N_s'])/arms['B']['J_F_N_s'],knee_max_ratio=abs(arms['E']['knee_acceleration_peak']['value_deg_s2'])/abs(arms['B']['knee_acceleration_peak']['value_deg_s2'])))
g='N2';ident=g+'_E';summary=json.loads((Q/'source/results'/ident/'summary.json').read_text())
with np.load(Q/'source/results'/ident/'native_reference.npz') as z:
 t=z['data'][:,0];data=z['data'];peak=next(r for r in rows if r['group']=='N2')['arms']['E']['knee_acceleration_peak']['task_s'];mask=abs(t-peak)<.15
 ref=dict(columns=['task_s','qhip','qknee','dqhip','dqknee','ddqhip','ddqknee'],near_peak=data[mask][::20],closest=data[int(np.argmin(abs(t-peak)))])
selected=[]
for r in summary['learning_records']:
 sp=r.get('selected_plan',{});meta=sp.get('execution_screen',{}).get('free_trajectory')
 if meta:selected.append(dict(decision_index=r['decision_index'],keys=list(r),plan=sp,activation=r.get('selected_plan_activated')))
put('audit/HISTORICAL_RAW_RECHECK.json',dict(status='PASS',unix=time.time(),evidence='Historical raw recomputation, zero new physics',rows=rows,N2_issued_reference_near_peak=ref,N2_free_intents=selected,claim='Peak localization and velocity ablation motivate a hypothesis; no unique physical causality inferred.'))
(P/'PRIORITY_AUDIT.md').write_text('''# 优先级审查

|问题|支持证据|重要性|本轮可验证|推进目标|
|---|---|---|---|---|
|1. 18D去程运动资格的状态敏感性|N1–N4全降力；N2膝加速度最大比1.249192>1.10；历史另有0/4|最高，降力不能抵消motion失败|可：N2机制对照、完整新prefix配对|保留降力同时提高运动可靠性|
|2. 位姿偏移与通过速度作用混合|18D含位姿与速度两类参数，参考改变经过闭环；峰值不能单独归因|高，为主问题提供可检验机制|可：仅去除去程速度偏置，保持RETURN及plateau|建立可解释动作表示与后续反馈基础|
|3. Waypoint局部平滑与全程力不一致|前包E_R局部降力被窗口外抵消；E_OR ΔJF=+0.000017610，TV下降0.4602%|中，明确不是新降力里程碑|本轮以历史重核为限，不重新搜索局部窗口|将平顺性作为独立目标|
|4. 方法身份与复现闭包|18参数之外还有RETURN两个plateau；现包开发精确复现|必要前提，已有较完整证据|可：逐字节参数、原B/18D新物理复现|可靠研究与RL数据来源|
|5. 状态准入筛选器/条件校准|当前没有被验证的因果风险预测器；4个prefix不足以训练或设边界|重要但现阶段依据不足|本轮不拟合筛选器；避免看truth作在线选择|未来有界适用范围|

主问题选1，以2的固定消融作机制检验；辅助问题为参考、receipt、native运动的原始可复核诊断。暂不叠加Waypoint：已测收益很小且不解决N2的已知资格瓶颈。不将历史0/4与最新3/4合并或覆盖；集合不同。当前Windows目录是审阅镜像，canonical原始数据来自WSL manifest。\n''')
(P/'SELECTED_IMPROVEMENT.md').write_text('''# 选定改进：OUTBOUND速度偏置归零

原问题：固定18D在同一Human的合法prefix N2完整膝加速度超限；力收益仍在。原18D对共同/差分位姿与终端通过速度同时施加偏置，现有平滑只触及小窗口，不能识别或解决该问题。

机制假设：保留去程姿态协调和全部RETURN参数及plateau，去除去程速度偏置，可能降低后段制动负担且保留姿态带来的力收益。候选仅将零基3、4、13号系数置零。它仍按原B已选target重新求quintic、原认证/bridge/admission/FAST/contact执行；不是直接指定Human运动。该假设可被否证，不能预设速度偏置是原因。

证明设计：原B/18D精确新物理复现；N2同完整活父状态B/E/C/C_repeat，完整原motion与task/safety/receipt和独立raw重算；C若通过再做开发完整C及三个事前冻结的新prefix。N2为已暴露开发状态，重复不增加独立状态数。晋级需每个新prefix合格并保留>=1%对B降力。相对E不足1 N·s或0.1%B的差异不作为明确额外降力里程碑。

首次失败分类：实现或合同错误保存后允许一次有界工程修复；若数学实现正确而motion失败，视为科学假设未成立，最多检验事前定义的全去程偏移减半R，不对各失败prefix补丁。R失败停止物理搜索。

回滚：本轮仅新Side Study，恢复使用冻结E文件即回滚；主仓库与所有历史原件不写入。无架构修改，不训练RL/Q/Neural Q，不commit/push/merge。\n''')
(P/'METHOD_AND_PARAMETER_CONTRACT.md').write_text('''# 方法与参数合同

原B与历史18D公式、完整原向量及RETURN两plateau分别见METHOD_DEFINITION.md、PARAMETER_MAP.json、FROZEN_18D.json。候选CANDIDATE.json与BOUNDED_REPAIR.json是完整候选，各自包含全部18项和plateau，不仅保存差值。

C：free_parameters[3,4,13]=0，其余逐字节数值相同；normalized同索引归零。令e=sin²(πclip(m,0,1)),u=2m−1，原去程速度乘数1+e[x3±x4±x13u]成为1；原native速度仍由当前目标与因果reference state决定，因此不是固定速度，也不保证最终已发reference速度恒定。原姿态公式、RETURN及终点/HOLD保持原规则。

R：仅若C科学假设失败，全OUTBOUND位置/速度9项[0,1,2,3,4,10,11,12,13]乘0.5；RETURN原样。R是新固定策略，不能称冻结18D泛化。

RUN_PLAN在新physics前冻结候选、N2开发与U1/U2/U3验证prefix、gate、最大40 START和T0+4h硬截止。T0=2026-10-17 13:26:19北京时间；最迟16:26:19停止派发，16:46:19结束物理，17:26:19前交付STOP。所有真实attempt串行，live os.fork完整继承隐藏状态；共同prefix进入完整JF，父hash前后不变。

评价：TASK 5ms force向量范数左积分；phase精确区间裁剪；native0.25ms qvel数值导数的全程/phase motion；tracking、moment、ROM、clearance、contact、torque、task/HOLD/goal、source age与receipt/native ownership均由原冻结评价器。原motion协议逐字节一致，raw jerk max仅诊断。失败/partial不排名；旧host实时失败不得被scientific PASS替代。

证据只为PHYSICAL_LEVEL1、同一Human/模型的开发和合法prefix remaining suffix；不是不同患者、正式Native LEVEL2、host-clock LEVEL3、临床结论。数学合同不冒充物理验证。\n''')
print('HISTORY_AUDIT_PASS',[(r['group'],r['knee_max_ratio']) for r in rows])
