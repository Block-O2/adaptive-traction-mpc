"""Evidence-derived Chinese report tables. Does not seal or invent unfinished results."""
from pathlib import Path
import json,math,time,datetime,collections,sys
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');A=json.loads((P/'ACTIVATION.json').read_text())
def read(p,default=None):
 f=P/p;return json.loads(f.read_text()) if f.exists() else default
def put(p,x):
 f=P/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def md(p,s):(P/p).write_text(s.strip()+'\n')
def num(x,n=6):return '—' if x is None else f'{x:.{n}f}'
def norm(x):return math.sqrt(sum(float(v)**2 for v in x))
def table(headers,rows):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(str(v) for v in row)+' |\n' for row in rows)
rows=[json.loads(f.read_text()) for f in sorted((P/'attempts').glob('*_RESULT.json'))];by={r['id']:r for r in rows}
ext={f.stem:json.loads(f.read_text()) for f in (P/'analysis/extended').glob('*.json')};nw={f.stem:json.loads(f.read_text()) for f in (P/'analysis/native_wrench').glob('*.json')}
permission=read('audit/ACTION_PERMISSION_REVIEW.json',{});excluded=set(permission.get('excluded_from_formal_same_domain_comparison',[]))
events=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];account=[]
for start in starts:
 ident=start['id'];end=[r for r in ends if r['id']==ident];metric=None;path=None
 for suffix in ['_DATA.json','_PARTIAL_COMPUTE.json']:
  path='runtime/output/'+ident+suffix;data=read(path)
  if data is not None:metric=data.get('metric',data);break
 steps=None if metric is None else metric.get('actual_new_native_physics_steps');su=read('runtime/source/results/'+ident+'/summary.json',{});child=read('runtime/output/'+ident+'_DATA.json',{}).get('child');fork=0. if child is None else child['physical_time_at_fork'];mpc=su.get('learning_records',[])
 account.append(dict(id=ident,group=start.get('group'),kind=start.get('kind'),category=start.get('category'),START_unix=start['unix'],END_unix=end[-1]['unix'] if end else None,END_count=len(end),exit_code=end[-1].get('returncode') if end else None,actual_new_native_steps=steps,complete=by.get(ident,{}).get('complete',bool(metric and metric.get('task_valid'))),original_qualified=by.get(ident,{}).get('qualified'),same_domain_formal_eligible=bool(by.get(ident,{}).get('qualified') and ident not in excluded),new_MPC_requests=sum(r.get('request_time_s',-1)>=fork-1e-9 for r in mpc),archived_MPC_requests=len(mpc),physical_wall_s=by.get(ident,{}).get('wall_s',end[-1].get('wall_seconds') if end else None),START_reporting_pid=start.get('pid'),actual_child_metadata=child,metric_path=path,parent_hash_equal=end[-1].get('parent_hash_equal') if end else None))
native=sum(r['actual_new_native_steps'] or 0 for r in account);closed=all(r['END_count']==1 and r['actual_new_native_steps'] is not None for r in account);groups={}
for group in sorted(set(r['group'] for r in account)):
 use=[r for r in account if r['group']==group];groups[group]=dict(START=len(use),END=sum(r['END_count'] for r in use),new_native_steps=sum(r['actual_new_native_steps'] or 0 for r in use),candidate_complete=sum(r['complete'] for r in use if r['kind']!='LEGAL_COLD_PARENT'),candidate_original_qualified=sum(r['original_qualified'] is True for r in use),same_domain_eligible=sum(r['same_domain_formal_eligible'] for r in use))
resources=[]
for f in (P/'logs').glob('*_RESOURCES.jsonl'):
 resources += [json.loads(s) for s in f.read_text().splitlines()]
