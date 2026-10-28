"""Reconstruct requested deliverables from saved attempt evidence, never invent data."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
import json,os,sys,time,shutil
from research_common import ROOT,RUNTIME,STATE,HARD_STOP,NO_TRAIN,atomic,read,resources,now,sha
from report_status import snapshot
from stability_lineages import resolve,retained as retained_lineages,latest_mean,longest_mean_evidence
T0=datetime.fromisoformat(STATE['t0_utc']).timestamp()
SEEDS=[1495656323,1630784693]

def text(name,value): (ROOT/name).write_text(value)
def rows():
    out=[]
    p=ROOT/'ALL_ATTEMPTS.jsonl'
    if p.exists():
        for line in p.read_text().splitlines():
            try:out.append(json.loads(line))
            except json.JSONDecodeError:continue
    return out
def build(final=False):
    allrows=rows();train=[x for x in allrows if x['mode']=='training'];ev=[x for x in allrows if x['mode']=='evaluation']
    ledger=read(ROOT/'LEDGER.json',{})
    official_end=read(ROOT/'END.json',{})
    study_end=official_end.get('unix',time.time()) if final and official_end.get('status')=='STOP' else time.time()
    elapsed=(study_end-T0)/3600
    enriched=[]
    for x in ev:
        metric=read(Path(x['run'])/'COMMON_MOTION_METRICS.json')
        checkpoint_meta=read(Path(x['parent']).with_suffix('.json'),{})
        policy_reward=checkpoint_meta.get('research_config',{}).get('reward','R0')
        evaluation_dir=Path(x['run']).parent
        evaluation_config=read(evaluation_dir/'EFFECTIVE_CONFIG.json') or read(evaluation_dir/'START.json',{}).get('config',{})
        enriched.append(dict(**x,common_motion_metrics=metric,
              trained_policy_reward_version=policy_reward,evaluation_reward_contract=x['reward_version'],
              evaluation_rng=evaluation_config.get('evaluation_rng'),evaluation_split=evaluation_config.get('evaluation_split','development'),
              evaluation_reward_note='Frozen physical evaluation retains original R0 reward arithmetic for common audit; candidate training Reward is identified separately from checkpoint metadata.'))
    atomic(ROOT/'FROZEN_EVALUATION_RESULTS.json',dict(generated_utc=now(),final=final,evaluations=enriched,
           scope='Nominal development; no independent physical initial-state or full B/H150 live matched qualification',
           evaluated_attempts=ledger.get('evaluation_attempts',0),successful_recorded=sum(x['success'] for x in ev)))
    groups=defaultdict(list)
    for x in allrows:groups[x['branch']].append(x)
    lineage_map=read(ROOT/'STABILITY_LINEAGES.json',{}).get('branch_to_lineage',{})
    lineage=resolve(allrows,lineage_map)
    qualification_groups=lineage['groups'] if not lineage['errors'] else {}
    atomic(ROOT/'audit/STABILITY_LINEAGE_AUDIT.json',dict(generated_utc=now(),
        **{k:v for k,v in lineage.items() if k!='groups'},
        failed_mean_endpoints=[dict(lineage=b,job=x['job_id'],seed=x['seed'],endpoint=x['index']-1)
           for b,xs in lineage['groups'].items() for x in xs
           if x['mode']=='evaluation' and x['policy_mode']=='deterministic' and not x['success']],
        physical_attempts=0,optimizer_updates=0))
    summary={}
    for b,xs in groups.items():
        tr=[x for x in xs if x['mode']=='training'];ee=[x for x in xs if x['mode']=='evaluation']
        perseed={}
        for s in sorted({x['seed'] for x in xs}):
            ss=[x for x in ee if x['seed']==s]
            last=max((x['index'] for x in ss),default=None)
            perseed[str(s)]=dict(training_attempts=sum(x['seed']==s for x in tr),
                training_successes=sum(x['seed']==s and x['success'] for x in tr),endpoint=last-1 if last else None,
                final_evaluations=[dict(job=x['job_id'],mode=x['policy_mode'],success=x['success'],
                  status=x['status'],task_s=x['task_s'],JF=x['JF'],JM=x['JM'],run=x['run'],parent=x['parent']) for x in ss if x['index']==last])
        summary[b]=dict(training_recorded=len(tr),training_successes=sum(x['success'] for x in tr),
            native_steps=sum(x['native_steps'] for x in xs),gradient_updates=sum(x['gradient_updates'] for x in tr),
            evaluation_recorded=len(ee),perseed=perseed,
            singleton_minibatches=sum(x['update']['singleton_minibatches'] for x in tr if x['update']))
    atomic(ROOT/'CHECKPOINT_COMPARISON.json',dict(generated_utc=now(),branches=summary,
        preserved_successful_parents=[str(ROOT.parent/f'rl_b_autonomous_replication_v1/seeds/{s}/stage1/checkpoints/episode_050') for s in SEEDS],
        drift_details='CHECKPOINT_POLICY_DIAGNOSTICS.json',raw='FROZEN_EVALUATION_RESULTS.json',
        lineage_audit='audit/STABILITY_LINEAGE_AUDIT.json',branch_to_lineage=lineage_map,
        restriction='Do not collapse different checkpoints or deterministic nominal repeats into independent success-rate trials'))
    rewards={k:v for k,v in summary.items() if k.startswith('REWARD_')}
    additional_studies=read(ROOT/'ADDITIONAL_REWARD_STUDIES.json',{}).get('studies',[])
    additional_checks=[]
    for study in additional_studies:
        result_path=ROOT/study.get('result_path','MISSING_ADDITIONAL_REWARD_RESULT')
        result=read(result_path,{})
        verified=study.get('status')=='COMPLETE' and result_path.is_file() and study.get('result_sha256')==sha(result_path) and result.get('status')=='COMPLETE_BOUNDED_DEVELOPMENT_COHORT' and result.get('reward')==study['reward']
        additional_checks.append(dict(reward=study['reward'],status=study.get('status'),completion_verified=verified,result_path=str(result_path.relative_to(ROOT))))
    search_complete=(ROOT/'FINITE_QUEUE_COMPLETE.json').exists() and all(x['completion_verified'] for x in additional_checks)
    atomic(ROOT/'REWARD_SEARCH_RESULTS.json',dict(generated_utc=now(),final=final,status='COMPLETED' if search_complete else 'INCOMPLETE' if final else 'RUNNING',
         branches=rewards,registered_additional_studies=additional_checks,
         reward_retention_followups={alias:summary[alias] for alias,base in lineage_map.items() if base.startswith('REWARD_') and alias in summary},
         branch_count_scope='Raw execution branch counts; linked retention followups must be included when reporting each Reward full cost.',
         common_evaluation='FROZEN_EVALUATION_RESULTS.json',
         decisions='RESEARCH_DECISION_LOG.jsonl',selection='Lexicographic safety/full completion, retention, complete-task dose and actual Human motion'))
    endchecks=read(ROOT/'audit/HISTORICAL_PROTECTION_END.json',{})
    all_audit=all(x.get('independent_audit_pass') for x in allrows)
    failed_physics=[a for a in ledger.get('attempts',[]) if a.get('outcome') not in ['COMPLETE','ABORTED'] and a.get('settled')]
    quals=dict(
        DEVELOPMENT_TRAINING_VALID=dict(status='PASS' if all_audit and allrows and not failed_physics else 'IN_PROGRESS_OR_REVIEW_REQUIRED',scope='Observed isolated development attempts only; inherited + affected tests',evidence=['audit/DEVELOPMENT_LEVEL_A.json','ALL_ATTEMPTS.jsonl']),
        PPO_STABILITY_IMPROVED=dict(status='NOT_YET_ESTABLISHED',scope='Read complete per-seed checkpoint trajectories; no independent initial-state qualification',evidence=['H1_STABILITY_RESULTS.json','CHECKPOINT_COMPARISON.json']),
        REWARD_SEARCH_COMPLETED=dict(status='PASS' if search_complete else 'INCOMPLETE' if final else 'IN_PROGRESS',scope='Bounded development search; success of a reward is a separate question',evidence=['REWARD_SEARCH_RESULTS.json','REWARD_VERSION_MANIFEST.json']),
        RUNTIME_TASK_SUCCESS=dict(status='PASS' if any(x['success'] for x in ev) else 'NOT_ESTABLISHED',scope='Only explicitly listed frozen checkpoints and nominal action streams',evidence=['FROZEN_EVALUATION_RESULTS.json']),
        FORCE_IMPROVEMENT=dict(status='NOT_ESTABLISHED',scope='Only complete, equal-duration same-seed nominal parent comparisons can support descriptive dose improvement',evidence=['TASK_FORCE_MOTION_COMPARISON.md']),
        MOTION_QUALIFIED=dict(status='OBSERVED_EPISODE_AUDITS_PASS' if all_audit and ev else 'NOT_ESTABLISHED',scope='No independent generalization, full matched or all-action qualification; jerk diagnostic only',evidence=['FROZEN_EVALUATION_RESULTS.json']),
        G4_STRICT_PASS=dict(status='FAIL',scope='Historical natural extreme paths and complete strict safety matrix remain unclosed',evidence=[str(ROOT.parent/'rl_b_autonomous_replication_v1/G4_NATURAL_PATH_UPDATE.json')]),
        NEW_LIVE_MATCHED_READY=dict(status='NOT_READY',scope='New PPO lacks original same-parent-prefix portable fork/B/H150 live matched chain',evidence=[str(ROOT.parent/'rl_b_matched_recovery_stability_v1/FROZEN_SCORER_VALIDATION.md')]),
        STAGE2_READY=dict(status='NOT_READY',scope='G4/live matched/independent legal initial-state and retained stability gates not closed',evidence=['GENERALIZATION_AUDIT.md']),
        FINAL_CAMPAIGN_READY=dict(status='NOT_READY',scope='Final large-scale Campaign not authorized or started',evidence=['FINAL_CAMPAIGN_READINESS.md']))
    # Nominal stability support requires both seeds at every tested deterministic
    # endpoint, and each seed at least a 30-episode continuation endpoint.
    retained=retained_lineages(qualification_groups,SEEDS)
    if retained:
        windows={b:sorted({x['index']-1 for x in qualification_groups[b] if x['mode']=='evaluation' and x['policy_mode']=='deterministic'}) for b in retained}
        quals['PPO_STABILITY_IMPROVED'].update(status='SUPPORTED_NOMINAL_DEVELOPMENT',supported_branches=retained,
             tested_continuation_endpoints=windows,
             scope='Two selected successful050 parents retained mean completion at the explicitly tested nominal endpoints; longer continuation, stochastic robustness and independent initial-state qualification remain separate')
    else:
        partial={}
        for b,xs in qualification_groups.items():
            for seed in SEEDS:
                ee=[x for x in xs if x['mode']=='evaluation' and x['policy_mode']=='deterministic' and x['seed']==seed]
                if ee and max(x['index'] for x in ee)>=31 and all(x['success'] for x in ee):
                    partial.setdefault(b,[]).append(seed)
        if partial:
            quals['PPO_STABILITY_IMPROVED'].update(status='PARTIAL_NOMINAL_PARENT_RETENTION',
                  supported_parent_seeds=partial,
                  scope='Only listed parents retained mean success across tested endpoints; no uniform two-parent stability or independent initial-state qualification')
    history=ROOT.parent/'rl_b_autonomous_replication_v1'
    parent_rows=[json.loads(l) for l in (history/'ALL_EVALUATION_LOG.jsonl').read_text().splitlines()]
    parent={x['training_seed']:x for x in parent_rows if x['kind']=='checkpoint050_first' and x['training_seed'] in SEEDS}
    comparisons=[]
    for x in enriched:
        p=parent[x['seed']];comparable=x['success'] and p['success'] and x['policy_mode']=='deterministic' and abs(x['task_s']-p['task_s'])<1e-7
        comparisons.append(dict(job=x['job_id'],branch=x['branch'],lineage=lineage_map.get(x['branch'],x['branch']),seed=x['seed'],success=x['success'],
             continuation_endpoint=x['index']-1,
             mode=x['policy_mode'],task_s=x['task_s'],JF=x['JF'],JM=x['JM'],scope=x['integral_scope'],
             parent_nominal_same_duration_comparable=comparable,
             parent_JF=p['JF'],parent_JM=p['JM'],JF_relative_percent=(x['JF']/p['JF']-1)*100 if comparable else None,
             JM_relative_percent=(x['JM']/p['JM']-1)*100 if comparable else None,
             motion=x['common_motion_metrics']))
    atomic(ROOT/'COMPLETE_TASK_DOSE_COMPARISON.json',dict(comparisons=comparisons,formal_B_H150_comparison='NOT_AVAILABLE_FOR_NEW_PPO'))
    force_support={}
    for branch in retained:
        selected=[]
        for seed in SEEDS:
            last=latest_mean(comparisons,branch,seed)
            if last:
                if last['parent_nominal_same_duration_comparable'] and last['JF_relative_percent']<0:selected.append(last)
        if len(selected)==len(SEEDS):
            force_support[branch]=[dict(job=x['job'],seed=x['seed'],JF_change_percent=x['JF_relative_percent'],
                 JM_change_percent=x['JM_relative_percent'],task_s=x['task_s']) for x in selected]
    if force_support:
        quals['FORCE_IMPROVEMENT'].update(status='SUPPORTED_NOMINAL_MEAN_ONLY',
             scope='Listed equal-duration COMPLETE nominal mean tasks versus each selected parent050; JM tradeoffs remain, no original B/H150 live matched or generalization qualification',
             supported_branches=force_support,formal_matched_status='NOT_READY')
    horizon_evidence=longest_mean_evidence(qualification_groups,retained,SEEDS)
    quals['PPO_STABILITY_IMPROVED']['horizon_evidence']=horizon_evidence
    if retained and horizon_evidence['longest_tested_mean_endpoint']>30 and not horizon_evidence['supported_at_longest_endpoint']:
        quals['PPO_STABILITY_IMPROVED']['status']='SUPPORTED_SHORT_WINDOW_LONGER_REGRESSION' if horizon_evidence['two_parent_families_tested_at_longest'] else 'SUPPORTED_SHORT_WINDOW_LONGER_TEST_INCOMPLETE'
    quals['PPO_STABILITY_IMPROVED']['lineage_audit']='audit/STABILITY_LINEAGE_AUDIT.json'
    if lineage['errors']:
        quals['PPO_STABILITY_IMPROVED'].update(status='REVIEW_REQUIRED',lineage_errors=lineage['errors'])
    quals['RUNTIME_TASK_SUCCESS'].update(successful_frozen_job_ids=[x['job_id'] for x in ev if x['success']],
             failed_frozen_attempts=sum(not x['success'] for x in ev))
    atomic(ROOT/'QUALIFICATIONS.json',dict(generated_utc=now(),qualifications=quals))
    body='# 完整任务 force/moment 与真实 Human 运动\n\n同seed父checkpoint050名义确定性评价作为开发参照。不同任务时长或失败partial不计算相对收益；随机轨迹的JF/JM只作描述。新PPO没有原同父prefix/B/H150完整matched链，不能宣称优于B/H150。\n\n'
    body+='|job|完整完成|模式|TASK s|JF N·s|JM Nm·s|同父JF变化%|同父JM变化%|\n|---|---|---|---|---|---|---|---|\n'
    for x in comparisons:
        f=lambda a:'—' if a is None else f'{a:.5f}'
        body+=f'|{x["job"]}|{x["success"]}|{x["mode"]}|{x["task_s"]:.5f}|{x["JF"]:.6f}|{x["JM"]:.6f}|{f(x["JF_relative_percent"])}|{f(x["JM_relative_percent"])}|\n'
    body+='\nJF/JM沿用原5ms传感器左端值、按实际已执行区间时长积分，零时长通知不占剂量；不冒称0.25ms force逐步求积。分phase归属与原总量独立核对见audit/PHASE_DOSE_ATTRIBUTION.json。真实native Human q/dq、5ms参考tracking RMS、native速度/加速度/jerk、终末误差及RETURN/OUTBOUND overshoot见每run/COMMON_MOTION_METRICS.json及ACTUAL_HUMAN_TASK_SERIES.npz。没有自造jerk通过阈值。Moment上升必须报告trade-off；低force不能抵消任务或安全失败。\n'
    body+='\n以下运动表仅列完整任务；失败partial保留在上表和完整JSON中。每格按hip/knee顺序；原050行来自只读历史raw的独立重算。\n\n'
    motionrows=[]
    for seed in SEEDS:
        pm=read(ROOT/f'audit/parent_motion/{seed}/COMMON_MOTION_METRICS.json')
        if pm:motionrows.append((f'原050/{seed}',pm))
    for x in comparisons:
        if x['success'] and x['motion']:motionrows.append((x['job'],x['motion']))
    pair=lambda v:' / '.join(f'{z:.5f}' for z in v) if v is not None else 'UNAVAILABLE'
    body+='|完整任务|tracking RMS °|velocity RMS °/s|acceleration RMS °/s²|jerk RMS °/s³|\n|---|---|---|---|---|\n'
    for name,m in motionrows:
        body+=f'|{name}|{pair(m["tracking_RMS_deg"])}|{pair(m["velocity_RMS_deg_s"])}|{pair(m["acceleration_RMS_deg_s2"])}|{pair(m["jerk_RMS_deg_s3"])}|\n'
    body+='\n|完整任务|velocity peak °/s|acceleration peak °/s²|jerk peak °/s³|\n|---|---|---|---|\n'
    for name,m in motionrows:
        body+=f'|{name}|{pair(m["velocity_peak_deg_s"])}|{pair(m["acceleration_peak_deg_s2"])}|{pair(m["jerk_peak_deg_s3"])}|\n'
    body+='\n|完整任务|terminal q °|terminal dq °/s|terminal absolute return error °|RETURN overshoot below goal °|OUTBOUND overshoot above goal °|\n|---|---|---|---|---|---|\n'
    for name,m in motionrows:
        body+=f'|{name}|{pair(m["terminal_q_deg"])}|{pair(m["terminal_dq_deg_s"])}|{pair(m["terminal_return_absolute_error_deg"])}|{pair(m["RETURN_overshoot_below_goal_deg"])}|{pair(m["OUTBOUND_overshoot_above_goal_deg"])}|\n'
    text('TASK_FORCE_MOTION_COMPARISON.md',body)
    resource_rows=[read(p) for p in (ROOT/'jobs').glob('*/LIVE.json')]
    synthetic_Adam=sum(read(ROOT/'audit'/name,{}).get('synthetic_Adam_updates',0)
         for name in ['H2_AGGREGATION_ENGINEERING_TEST.json','PENDING_BUFFER_EQUIVALENCE_TEST.json'])
    atomic(ROOT/'RESOURCE_USAGE.json',dict(generated_utc=now(),elapsed_h=elapsed,current=resources(),
        observed_job_minimum_available_GiB=min((x['resources']['minimum_available_GiB'] for x in allrows),default=None),
        package_bytes=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()),
        environment='CPU-only; one owned physical environment; one Torch/BLAS thread',jobs=len(list((ROOT/'jobs').glob('*/START.json'))),
        engineering_only_synthetic_Adam_updates=synthetic_Adam,synthetic_updates_in_task_training_ledger=False,
        process_limits='Per-attempt 300s/128 decisions/165000 native; per-job outer timeout; independent PID-identity watchdog',
        limits=STATE['limits']))
    atomic(ROOT/'ATTEMPT_ACCOUNTING.json',dict(generated_utc=now(),ledger=ledger,
        program_attempts=[dict(job=p.parent.name,start=read(p),end=read(p.parent/'END.json')) for p in (ROOT/'jobs').glob('*/START.json')],
        physical_attempts_include_early_failures=True,uncertain_native_reservation_policy='Charge full165000 after abnormal unclosed worker exit',
        recorded_rows=len(allrows),START_END_closed=all((Path(a['run'])/'END.json').exists() for a in ledger.get('attempts',[]))))
    text('FINAL_CAMPAIGN_READINESS.md','# 最终 Campaign 资格\n\n**FINAL_CAMPAIGN_READY=NOT_READY；不得自动启动。**\n\n'+
        '\n'.join(f'- {k}：{v["status"]}；{v["scope"]}。' for k,v in quals.items())+'\n\n开发nominal成功与正式资格分离；历史离线B/H150复现PASS不等于新live matched链就绪。\n')
    reviewed_next=ROOT/'FINAL_NEXT_RESEARCH_DECISION.md'
    text('NEXT_RESEARCH_DECISION.md',reviewed_next.read_text() if reviewed_next.exists() else '# 下一研究决策\n\n本包结束后不自动启动下一包或正式Campaign。\n\n唯一建议下一步：在本包冻结证据上审阅保留最佳候选，优先闭合合法独立初态与原runtime完成保持的共同开发验证合同；保持G4及live matched缺口独立可见。\n')
    table='|分支|训练完成/记录|Adam steps|冻结评价数|\n|---|---|---|---|\n'
    for b,g in summary.items():table+=f'|{b}|{g["training_successes"]}/{g["training_recorded"]}|{g["gradient_updates"]}|{g["evaluation_recorded"]}|\n'
    answers=[
      f'实际elapsed：{elapsed:.3f}小时；T0为{STATE["t0_client"]}，当前UTC {now()}。'+('本报告为最终封存稿。' if final else '研究仍在进行，不能把阶段报告视作STOP。'),
      '分支依据：历史mean累计漂移及RETURN准入失败先测H1；single-transition/singleton与弱critic驱动H2；随后在共同父策略和PPO配置下检验R1/R2等Reward。',
      'H1结果以H1_STABILITY_RESULTS.json和逐seed/逐checkpoint冻结结果为准；不以训练sample成功代替mean保持。',
      'H2消除singleton与任务完成分开评价；Adam步数和样本量见UPDATE_LOG.jsonl。',
      'Reward公式、权重、完整代码及独立SHA见REWARD_CANDIDATES.md、REWARD_VERSION_MANIFEST.json和source_versions。',
      '每候选接受/拒绝与reflection见RESEARCH_DECISION_LOG.jsonl；不同Reward数值不直接比较。',
      '完整runtime成功的明确checkpoint及动作流逐项见FROZEN_EVALUATION_RESULTS.json；失败父子版本均保留。',
      '完整JF相对变化只计算相同seed、同TASK时长的确定性nominal父策略比较，见TASK_FORCE_MOTION_COMPARISON.md；无新B/H150正式收益结论。',
      'JM和真实运动逐项记录；force下降而moment上升是trade-off，jerk没有人为放宽通过标准。',
      '父checkpoint050从未覆盖；权重/Adam/RNG/计数恢复、共享因果观测上的policy漂移与训练代价分别保存。',
      'deterministic与stochastic结果分开保留；动作随机流不等于独立物理患者样本。',
      '已完成attempt均做独立reward/物理/receipt/causal/原安全检查；工程失败和安全异常不能混为普通任务失败，未完成检查不补写PASS。',
      '独立合法初态BLOCKED：当前reset seed/options不改变nominal初始化；没有冒充泛化。',
      '仅两个已选成功父seed的继续训练研究；跨seed一致性按全部冻结端点报告，不宣称从零三seed复现。',
      '值得保留的策略必须先满足完整任务和保持门；当前选择与候选出处见STABILITY_SELECTION.json、CHECKPOINT_COMPARISON.json。',
      'Stage2_READY=NOT_READY，开发成功不能代替其科学资格。',
      'G4_STRICT_PASS=FAIL；自然极端路径/严格全矩阵与新live matched同父prefix可移植执行链仍缺。',
      '目前不建议直接开始正式大规模训练；本轮授权也明确排除最终Campaign。',
      'CCX33适合当前单环境CPU开发；资源实测见RESOURCE_USAGE.json，不自动扩容、租赁或迁移Isaac Lab。',
      '下一轮优先解决独立合法初态和成功checkpoint继续训练保持的共同验证合同，随后才讨论正式扩大预算。']
    report='# iHEAR Lab — 自主 PPO 稳定性与 Reward 研究 v1\n\n'+('**最终状态：STOP。**\n\n' if final else '**状态：RUNNING。**\n\n')
    review=ROOT/'SCIENTIFIC_REVIEW.md'
    report+=f'T0：{STATE["t0_client"]}；报告生成UTC：{now()}；elapsed约{elapsed:.3f}小时。\n\n'
    report+=f'实际MuJoCo训练attempt {ledger.get("training_attempts",0)}，冻结评价attempt {ledger.get("evaluation_attempts",0)}，native steps {ledger.get("native_steps",0)}，Adam steps {ledger.get("optimizer_steps",0)}。\n\n'
    report+=f'工程验证另有{synthetic_Adam}次合成Adam更新，无MuJoCo物理attempt，不计作任务训练证据。\n\n'
    report+=table+'\n'
    if review.exists():
        report+=review.read_text()+'\n\n'
        report+='|独立资格|当前状态|范围|\n|---|---|---|\n'
        for k,v in quals.items():report+=f'|{k}|{v["status"]}|{v["scope"]}|\n'
        report+='\n'
    else:
        report+='以下为运行中的交付框架，最终二十问将由实际结果审阅填入。\n\n'
        report+='\n\n'.join(f'{i}. {answer}' for i,answer in enumerate(answers,1))+'\n\n'
    report+='本轮只写新研究包；无Git写操作、主源码覆盖、硬件操作或最终Campaign。实际保护核验见PACKAGE_VERIFICATION.json。全部科学结论限制在保存的证据范围。\n'
    text('REPORT.md',report)
    snapshot()
    return dict(final=final,elapsed_h=elapsed,rows=len(allrows),evaluations=len(ev),branches=summary,qualifications=quals)
if __name__=='__main__':print(json.dumps(build('--final' in sys.argv),ensure_ascii=False))
