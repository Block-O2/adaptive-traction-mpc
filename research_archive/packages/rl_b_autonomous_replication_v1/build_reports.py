"""Render Chinese research deliverables from preserved measured evidence only."""
from common import ROOT,put
from pathlib import Path
import json,time,math,hashlib,statistics
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

def read(p):return json.loads(p.read_text())
def lines(p):return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
def fmt(x,n=3):return 'N/A' if x is None else f'{x:.{n}f}'
def stamp(unix):return datetime.fromtimestamp(unix,ZoneInfo('Asia/Shanghai')).isoformat()
def write(name,s):(ROOT/name).write_text(s.rstrip()+'\n')
def main():
 from replication_analysis import summarize
 result=summarize();cfg=read(ROOT/'PPO_TRAINING_CONFIG.json');ledger=read(ROOT/'LEDGER.json');train=lines(ROOT/'ALL_TRAINING_LOG.jsonl');evaluation=lines(ROOT/'ALL_EVALUATION_LOG.jsonl');metrics=read(ROOT/'audit/ALL_SCIENTIFIC_METRICS.json')['episodes'];lookup={x['run']:x for x in metrics};seeds=result['seeds'];now=time.time();stage2=read(ROOT/'STAGE2_RESULTS.json') if (ROOT/'STAGE2_RESULTS.json').exists() else {'status':'NOT_RUN','reason':'Gate decision pending','training_episodes':0}
 host=lines(ROOT/'audit/HOST_RESOURCE_SAMPLES.jsonl');physwall=sum(x['resource']['wall_s'] for x in train+evaluation);trainwall=sum(x['resource']['wall_s'] for x in train);evalwall=sum(x['resource']['wall_s'] for x in evaluation)
 programs=[]
 for p in (ROOT/'seeds').rglob('runs/*/START.json'):
  end=p.parent/'END.json'
  if end.exists():
   x=read(p);y=read(end);programs.append({'run':str(p.parent.relative_to(ROOT)),'mode':x['arguments']['mode'],'stage':x['arguments']['stage'],'wall_s':y['unix']-x['unix']})
 inner_train_wall=sum(x['wall_s'] for x in programs if x['mode']=='train');inner_eval_wall=sum(x['wall_s'] for x in programs if x['mode']=='evaluate')
 outer=[]
 for p in (ROOT/'audit/guards').rglob('START.json'):
  if not (p.parent/'END.json').exists():continue
  a=read(p);b=read(p.parent/'END.json');cmd=a.get('command',[])
  if '--mode' in cmd and any('replication_run.py' in str(c) for c in cmd):outer.append({'mode':cmd[cmd.index('--mode')+1],'wall_s':b['resources']['wall_s'],'min_RAM_GiB':b['resources']['minimum_available_GiB']})
 trainprogramwall=sum(x['wall_s'] for x in outer if x['mode']=='train');evalprogramwall=sum(x['wall_s'] for x in outer if x['mode']=='evaluate')
 process=[p for x in host for p in x['owned_processes']];resource={'unix':now,'t0_unix':cfg['t0_unix'],'end_unix':now,'elapsed_campaign_wall_s':now-cfg['t0_unix'],'training_physical_wall_s':trainwall,'evaluation_physical_wall_s':evalwall,'training_program_wall_s_including_audit_checkpoint':trainprogramwall,'evaluation_program_wall_s_including_audit_raw_storage':evalprogramwall,'training_inner_runner_wall_s':inner_train_wall,'evaluation_inner_runner_wall_s':inner_eval_wall,'program_wall_includes_module_import_and_outer_guard':True,'training_native_steps':sum(x['native_steps'] for x in train),'evaluation_native_steps':sum(x['native_steps'] for x in evaluation),'training_task_native_steps':sum(x['task_native_steps'] for x in train),'training_RL_decisions':sum(x['decisions'] for x in train),'evaluation_RL_decisions':sum(x['decisions'] for x in evaluation),'training_Adam_updates':ledger['optimizer_steps'],'minimum_available_ram_GiB':min([x['available_ram_bytes']/1024**3 for x in host]+[x['resource']['minimum_available_GiB'] for x in train+evaluation]+[x['min_RAM_GiB'] for x in outer]),'minimum_free_disk_GiB':min((x['disk_free_bytes']/1024**3 for x in host),default=None),'peak_observed_package_GiB':max((x['package_bytes']/1024**3 for x in host),default=None),'peak_observed_owned_process_RSS_MiB':max((x['rss_KiB']/1024 for x in process),default=None),'peak_observed_runner_CPU_pct':max((x['cpu_pct'] for x in process if 'replication_run.py' in x['command']),default=None),'max_simultaneous_physics_envs':1,'CPU_only':True,'instance_changed_or_purchased':False,'sample_native_steps_per_physical_wall_s':ledger['native_steps']/max(1,physwall),'training_RL_decisions_per_program_wall_s':sum(x['decisions'] for x in train)/max(1,trainprogramwall),'training_native_steps_per_program_wall_s':sum(x['native_steps'] for x in train)/max(1,trainprogramwall),'training_mean_program_s_per_episode':trainprogramwall/max(1,len(train)),'physical_wall_note':'Reset/commissioning/recovery/rollout/save time until environment close; independent audits and checkpoint/compression are additionally counted in program wall. No claim of host real-time safety.'}
 put(ROOT/'RESOURCE_USAGE.json',resource)
 controls=[x for x in evaluation if x['kind']=='fixed_legal_plus_one'];baseline=read(ROOT/'BASELINE_REPRODUCTION.json')
 if controls:
  x=controls[0];m=lookup[x['run']];baseline['fixed_legal_control']={'identity':'FIXED_LEGAL_PLUS_ONE_NOT_B_OR_H150','run':x['run'],'success':x['success'],'task_s':x['task_s'],'JF':x['JF'],'JM':x['JM'],'historical_expected_JF':1449.840060953,'historical_expected_JM':98.40661738581369,'historical_expected_task_s':19.03,'historical_force_moment_timing_parity':abs(x['JF']-1449.840060953)<1e-6 and abs(x['JM']-98.40661738581369)<1e-6 and abs(x['task_s']-19.03)<1e-6,'scientific_metrics':m,'no_B_H150_identity_inference':True}
  put(ROOT/'BASELINE_REPRODUCTION.json',baseline)
 fixed=controls[0] if controls else None
 train_table=['|seed|训练成功/集数|RL decisions|native steps（含准备）|PPO epochs|Adam更新|初始冻结|最终冻结|','|---:|---:|---:|---:|---:|---:|---:|---:|']
 for x in seeds:train_table.append(f"|{x['seed']}|{x['training_successes']}/{x['training_episodes']}|{x['RL_decisions']}|{x['native_physics_steps']}|{x['PPO_epochs']}|{x['Adam_updates']}|{x['initial_evaluation_successes']}/{x['initial_evaluation_attempts']}|{x['final_evaluation_successes']}/{x['final_evaluation_attempts']}|")
 evaltable=['|seed / checkpoint|runtime|TASK s|JF N·s|JM Nm·s|tracking RMS °（hip/knee）|5ms jerk RMS °/s³（hip/knee）|','|---|---|---:|---:|---:|---|---|']
 finalrows=[]
 for seed in seeds:
  for x in seed['evaluations']:
   if x['kind']=='fixed_legal_plus_one':continue
   m=x['scientific_metrics'];j=m['native_motion']['jerk_5ms_rms_deg_s3'] if m['native_motion'] else None
   evaltable.append(f"|{seed['seed']} / {x['kind']}|{x['status']}|{x['task_s']:.3f}|{x['JF']:.3f}{'' if x['success'] else ' partial'}|{x['JM']:.3f}{'' if x['success'] else ' partial'}|{[round(v,4) for v in m['tracking_rms_deg']]}|{[round(v,3) for v in j] if j else 'N/A'}|")
   if x['kind']==f"checkpoint{result['final_preregistered_target']:03d}_first":finalrows.append(x)
 curves=['# 三seed PPO学习曲线','', '三个seed的全部训练采样、失败、reward分项、entropy与loss保存在ALL_TRAINING_LOG.jsonl及seeds/*/stage1/TRAINING_LOG.jsonl。下表按连续10集汇总。失败的partial JF不能同完整成功JF当收益比较。clip前Gaussian entropy不是实际扭矩熵。nominal重复不是新患者泛化。','', '|seed|episodes|训练成功|平均return|平均TASK s|平均entropy nats|','|---:|---|---:|---:|---:|---:|']
 for x in seeds:
  for b in x['training_curve_blocks']:curves.append(f"|{x['seed']}|{b['first']}–{b['last']}|{b['successes']}/{b['episodes']}|{b['mean_reward']:.6f}|{b['mean_task_s']:.3f}|{b['mean_entropy_nats']:.4f}|")
 curves+=['','![三seed学习曲线](PPO_LEARNING_CURVES.png)','','## 冻结评价','','\n'.join(evaltable),'','失败成本下限保持v3；训练reward提高不单独构成force/motion优化。冻结评价没有用于改reward或挑训练seed。']
 write('PPO_LEARNING_CURVES.md','\n'.join(curves))
 # Publication-style standalone chart with matched axes and all seeds.
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 import numpy as np
 fig,axes=plt.subplots(2,2,figsize=(12,7),constrained_layout=True)
 for seed in cfg['seeds']:
  rows=[x for x in train if x['stage']=='stage1' and x['training_seed']==seed]
  if not rows:continue
  ix=np.array([x['index'] for x in rows]);rewards=np.array([x['reward'] for x in rows]);success=np.array([x['success'] for x in rows],float)
  rolling=np.array([success[max(0,i-9):i+1].mean() for i in range(len(rows))]);label=str(seed)
  axes[0,0].plot(ix,rewards,alpha=.7,label=label);axes[0,1].plot(ix,rolling,label=label);axes[1,0].plot(ix,[x['task_s'] for x in rows],alpha=.7,label=label);axes[1,1].plot(ix,np.cumsum([x['native_steps'] for x in rows])/1e6,label=label)
 for ax,title,ylabel in zip(axes.ravel(),['Frozen reward v3','Rolling 10-episode runtime completion','Task elapsed (failed attempts retained)','Cumulative native physics sample cost'],['Episode return','Completion fraction','TASK seconds','Million native steps incl. preparation']):
  ax.set_title(title);ax.set_ylabel(ylabel);ax.set_xlabel('Training episode');ax.grid(alpha=.25);ax.axvline(20,color='gray',ls='--',alpha=.3);ax.legend(fontsize=7)
 axes[0,1].set_ylim(-.05,1.05);fig.suptitle('3 independently initialized PPO seeds; deterministic nominal development environment')
 fig.savefig(ROOT/'PPO_LEARNING_CURVES.png',dpi=170);fig.savefig(ROOT/'PPO_LEARNING_CURVES.pdf');plt.close(fig)
 replicated=result['three_seed_replication_pass'];replication_text='是，达到预注册3/3条件' if replicated else f"未达到预注册3/3条件；只有{result['replicated_seed_count']}/3 seed达到初始失败→最终2/2成功"
 if result['final_preregistered_target']==80:
  exact=result.get('exact50_episode_replication') or {}
  replication_text=f"精确50集预算只有{exact.get('replicated_seed_count','未知')}/3 seed复现；延长至80集后，"+replication_text
 regressions=read(ROOT/'LEARNING_STABILITY_AUDIT.json') if (ROOT/'LEARNING_STABILITY_AUDIT.json').exists() else None
 if regressions and regressions['previously_successful_seeds_regressed']:
  replication_text+=f"；有{regressions['previously_successful_seeds_regressed']}个seed由50集冻结2/2成功退回80集0/2，继续训练没有带来单调改进"
 delta=[]
 if fixed:
  for x in finalrows:
   if x['success'] and abs(x['task_s']-fixed['task_s'])<1e-6:delta.append(f"seed {x['training_seed']}：相对固定合法对照，JF {(x['JF']/fixed['JF']-1)*100:+.3f}%，JM {(x['JM']/fixed['JM']-1)*100:+.3f}%")
 delta_text='；'.join(delta) if delta else '80集最终checkpoint没有可用于完整性能比较的成功配对。'
 if (ROOT/'FROZEN50_PERFORMANCE_DIAGNOSTIC.json').exists():
  d50=read(ROOT/'FROZEN50_PERFORMANCE_DIAGNOSTIC.json');parts50=[f"seed{x['seed']}的JF {x['JF_change_pct']:+.3f}%、JM {x['JM_change_pct']:+.3f}%" for x in d50['seed_results'] if x['comparable_complete_equal_duration']]
  delta_text+=' 50集的相同时长完整执行则为：'+'；'.join(parts50)+'。force略降伴随moment上升，详见FROZEN50_PERFORMANCE_DIAGNOSTIC.json/md，不能称完整性能优势。'
 ready='NOT_READY_FOR_FINAL_CAMPAIGN';stage2run=stage2.get('status')!='NOT_RUN' and stage2.get('training_episodes',0)>0
 recommendation={'status':ready,'do_not_start':True,'architecture':'Retain bounded causal 41D observation → 2D Gaussian PPO intent → original certified native robot execution for next bounded development. No teacher; Stage2 descendants must be labeled TASK_PRETRAINED_PPO_FINETUNING.','reward':'pilot_v3_failure_cost_floor for exact Stage1 replication; no final performance reward accepted without objective paired task/safety/motion evidence.','PPO':cfg['ppo'],'seeds':cfg['seeds'],'campaign_training_budget':'NOT_AUTHORIZED; configure only after original B/H150 scorer, G4 and repeatability/performance gates close.','exact50_episode_replication':result.get('exact50_episode_replication'),'final_task_learning_training_budget_per_seed':result['final_preregistered_target'],'conditional_next_bounded_budget':{'seed_count':3,'episodes_per_seed':result['final_preregistered_target'],'episodes_total':3*result['final_preregistered_target'],'decision_reserve':3*result['final_preregistered_target']*128,'native_reserve':3*result['final_preregistered_target']*165000,'evaluation_cap':24,'note':'Planning envelope only, not an automatic rerun or final campaign.'},'measured_mean_program_s_per_training_episode':resource['training_mean_program_s_per_episode'],'planning_wall_150_episode_hours':resource['training_mean_program_s_per_episode']*150/3600,'conditional_240_episode_hours':resource['training_mean_program_s_per_episode']*240/3600,'CPU_server_expansion_needed':'No evidence of RAM or CPU-capacity blocker in this bounded campaign; recover qualification and information value before considering expansion. A two-environment short benchmark would be required before parallel use.','formal_evaluation':'Original frozen B/H150 scorer/dependency closure + known PASS/FAIL fixtures + deterministic state restoration; same task/physics/mode; full raw/native/receipts; runtime/matched/full separated; nominal and fresh hidden patient split preregistered.','primary_blockers':['Original B/H150 full scorer/baseline manifest/raw/state identity missing','G4_STRICT_PASS remains FAIL: natural HOLD-failure/absolute-safety and complete original matrix not closed; new natural OUTBOUND/RETURN timeout evidence is preserved separately','Observed regression: two previously successful50-episode deterministic checkpoints failed after continued80-episode training; stochastic-vs-mean execution and credit assignment remain unresolved','No cross-patient held-out generalization','No formally qualified force/motion advantage demonstrated']+([] if replicated else ['Exact three-seed learning replication criterion failed']),'priority_next_step':'Recover the original frozen B/H150 scorer, fixtures and state restoration; run one known original baseline regression before scaling training.'}
 complete_costs=[x['resource']['wall_s'] for x in train+evaluation if x['success']]
 conservative_complete_s=max(complete_costs,default=resource['training_mean_program_s_per_episode'])+10.
 draft={'status':'BLOCKED_PROPOSAL_ONLY_NOT_EXECUTION_AUTHORIZED','execution_allowed':False,'training_seeds':cfg['seeds'],'seed_count':3,'episodes_per_seed_candidate':200,'episode_budget_candidate':600,'RL_decision_hard_cap_candidate':600*128,'native_training_reserve_candidate':600*165000,'evaluation_attempt_cap_candidate':48,'native_total_reserve_candidate':648*165000,'scheduled_review_episodes_per_seed':[50,100,200],'architecture':recommendation['architecture'],'PPO':cfg['ppo'],'task_pretraining_reward':'pilot_v3_failure_cost_floor','performance_reward':'UNRESOLVED_DO_NOT_EXECUTE; accept only after paired Stage2 task/safety/motion qualification with original scorer','original_scorer_sha256':None,'original_B_H150_baseline_identity':None,'fresh_patient_train_validation_final_test_manifest':None,'wall_estimate_hours_current_failed_success_mix':600*resource['training_mean_program_s_per_episode']/3600,'wall_estimate_hours_complete_episode_cost_plus10s_overhead':600*conservative_complete_s/3600,'evaluation_and_report_reserve_hours':48*conservative_complete_s/3600+2.,'estimate_limitation':'Planning only. Successful episodes are longer than many failed partials; do not extrapolate only the cheaper failed-episode mix. No million-RL-decision campaign is recommended or started.','unlock_conditions':recommendation['primary_blockers'],'instance_change':'No purchase/resize; benchmark at most2 independent environments after parity and resource checks if throughput is later the limiting factor.'}
 recommendation['conditional_final_campaign_draft']=draft
 put(ROOT/'FINAL_CAMPAIGN_CONFIG_DRAFT.json',draft)
 put(ROOT/'FINAL_CAMPAIGN_PLAN.json',recommendation)
 readiness=f'''# 最终大规模训练前决策

**{ready}**。本轮没有启动最终campaign；READY即使将来成立，也不是自动训练授权。

{replication_text}。正式scorer与G4缺口仍阻碍公平资格；没有依据把reward上涨、单seed或nominal重复当正式性能优势。

建议保留41维因果观测、2维有界协调意图和原执行保护作为研究架构；当前Gaussian PPO（MLP32×32）仅作为诊断对照基线，尚未获最终campaign推荐。Stage1复现reward为pilot_v3_failure_cost_floor；PPO lr=.0003、γ=1、GAE=.95、clip=.2、4 epochs、batch16、vf=.5、entropy=0、max_grad_norm=.5。每episode一个完整rollout，128是单episode决策上限，不是固定训练rollout。Stage2不冒称scratch。

三个预注册训练seed：{cfg['seeds']}。至少三训练seed全部保留；真正跨患者推广须另冻结患者/初态划分，当前没有证明。明天不能直接启动百万decision训练。可执行准入顺序：

1. 找回原B/H150 manifest、scorer、基准raw与state恢复；逐SHA确认依赖，复现至少一个原条件和已知PASS/FAIL fixture。
2. 补齐剩余G4矩阵（HOLD失败、绝对安全终止及global TASK timeout等）；本轮OUTBOUND/RETURN自然timeout已有证据；恢复完整原motion/fairness/causal门；scientific与host realtime/strict55分别判定。
3. 预注册独立训练/验证/最终测试患者与配置选择规则；通过有界3-seed runtime及配对性能门后，再审批正式episode/decision/native预算。
4. 只有用户批准正式方案后才开始；本包没有可自动启动正式训练的命令。

实测训练程序均摊约{resource['training_mean_program_s_per_episode']:.2f}s/episode（含审计/checkpoint，含commissioning/recovery）。按本轮长度分布，仅供计划的150集约{recommendation['planning_wall_150_episode_hours']:.2f}h，240集约{recommendation['conditional_240_episode_hours']:.2f}h，不保证更长/更难任务吞吐。决策较稀疏，不能把native步数当RL decision。150集控制上限为19,200 decisions、24,750,000 native预算；加评价需另留24次，每次预留165,000 native。正式大规模预算当前未批准。另给出不可执行的条件草案：3 seed×200集=600集，分50/100/200复核，最多76,800 decisions、99,000,000训练native；另48次评价及7,920,000 native预留。原scorer SHA、基准身份、未见患者划分与性能reward仍为空，execution_allowed=false，不能启动。按当前失败/成功混合成本约{draft['wall_estimate_hours_current_failed_success_mix']:.2f}h，按完整任务实测成本加10秒开销约{draft['wall_estimate_hours_complete_episode_cost_plus10s_overhead']:.2f}h；评价和报告另留约{draft['evaluation_and_report_reserve_hours']:.2f}h。这是未来重新授权与准入后的资源草案，不是本轮扩大训练。

CCX33当前单环境最低可用RAM {resource['minimum_available_ram_GiB']:.2f}GiB，未观察到容量瓶颈；没有证据支持现在扩容。若准入完成后确有wall预算需求，应先独立短测最多双环境，保证6GiB余量，再决定是否换机器。没有购买或调整实例。

正式评价必须使用原冻结完整合同与B/H150同mode对照，保留完整JF/JM、实际velocity/acceleration/jerk、tracking、excursion、terminal overshoot、dose、source-age和native receipt。缺任一权威门不晋级。主要风险见FINAL_CAMPAIGN_PLAN.json。
'''
 write('FINAL_CAMPAIGN_READINESS.md',readiness)
 write('NEXT_RESEARCH_DECISION.md',f'''# 下一研究决策

{ready}。本轮最终STOP，不自动开下一研究包。

唯一优先下一步：按原B/H150来源manifest找回完整scorer、基准fixture与state恢复，并复现一条原已知资格结果。完整评价闭合前不扩大训练规模、不改算法以追求表面成功。

就reward、动作空间、算法、规模四项，当前先保留算法与动作接口；在客观scorer到位后，用受控reward审计决定下一次小实验。未证明现有PPO容量或训练规模是主要瓶颈。本轮三seed不稳定，需研究失败成本平坦区、rollout信用分配以及随机策略与确定性均值动作在非线性可行域中的差异；若Stage2失败，则保留失败，不将其checkpoint晋升。所有新实验须另有明确授权；本包没有自动继续入口。
''')
 report=f'''# iHEAR Lab — 自主PPO三seed复现与性能就绪评估 v1

本轮结论：**{ready}**。{replication_text}。B/H150原完整matched scorer仍NOT_READY，PPO未获FULL资格；Stage2状态为{stage2.get('status')}。没有启动正式大规模训练。

T0为{stamp(cfg['t0_unix'])}；报告时间{stamp(now)}；当前累计{(now-cfg['t0_unix'])/60:.1f}分钟。实验在独立目录进行，原ZIP、checkpoint、历史结果及414份原科学源码受hash保护。初次初始化缺vendor manifest而在任何物理/模型前退出，补齐原28资产manifest后恢复；失败记录保留。没有训练reward/算法修复分支。

## 1. 单seed学习能否在3个seed复现？

{replication_text}。严格规则事先冻结为三个seed均从训练前冻结失败改善到最终冻结2/2原runtime成功；不能把一个或两个seed成功称为3-seed成功。三个初始冻结均失败；nominal重复不证明泛化。若从50延长至80，依据预注册全体延长门，复用已知nominal开发评价；不称未见最终测试，也不据此挑reward、超参数或seed。

## 2–3. 训练量、梯度更新与冻结完成率

{chr(10).join(train_table)}

总Stage1训练attempt为{ledger['stage1_attempts']}，Stage2为{ledger['stage2_attempts']}，独立冻结评价为{ledger['evaluation_attempts']}。全部失败seed/episodes保留。PPO train call每已完成训练episode一次，epochs与真实Adam更新分开记录；所有训练transition进入更新。checkpoint保留于seeds/<seed>/<stage>/checkpoints，含model/Adam/RNG及SHA。详情见MULTISEED_PPO_RESULTS.json与PPO_CHECKPOINT_AUDIT.json。

## 4–6. 正式评价器、完整资格及性能比较

原ZIP450/450载荷核验通过；四历史包各414份source及真实差异已核对。现有唯一在线接口development合同不是B/H150 Master；缺原完整scorer、motion/fairness/dose语义、原基准raw与state身份。B/H150原条件复现NOT_RUN，正式匹配NOT_READY，不能近似替代。

RUNTIME_COMPLETE按原完整phase链/causal completion判定；19.030±.050仅是必要时长项；MATCHED_TASK_PASS和FULL_QUALIFIED未授予。G4_STRICT_PASS历史FAIL保持，本轮新增自然OUTBOUND/RETURN timeout证据（见G4_NATURAL_PATH_UPDATE），但自然HOLD失败、绝对安全触发及完整矩阵仍未闭合。每episode观测物理审计PASS不等于全动作安全或host实时/strict55资格。

{chr(10).join(evaltable)}

{delta_text} 只有相同TASK时长的完整执行才列相对百分比，时长不同只保留描述性原数值。这些比较的对象是固定合法[+1,+1]，不是B/H150。相对B/H150的JF、JM和motion均NOT_EVALUABLE。失败partial积分不可与完整任务积分宣称收益。完整native motion、terminal误差/overshoot、excursion、tracking、phase JF/JM见audit/ALL_SCIENTIFIC_METRICS.json及各评价raw。jerk没有新造通过门。

## 7–8. Stage2与任务完成代价

状态：{stage2.get('status')}。原因/结果：{stage2.get('reason',stage2.get('conclusion','详见Stage2文件'))}。详见STAGE2_PERFORMANCE_STUDY.md与STAGE2_RESULTS.json。若启动，其身份只能是TASK_PRETRAINED_PPO_FINETUNING；父子完整配对与任务、安全、moment/jerk权衡单列。未运行时不能声称有优化收益或任务牺牲；父策略不被覆盖。

## 9. seed间差异

各seed训练完成率、失败阶段和原因、连续10集曲线及冻结结果全部公开。训练完成率分别为18.75%、36.25%、30.00%；50集冻结为0/2、2/2、2/2，80集冻结均0/2。两个已成功checkpoint在继续训练后回退，见LEARNING_STABILITY_AUDIT.json。仅三个训练seed、同一nominal物理初态，差异作描述性比较；不声称统计显著性或跨患者鲁棒性。学习reward不等于正式motion/force优化。

## 10. CPU样本成本与wall time

训练{resource['training_RL_decisions']}个RL decisions、{resource['training_native_steps']}个native steps（TASK {resource['training_task_native_steps']}）；评价{resource['evaluation_RL_decisions']}个decisions、{resource['evaluation_native_steps']}个native steps。训练程序wall约{trainprogramwall/60:.2f}min（含独立审计与checkpoint），评价程序约{evalprogramwall/60:.2f}min；全研究包准备/审计/报告另计入总elapsed。native步与RL决策严格区分。

单物理环境、每环境单线程、CPU-only，最低可用RAM {resource['minimum_available_ram_GiB']:.2f}GiB，最低磁盘余量{resource['minimum_free_disk_GiB']:.2f}GiB；未购买或调整Hetzner。资源样本、进程超时及退出检查保留。吞吐与条件估时见RESOURCE_USAGE.json/FINAL_CAMPAIGN_PLAN.json。

## 11–13. 阻碍、明日配置与下一优先项

主要阻碍：原B/H150完整scorer和state/基准身份缺失；G4的HOLD/绝对安全及完整矩阵未闭合（自然OUTBOUND/RETURN timeout已有新证据）；未见患者泛化未测试；没有完整资格支持的force/motion收益。{'另有三seed严格学习复现失败。' if not replicated else ''}

明日应先补齐原评价器与基准复现，再按FINAL_CAMPAIGN_READINESS.md的原PPO/reward配置和至少3 seed做已批准范围内的有界验证；正式campaign预算当前未批准，不应直接开百万decision训练。现有CPU未见扩容依据。若必须在reward/动作空间/算法/规模中排序，先补齐原scorer，再审计reward/rollout信用分配及随机采样与确定性均值执行差异；在有界开发中比较reward和动作分布/协调参数化，保持原物理、安全与任务门；不靠盲目增大规模弥补资格缺口。唯一下一步见NEXT_RESEARCH_DECISION.md。

## 复核、记录与停止边界

独立复核使用同一Agent的分离原始证据读取与积分代码；没有第二Agent/人工独立审稿。train/evaluation及失败/partial身份分开，未用真值/未来Human输入actor，未按测试反复挑配置。训练大raw在逐native与causal审计通过后按SHA记录去向；摘要/transition/receipt与周期checkpoint保留。关键评价保留完整无损raw，原始JF/JM和实际native运动可再计算。

冻结评价额外使用TASK前20ms真实native历史作锚，复核第一个TASK区间及所有native/5ms/20ms加速度窗口；jerk以TASK内全部结束点计算并保留原无锚窗口诊断数值。该补查不重定义原scorer。最终保护、START/END闭合、checkpoint身份、完整原始评价重算、所有owned进程退出、文件与manifest完整性以VALIDATION_RESULTS.json、ATTEMPT_ACCOUNTING.json、PROCESS_EXIT_AUDIT.json和PACKAGE_VERIFICATION.json为准。没有Git checkout；没有stage/commit/push/merge/reset/stash/clean，没有改正式控制器、物理或任务门。

本轮最终STOP。不得自动开始最终训练或下一研究包。
'''
 write('REPORT.md',report)
 print(json.dumps({'status':ready,'replicated_seed_count':result['replicated_seed_count'],'stage1_training_attempts':ledger['stage1_attempts'],'stage2_training_attempts':ledger['stage2_attempts'],'evaluation_attempts':ledger['evaluation_attempts']}))
if __name__=='__main__':main()