accounting=dict(status='ALL_STARTED_ATTEMPTS_ACCOUNTED' if closed else 'RUNNING_OR_REVIEW_REQUIRED',activation=A,updated_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),physical_START=len(starts),physical_END=len(ends),all_starts_accounted=closed,actual_new_native_steps=native,actual_new_simulation_seconds=native*.00025,native_dt_s=.00025,original_motion_failure_ids=[r['id'] for r in rows if r['complete'] and not r['qualified']],partial_failure_ids=[r['id'] for r in rows if not r['complete']],exploratory_permission_exclusions=sorted(excluded),groups=groups,attempts=account,minimum_available_ram_gib=min((r['available_ram_bytes']/2**30 for r in resources),default=None),minimum_free_disk_gib=min((r['disk_free_bytes']/2**30 for r in resources),default=None),new_PPO_training_episodes=0,new_PPO_optimizer_updates=0,notes=['Each cold parent and each full-state fork consumes one true START; zero-physics import/analysis failures separately documented.','Full JF includes inherited TASK prefix; native counts charge only new integration, not each archived inherited row.','Parent wall includes child waits; do not sum parent/child wall as disjoint compute.','Three H samples from one branch are correlated labels, not three independent episodes or patients.','Actor evaluations and ordinary MPC requests are separate from new PPO training episodes.','The 8/16-label critic models reuse real training branches. Do not sum model training-row counts as additional physical attempts.'])
accounting['historical_PPO_sunk_cost']=read('audit/HISTORICAL_PPO_COST.json')
accounting['shared_historical_baseline_context']=read('audit/HISTORICAL_SHARED_BASELINE_COST.json')
accounting['posthoc_query_sensitivity_job']=read('audit/CRITIC_FEATURE_SENSITIVITY_RUN_IDENTITY.json')
accounting['critic_fit_resources']=[dict(model=f.stem,training_physical_attempts=d['training_physical_attempts'],captured_horizon_rows=d['captured_horizon_rows'],fitted_rows=d['fitted_rows'],fit_resources=d.get('fit_resources')) for f in sorted((P/'models').glob('CRITIC_*_FROZEN.json')) for d in [json.loads(f.read_text())]]
accounting['optimization_proxy_and_budget_audit']=read('analysis/optimization/OPT01_POSTHOC_AUDIT.json')
accounting['exact_validation_action_aliases']=read('analysis/LOCKED_VALIDATION_SELECTION.json',{}).get('configs',[])
core_buckets={'CORE01','SMOOTH01','ANT01','HANDOFF01','STRICT01','BRANCH02'}
for item in account:item['budget_bucket']='LOCKED_VALIDATION' if item['group'].startswith('VAL') or item['group']=='PPOREPAIRVAL' else 'CORE' if item['group'] in core_buckets else 'ADAPTIVE'
accounting['budget_buckets']={name:dict(physical_START=sum(r['budget_bucket']==name for r in account),actual_new_native_steps=sum(r['actual_new_native_steps'] or 0 for r in account if r['budget_bucket']==name)) for name in ['CORE','ADAPTIVE','LOCKED_VALIDATION']}
accounting['budget_bucket_scope']='Group-level research roles including cold-parent and anchor cost. Fixed optimizer arms remain12+12; supplementary adaptive tests and pre-frozen supplementary validation never rewrite primary checkpoints.'
frozen_actor_ids={'PPOCHECK_FROZEN_MEAN','PPOCHECK_FROZEN_PLUS_RULE','VAL01_PPO_MEAN','VAL01_PPO_RULE','VAL03_PPO_MEAN','VAL03_PPO_RULE','PPOREPAIR01_TIME0','PPOREPAIR01_TIME0_RULE','PPOREPAIRVAL_MEAN','PPOREPAIRVAL_RULE','PPOREPAIRVAL_TIME0','PPOREPAIRVAL_TIME0_RULE'}
for item in account:item['frozen_actor_or_explicit_hybrid']=item['id'] in frozen_actor_ids
accounting['RL_decision_accounting']=dict(new_on_policy_training_decisions=0,new_PPO_gradient_updates=0,frozen_global_mean_and_explicit_hybrid_task_evaluations=sum(r['frozen_actor_or_explicit_hybrid'] for r in account),actor_per_slot_state_feedback_inferences=0,scope='Original actor is a global Gaussian mean/std; frozen tanh(mean) or explicit hybrid vector is set once per candidate task, then the original rolling planner executes it. Config-fixed action applications are not new on-policy training decisions or arbitrary per-slot actor inferences.')

put('RESOURCE_AND_ATTEMPT_ACCOUNTING.json',accounting)
dev_groups={'CORE01','SMOOTH01','ANT01','HANDOFF01','STRICT01','OPT01','PPOCHECK','BRANCH02','COMPOSE01'}
dev=[r for r in rows if r['id'].split('_')[0] in dev_groups and r['qualified'] and r['id'] not in excluded and r['id'] in ext];base=ext.get('CORE01_BEST');bestjf=min(dev,key=lambda r:r['JF']) if dev else None;bestjerk=min(dev,key=lambda r:norm(ext[r['id']]['native_motion']['jerk_deg_s3']['rms'])) if dev else None
def metrics_table(use):
 output=[]
 for r in use:
  d=ext.get(r['id']);w=nw.get(r['id']);jr='—' if not d else '/'.join(num(x,2) for x in d['native_motion']['jerk_deg_s3']['rms']);fr=None if not d else d['wrench']['force']['norm_rate']['rms'];nfr=None if not w else w['force']['norm_rate']['rms']
  output.append([r['id'],'PASS' if r['qualified'] else 'FAIL','EXPLORATORY' if r['id'] in excluded else 'original domain',num(r.get('JF')),num(r.get('JM')),jr,num(fr,4),num(nfr,4)])
 return table(['身份','原门','权限','JF N·s','JM Nm·s','native jerk RMS 髋/膝 °/s³','200Hz ‖F‖ rate RMS N/s','4kHz ‖F‖ rate RMS N/s'],output)
