"""Chinese research reports from attributed records; no physics and no learning."""
from pathlib import Path
from datetime import datetime,timezone
import os,sys,json,math,statistics,hashlib,csv,collections,time
R=Path(__file__).resolve().parents[1];os.environ['IHEAR_RESEARCH_ROOT']=str(R);sys.path.insert(0,str(R/'scripts'))
from research_common import read,atomic,append,sha,now
SEEDS=[1495656323,1630784693]
SCOPE='两个既有成功父、相同 nominal 物理初态的开发证据；动作流变化不代表跨患者或跨初态泛化。'

def lines(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.exists() else []
def fmt(x,d=6):return '未取得' if x is None else f'{x:.{d}f}' if isinstance(x,(int,float)) and not isinstance(x,bool) else str(x)
def doc(name,text):
 p=R/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text.rstrip()+'\n')
def safe_ratio(a,b):return a/b if b else None

def compact(row):
 keys=['job_id','branch','seed','index','mode','policy_mode','evaluation_rng','evaluation_split','reward_version','run','parent','success','complete_evidence','status','abort_reason','task_s','native_steps','task_native_steps','rl_decisions','training_reward','JF','JM','integral_scope','accepted','rejections','entropy_mean','mean_initial','std_initial','raw_clipped_fraction','gradient_updates','pending_complete_transitions','policy_before','policy_after','update']
 x={k:row.get(k) for k in keys};p=R/'audit/independent_all_attempts'/row['job_id']/Path(row['run']).name/'COMMON_MOTION_METRICS.json'
 if not p.exists():p=Path(row['run'])/'COMMON_MOTION_METRICS.json'
 x['motion']=read(p);x['motion_evidence']=str(p) if p.exists() else None
 rejected=[a for a in row.get('native_actions',[]) if a.get('outcome')!='ACTIVATED']
 def refusal_class(a):
  reason=str(a.get('reason','')).lower()
  return 'geometry' if 'geometry' in reason else 'reference' if 'regress the emitted reference' in reason else 'other'
 classes=[refusal_class(a) for a in rejected]
 x['geometry_refusals']=classes.count('geometry')
 x['emitted_reference_refusals']=classes.count('reference')
 x['other_refusals']=classes.count('other')
 x['refusal_count_matches_runtime']=len(rejected)==row['rejections']
 x['fallback_events']=row.get('fallback_events',[])
 return x

def summarize(rows):
 groups=collections.defaultdict(list)
 for r in rows:groups[(r['branch'],r['seed'],r['mode'],r['policy_mode'])].append(r)
 out=[]
 for (branch,seed,mode,pm),rr in sorted(groups.items()):
  out.append(dict(branch=branch,seed=seed,mode=mode,policy_mode=pm,attempts=len(rr),complete=sum(r['success'] for r in rr),failed=sum(not r['success'] for r in rr),native_steps=sum(r['native_steps'] for r in rr),optimizer_steps=sum(r['gradient_updates'] for r in rr),geometry_refusals=sum(r['geometry_refusals'] for r in rr),emitted_reference_refusals=sum(r['emitted_reference_refusals'] for r in rr),other_refusals=sum(r['other_refusals'] for r in rr),decisions=sum(r['rl_decisions'] for r in rr),std_first=rr[0]['std_initial'],std_last=rr[-1]['std_initial'],clip_fraction_weighted=sum(r['raw_clipped_fraction']*r['rl_decisions'] for r in rr)/sum(r['rl_decisions'] for r in rr),complete_JF=[r['JF'] for r in rr if r['success']],complete_JM=[r['JM'] for r in rr if r['success']],partials=[dict(run=r['run'],reason=r['abort_reason'],task_s=r['task_s'],JF=r['JF'],JM=r['JM']) for r in rr if not r['success']]))
 return out

def table(rows):
 s=['|分支|父seed|端点/模式|完整|task s|JF N·s|JM Nm·s|膝 tracking °|膝 jerk °/s³|RETURN 膝 overshoot °|积分身份|','|---|---|---|---|---|---|---|---|---|---|---|']
 for r in rows:
  m=r.get('motion') or {};tracking=m.get('tracking_RMS_deg',[None,None]);jerk=m.get('jerk_RMS_deg_s3',[None,None]);overshoot=m.get('RETURN_overshoot_below_goal_deg')
  s.append(f"|{r['branch']}|{r['seed']}|{r['index']-1}/{r['policy_mode']}/{r.get('evaluation_rng')}|{r['success']}|{fmt(r['task_s'],5)}|{fmt(r['JF'])}|{fmt(r['JM'])}|{fmt(tracking[1],5)}|{fmt(jerk[1],3)}|{fmt(overshoot[1] if overshoot else None,5)}|{r['integral_scope']}|")
 return '\n'.join(s)

