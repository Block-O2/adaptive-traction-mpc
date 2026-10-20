from research_common import *
import shutil
def md(name,body): (OUT/name).write_text(body.strip()+'\n')
def table(headers,rows):
 return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n'
def n(x):return f'{x:.4f}'
def main():
 m=load(OUT/'MOTION_BURDEN_AUDIT.json');e=load(OUT/'NEURAL_Q_EVALUATION.json');d=load(OUT/'DATASET_AUDIT.json');tr=load(OUT/'TRAINING_MANIFEST.json');c=load(OUT/'MODEL_AND_FEATURE_CONTRACT.json');pr=load(OUT/'PREREGISTERED_PROTOCOL.json')
 motionrows=[];phaserows=[];sensrows=[];events=[];total=0
 for pair in m['pairs']:
  audits=[load(OUT/'motion_series'/f"{pair['package']}_{pair[k]}_AUDIT.json") for k in ['B_id','M2_id']];b,a=audits;total+=sum(r['quality']['native_samples'] for r in audits)
  def val(r,k,met='p95_abs',fil='raw'):return r['actual_human'][fil]['full'][k][met][1]
  motionrows.append([pair['B_id'],n(pair['J_F_delta_N_s']),n(val(b,'velocity_deg_s','max_abs')),n(val(a,'velocity_deg_s','max_abs')),n(val(b,'acceleration_deg_s2')),n(val(a,'acceleration_deg_s2')),n(val(a,'jerk_deg_s3')-val(b,'jerk_deg_s3')),n(pair['angle_excursion_delta_deg'][1])])
  for ph in ['OUTBOUND','HOLD','RETURN']:
   x=b['actual_human']['raw']['phases'][ph];y=a['actual_human']['raw']['phases'][ph]
   phaserows.append([pair['B_id'],ph,n(y['velocity_deg_s']['p95_abs'][1]-x['velocity_deg_s']['p95_abs'][1]),n(y['acceleration_deg_s2']['p95_abs'][1]-x['acceleration_deg_s2']['p95_abs'][1]),n(y['jerk_deg_s3']['p95_abs'][1]-x['jerk_deg_s3']['p95_abs'][1])])
  sensrows.append([pair['B_id']]+[n(val(a,'acceleration_deg_s2',fil=fil)-val(b,'acceleration_deg_s2',fil=fil)) for fil in ['raw','savgol_5','savgol_21']])
  for r in audits:
   peak=max(r['actual_human']['raw']['peak_events']['jerk_deg_s3'],key=lambda x:abs(x['value']));events.append([r['id'],peak['joint'],n(peak['time_s']),peak['phase'],n(peak['value']),peak['within_1ms_edge']])
 md('MOTION_BURDEN_AUDIT.md',f'''# 真实人体运动负担审计

结论 **SUPPORTED**：在这八组已完成的配对仿真中，M2 的真实 knee 运动速度与加速度负担相对 B 上升。并非所有关节、所有 jerk 指标都恶化；可接受性 **UNRESOLVED**，临床舒适度 **NOT_EVALUABLE**。接触 moment integral 不是 momentum，本结论来自真实 dq 的重新计算。

## 数据、信号与方法

复用两包各四组完整 B/M2 物理 trace，共16条轨迹、{total:,}个 TASK native 节点。无新增物理 rollout 或 host run。每条 native qpos/qvel 列通过共同物理时间节点与 `evaluation_only_human_state_rad_rad_s` 对应，映射误差小于1e-8 rad/rad·s⁻¹。每条审计保存列索引、节点数、间隔范围及原文件SHA256。原生步长约0.25ms。使用原 `summary.task.phase_transitions` 物理时间分 OUTBOUND/HOLD/RETURN；导数跨交接计算，不在阶段边界重置。

主要速度取真实 native dq；加速度=`numpy.gradient(dq,time,edge_order=2)`，jerk=同法再次微分。未用 q 低频差分代替真实 dq，也未把 trace 中原有因果加速度估计字段当作真值。原始峰值保留。敏感性：dq 经3阶 Savitzky–Golay、5与21节点窗口（名义1.25/5.25ms）后同法微分。端点一侧导数保留并标识 `within_1ms_edge`；没有为得到改善而删除峰值。均匀 native 节点分位数接近时间分布；保存实际时间供复查。重复 sensor trace 时间节点保留最后边界值，原文件未改，数量与最大缺口在各 quality 字段。

分别报告真实人体、参考 q/dq/ddq、机器人 torque/人体 generalized action、接触 force/moment；参考 jerk 和 force-vector/magnitude rate 是约5ms trace 导数，其间未记录的高速峰值 **NOT_EVALUABLE**。可信真 shank 代表点坐标/几何合同未恢复，shank速度/加速度 **NOT_EVALUABLE**。已有物理 cuff 速度与加速度单独标为 cuff，不能替代人体 shank。

每条 run JSON 给出 max、p95、p99、RMS、mean-abs、三个阶段；force peak、快速变化、moment peak/integral、true-reference RMS/max、clearance与原生完整 safety audit。积分权威口径为原 native scorer；去重后的 sampled interval sum 单独保留，不替代 native J_F。原 scorer保留未提供门限的条件结果，不猜造 ROM/加速度临床阈值。

## 配对完整任务结果

Δ=M2−B；速度 deg/s，加速度 deg/s²，jerk deg/s³，角幅 deg。下表 knee 列来自未滤波 native 真值。

{table(['B运行','ΔJ_F N·s','B max速度','M2 max速度','B p95加速度','M2 p95加速度','Δp95 jerk','Δ真实knee角幅'],motionrows)}

8/8 knee max速度、p95速度、RMS速度、p95加速度和RMS加速度上升；knee max加速度7/8上升。Knee p95 jerk 7/8上升，而 jerk max与p99有混合变化。Hip RMS速度8/8略下降，但加速度p95与RMS8/8上升。不能概括为每个指标都恶化，也不能用下降的单个 jerk peak 宣称整体平顺性改善。

任务目标、原生物理模型、安全规则、waypoints保持原配对条件。完整任务时长差范围约−0.005至+0.065s；真实 knee excursion 增加约1.109至2.834°，同时 true-reference knee RMS代价存在。故本比较是相同任务下的真实行为差异，不能声称实际运动幅度完全相同。没有缩短HOLD、裁剪RETURN或通过幅度归一化掩盖代价。

## 阶段分布

下表为 knee p95差值；完整 hip/knee p99、max、RMS见逐run JSON。

{table(['B运行','阶段','Δp95速度','Δp95加速度','Δp95 jerk'],phaserows)}

## 滤波敏感性

{table(['B运行','raw Δknee p95加速度','5节点 Δ','21节点 Δ'],sensrows)}

Knee速度/加速度主要分布的恶化方向对轻度滤波稳定。Jerk峰值更受离散微分及窗口影响，raw与两个过滤版本均保留。该敏感性是测量分析，未进入模型调参或控制。

## 短时事件与计划交接

每条运行的原始jerk最强事件：

{table(['运行','joint 0hip/1knee','物理秒','阶段','signed jerk','端点1ms内'],events)}

逐run `windows` 保存阶段启停/反向±100ms、实际非零计划每个 receipt 起止±50ms，以及速度符号反转±20ms。反转事件需附近20ms内速度达到0.5deg/s，仅用于避免零速数值抖动形成无限事件，**不是舒适度或安全门限**。窗口包含真实运动、force及rate、moment、tracking与clearance，不仅看selected plan。每个 signal 另存每关节五个最强节点；未自动删去异常。

## 目标优先级判断

第0层：旧原生物理检查通过；实际幅度存在上述差异，临床含义不可推定。第1层：真实 knee 速度与加速度代价得到支持。第2层：力积分收益仍成立，最新四组−6.828%、RETURN贡献85.578%、平均力项99.962%的历史结论未被本包改写。第3层：moment、tracking、clearance代价仍保留。

因此现有M2不能凭力下降被认定为满足新优先级。需预先约定运动负担接受规则及公平幅度口径，并检验低力候选是否可同时降低这些真实运动指标。不能从“原native安全PASS”自动推出“新运动目标已满足”。

来源：两包 REPORT、PAIRED_RESULTS/PAIRED_HOST_RESULTS、EXECUTION_LINEAGE、每条native与sensor trace、原AXES；具体文件/hash在 `motion_series/*_AUDIT.json`。初始派生summary与后续物理phase-clock口径说明保留于 `derived_history`。
''')
 oldpath=Path('/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/docs/value_learning_research_v1/OFFLINE_VALUE_MODEL_COMPARISON.json');old=load(oldpath);hist=load(FROZEN/'TRAINING.json')
 ht=[]
 for k,a in old['selected_models'].items():ht.append([k,n(a['validation_full_action_ranking']['mean_regret_n_s']),n(a['test_full_action_ranking']['mean_regret_n_s']),n(a['test_full_action_ranking']['top1_accuracy']),n(a['test_target_prediction']['RMSE_n_s'])])
 md('HISTORICAL_MLP_RECOVERY.md',f'''# 历史MLP恢复

**CONFIRMED**：至少两条历史线，特征合同、数据与目标版本不同，不能混为同一线性Q对照。

## 原生120D/K3（直接相关）

脚本 `{MATRIX}/code/train_native.py`，feature/candidate `{MATRIX}/code/native_core.py`，物理分支 `{MATRIX}/code/native_data.py`，原DATA与snapshot在output，trace在source/results。checkpoint已恢复：`{FROZEN}/weights.npz` 同时含原linear、Q MLP和G；仅只读Q、未训练G/P。SHA256 `{sha(FROZEN/'weights.npz')}`。

MLP=120→128 ReLU→128 ReLU→1，32,229参数；输入state/history、candidate、carry/count通过联合全连接建模，具有state×plan交互能力。训练seed2026100611，Adam lr0.001、1000 epoch、每20 epoch评估；loss=标准化absolute MSE+10×同状态pair差值MSE，最佳Q epoch760。训练集x mean/std只从train计算，std floor0.02；y std floor10N·s。253 train rows、73 dev rows，136同状态train pairs；row多来自同源分支后续状态，不是独立轨迹数。train来源parent_train_0/1，dev parent_dev_0；排除跨split causal58近重复与名义B轨迹状态。原数据集349行，部分行未进入最终train/dev。原training JSON记录排除项、来源hash、完整history与numpy parity。

原验证结果：linear RMSE {hist['linear_dev']['RMSE']:.6f} N·s、mean regret {hist['linear_dev']['mean_selection_regret']:.6f}、harmful top1 {hist['linear_dev']['harmful_top1']}；MLP RMSE {hist['mlp_dev']['RMSE']:.6f}、mean regret {hist['mlp_dev']['mean_selection_regret']:.6f}、harmful top1 {hist['mlp_dev']['harmful_top1']}。两者5个same-state dev groups含两个零spread组。选择按dev regret再RMSE，故selected_Q=linear；不是因为MLP缺乏交互结构，也不是证明所有神经网络必然差。此历史选择没有独立test gate。

线性native120D模型只做标准化后的线性回归，**没有交叉特征**；当前固定mask/候选排序确为g(s)+h(p)。历史MLP的结构有交互，原验证决策成绩不足以取代linear。

## 更早96D cost-to-go研究

脚本位于 `adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/scripts/value_learning_v1/value_models.py`、`train_value_models.py`、`value_dataset.py`。96D输入包含estimated state/belief、reference、task、continuation与candidate target/delta；MLP=96→32 tanh→32 tanh→1，NumPy CPU、batch256、Adam lr0.003、weight_decay0.001、最多500 epochs、validation MSE patience50。x scale低于1e-6置1，y std floor1。三个seed20260930/31/32；full与1.5s short分别训练。模型按validation **full-return regret**再target RMSE选择，test不参与选择。

train conditions：low_ordinary_early/late、balanced_middle、hip_ordinary、sync_120；validation：knee_ordinary、balanced_high；test：elevated_start、variable_start_120。按physical condition/session划分，同状态candidate留在一起。所有历史条件此前已探索，不能称完全未见科学数据。

{table(['模型','val FULL regret','test FULL regret','test top1','test target RMSE'],ht)}

96D full选择ridge_full_100.0：其validation regret0.6842优于MLP full1.2585。**但short MLP的test FULL regret2.1946优于short ridge8.5562**；不能笼统宣称历史MLP全面更差。short模型的test target RMSE与full RMSE目标不同，不能跨行直接比较。96D ridge具有显式progress/span/beta/phase×candidate_delta交叉项；它不是当前native120D可加线性Q。96D MLP同样具有联合交互。

96D checkpoint保留在原docs/models及Windows `learning_research_v1_evidence/models`；feature合同不兼容120D，不能无定义补零后纳入本轮相同candidate评分。直接离线对照B使用兼容的历史120D MLP。96D实际plan-selection/pilot evidence见 `ONLINE_POLICY_IMPROVEMENT_PILOT.json`；本轮没有重跑旧pilot，没有将cost prediction或ranking成绩等同于host执行收益。

来源原比较JSON `{oldpath}` SHA256 `{sha(oldpath)}`；原120D TRAINING SHA256 `{sha(FROZEN/'TRAINING.json')}`。本轮完整source hashes见保护快照及manifest。
''')
 md('DATASET_AUDIT.md',f'''# Neural Q 数据审计

状态 **EXPLORATORY_SUFFICIENT_FOR_BOUNDED_PROTOTYPE**。存在真实同状态、多候选remaining J_F，不是只有已执行单计划的监督；规模不足以建立独立泛化与motion qualification。

原freeze DATASET：349×120，253train、73dev，SHA256 `{sha(FROZEN/'DATASET.npz')}`。本轮从原 *_DATA.json 恢复branch-start row，**不把其后续相邻value_rows扩增成独立状态**。使用80条候选分支：train47（8完整snapshot、2父轨迹）、validation16（3snapshot、1父轨迹）、test17（2snapshot、1历史诊断父轨迹）。候选分支与完整来源轨迹整体隔离；按causal58 round4排除later-split重复snapshot的全部候选。Cross-split causal58 overlap=0；同snapshot的state/history/carry/count特征一致。原parent_train_0/1重复RETURN因都在train未拆分。验证初始snapshot被整体剔除，烟测outside split；具体排除保存，不按结果删差样本。

原branches由CPU quiescent Linux fork复制完整address-space、物理状态、scheduler/governor/interface、随机状态；branch manifest包含完整状态hash。原BRANCH_GATE确认zero-branch full trace equality、parent before/after digest equal、child waitpid joined。新包仅复用旧trace及receipts，未将JSON hash manifest当作可恢复实时状态，也未以q/dq重建counterfactual。新增物理rollout=0。

监督任务为 `native-certified-committed-K3-suffix-v1`：候选完整合法masked K3后缀由一致的原生B规划/执行规则实现。remaining J_F=完整任务native integral−fork时prefix integral，并核验等于第一个value_row；输入candidate slot重新按counts mask核验。**这不是仅当前slot后立即zero-B，也不是持续Neural-Q replanning policy的已验证价值**。故可训练plan-conditioned剩余cost，但不能直接把offline regret差称为完整host policy收益。

所有回归/比较分支均native-valid COMPLETE。原始失败数量{d['failed_count']}条保留于 BRANCH_LABELS.json，未变成低成本标签。该筛选是完成与安全资格，原全部source/hash、失败metric和排除原因均保留。

训练只用原生120D：causal55 observation + previous3 + maskedcandidate30 + maskedcarry30 + counts2。真q/dq、未来force与clearance仅作label/审计；无真值部署输入。labels另导出sampled真实速度、加速度、jerk、force peak、remaining moment、tracking、clearance、原native safety、完成、剩余时长与真实幅度。旧分支trace约5ms，辅助motion峰值不具备0.25ms native保证；新host-motion audit有dense native真值，但这些host轨迹没有同状态完整counterfactual候选标签，**未伪造候选价值**。

原生MLP128×128的32,229参数相对该规模过大；本轮限定16×16与32×32，只能作为EXPLORATORY。chosen32×32共{tr['chosen_model']['parameters']}参数。不能仅凭训练误差评价决策成功。

Test v1_committed_attribution 是已公开历史诊断来源，曾用于fixed-versus-committed归因；它未参与本轮拟合/模型选择，但并非新Human、前瞻性未见数据或独立人口样本。Old Q也已有train/development来源暴露。64个test候选pair来自2个状态，不是64个独立实验。临床舒适度、跨Human泛化、在线个体化均NOT_EVALUABLE。

模型训练前 protocol固定，按validation regret再RMSE选择；选定后才计算三模型的test对照，不根据test重训。Manifest保存全部source IDs、split、normalization、config、model hashes。训练数据 `{OUT}/NEURAL_DATASET.npz` SHA256 `{sha(OUT/'NEURAL_DATASET.npz')}`。

主要补数条件：保留能够合法fork/恢复的完整原生执行状态，在独立来源轨迹上覆盖相同合法计划、不同状态下真实最优候选变化，并保存dense运动/force与所有安全结果；原生B continuation语义应先明确冻结。当前仅hash快照不足以新启动counterfactual，本轮不重建plant冒充原Human session。
''')
 evalrows=[]
 for name,a in e['models'].items():
  for split in ['validation','test']:
   b=a[split];evalrows.append([name,split,b['same_state_groups'],n(b['RMSE_N_s']),n(b['MAE_N_s']),n(b['pairwise_accuracy']),n(b['top1_accuracy']),n(b['mean_selection_regret_N_s'])])
 detail=[]
 for name,a in e['models'].items():
  for g in a['test']['groups']:detail.append([name,g['snapshot'][:10],g['candidate_count'],n(g['actual_spread_N_s']),g['selected_id'],n(g['regret_N_s'])])
 latency=table(['模型','batch','p50 ms','p95 ms','score所需bytes','loaded bundle bytes'],[[r['model'],r['batch_size'],n(r['p50_ms']),n(r['CPU_numpy_ms']['p95_abs']),r['scorer_required_array_bytes'],r['resident_loaded_bundle_bytes']] for r in e['inference']])
 md('NEURAL_Q_EVALUATION.md',f'''# Neural Q离线对照

终态 **EXPLORATORY**；当前测试实际决策优势 **FAIL / NOT_DEMONSTRATED**，进入host条件 **NOT_READY**。保留两个权重及负结果，没有test驱动追加搜索。

A=冻结native120D linear/fixed masked ranking；B=同一冻结NPZ中的历史120D MLP；C=joint120D→32ReLU→32ReLU→1 challenger。候选、observed合法mask、实际完整snapshot与分支标签、测试预算完全相同。尚未形成受运动资格约束的可部署选择器。

## 训练与选择

固定seed{pr['seed']}、CPU single thread、Adam lr0.001/weight_decay0.001、600epochs；loss=normalized absolute MSE+10×同完整snapshot的pair-difference MSE；每10epochs按validation regret再RMSE保存最佳。仅比较16×16/32×32，未训练G/P与辅助head。两者validation regret0；32×32的RMSE13.1024优于16×16的16.1091，故选32×32。Best epoch {tr['chosen_model']['selected_epoch']}；Torch/NumPy inference parity误差{tr['chosen_model']['torch_numpy_max_error_N_s']:.6f}N·s。所选weight SHA256 `{c['sha256']}`。

## 预测、排序与真实selection regret

{table(['模型','split','状态组','RMSE N·s','MAE N·s','pair准确率','top1','mean regret N·s'],evalrows)}

Test2个state、17个候选、64个非tie pair，不能当作64个独立样本。Challenger mean regret9.9306，冻结linear1.6207，差值+8.3099N·s；历史MLP16.6014。新模型比历史MLP部分改善，但没有超过旧固定排序。Top1同为0.5不能掩盖错误选择的实际cost差。

{table(['模型','snapshot','候选数','真实cost spread','所选计划','regret N·s'],detail)}

OUTBOUND状态真实best为candidate6，而challenger选candidate7产生19.8612N·s regret；RETURN选candidate1为正确。当前两个state的candidate集合/issued mask不同，不能把这种跨phase best身份变化当作“同固定候选集下最优随state变化”的充分证明；相关能力仍UNRESOLVED。冻结方案在RETURN确实最优，保持排序是正确行为。

## state×plan能力与有效学习必须分开

固定±0.2合成候选、固定mask/carry/count，仅交换真实state/history的结构probe：linear candidate score差随state的范围约2.27e-13N·s；历史MLP40.063、新MLP18.019N·s。支持两MLP存在交互表达且本checkpoint有非加性响应；这些合成feature组合没有真实rollout标签，**不是决策优势证据**。没有把ranking inversion数量作为成功指标。

## 真实运动与其他物理代价

每个test candidate导出remaining任务的sampled运动速度/加速度/jerk、force peak、moment、true-reference tracking、clearance、实际幅度/时长、原native qualification；每模型的选择附同样labels。没有把所有代价随意加权为reward。原native安全与完成有效，但不能自动承认额外运动代价可接受。

预注册B-relative ratios=1.0/1.1/1.25的敏感性筛选同时比较真实速度/加速度/jerk max,p95,p99：1.0和1.1下三个模型都回到两个state的B候选；1.25下OUTBOUND选candidate8、RETURN仍B，三者相同。ratio是描述性分析，不是临床阈值、也不是“+25%自动可接受”。筛选使用真实未来label，是**outcome-oracle analysis**，不可部署，未参与模型选择。它提示严格B负担约束下当前候选空间的力收益选择有限，但不足以证明空间根本无解。

本轮并未改善force/真实平顺性权衡。候选安全硬mask不能用future真值实时构造，未来要有可信的前瞻性筛选/辅助预测合同。样本不足以训练并验证motion辅助head，所以未这样做。

## 推理、内存和特征可用性

{latency}

单线程NumPy、9候选batch、20warmup/300 measurements。Loaded old bundle含G及未使用Q权重；score所需bytes才是可抽取部署权重大小。上述是CPU评分微基准，未包括native candidate构造、admission、bridge、lifecycle、host contention，不能推断40ms路径资格。现有native TASK已可提供120D feature，新scorer只读Nx120、不导入plant、无actuation/update；mask与安全仍是原caller责任。

## 失败归因与下一轮条件

主要瓶颈SUPPORTED为数据有效覆盖小（8train snapshot、3validation、2test且历史暴露），而非已证明容量不足；增加容量尚无依据。Observed排名失败保留；labels有合法历史完整fork证据，但committed suffix监督与重复host replanning不同，泛化及continuation-policy mismatch UNRESOLVED。候选空间与motion资格同样有瓶颈迹象，不能将其全部归咎MLP。

下一轮先补充独立来源、完整state分支、dense运动标签及同固定候选下真实state-dependent最优的离线数据；冻结B参考与平顺性接受口径，再按预注册模型选择比较。只有独立test的regret优于linear、任务/幅度/时间/原native安全公平、运动负担规则满足、feature/scorer parity与影子评分链完整、原FAST资格轴单独记录后，才考虑新的host-clock工作包。本轮没有启动或激活新控制器。
''')
 md('REPORT.md',f'''# iHEAR Lab — Motion-Aware Neural Q v1

终态：**EXPLORATORY_TRAINED / OFFLINE_ADVANTAGE_NOT_DEMONSTRATED / HOST_NOT_READY**。阶段A真实运动审计完成；阶段B两条历史MLP恢复完成；阶段C合法历史分支数据审计完成；阶段D两个小型challenger完成并仅用validation选择；阶段E直接对照完成，保留负结果。Package verification是证据/保护检查，不是科学或实时资格。

旧M2的力收益伴随真实knee速度/加速度负担上升：八组配对knee max速度、p95速度、p95加速度与RMS加速度均更高，轻度滤波不改变主要方向；真实knee excursion亦增加1.109–2.834°。Hip速度RMS略降、jerk结果混合。不能从moment integral推断momentum，也不能宣称临床不适。

新32×32 joint Neural Q具有state×plan交互，但在2个历史诊断测试state上的mean selection regret **9.9306N·s**，冻结linear为 **1.6207N·s**，历史128×128 MLP为 **16.6014N·s**。新模型没有显示超过固定排序的实际优势。80条合法branch-start row（47/16/17）来自8/3/2snapshot与2/1/1父轨迹，不能按行数宣称大数据或跨Human泛化。

## 执行边界与交付

独立Linux目录 `{OUT}`；Windows交付副本 `C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_neural_q_motion_v1`。Python `/home/hank/envs/adaptive-online-rl-v1/bin/python`，与用户指定一致。Wall cap2.5h，新增离线rollout **0/12**，host-clock run **0**，无新persistent Human session、无plant重建、无G/P训练、无online adaptation。全部训练CPU单线程；无重型物理实验。

主要文件：MOTION_BURDEN_AUDIT.md/json及16条dense派生series/逐run审计；HISTORICAL_MLP_RECOVERY.md；DATASET_AUDIT.md/json与BRANCH_LABELS.json；TRAINING_MANIFEST.json与NEURAL_DATASET.npz；NEURAL_Q_EVALUATION.md/json；MODEL_AND_FEATURE_CONTRACT.json；两个models权重、offline_score.py；PREREGISTERED_PROTOCOL.json、保护快照、PACKAGE_VERIFICATION.json。所选模型 `{c['model']}` SHA256 `{c['sha256']}`。原Q SHA256 `{c['frozen_original_Q_sha256']}`，不变。

只增加本研究目录中的代码、数据派生与报告；原B/controller/commissioning、40ms bridge、100ms lifecycle、admission、causal ownership、native安全、carry/fallback与全部旧权重/结果未修改。未进行Git stage/commit/push/reset/branch变更；Git保护与历史hash核验见PACKAGE_VERIFICATION。原FAST未正式资格化，旧R2/strict55失败继续保留。

## 最终八问

1. **旧M2是否真的让人体运动更猛烈？SUPPORTED（限定指标）**：真实knee速度、加速度分布更高；jerk和hip表现混合。不能升级为普遍或临床结论。真实shank代表点与临床舒适性NOT_EVALUABLE。
2. **force收益是否符合新的目标优先级？UNRESOLVED/尚不能接受为整体成功**：第2层force收益成立，但第1层knee运动代价及第0层实际幅度差需先处理；原native安全PASS不等价于新平顺性目标满足。没有把所有正代价自动视作可接受。
3. **历史MLP当时表现如何，为何最终linear？CONFIRMED**：native120D MLP dev regret0.851245、RMSE11.21944，linear regret0、RMSE8.523668，所以按dev规则选linear。早期96D short MLP有优于ridge的test FULL regret，不能笼统说MLP必然差；早期ridge含显式交互，当前native linear没有。
4. **训练数据是否支持state-conditioned candidate ranking？SUPPORTED（探索性）**：真实同完整state多个候选、actual remaining cost、fork恢复证据存在；80rows仅13个snapshot与少量来源，独立泛化与同固定候选跨state变优证据不足。按来源/轨迹隔离，cross-split近重复为0。
5. **新Q比固定排序有实际优势？CONFIRMED（此样本负结果）**：未显示。Mean regret9.9306 vs1.6207，pairwise accuracy0.90625 vs0.953125，top1均0.5；不能用交互probe或validation loss称成功。
6. **是否改善force与平顺性权衡？UNRESOLVED / NOT_DEMONSTRATED**：B-relative future-label敏感性下三模型落到相同计划；不存在已验证可部署的smoothness gate。无法宣称更佳权衡。
7. **主要瓶颈是容量、数据还是计划空间？SUPPORTED：有效独立数据覆盖不足；UNRESOLVED：计划空间与continuation价值合同**。当前更大历史网络并未更好，容量不足未被证明。Motion约束下可选获益计划有限，不能宣称空间无解。
8. **具备下一轮原生host-clock验证条件？CONFIRMED：本challenger尚不具备**。先补独立来源的合法完整state分支及dense运动标签，冻结B-relative接受口径并完成直接优于linear的离线决策验证。保留接口与EXPLORATORY权重供复用；不启动下一包。

## 验证与负结果

源数据合法COMPLETE筛选、同snapshot feature equality、cross-split causal58 overlap=0、K3 mask重构、remaining integral与value_row闭合、Torch/NumPy parity、有限输入输出与错误输入拒绝、native q/dq映射、native时间严格增加、16run/8pair完整性、原Q identity与旧数据hash、Git保护、进程退出全部在独立验证脚本检查。原始失败DATA保留，历史坏结果未重写。两个容量候选及完整validation histories全部导出；未根据test再训练。

方法限制包括有限已暴露Human仿真、候选/phase mask变化、host commissioning差异、sampled force与branch辅助运动label分辨率、finite-difference jerk端点敏感性，以及committed suffix监督不等于host反复replanning policy价值。Observed host收益的原RETURN/平均力描述性归因保留，未重新作因果证明。

STOP：完成导出、校验、进程退出和Git保护检查后停止，不自动启动下一工作包。唯一建议下一步：另行有界补充独立完整state的离线候选数据与dense运动标签，先解决资格与排序证据。
''')
 save('HISTORICAL_RECOVERY_EVIDENCE.json',{'native_training':str(FROZEN/'TRAINING.json'),'native_training_sha256':sha(FROZEN/'TRAINING.json'),'native_checkpoint_sha256':sha(FROZEN/'weights.npz'),'historical96_comparison':str(oldpath),'historical96_comparison_sha256':sha(oldpath),'historical96_selected_metrics':{k:{'val_regret':a['validation_full_action_ranking']['mean_regret_n_s'],'test_regret':a['test_full_action_ranking']['mean_regret_n_s']} for k,a in old['selected_models'].items()}})
 # Standard static scientific plot, read-only derived results.
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,ax=plt.subplots(1,3,figsize=(12,4));xx=np.arange(8)
 for axis,k,title in zip(ax,['velocity_deg_s','acceleration_deg_s2','jerk_deg_s3'],['Knee maximum velocity (deg/s)','Knee p95 acceleration (deg/s²)','Knee p95 jerk (deg/s³)']):
  bv=[];mv=[]
  for p in m['pairs']:
   b=load(OUT/'motion_series'/f"{p['package']}_{p['B_id']}_AUDIT.json");a=load(OUT/'motion_series'/f"{p['package']}_{p['M2_id']}_AUDIT.json");met='max_abs' if k=='velocity_deg_s' else 'p95_abs';bv.append(b['actual_human']['raw']['full'][k][met][1]);mv.append(a['actual_human']['raw']['full'][k][met][1])
  axis.plot(xx,bv,'o-',label='B');axis.plot(xx,mv,'s-',label='M2');axis.set_title(title,fontsize=10);axis.set_xlabel('Historical paired case');axis.set_xticks(xx,[str(i+1) for i in xx]);axis.grid(alpha=.25);axis.legend()
 fig.suptitle('Native true motion: eight recorded B/M2 pairs; unfiltered');fig.tight_layout();fig.savefig(OUT/'MOTION_COMPARISON.png',dpi=160);plt.close(fig)
 print('REPORTS_WRITTEN')
if __name__=='__main__':main()