core=[r for r in rows if r['id'].split('_')[0] in ['CORE01','SMOOTH01','ANT01','HANDOFF01','STRICT01','PPOCHECK','COMPOSE01'] and r['complete']]
md('SMOOTHNESS_INTERVENTION_COMPARISON.md','# 平顺性干预实际比较\n\n参考、Human和wrench分别评价，失败及权限不齐探索不进入正式同权限排名。原未滤波native导数与原motion门保持。\n\n'+metrics_table(core)+'\n\n首版逐关节参考优化与未裁剪强固定相对参数的权限问题见[审查](audit/ACTION_PERMISSION_REVIEW.json)。STRICT01重新在原共同速度坐标和原相对坐标[-1,1]内执行；不能把原证书通过当成相同动作权限。\n\n逐项RMS/峰值/分位数、tracking、excursion、overshoot、phase积分和各门余量见analysis/extended。实际参考提议、接受、激活及原始schedule见analysis/execution与runtime/source/results/*/summary.json。\n\n![正式同权限实际运动、施力与积分权衡](figures/02_VALID_PHYSICAL_TRADEOFF.png)\n\n![交接参考、实际torque与未滤波native jerk](figures/03_HANDOFF_RAW_MECHANISM.png)')
md('WRENCH_FLUCTUATION_ANALYSIS.md','# cuff施力波动与采样\n\n原JF/JM始终为原5ms TASK左积分，不用新采样口径制造积分收益。早期组只有200Hz actual cuff stream，不据此解析亚毫秒瞬态。后续原native step已经计算Human-site实际接口wrench，评价日志只复制其缓存，不另调用observe/refresh/step；4kHz流必须与原5ms重合点逐分量吻合。它是仿真真实接口wrench，不是新增硬件传感器能力。\n\n'+metrics_table([r for r in rows if r['id'] in nw and r['id'].split('_')[0] in dev_groups])+'\n\nforce/moment向量与norm的峰值、RMS、变化率、TV、100ms分箱线性趋势残差以及phase统计分别保留在analysis/native_wrench和analysis/extended。趋势残差只是附加描述量，不替代raw、原motion或原积分。高低采样率的TV和导数不直接混为同口径排名。audit/NATIVE_WRENCH_UPDATE_CADENCE.json核对原step_native逐步post-refresh更新，三条代表轨迹相邻native wrench均真实变化；audit/NATIVE_WRENCH_LOGGING_PHYSICAL_IDENTITY.json验证新增日志前后B/BEST的所有原物理和参考字段精确一致。4kHz记录不等于硬件测量带宽或连续sub-step重建。')
branch=[r for r in rows if r['id'].split('_')[0] in ['ANT01','STRICT01','BRANCH02'] and r['complete']]
md('CLEARANCE_BRANCH_MECHANISM.md','# 分支机制与信息价值\n\n复用既有v3/v4机制，不重新证明abs尖点。本轮正式原guard及阈值完全保持。C19原反例及已知避让已复现。首版通用分支启发式在较早RETURN1改target而消除了较晚的C19冲击；这不等于已准确预报该晚期冲击。强固定TASK原guard未激活、原有限仿真门PASS时的小JF变化也不等于平顺性增益。\n\n'+metrics_table(branch)+'\n\nBRANCH02以另一已知训练反例与不读分支信息的±0.02度盲移位区分“预测信息有用”和“任意扰动绕开窄失败带”。训练09只作失败压力点，绝不冒称PPO部署策略。执行前菜单、参数、实际激活与曲率/饱和日志见analysis/execution及analysis/extended。数学点态等价、采样间安全、最终torque响应与替代guard晋级仍是独立问题，本轮替代guard NOT_RUN。')
md('ANTICIPATORY_COORDINATION.md','# 提前协调：几何分支与交接分开\n\n显式几何模型只读当前估计、已签参考、scheduler几何及当前tracking误差，预测5ms栅格的端点模板距离；0.1s误差衰减和2e-4 axis不确定带是排序启发式，不是安全证书。STRICT01在原相对模式box内裁剪候选，实际变化可能低于0.02度。是否改变选择、是否激活、是否改善真实Human/wrench分别报告。\n\n交接感知方案依据原receipt确认的q保持而dq非零现象，提前降低原通过速度坐标。强固定十个固定邻近窗口覆盖约83%原始jerk平方和；这是描述性窗口重合，不是已识别独占中介比例。原guard在该强固定TASK内未激活。\n\n'+metrics_table([r for r in rows if r['id'].split('_')[0] in ['HANDOFF01','STRICT01'] and r['complete']])+'\n\n源代码与前瞻菜单见source/v5_bounded_anticipatory.py；实际签发、torque和native证据不经过事后滤波。对照与跨prefix资格见冻结验证和最终REPORT，不能从单个C19恢复推广为一般模型收益。')
branch_audit=read('analysis/BRANCH_BLIND_COUNTERFACTUAL_AUDIT.json')
if branch_audit:
 with (P/'CLEARANCE_BRANCH_MECHANISM.md').open('a') as f:
  f.write('\n\nCONFIRMED：两处已知失败均被模型和两个预登记盲扰动恢复，模型与相应盲移位的实际reference、torque、wrench和native Human逐字段完全一致。分支信息改变了候选，但其独立恢复价值尚未建立。两处base-risk预报时间与原实际stencil事件相差约0.085秒和5.16秒；C19的恢复不能解释为准确预报晚期冲击。原失败点guard各有一次active与constraint-unsatisfied记录，实际原物理安全门与原motion门分别判定，不能因此声称形式闭环安全已建立。详见analysis/BRANCH_BLIND_COUNTERFACTUAL_AUDIT.json。\n\n![原guard事件附近的实际force/moment与native jerk](figures/05_BRANCH_ACTUAL_FORCE_PULSE.png)\n')