def paired(a,b):
 ok=bool(a and b and a['success'] and b['success'] and abs(a['task_s']-b['task_s'])<1e-7)
 result=dict(control_run=a['run'] if a else None,candidate_run=b['run'] if b else None,complete_equal_duration=ok,control_success=a['success'] if a else None,candidate_success=b['success'] if b else None,JF_delta=b['JF']-a['JF'] if ok else None,JM_delta=b['JM']-a['JM'] if ok else None,JF_percent=100*(b['JF']/a['JF']-1) if ok else None,JM_percent=100*(b['JM']/a['JM']-1) if ok else None)
 for key in ['tracking_RMS_deg','jerk_RMS_deg_s3','RETURN_overshoot_below_goal_deg']:
  x=(a or {}).get('motion') or {};y=(b or {}).get('motion') or {};v=x.get(key);w=y.get(key)
  result[key+'_delta']=[z-q for q,z in zip(v,w)] if ok and v and w else None
 return result

def comparison_text(pairs):
 out=['|父seed|mode/流|完整等时|ΔJF %|ΔJM %|Δ膝 tracking °|Δ膝 jerk °/s³|ΔRETURN 膝 overshoot °|','|---|---|---|---|---|---|---|---|']
 for p in pairs:
  get=lambda k:(p.get(k) or [None,None])[1]
  out.append(f"|{p['seed']}|{p['mode']}/{p.get('rng')}|{p['complete_equal_duration']}|{fmt(p['JF_percent'])}|{fmt(p['JM_percent'])}|{fmt(get('tracking_RMS_deg_delta'))}|{fmt(get('jerk_RMS_deg_s3_delta'),3)}|{fmt(get('RETURN_overshoot_below_goal_deg_delta'))}|")
 return '\n'.join(out)