tails=[read(str(f.relative_to(P))) for f in sorted((P/'analysis/tail').glob('*.json'))];tailtable=[]
for g in tails:
 for r in g['comparisons']:
  h=str(float(r['horizon_s']));available=[x for x in g['rows'] if x['complete'] and h in x['horizons']];unmasked=min(available,key=lambda x:x['horizons'][h]['short_JF']);lookup={x['id']:x for x in g['rows']};oracle=lookup[r['actual_full_tail_choice']]
  regret=num(unmasked['JF']-oracle['JF']) if unmasked['qualified'] else '主选择FAIL'
  jm=num(oracle['JM']-unmasked['JM']) if unmasked['qualified'] else '主选择FAIL'
  tailtable.append([g['group'],r['horizon_s'],r['qualified_candidates'],unmasked['id']+(' PASS' if unmasked['qualified'] else ' FAIL'),r['actual_full_tail_choice'],regret,jm,r['short_choice'],num(r['spearman'],3)])
md('SHORT_HORIZON_VS_FULL_TAIL.md','# 同状态真实rolling续跑\n\n每个合法中间状态完整地址空间fork。候选只改变当前一个决策，随后恢复同一原B rolling/replan；原admission、拒绝、fallback和HOLD继续生效。后续planner类恢复与每个实际selected plan核验，不能把整段承诺轨迹当rolling标签。B为原B控制；ZERO为当前一个T-family决策的零额外modal，二者不同。gamma=1，原左积分验证C_short+V_actual_tail=C_remaining。\n\n'+table(['父状态','H秒','原门合格数','无未来mask short选择','actual-tail合格参照','无mask short完整JF regret N·s','oracle−short JM Nm·s','事后合格集short','事后合格集Spearman'],tailtable)+'\n\n无mask short对所有完整候选按实际近期费用选择，其未来motion失败必须保留；事后合格集short及相关系数只是资格条件诊断，不能替代主选择。C1触发训练时两个原始菜单全合格，因此门控不依赖未来失败mask。完整tail是离线诊断参照，不是实时预测器或全局最优oracle。该诊断针对近期JF排名，不能直接推出原MPC综合目标普遍短视。三种H来自同一条分支，不能算独立重复。TAILRESCUE01是TAILOT已暴露失败的同条件重放／微移位菜单，不是新增独立test父状态，也不进入冻结Critic训练；它的合格完整参照只限该五候选菜单。\n\n![短期差值到完整尾部差值](figures/04_ACTUAL_ROLLING_TAIL_GAP.png)\n\nC1去/回两对候选的累计费用差在约4.53/4.17秒后进入最终差值的5%或0.005N·s容差内。RETURN的1秒short已恢复该菜单的完整最优选择；这支持检验延长近期窗口和固定动作等简单解释，不能把效应描述为贯穿整个任务的长期记忆。触发阈值在新物理前定为选择不同且完整合格JF差>0.02N·s，非临床意义阈值。所有失败与partial另列不按小积分获胜。')
late_branch=read('analysis/LATE_BRANCH_POLICY_TAIL_DIAGNOSTIC.json')
if late_branch:
 with (P/'SHORT_HORIZON_VS_FULL_TAIL.md').open('a') as f:
  f.write('\n\n## 补充固定modal后续策略诊断（探索性、无新物理）\n\n')
  for case in late_branch['rows']:
   for c in case['comparisons']:
    f.write(f"{case['case']}，H={c['horizon_s']}秒：无未来资格mask的short选择{c['unmasked_short_choice']}，原资格={c['short_choice_original_qualified']}；完整合格参照选择{c['actual_full_qualified_choice']}，合格short regret={c['qualified_short_regret_N_s']} N·s。\n\n")
  f.write('SUPPORTED：同一初始live parent、完全相同的已记录因果物理/参考prefix与R1请求时刻、仅一个盲移位支持中间状态比较；R1未单独保存完整RAM hash，所以不替代主C1的严格live-state fork。FAIL9在0.5秒short下选到最终motion失败轨迹；两处1秒short都恢复该菜单完整合格最优。固定modal后续策略与主Critic的B后续策略不同，不能混标签；主模型没有因此获得失败概率资格。\n')
critic_files=sorted((P/'analysis').glob('CRITIC_*_RESULTS.json'));critics=[json.loads(f.read_text()) for f in critic_files];ct=[]
for d in critics:
 for r in d['results']:
  lookup={z['id']:z for z in r['rows']};si=r.get('unrestricted_short_choice',r['short_choice']);ci=r.get('unrestricted_critic_choice',r['critic_choice']);fi=r['fixed_training_choice'];sq=lookup[si]['qualified'];cq=lookup[ci]['qualified'];fq=lookup[fi]['qualified'];complete_menu=r.get('all_offered_candidates_have_complete_short_and_tail_labels',False)
  short_gain=num(r.get('unrestricted_actual_JF_improvement_vs_short_N_s')) if complete_menu and sq and cq else '主选择FAIL' if not(sq and cq) else '菜单未完整'
  fixed_gain=num(lookup[fi]['actual_full_remaining_JF']-lookup[ci]['actual_full_remaining_JF']) if complete_menu and cq and fq else '主选择FAIL' if not cq else '未建立'
  ct.append([d['id'],r['group'],r['horizon_s'],si+(' PASS' if sq else ' FAIL'),ci+(' PASS' if cq else ' FAIL'),r['actual_tail_choice'],short_gain,fi+(' PASS' if fq else ' FAIL'),fixed_gain,num(r['tail_JF_RMSE_N_s']),num(r['ranking_spearman'],3)])
gate=read('analysis/CRITIC_GATE_DECISION.json',{});frozen_models=list((P/'models').glob('CRITIC_*_FROZEN.json'));status='ALL_FROZEN_MODEL_TESTS_COMPLETED' if critics and len(critics)==len(frozen_models) else 'TRAINED_FROZEN_PARTIAL_TEST_RESULTS' if critics else 'TRAINED_FROZEN_TEST_PENDING' if frozen_models else 'NOT_RUN_OR_PENDING'
md('CRITIC_STUDY.md','# 长期成本Critic\n\n状态：'+status+'。先以完整C1菜单诊断真实短视，再以小型三lengthscale RBF ensemble预测remaining JF/JM、剩余时间及原motion最差比。H处输入含因果估计、参考、active suffix、governor及接口记忆；不只是q/dq，也不输入未来Human/receipt。固定任务gamma=1，不对MuJoCo反向传播。\n\nfit_only只打开training父状态，保存source/config/weights SHA；test START必须晚于权重冻结。evaluate_only不更新模型。按完整父状态分组，不随机拆同分支horizon。主模型COSTO/COSTR每阶段拟合16条真实候选标签；COSTO8/COSTR8为在test执行前预登记冻结的8条标签次要消融，不能按test后最佳替代主模型。失败不以低积分进入cost训练胜利；failure/safety classifier未建立，ensemble差异也不当校准区间。当前100字段未显式包含完整native累计剂量/历史极值，worst_ratio分量不能作为原全任务motion资格的充分因果预测器。\n\n门控见analysis/CRITIC_GATE_DECISION.json，冻结模型见models/CRITIC_*_FROZEN.json，训练和test群组见对应配置。全候选short与tail已经实际执行时，新增物理节省是0；预测准确不能替代选择收益。\n\n'+table(['模型','test父','H','short','critic','actual tail','critic vs short ΔJF','训练固定动作','critic vs fixed ΔJF','tail RMSE','合格集合排序r（事后）'],ct))
md('CRITIC_DECISION_VALUE.md','# Critic是否具有决策价值\n\n'+table(['模型','test父','H','short','critic','actual tail','critic vs short ΔJF','训练固定动作','critic vs fixed ΔJF','tail RMSE','合格集合排序r（事后）'],ct)+'\n\n主选择使用实测短期费用+冻结Critic，不使用未来资格mask；只有完整观察所有offered候选时才可评价无mask结果。原合格集合内的条件排名另列并明确是事后资格诊断。预测更准但不改变选择，不认定决策价值；改变但真实更差保留负结果。固定训练动作在新test前冻结，用于检验是否更简单的动作库即可解决。所有菜单为独立真实物理全续跑，实际节省尝试NOT_ESTABLISHED/0。本轮C_short与z_H也来自真实分支执行，尚无廉价短期候选状态/成本预测器；Critic尾部排序检验不能直接称实时控制器。')
critic_O_diagnosis=read('analysis/CRITIC_COSTO_HELDOUT_DIAGNOSIS.json')
if critic_O_diagnosis:
 with (P/'CRITIC_DECISION_VALUE.md').open('a') as f:
  f.write('\n\nCONFIRMED：COSTO主模型在TAILOT未改变无mask选择SPEEDP，原motion FAIL；事后合格集合内的排名/收益不能替代此主结果。原加速度峰值门已在H前失败：guard事件发生于决策后0.18秒，H为0.5秒；尾部force成本无法抹去已发生极值。predicted worst_ratio约0.956，actual约1.986。训练只有合格样本，且未显式记录累计运动极值/guard历史。\n\n输入域也变化：train剩余时间恒15.490秒，test为15.505秒；重复的phase/task elapsed字段在训练中为常数，以0.001缩放，15ms偏移带来主要核距离，最近训练RMS距离约2.5。raw tail误差RMSE约1.884 N·s，去菜单共同误差后仍约1.301 N·s，明显大于约0.04 N·s的关键选择差。ensemble分歧约0.07 N·s未校准。SUPPORTED：状态覆盖、核外推与缺失历史风险共同限制此版本；完整模型修复的盲验证未做，查询敏感性另列，不能把全部误差唯一归因某一字段。只修共同状态费用偏差会在排序中相消，不能当新的决策价值。原模型、选择和test均保持冻结。详见analysis/CRITIC_COSTO_HELDOUT_DIAGNOSIS.json。\n')