def build(live=False):
 started=read(R/'START.json');activation=read(R/'ACTIVATION.json');ledger=read(R/'LEDGER.json',{});full=read(R/'audit/INDEPENDENT_FULL_AUDIT.json',{});end=read(R/'END.json',{});queue=read(R/'CAMPAIGN_QUEUE_END.json',{});raw=lines(R/'ALL_ATTEMPTS.jsonl');rows=[compact(x) for x in raw];train=[r for r in rows if r['mode']=='training'];ev=[r for r in rows if r['mode']=='evaluation'];dev=[r for r in ev if r.get('evaluation_split')!='reserved_action_streams'];hold=[r for r in ev if r.get('evaluation_split')=='reserved_action_streams'];std=[r for r in train if r['branch'] in ['CHECKPOINT_STD','STD_INIT_0p2']];rr=[r for r in train if r['branch'].startswith('REWARD_')];updates=lines(R/'UPDATE_LOG.jsonl');selection=read(R/'FINAL_SELECTION_BEFORE_HOLDOUT.json',{});method=read(R/'TRAINING_METHOD_SELECTION.json',{});summary=summarize(rows);t0=datetime.fromisoformat(activation['activation_utc']);close=datetime.fromisoformat(end.get('time_utc',now()));hours=(close-t0).total_seconds()/3600
 origin=Path(started['origin_package']);history=read(origin/'STD_ABLATION_RESULTS.json');baselines={r['seed']:r for r in history['cases'] if r['arm']=='C'}
 baseline_rows={seed:dict(run=r['run'],success=r['success'],task_s=r['task_s'],JF=r['JF'],JM=r['JM'],motion=r['motion']) for seed,r in baselines.items()}
 reward_pairs=[]
 for seed in SEEDS:
  for mode,rng in [('deterministic',2026102201),('stochastic',2026102201),('stochastic',2026102202)]:
   aa=[r for r in dev if r['seed']==seed and r['policy_mode']==mode and r.get('evaluation_rng')==rng and (r['branch'].startswith('REWARD_R1_') or r['branch']=='PAIRED_DEV2_R1')]
   bb=[r for r in dev if r['seed']==seed and r['policy_mode']==mode and r.get('evaluation_rng')==rng and (r['branch'].startswith('REWARD_R4_') or r['branch']=='PAIRED_DEV2_R4')]
   if aa or bb:reward_pairs.append(dict(seed=seed,mode=mode,rng=rng,**paired(aa[-1] if aa else None,bb[-1] if bb else None)))
 selected_mean={}
 for seed in SEEDS:
  cp=(selection.get('checkpoints') or {}).get(str(seed))
  matches=[r for r in dev if r['seed']==seed and r['policy_mode']=='deterministic' and r['parent']==cp]
  if matches:selected_mean[seed]=matches[-1]
 baseline_pairs=[dict(seed=seed,mode='selected mean vs original R1/60 historical mean',rng=None,**paired(baseline_rows[seed],selected_mean.get(seed))) for seed in SEEDS]
 valid=bool(train) and bool(full.get('pass_'));mean_all=len(selected_mean)==2 and all(r['success'] for r in selected_mean.values());hold_per=[]
 for seed in SEEDS:
  hh=[r for r in hold if r['seed']==seed];n=len(hh);k=sum(r['success'] for r in hh);ci=None
  if n:
   try:
    from scipy.stats import beta
    ci=[0. if k==0 else float(beta.ppf(.025,k,n-k+1)),1. if k==n else float(beta.ppf(.975,k+1,n-k))]
   except ImportError:pass
  hold_per.append(dict(seed=seed,complete=k,attempts=n,binomial_95pct_interval_descriptive=ci,scope='Fixed selected model, six nominal action streams; not patient/general initial-state reliability'))
 stdscreen={m:[r for r in dev if r['branch']==m and r['index']==11] for m in ['CHECKPOINT_STD','STD_INIT_0p2']}
 std_complete=all(len(v)==4 for v in stdscreen.values())
 stdsignal=std_complete and all(next(r for r in stdscreen['STD_INIT_0p2'] if r['seed']==seed and r['policy_mode']=='deterministic')['success'] for seed in SEEDS) and all(sum(r['success'] for r in stdscreen['STD_INIT_0p2'] if r['seed']==seed)>=sum(r['success'] for r in stdscreen['CHECKPOINT_STD'] if r['seed']==seed) for seed in SEEDS) and any(sum(r['success'] for r in stdscreen['STD_INIT_0p2'] if r['seed']==seed)>sum(r['success'] for r in stdscreen['CHECKPOINT_STD'] if r['seed']==seed) for seed in SEEDS)
 update_summaries=[]
 for branch in sorted({r['branch'] for r in train}):
  for seed in SEEDS:
   uu=[r['update'] for r in train if r['branch']==branch and r['seed']==seed and r.get('update')]
   dd=[u['distribution_diagnostics'] for u in uu if u.get('distribution_diagnostics')]
   if dd:update_summaries.append(dict(branch=branch,seed=seed,rollout_updates=len(uu),Adam_steps=sum(u['optimizer_steps'] for u in uu),max_full_rollout_approx_KL=max(d['full_rollout_approx_KL'] for d in dd),ratio_min=min(d['ratio_min'] for d in dd),ratio_max=max(d['ratio_max'] for d in dd),max_actor_mean_RMS_drift=max(d['actor_mean_rms_drift'] for d in dd),std_before=dd[0]['std_before'],std_after=dd[-1]['std_after']))
 atomic(R/'PPO_DISTRIBUTION_SUMMARY.json',dict(time_utc=now(),updates=update_summaries,interpretation='Initial sampling ratio=1 is separately guarded. Post-update PPO clip objective does not enforce hard ratio bounds. Smaller STD can amplify normalized mean-shift KL; no claim of improved PPO stability from completion alone.'))
 for seed in SEEDS:
  a=next((x for x in update_summaries if x['branch']=='CHECKPOINT_STD' and x['seed']==seed),None);b=next((x for x in update_summaries if x['branch']=='STD_INIT_0p2' and x['seed']==seed),None)
  if a and b and b['max_full_rollout_approx_KL']>a['max_full_rollout_approx_KL']:stdsignal=False
 r4eval=all(any(r['seed']==seed and r['branch'].startswith('REWARD_R4_') and r['policy_mode']=='deterministic' for r in dev) for seed in SEEDS)
 forcegood=all(p['complete_equal_duration'] and p['JF_delta']<0 for p in baseline_pairs);momentgood=all(p['complete_equal_duration'] and p['JM_delta']<0 for p in baseline_pairs)
 flags=dict(DEVELOPMENT_TRAINING_VALID='PASS' if valid else 'PENDING' if live else 'NOT_ESTABLISHED',STD_TRAINING_COMPARISON_PASS='PASS_COMPARISON_COMPLETE' if valid and std_complete else 'PENDING' if live else 'INCOMPLETE',PPO_STABILITY_IMPROVED='SUPPORTED_SMALL_N_NOMINAL_DEVELOPMENT' if stdsignal else 'NOT_ESTABLISHED',REWARD_R4_EVALUATED='PASS_EVALUATED' if r4eval else 'PENDING' if live else 'NOT_EVALUATED',RUNTIME_TASK_SUCCESS='SELECTED_BOTH_MEAN_PASS' if mean_all else 'HISTORICAL_BASELINE_ONLY' if selection and not selected_mean else 'NOT_ESTABLISHED',STOCHASTIC_RELIABILITY='OBSERVED_6_OF_6_EACH_PARENT_NOMINAL_ONLY' if all(x['complete']==x['attempts']==6 for x in hold_per) else 'NOT_ESTABLISHED',FORCE_IMPROVEMENT='SELECTED_BOTH_MEAN_LOWER_VS_HISTORICAL_R1_60' if forcegood else 'NOT_ESTABLISHED',MOMENT_IMPROVEMENT='SELECTED_BOTH_MEAN_LOWER_VS_HISTORICAL_R1_60' if momentgood else 'NOT_ESTABLISHED',MOTION_QUALIFIED='OBSERVED_ORIGINAL_LIMITS_PASS_ONLY' if valid else 'NOT_ESTABLISHED',G4_STRICT_PASS='FAIL',NEW_LIVE_MATCHED_READY='NOT_READY',STAGE2_READY='NOT_READY',FINAL_CAMPAIGN_READY='NOT_READY')
 flag_evidence={key:dict(status=value,scope=SCOPE,evidence=['audit/INDEPENDENT_FULL_AUDIT.json','STD_TRAINING_RESULTS.json','R1_R4_REWARD_COMPARISON.md','HOLDOUT_EVALUATION_RESULTS.json']) for key,value in flags.items()};atomic(R/'QUALIFICATIONS.json',dict(time_utc=now(),labels=flag_evidence,formal_gates='Independent historical G4 FAIL; no new live matched, Stage2 or final Campaign attempted'))
 atomic(R/'PPO_TRAINING_RESULTS.json',dict(time_utc=now(),scope=SCOPE,rows=train,summary=[s for s in summary if s['mode']=='training'],optimizer_steps=ledger.get('optimizer_steps',0),update_calls=len(updates),updates=updates,source_identity=activation['script_sha256'],historical_training_excluded=True))
 atomic(R/'STD_TRAINING_RESULTS.json',dict(time_utc=now(),scope=SCOPE,training=std,development=[r for r in dev if r['branch'] in ['CHECKPOINT_STD','STD_INIT_0p2']],summary=[s for s in summary if s['branch'] in ['CHECKPOINT_STD','STD_INIT_0p2']],selection=method,primary_method_comparison='Matched first10 episodes at both parents; only selected method has conditional extension to30; no checkpoint-STD/30 control',total_training_episodes=len(std),cap=80,initialization_semantics=activation['training_std_semantics']))
 atomic(R/'FROZEN_EVALUATION_RESULTS.json',dict(time_utc=now(),split='development',rows=dev,attempts=len(dev),cap=24,historical_results_excluded=True,final_stream_results_excluded=True))
 atomic(R/'HOLDOUT_EVALUATION_RESULTS.json',dict(time_utc=now(),split='reserved nominal action streams',rows=hold,per_parent=hold_per,attempts=len(hold),cap=12,lock=selection,lock_sha256=sha(R/'FINAL_SELECTION_BEFORE_HOLDOUT.json') if selection else None,no_post_final_tuning=True,scope=SCOPE))
 atomic(R/'CHECKPOINT_STABILITY_AUDIT.json',dict(time_utc=now(),initial_parents=read(R/'audit/ADMISSION_PREFLIGHT.json')['parents'],complete_generation_audits=full.get('checkpoints',[]),independent_full_audit='audit/INDEPENDENT_FULL_AUDIT.json',partial_generations_promoted=False,selected=selection,formal_scientific_qualification=False))
 atomic(R/'R1_R4_REWARD_RESULTS.json',dict(time_utc=now(),training=rr,pairs=reward_pairs,lock=read(R/'REWARD_EXPERIMENT_LOCK.json'),reward_only_difference='moment_per_Nms .005 -> .020; inherited mean/critic/Adam/RNG identical at fork; actual closed loops diverge after reward-driven updates',selected=selection.get('reward'),scope=SCOPE))
 # Every decision and branch result is attributed; never rewrite source decision logs.
 decisions=lines(R/'RESEARCH_DECISION_LOG.jsonl')+lines(R/'BRANCH_DECISIONS.jsonl')
 decisions=sorted(decisions,key=lambda x:x.get('time_utc',''))
 out=R/'AUTONOMOUS_RESEARCH_DECISIONS.jsonl';out.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in decisions))
 resources=lines(R/'RESOURCE_TELEMETRY.jsonl');job_ends=[read(p) for p in (R/'jobs').glob('*/END.json')];minram=min([r.get('resources',{}).get('minimum_available_GiB',float('inf')) for r in raw]+[x['available_bytes']/1024**3 for x in resources]+[float('inf')]);mindisk=min([x['disk_free_bytes']/1024**3 for x in resources]+[float('inf')]);packagebytes=sum(p.stat().st_size for p in R.rglob('*') if p.is_file());walls=sum(x.get('wall_s',0) for x in job_ends)
 resource=dict(time_utc=now(),activation_utc=activation['activation_utc'],physics_queue_closed_utc=end.get('time_utc'),hard_stop_utc=started['hard_stop_utc'],autonomous_queue_hours=hours,available_ram_min_GiB=None if not math.isfinite(minram) else minram,disk_free_min_GiB=None if not math.isfinite(mindisk) else mindisk,package_GiB=packagebytes/1024**3,max_parallel_physical_environments=1,BLAS_Torch_threads=1,actual_native_per_job_wall_s=ledger.get('native_steps',0)/walls if walls else None,host='Existing CPU-only CCX33; no expansion or purchase',telemetry_samples=len(resources))
 atomic(R/'RESOURCE_USAGE.json',resource)
 atomic(R/'ATTEMPT_ACCOUNTING.json',dict(time_utc=now(),training_episodes=len(train),STD_training_episodes=len(std),reward_training_episodes=len(rr),development_evaluations=len(dev),reserved_evaluations=len(hold),native_steps=ledger.get('native_steps',0),row_native_sum=sum(r['native_steps'] for r in rows),optimizer_steps=ledger.get('optimizer_steps',0),row_optimizer_sum=sum(r['gradient_updates'] for r in rows),attempts=ledger.get('attempts',[]),open_attempts=[a for a in ledger.get('attempts',[]) if not a['settled']],limits=started['limits'],STD_cap=80,all_global_native_includes_commissioning_and_recovery=True,raw_rows='ALL_ATTEMPTS.jsonl',independent_check=full.get('checks',{})))
 # Clear separation of training success, development screens, final streams and historical references.
 t=['# STD 训练比较','',SCOPE,'','CHECKPOINT_STD 继承实际约 .97–1.00 的可训练 Gaussian STD；STD_INIT_0p2 在空 pending 下只将 log_std 初始化为 log(.2)，随后仍由 PPO 学习。两者完整继承 mean、critic、Adam（包括 log_std 的既有矩）和 RNG。每个分支都用自己的实际新分布生成 raw action 与 log_prob；原 [-1,1] clip 仅用于执行。','',f'实际 STD 训练 {len(std)}/80 集。两方法先各做两父 10 集；仅选定方法允许两父各延长 20 集。没有扩大 STD 网格。','','|分支|父seed|训练完整/attempt|Adam steps|决策数|clip分量率|首次STD|末集初STD|几何/回退拒绝|','|---|---|---|---|---|---|---|---|---|']
 for s in summary:
  if s['mode']=='training' and s['branch'] in ['CHECKPOINT_STD','STD_INIT_0p2']:t.append(f"|{s['branch']}|{s['seed']}|{s['complete']}/{s['attempts']}|{s['optimizer_steps']}|{s['decisions']}|{fmt(s['clip_fraction_weighted'])}|{s['std_first']}|{s['std_last']}|{s['geometry_refusals']}/{s['emitted_reference_refusals']}|")
 t+=['','各端点的 mean/sample 开发评价：','',table([r for r in dev if r['branch'] in ['CHECKPOINT_STD','STD_INIT_0p2']]),'','选择记录：`TRAINING_METHOD_SELECTION.json`；完整逐次 Adam/KL/ratio/actor mean 漂移在 `PPO_TRAINING_RESULTS.json` 和各 UPDATE.json。训练成功率与冻结评价分开，不能把上一轮只在评价时减小 STD 的证据当成本轮训练证据。','',f'开发信号：{flags["PPO_STABILITY_IMPROVED"]}。单条 stochastic 端点评价只能用于有限开发分配；没有证明总体可靠性。']
 t+=['','主方法比较只使用两方法各父前10集；30集是按筛选选择后的单方法延长，没有CHECKPOINT_STD/30对照，不能把不同训练暴露量的结果直接归因于STD。','', '## 实际 PPO 分布漂移','','|分支|父seed|rollout更新|Adam steps|max approximate KL|ratio min/max|max mean RMS漂移|末STD|','|---|---|---|---|---|---|---|---|']
 for u in update_summaries:
  if u['branch'] in ['CHECKPOINT_STD','STD_INIT_0p2']:t.append(f"|{u['branch']}|{u['seed']}|{u['rollout_updates']}|{u['Adam_steps']}|{fmt(u['max_full_rollout_approx_KL'])}|{fmt(u['ratio_min'])}/{fmt(u['ratio_max'])}|{fmt(u['max_actor_mean_RMS_drift'])}|{u['std_after']}|")
 t+=['','STD更小不保证PPO分布漂移更小。ratio在更新后的极值不是采样归属检查的初始ratio；PPO clip objective不构成最终ratio硬界限。完整保存的GAE/returns已独立重算，见PPO_ADVANTAGE_AUDIT.json。','', '安全终止与执行归属另见audit/SESSION_CLEARANCE_EVENT_CLASSIFICATION.json及REWARD_CREDIT_ASSIGNMENT_AUDIT.md。']
 doc('STD_TRAINING_COMPARISON.md','\n'.join(t))
 rt=['# R1 / R4 Reward 比较','',SCOPE,'','R4 唯一目标变化是 cuff moment 的价格由 .005 增至 .020 /(Nm·s)。其余进度、成功/失败、JF、online variation 与失败总代价 floor 均保持 R1；失败补偿按 R4 新成本重算。gamma=1，GAE lambda=.95。actor 只消费原 41D 因果观测；native truth 只用于独立评价。','',f'R4 已评价：{flags["REWARD_R4_EVALUATED"]}。本轮 Reward 训练 {len(rr)} 集。共同父和采样/优化配置在 `REWARD_EXPERIMENT_LOCK.json` 先冻结。两分支初始全状态相同，Reward 开始影响更新后，状态和样本分离，不声称同轨迹比较。','','下表为 R4−R1；只有完整等时 pair 才计算 JF/JM 与运动差。','',comparison_text(reward_pairs),'','全部逐条开发结果：','',table([r for r in dev if r['branch'].startswith('REWARD_') or r['branch'].startswith('PAIRED_DEV2_')]),'',f'最终保留 Reward：{selection.get("reward","尚未锁定")}；理由：{selection.get("reason","尚未锁定")}。','', 'JM 降低而任务失败增加不晋级；JM 降低/JF 上升必须保留取舍。额外开发动作流 2026102202 单列，未改变预先固定的主选择规则。训练 Reward 的跨版本大小未用于选优；没有用最终保留动作流修改 Reward。']
 doc('R1_R4_REWARD_COMPARISON.md','\n'.join(rt))
 doc('TASK_FORCE_MOMENT_MOTION.md','\n'.join(['# 任务、Force、Moment 与真实 Human Motion','',SCOPE,'','开发冻结评价：','',table(dev),'','最终预留流：','',table(hold),'','选定 mean 对历史 R1/60 mean：','',comparison_text(baseline_pairs),'','历史比较只作已见、完整等时 nominal 诊断；最终流不为不同模型补选有利样本。所有失败保留 FAILED_PARTIAL_TASK 身份和原 reason；partial 低 JF/JM 不参与完整性能晋级。jerk 是 native 速度后向差分的诊断量，无新造合格阈值。']))
 pre=read(R/'audit/ADMISSION_PREFLIGHT.json');audittext=['# 训练准入审计','',f'ACTIVATION UTC：{activation["activation_utc"]}。硬截止：{started["hard_stop_utc"]}。物理收尾窗口：{started["no_new_physics_utc"]} 起。','', '原正式 launcher 的 inspect() 未修改并在隔离启动器中原样执行，核对模板、447 文件合同、完整父 ZIP/RNG/metadata 和硬预算。新启动器因本轮 STD 总量 80 与最后 45 分钟要求，版本化修正队列；未修改原模板或历史 ACTIVATION。','', '准入独立进程未 reset 物理或调用 Adam；两父 snapshot、actor mean/critic hash、log_std trainable 与 Adam 参数归属、空 pending、原分布与新分布密度检查均通过。旧 log_prob 在修改 STD 后被测试拒绝。R1/R4 保存轨迹重放、失败 floor、potential 闭环测试通过。','',f'保存轨迹 Reward 重放 {len(pre["reward_saved_raw_replays"])} 项，历史包 {pre["origin_manifest"]["entries"]} 文件 SHA 核验；预留流检索 {pre["reserved_streams"]["checked_records"]} 项，无已执行命中。','', 'log_std 初始化保留既有 Adam 一阶/二阶矩和 step；这是明确的继承合同，不等同于重置优化器。之后 std 可以变化；更新前 evaluate_actions 必须重现每个旧 log_prob，raw Gaussian 用于 PPO ratio，clip 只用于物理执行。','', '只接受完整 generation metadata 与 payload SHA；episode pending 保存 policy/reward 身份；Reward 分叉与 STD 改分布前 pending 必须为空。partial Adam 不自动晋级。','', f'最终独立全量审计：{full.get("pass_","等待")}', '', '源码：audit/launch.py、audit/ISOLATED_TEMPLATE_IDENTITY.json、ACTIVATION.json、source_versions/。原物理/任务/硬安全/准入/scorer 不变；没有 Git 写入、Stage2 或最终大规模 Campaign。']
 doc('TRAINING_ADMISSION_AUDIT.md','\n'.join(audittext))
 # Export flat training curves. Plot with a standard plotting library, retaining standalone artifacts.
 curve=R/'TRAINING_CURVES';curve.mkdir(exist_ok=True)
 with (curve/'training.csv').open('w',newline='') as f:
  fields=['branch','seed','index','success','training_reward','JF','JM','task_s','raw_clipped_fraction','entropy_mean','gradient_updates'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in train)
 atomic(curve/'updates.json',updates)
 if not live:
  try:
   os.environ['MPLCONFIGDIR']=str(R/'analysis_tools/mpl-cache');import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
   fig,ax=plt.subplots(3,2,figsize=(12,10),layout='constrained')
   for (branch,seed),rrr in __import__('itertools').groupby(sorted(train,key=lambda r:(r['branch'],r['seed'],r['index'])),key=lambda r:(r['branch'],r['seed'])):
    xx=list(rrr);ep=[r['index'] for r in xx];label=f'{branch}/{seed}'
    for axes,key in zip(ax.flat,['success','raw_clipped_fraction','JF','JM','entropy_mean','gradient_updates']):axes.plot(ep,[r[key] for r in xx],marker='.',label=label,linewidth=1)
   for axes,title in zip(ax.flat,['Runtime completion (training)','Clipped raw components','JF (includes marked failed partials)','JM (includes marked failed partials)','Gaussian entropy before clipping','Adam steps per episode']):axes.set_title(title);axes.set_xlabel('Continuation episode');axes.grid(alpha=.2)
   if train:ax[0,0].legend(fontsize=5,loc='best')
   fig.savefig(curve/'training_curves.png',dpi=160);fig.savefig(curve/'training_curves.pdf');plt.close(fig)
   doc('TRAINING_CURVES/README.md','# 训练曲线\n\n每条线是独立分支/父；失败 partial 的 JF/JM 只作为原值画出，不能用于任务效率排名。训练 Reward 不跨版本比较；success 表示真实 runtime 完整任务。原 CSV 和更新诊断一并提供。')
  except BaseException as e:atomic(curve/'PLOT_ERROR.json',dict(error=repr(e)))
 # Final report answers every requested question using explicit observed scope.
 early='有限核心清单、独立保留流与审计已完成；未为了填满 8 小时重复计算，也未新增未经机制证据支持的 Reward 候选。' if hours<7 else '按原激活时钟和硬预算进入收尾。'
 r4mean=[p for p in reward_pairs if p['mode']=='deterministic'];r4desc='；'.join(f"父{p['seed']}: 完整等时={p['complete_equal_duration']}, ΔJF={fmt(p['JF_percent'])}%, ΔJM={fmt(p['JM_percent'])}%" for p in r4mean) or '尚无完整配对证据'
 train_desc='；'.join(f"{s['branch']}/父{s['seed']} {s['complete']}/{s['attempts']}" for s in summary if s['mode']=='training' and s['branch'] in ['CHECKPOINT_STD','STD_INIT_0p2']) or '无已完成训练'
 meanpass=[f"{r['branch']}/父{r['seed']}/端点{r['index']-1}" for r in dev if r['policy_mode']=='deterministic' and r['success']]
 hold_desc='；'.join(f"父{x['seed']} {x['complete']}/{x['attempts']}" for x in hold_per)
 state='RUNNING' if live else 'STOP' if end else queue.get('status','INCOMPLETE')
 report=['# iHEAR Lab — 自主 PPO / STD 与 R4 研究报告','',f'状态：**{state}**。ACTIVATION：{activation["activation_utc"]} UTC；硬截止：{started["hard_stop_utc"]}。', '', SCOPE,'',f'已完成训练 {len(train)} 集（STD {len(std)}/80），开发冻结 {len(dev)}/24，最终预留流 {len(hold)}/12；native {ledger.get("native_steps",0):,}/33,000,000，Adam step {ledger.get("optimizer_steps",0)}，完整 rollout 更新 {len(updates)} 次。', '', '## 本轮结果','',*['|状态|判定|','|---|---|'],*[f'|{k}|{v}|' for k,v in flags.items()],'','## 二十项回答','',f'1. **实际运行多久？** 从实际 ACTIVATION 到物理队列关闭 {hours:.4f} 小时；完整归档结束时间见 FINALIZATION_END.json。激活时钟未重置。',f'2. **按预算结束？** 队列状态 `{queue.get("status","运行中")}`；训练/评价/native 数见上。{early}',f'3. **两种 STD 方法？** CHECKPOINT_STD 继承原约 .97–1.00 的可训练 STD；STD_INIT_0p2 只初始化 log_std=.2 并继承完整 Adam，后续 STD 仍可学习。mean/critic/RNG 相同身份分叉，无旧密度或跨分布 pending 混用。',f'4. **任务保留谁更好？** 训练观察：{train_desc}。冻结端点另见 STD_TRAINING_COMPARISON.md，预定方法选择为 `{method.get("method","尚未选择")}`。',f'5. **训练时减 STD 改善执行？** `{flags["PPO_STABILITY_IMPROVED"]}`。判断基于本轮真实训练与独立端点，不沿用上轮评价 override 结论。两父逐项完成/拒绝/clip 均保留；小样本不等于总体可靠。','6. **是否牺牲探索或 PPO 学习？** 较小 STD 明确缩小 pre-clip Gaussian 探索与 differential entropy；实际 rollout、Adam、KL/ratio/loss、actor mean RMS 漂移和 STD 演化逐次保存。若仍有更新，只能证明学习入口工作，不能证明长期探索充分；原 Adam 的 std 矩继承是已声明耦合。',f'7. **R4 减少 moment？** {r4desc}。仅完整等时结果比较；选择 `{selection.get("reward","尚未锁定")}`，不以训练 Reward 大小跨版本排序。','8. **force 和 Human motion 代价？** R1_R4_REWARD_COMPARISON.md 列逐父 ΔJF/ΔJM、膝 tracking、native jerk 和 RETURN overshoot；减少 JM 而增加 JF 或破坏完整任务均明确保留取舍，不笼统称改进。',f'9. **哪些通过冻结 mean？** {"；".join(meanpass) or "暂无新的 mean 完整端点"}。',f'10. **哪些通过新随机流？** 锁定候选 `{selection.get("reward")}/{selection.get("method")}`：{hold_desc}。逐条失败原样保留；无最终流后调参。','11. **reward hacking 或安全异常？** 观察范围由 audit/INDEPENDENT_FULL_AUDIT.json 的 native/receipt、原 ROM/速度/加速度/torque/force/moment/clearance/contact、因果 firewall 与 Reward 复算共同界定。失败 floor 及完整/partial 身份未改变。未通过审计时 DEVELOPMENT_TRAINING_VALID 不得写 PASS。',f'12. **两父一致性？** STD 方法按两父完整端点共同筛选；R4 两父 mean 方向：{r4desc}。不合并两个父的成功次数冒充单策略可靠率。',f'13. **JF 与 JM 同时改善？** 对选定 mean 与历史 R1/60，跨两父同时降低的观察：{forcegood and momentgood}。此为已见 nominal 完整等时诊断，仍非 B/H150 live matched 科学收益。',f'14. **保留哪个 checkpoint？** `{selection.get("checkpoints","尚未锁定")}`；完整 ZIP/RNG/metadata SHA 在 FINAL_SELECTION_BEFORE_HOLDOUT.json 和 CHECKPOINT_STABILITY_AUDIT.json。保留两父独立身份，不选全局赢家父。','15. **Gaussian STD 未解释机制？** clip 会同时改变 bounded proposal 的一阶矩；边界外 mean 与双进度协调可能仍引起 RETURN geometry/回退拒绝。轨迹分离后，末步失败不能唯一归于 STD、clip 或此前路径；需要固定失败状态的安全机制诊断。','16. **可开展更大多 seed 研究？** 本轮只提供有界开发证据。候选若保留两父任务且采样/优化审计通过，可据此提出受控多 seed 开发方案；本轮不自动启动更大研究或最终 Campaign。','17. **G4/live matched/Stage2 缺什么？** G4 严格矩阵和自然极端失败链未闭合；新 PPO 缺原同父 prefix 可移植 fork、B/H150 同链 live matched 和独立合法初态/跨患者验证。离线 scorer 复现不能替代它们。',f'18. **CCX33 够用？** 本轮单物理环境，最小可用 RAM {fmt(resource["available_ram_min_GiB"],3)} GiB，最小磁盘余量 {fmt(resource["disk_free_min_GiB"],3)} GiB，包大小 {resource["package_GiB"]:.3f} GiB；实际 native/job wall 吞吐 {fmt(resource["actual_native_per_job_wall_s"],2)}。这些数据支持本轮预算，不代表任意扩展都足够。','19. **哪些代码值得回流 GitHub？** 经复核的 STD80 有限队列、完整 sampling-density guard、episode pending generation、全状态恢复/因果 Reward 重放、最终 SHA 锁与原始完整/partial 审计。先 review 与独立测试；本轮没有 Git commit/push/merge/reset/stash/clean。','20. **下一步研究？** 按已保存选定两父 checkpoint，先建立新 PPO 的同父 prefix 可移植 fork 与原 B/H150 同链 live matched；保留 RETURN 拒绝反例，之后才讨论正式科学资格。','','## 全部冻结评价','',table(ev),'','## 工程与关闭','',f'完整准入：TRAINING_ADMISSION_AUDIT.md。逐分支决策：AUTONOMOUS_RESEARCH_DECISIONS.jsonl。源码与父 hash：ACTIVATION.json / source_versions / CHECKPOINT_STABILITY_AUDIT.json。最终审计：{full.get("pass_","等待")}。','', '原 handoff 目录及父文件最终 SHA 再核验；原物理/安全/任务/native-control-bridge-lifecycle/planner/admission/scorer 未修改。原历史失败未覆盖。Stage2 与最终大规模 Campaign 未启动。包内新代码均隔离、独立可定位。']
 report+=['','## 额外机制证据','', 'PPO_DISTRIBUTION_SUMMARY.json列实际更新后KL/ratio/mean漂移，PPO_ADVANTAGE_AUDIT.json逐次独立重算gamma=1/lambda=.95的GAE与returns。REWARD_CREDIT_ASSIGNMENT_AUDIT.md解释成功moment价格与失败floor补偿的区别；ACTION_EXECUTION_DIAGNOSTICS.json保留末次失败mean/std/raw/clip及所有FAILED/REJECTED归属。','', '曾出现SESSION_CLEARANCE_LIMIT：原保守因果session模型裕量−0.0579115mm，原guard终止任务；该例实际TASK shank clearance最小+8.98103mm，无真实接触，原native安全检查通过。记录为受保护的失败partial，未放宽guard，也不将它写成安全或任务通过；完整分类见audit/SESSION_CLEARANCE_EVENT_CLASSIFICATION.json。']
 doc('REPORT.md','\n'.join(report))
 readiness=['# 最终 Campaign 准备状态','', '|状态|判定|','|---|---|',*[f'|{k}|{flags[k]}|' for k in ['G4_STRICT_PASS','NEW_LIVE_MATCHED_READY','STAGE2_READY','FINAL_CAMPAIGN_READY']],'', '本轮开发训练许可不等于正式科学晋级；缺原同父 prefix 可移植 fork、B/H150 live matched、严格 G4 和独立初态/跨患者资格。本轮完成后 STOP，不自动启动下一包。']
 doc('FINAL_CAMPAIGN_READINESS.md','\n'.join(readiness))
 doc('NEXT_RESEARCH_DECISION.md','# 下一研究决策\n\n唯一推荐：基于本轮保存的两父完整候选建立原同父 prefix 的可移植 fork，完成原 B/H150 同链 live matched 开发验证。所有本轮失败与完整/partial 身份一并保留。G4/Stage2/正式 Campaign 继续关闭。\n\n下一研究包不在当前自动队列中。')
 atomic(R/'ANALYSIS_SUMMARY.json',dict(time_utc=now(),live=live,counts=dict(training=len(train),STD=len(std),development=len(dev),final=len(hold),native=ledger.get('native_steps',0),optimizer=ledger.get('optimizer_steps',0)),qualifications=flags,selected_mean_baseline_pairs=baseline_pairs,R1_R4_pairs=reward_pairs,selected=selection,scope=SCOPE))
 return dict(rows=len(rows),flags=flags,hours=hours)
if __name__=='__main__':print(json.dumps(build('--live' in sys.argv),ensure_ascii=False))