sensitivity=read('analysis/CRITIC_FEATURE_SENSITIVITY.json')
if sensitivity:
 for doc in ['CRITIC_STUDY.md','CRITIC_DECISION_VALUE.md']:
  with (P/doc).open('a') as f:f.write('\n\n已暴露test的查询敏感性诊断：训练常量clock字段置训练均值后，主出程最近训练距离约2.527→1.372，tail RMSE约1.884→1.547、去共同误差RMSE约1.301→0.965，但主选择仍SPEEDP且motion FAIL；处理所有训练近恒定字段也未改变选择。确认时钟影响算法距离，但不足以修复决策；未重训或改主模型/原test。完整风险状态修复和新盲验证仍NOT_TESTED，见[查询敏感性](CRITIC_FEATURE_SENSITIVITY.md)。\n')
opt=read('analysis/optimization/OPT01_MATCHED_BUDGET.json');optlines='NOT_RUN_OR_PENDING。'
if opt:
 out=[]
 for arm,rr in opt['arms'].items():
  for n in [4,8,12]:
   use=rr[:n];valid=[r for r in use if r['qualified']];best=min(valid,key=lambda r:r['score']) if valid else None
   out.append([arm,n,len(valid),sum(r.get('new_native_steps') or 0 for r in use),None if best is None else best['id'],num(None if best is None else best['score']),num(None if best is None else best['JF']),num(None if best is None else best['JM'])])
 optlines=table(['方法','真实attempt检查点','合格数','新增native','最佳身份','S','JF','JM'],out)
md('OPTIMIZATION_COMPARISON.md','# 传统上层优化与真实预算\n\n'+optlines+'\n\nPATTERN/BO在同一四维固定计划子族[O_pass,R_pass,O_time,R_time]∈[-1,1]比较，每臂12次真实尝试，失败和partial照计。共享初始强固定与HANDOFF历史起点选择另账；两臂仅消费自身优化反馈。代理查询、拟合与既有历史不是免费物理尝试，也不替代native计数。S=.65组合raw jerk RMS比+.35实测200Hz force-norm变化率RMS比+.004ΔJF+.004ΔJM；原门与同权限先通过。分量与Pareto取舍仍单列，不用S宣称所有指标同时改善。动态参考策略与固定计划的策略族不同，不把它们当相同搜索空间效率对照。两种新优化均从历史强固定与本轮Handoff证据出发，12次是增量预算，不能与历史scratchPPO64直接比较总样本效率；历史v2共285 START/20,093,240 native含PPO72 START，是背景总量，不能全部归因所选baseline或与PPO子集相加。')
composition=read('analysis/PHASE_COMPOSITION_MODEL.json')
if composition:
 with (P/'OPTIMIZATION_COMPARISON.md').open('a') as f:
  f.write('\n\n## 池化历史的相位组合：独立适应性分支\n\n')
  f.write(f"模型使用{composition['source_history_count']}条已完成合格modal历史；源Handoff7 START和OPT27 START共34次已花物理尝试，不能说新组合从零只花一次。两臂固定12次结论保持。HOLD后近似重置使RETURN代价/jerk对OUTBOUND历史变化很小；这只是当前nominal Human与原HOLD下的经验结构，非普遍安全或动力学分离定理。\n\n")
  for i,proposal in enumerate(composition['selected_proposals'],1):
   ident=f'COMPOSE01_PAIR{i:02d}';r=by.get(ident);pred=proposal['prediction']
   f.write(f"{ident}：来源OUTBOUND/HOLD={proposal['original_OUTBOUND_and_HOLD']}，RETURN={proposal['original_RETURN']}；目标={proposal.get('selection_objective','PRIMARY_S')}，预测JF={pred['JF']:.9f}、JM={pred['JM']:.9f}。")
   if r:f.write(f"实际原门={'PASS' if r['qualified'] else 'FAIL'}，JF={r['JF']:.9f}、JM={r['JM']:.9f}；预测差(actual−pred)为{r['JF']-pred['JF']:.3g} N·s／{r['JM']-pred['JM']:.3g} Nm·s。\n\n")
   else:f.write('实际结果尚未完成，不作收益结论。\n\n')
  f.write('质量前沿Q移除S中的JF/JM标量惩罚，按预先登记的归一Q增益>=0.005、预测JF/JM相对强固定增幅<=1%筛选，原资格一律不改。这一候选可改善实际jerk/wrench而提高JF，不能替代S最优结论；模型源hash、完整parts与预报见analysis/PHASE_COMPOSITION_MODEL.json。\n')
md('MOTION_FORCE_MOMENT_TRADEOFF.md','# 运动、力、力矩取舍\n\n'+metrics_table([r for r in dev if r['id'].split('_')[0] in ['HANDOFF01','STRICT01','OPT01','PPOCHECK','COMPOSE01']])+'\n\n原门PASS只表示该仿真工程合同合格；更低JF不自动表示更低JM、更小jerk、所有关节tracking或患者舒适度更好。阶段积分、各项最差余量及overshoot见完整extended JSON。权限不齐探索和原motion失败均不参加正式低成本排名。')
pporows=[r for r in rows if r['id'].startswith('PPOCHECK_') or r['id'].startswith('PPOREPAIR')]
ppostatus=[]
for r in pporows:
 mm=[e['modal'] for e in r.get('execution',[]) if e.get('modal')];ppostatus.append([r['id'],sum(m['status']=='ACCEPTED' for m in mm),sum(m['status']=='REJECTED' for m in mm)])
md('PPO_FROZEN_EXECUTION_MECHANISM.md','# 冻结PPO、执行权限与目标区别\n\n'+metrics_table(pporows)+'\n\n'+table(['身份','实际接受modal数','拒绝modal数'],ppostatus)+'\n\nCONFIRMED：原PPO每任务一次高层向量决策，部署动作是checkpoint64的tanh(mean)，不是训练最佳采样。历史72 START=64训练+4均值评价+3anchor+1cold parent，5,033,780新增native和约7935.69秒group wall属于历史投入；本轮新PPO训练为0。原合格奖励只包含5*tanh((base JF−actual JF)/5)，未奖励门内平顺性或JM，不能按本轮新S目标声称PPO训练样本效率差。\n\nCONFIRMED：冻结均值与均值加降速规则两种方案中OUTBOUND四个modal提议均因fixed-duration参考超原速度证书而拒绝，其余五个提议接受。加规则只带来约1.88%/2.30%髋/膝jerk RMS及0.55%force变化率改善，JF增加1.307398 N·s、JM减少0.400918 Nm·s。原guard在两次TASK内均未active。HYPOTHESIS：OUTBOUND负时间参数压缩导致执行权限被证书屏蔽；PPOREPAIR01只将该坐标置零进行有界反事实。\n\n补充修复与独立新prefix最多11 START，动作/条件在任何主VAL前已冻结，物理执行顺序在主验证结束后；不改变PATTERN/BO固定12次或主验证结论。实际状态见analysis/PPO_REPAIR_GATE.json及owned/PPO_REPAIR_QUEUE_END.json。所有修复均是显式混合方法，不称actor已经学会状态反馈机制。原始身份、目标、资源审计见audit/PPO_FROZEN_IDENTITY.json、audit/PPO_OBJECTIVE_AND_INTERFACE_SCOPE.json和audit/HISTORICAL_PPO_COST.json。')
reward_replay=read('audit/PPO_REWARD_BASELINE_AND_REPLAY.json')
if reward_replay:
 with (P/'PPO_FROZEN_EXECUTION_MECHANISM.md').open('a') as f:f.write('\n\nCONFIRMED：实际历史reward anchor是PPO_SCRATCH_STRONG（legacy2，JF1400.089728），不是原B1436.456498。64条原on-policy reward重放最大误差约4.44e−16；61条合格奖励范围约[-2.9115,1.0768]，无abs(reward)>4.9的饱和样本。由错误原B基准推导的“tanh饱和导致PPO无效”假设被否定；没有门内jerk/JM目标与实际动作证书屏蔽是不同问题，见audit/PPO_REWARD_BASELINE_AND_REPLAY.json。\n')
validation=[r for r in rows if r['id'].startswith('VAL') and r['complete']]
md('CROSS_STATE_VALIDATION.md','# 冻结后独立合法prefix\n\n四组prefix输入在16:54:53 UTC预登记，晚于早期CORE复现结果；当时尚无这些验证条件的执行结果。完整候选与模型随后锁定，再开始VAL物理执行。全部为同一Human；不同prefix不是跨患者泛化。\n\n'+metrics_table(validation)+'\n\n冻结候选身份及首次START先后关系由最终审计核验；验证结果不回流开发选点。')
elapsed=(time.time()-A['t0_unix'])/3600;final='--final' in sys.argv;state='等待最终END封包，精确终态见END.json' if final else 'RUNNING（中间报告，非结束记录）'
summary='当前正式同权限开发最小JF：'+('尚无' if bestjf is None else bestjf['id']+' '+num(bestjf['JF'])+' N·s')+'；最小组合native jerk：'+('尚无' if bestjerk is None else bestjerk['id'])+'。最小JF与最小jerk可以属于不同方案。'
answers=[f'截至报告生成约{elapsed:.3f}小时，真实physical START/END={len(starts)}/{len(ends)}，新增native={native:,}。精确结束时刻、耗时及最终计数以END.json为准。',summary,'200Hz与实际新增4kHz测量分开。完整force/moment峰值、RMS、变化率、TV和局部波动见WRENCH_FLUCTUATION_ANALYSIS；不能由早期5ms数据声称亚毫秒结论。','完整JF/JM与原phase左积分不变；所有方法同时报告motion、tracking和力矩取舍，不按单一JF评全面优劣。','通过速度和bounded target在进入后续区域前改变，实际issued/accepted/activated/receipt/native全链保存；没有事后滤波替代原运动门。','分支信息确实改变过真实候选；首版边界权限问题已隔离，正式增量只看STRICT01与BRANCH02盲对照及冻结prefix。','真实C1的short和actual-tail排序/选择、regret与JM列在SHORT_HORIZON_VS_FULL_TAIL；它是固定B后续策略下的局部证据，不是全局短视定理。','是否训练由完整C1预登记门控决定，实际状态见CRITIC_STUDY及模型冻结文件；不从训练曲线反推必要性。','Critic、short、真实tail与训练固定动作在独立test父上比较；主选择不使用未来资格，实际JF/JM/motion决定是否有效。','本轮全菜单续跑标签和评价未节省真实物理尝试；0/NOT_ESTABLISHED。代理/拟合开销与历史单列。','传统pattern/BO等真实预算比较、简单交接速度规则及固定训练动作用于检验是否已有更简单方案。','已确认原交接q保持/dq非零、原clearance反例的控制冲击、参考与实际运动分离，以及原资格和动作权限是不同轴；逐项证据见专题文件。','独占物理中介、广域分支预测、Critic状态充分性/不确定性校准、跨患者少次适应和临床舒适度仍未建立。','继续投入项以真正独立prefix上的完整合格、最高可得频率wrench及决策增量为门槛，见NEXT_RESEARCH_DECISION。','Learning定位以实际决策缺口为准：不把拟合更准、一次参数采样或历史相消scalar critic当独立学习价值。','长期日志只追加：v4流程回顾、本轮ACTIVATION、必要转折及最终简短总结；旧文本前缀SHA核验，最终记录见audit/JOURNAL_FINAL_AUDIT.json。','当前仍在运行时不宣称owned退出；最终必须核验全部owned scientific PID身份、服务退出与END STOP，无自动下一轮。']
md('REPORT.md','# iHEAR Lab — Smoothness-Aware Control & Long-Horizon Critic v5\n\n状态：'+state+f'。T0北京时间{A["T0_Asia_Shanghai"]}，硬截止{A["deadline_Asia_Shanghai"]}。\n\n'+summary+'\n\n'+''.join(f'{i}. {s}\n\n' for i,s in enumerate(answers,1))+'## 证据边界\n\nCONFIRMED只用于实际raw、原scorer和直接计算复核；SUPPORTED用于有界配对机制；HYPOTHESIS用于未闭合中介与域外解释；NOT_TESTED/NOT_RUN明确表示未实施。SCI仿真资格不提升为host实时、硬件或临床资格。\n\n详细数据：[平顺性](SMOOTHNESS_INTERVENTION_COMPARISON.md) · [wrench](WRENCH_FLUCTUATION_ANALYSIS.md) · [提前协调](ANTICIPATORY_COORDINATION.md) · [真实tail](SHORT_HORIZON_VS_FULL_TAIL.md) · [Critic](CRITIC_DECISION_VALUE.md) · [优化](OPTIMIZATION_COMPARISON.md) · [账本](RESOURCE_AND_ATTEMPT_ACCOUNTING.json)。')
md('NEXT_RESEARCH_DECISION.md','# 下一研究决策\n\n本轮未结束时此文件仅为待审草稿；最终STOP后不得自动启动下一轮。优先确认严格原modal权限内、独立prefix上可重复的实际motion/wrench改善与JF/JM取舍。若Critic不能胜过固定训练动作，优先简单执行感知协调；若有独立状态排序增量，再补可部署z_H预测、失败/不确定性和真实物理节省测试。\n\n新guard替代仍NOT_RUN：点态等价不补齐采样间、observer、最终torque、饱和及backup。无自动PPO长训、Stage2、Campaign、扩容或硬件。跨患者历史学习、独立Q增量若未实际实施则NOT_RUN，不从同Human新prefix推出结论。')
print('REPORT_DRAFT',len(rows),'candidate results',len(starts),'START',len(ends),'END',native,'new native','critic_results',len(critics),flush=True)
