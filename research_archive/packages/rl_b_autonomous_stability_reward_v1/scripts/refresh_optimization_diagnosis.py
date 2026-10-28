"""Current mechanism diagnosis from actual saved studies; no model or physics calls."""
from pathlib import Path
from collections import defaultdict
import json,shutil,math,statistics
from research_common import ROOT,read,atomic,sha,now
from stability_lineages import resolve,retained,longest_mean_evidence
SEEDS=[1495656323,1630784693]
def cfg(row):
    p=Path(row['run']).parent
    return read(p/'EFFECTIVE_CONFIG.json') or read(p/'START.json',{}).get('config',{})
def main():
    target=ROOT/'PPO_OPTIMIZATION_DIAGNOSIS.md'
    if target.exists():
        archive=ROOT/'audit/diagnosis_versions'/f'PPO_OPTIMIZATION_DIAGNOSIS_{sha(target)}.md';archive.parent.mkdir(exist_ok=True)
        if not archive.exists():shutil.copyfile(target,archive)
    rows=[json.loads(l) for l in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    mapping=read(ROOT/'STABILITY_LINEAGES.json')['branch_to_lineage'];joined=resolve(rows,mapping);assert joined['status']=='PASS',joined['errors']
    supported=retained(joined['groups'],SEEDS);horizon=longest_mean_evidence(joined['groups'],supported,SEEDS)
    body='# PPO更新与信用分配诊断\n\n'
    body+=f'生成UTC：{now()}。只使用已保存的真实尝试和明确标记的离线探针；最终状态以START/END/STOP及完成审阅为准。旧的阶段性诊断按SHA保存在audit/diagnosis_versions。\n\n'
    body+='原执行因果链是：policy mean变化→准入参考变化→实际receipt torque与Human运动变化→RETURN预测几何候选被原合法性门拒绝→任务ABORTED。它解释具体执行失败，不等于唯一优化根因。原447文件物理/任务/安全闭包保持，41D因果观测和raw Gaussian likelihood保留。提议经clip和原planner/bridge/governor执行，Gaussian KL不是实际torque距离。\n\n'
    body+='## 受控实验与实际训练成本\n\n两个原成功050父各5集Control逐transition、更新后policy、Adam/RNG/计数严格复演后，才复用原051–080对照；没有把历史重用计入新增物理预算。H1只改LR3e-4→1e-4，最终149 mean失败、163 mean成功，最终sample两父均失败，未形成一致两父保持。\n\n'
    body+='|父seed|旧Control完成/30|H1完成/30|Control/H1 decisions|Control/H1实际Adam|\n|---|---|---|---|---|\n'
    for c in read(ROOT/'H1_STABILITY_ANALYSIS.json')['seeds']:
        a=c['control_51_80'];b=c['H1_51_80'];body+=f'|{c["seed"]}|{a["training_successes"]}/30|{b["training_successes"]}/30|{a["decisions"]}/{b["decisions"]}|{a["Adam_steps"]}/{b["Adam_steps"]}|\n'
    body+='\nH2以LR3e-4/R0、相同原050/PPO/动作合同，跨完整episode累计>=64 transitions后更新，保留每个terminal/reset的GAE边界，singleton尾批并入前批（17），全局终末前一集保留余量。gamma1、GAE=.95、4epochs、batch16、clip=.2、entropy=0、vf=.5、joint norm clip=.5、target_kl=None。聚合、尾批组织、PPO.train频率和轨迹分布是一组被检验的更新机制，未分别因果隔离。\n\n'
    body+='下表按已核验谱系合并新增训练，含真实已完成延长段；动态训练完成比例不作为冻结策略成功率，已采样与已优化transition分开。\n\n'
    body+='|家族|父seed|训练成功/已记录|sampled|optimized|实际Adam|PPO.train/epochs|末次pending|\n|---|---|---|---|---|---|---|---|\n'
    for branch in ['H1','H2_AGG64','REWARD_R1','REWARD_R2','REWARD_R3']:
        for seed in SEEDS:
            xs=sorted([x for x in joined['groups'].get(branch,[]) if x['mode']=='training' and x['seed']==seed],key=lambda x:x['index'])
            if not xs:continue
            us=[x['update'] for x in xs if x['update']]
            pending=xs[-1].get('pending_complete_transitions')
            if pending is None:
                assert all(x['update'] and x['update']['rollout']=='episode' for x in xs),'MISSING_AGGREGATE_PENDING_EVIDENCE'
                pending=0
            body+=f'|{branch}|{seed}|{sum(x["success"] for x in xs)}/{len(xs)}|{sum(x["rl_decisions"] for x in xs)}|{sum(x["transitions"] for x in us)}|{sum(x["gradient_updates"] for x in xs)}|{len(us)}/{sum(x["epochs"] for x in us)}|{pending}|\n'
    body+='\nH2两父60的完整mean与最新sample均完成，而163/30 sample失败仍保留。累计935/922 transitions、248/244真实Adam，比旧失败30 Control的561/424、220/188更高；原始Adam总次数更少不足以独自解释保持。独特样本、每次更新组织、访问分布和有效目标仍不同，不能推断唯一根因。H2只冻结测了30/60，没有10/20。R1/R2从共同原050使用相同H2 PPO配置，不串接H2训练后的状态。\n\n'
    historical_training=ROOT.parent/'rl_b_autonomous_replication_v1/ALL_TRAINING_LOG.jsonl'
    oldtrain=[json.loads(l) for l in historical_training.read_text().splitlines()]
    metrics=[]
    names=['train/entropy_loss','train/std','train/approx_kl','train/clip_fraction','train/value_loss','train/explained_variance']
    for branch in ['ORIGINAL_CONTROL_051_080','H1','H2_AGG64','REWARD_R1','REWARD_R2','REWARD_R3']:
        for seed in SEEDS:
            if branch=='ORIGINAL_CONTROL_051_080':
                updates=[x['losses'] for x in oldtrain if x['training_seed']==seed and x['stage']=='stage1' and 51<=x['index']<=80]
                assert len(updates)==30
            else:
                updates=[x['update']['losses'] for x in joined['groups'].get(branch,[]) if x['mode']=='training' and x['seed']==seed and x['update']]
            stats={}
            for name in names:
                vals=[float(x[name]) for x in updates if x.get(name) is not None and math.isfinite(float(x[name]))]
                stats[name]=dict(finite_records=len(vals),median=statistics.median(vals) if vals else None,minimum=min(vals) if vals else None,maximum=max(vals) if vals else None)
            metrics.append(dict(branch=branch,seed=seed,recorded_PPO_train_calls=len(updates),statistics=stats))
    atomic(ROOT/'audit/RECORDED_OPTIMIZER_METRICS.json',dict(time_utc=now(),source_sha256=sha(Path(__file__)),cases=metrics,
        current_attempt_log_sha256=sha(ROOT/'ALL_ATTEMPTS.jsonl'),historical_training_log_sha256=sha(historical_training),
        definition='Unweighted descriptive distribution over recorded PPO.train loss reports; each report itself aggregates its actual epochs/minibatches. Finite values only, each metric has its own finite count. Different visited data and Reward units prevent causal or cross-unit value-loss quality rankings.',new_physics=0,new_Adam=0))
    body+='## 实际记录的优化分布\n\n下表是每次PPO.train记录的未加权median，KL另列最大值；不是按样本加权、共同状态因果估计或最终策略KL。entropy loss为原记录的负熵，std为原Gaussian std；这些数值不是执行torque分布。H1与Control仅LR受控，之后实际访问数据仍会分叉；跨Reward的value loss单位不同，不据此排名。这里clip fraction指PPO likelihood比率裁剪；Gaussian原始动作经[-1,1]截断的比例另见audit/SAVED_ACTION_EXECUTION_DIAGNOSIS.json，二者不能混用。完整min/max、有限记录数和source SHA见audit/RECORDED_OPTIMIZER_METRICS.json。\n\n'
    body+='|家族|父seed|PPO.train记录数|entropy loss median|std median|approx KL median / max|clip fraction median|max clip fraction|value loss median|explained variance median|\n|---|---|---|---|---|---|---|---|---|---|\n'
    def fmt(v):return '缺失' if v is None else f'{v:.7g}'
    for item in metrics:
        z=item['statistics'];med=lambda name:fmt(z['train/'+name]['median'])
        body+=f"|{item['branch']}|{item['seed']}|{item['recorded_PPO_train_calls']}|{med('entropy_loss')}|{med('std')}|{med('approx_kl')} / {fmt(z['train/approx_kl']['maximum'])}|{med('clip_fraction')}|{fmt(z['train/clip_fraction']['maximum'])}|{med('value_loss')}|{med('explained_variance')}|\n"
    body+='\n降低LR后的较小局部KL或clip fraction没有保证两父mean保持；聚合机制与其实际数据/频率共同变化。不能仅凭低value loss或低clip fraction解释全部任务结果。\n\n'
    body+='## 全部已测名义窗口\n\n'
    body+='|家族|父seed|开发mean端点|开发sample端点|\n|---|---|---|---|\n'
    for branch,xs in sorted(joined['groups'].items()):
        for seed in SEEDS:
            ev=[x for x in xs if x['mode']=='evaluation' and x['seed']==seed and cfg(x).get('evaluation_split','development')=='development']
            if not ev:continue
            def window(mode):return ', '.join(f'{x["index"]-1}:{"完成" if x["success"] else "失败"}' for x in sorted(ev,key=lambda z:z['index']) if x['policy_mode']==mode) or '未测'
            body+=f'|{branch}|{seed}|{window("deterministic")}|{window("stochastic")}|\n'
    body+=f'\n最长已测mean端点：{horizon["longest_tested_mean_endpoint"]}；两父均有该端点且全部已测mean保持的家族：{horizon["supported_at_longest_endpoint"]}。短窗口候选未测试更长不计作更长成功；同谱系后来失败不能被旧成功或新分支名覆盖。R1延长是否完整见RETENTION_R1_RESULTS.json，存在前不补写结论。\n\n'
    body+='## 局部梯度与真实多Adam\n\n固定未更新网络/保存minibatch的离线探针显示R1可使critic更主导，joint clip后的actor梯度更小。单一R1/30反事实重算了完整GAE而非简单除旧returns，没有做Adam；它只能说明初始点的单位耦合。所有这类探针零物理、零Adam，另有聚合/序列化等价工程测试合计80次合成Adam，与真实训练ledger严格分开。\n\n'
    controlled=read(ROOT/'audit/CONTROLLED_R3_FIRST_UPDATE.json',{})
    body+='四个Reward的实际first update，在每父自己的相同80/77条物理输入、policy/Adam/Python-Numpy-Torch RNG/计数、hyper和update AST上，各执行20真实Adam/4epochs；前后ZIP与原metadata SHA匹配。下表读取这些实际已训练模型，不做回放学习。\n\n'
    body+='|父seed|Reward/配置|实际Adam|actor参数L2变化|critic参数L2变化|共享obs Gaussian KL|\n|---|---|---|---|---|---|\n'
    for c in controlled.get('cases',[]):
        if c['status']!='CONTROLLED_FIRST_UPDATE':body+=f'|{c["seed"]}|{c["status"]}|—|—|—|—|\n';continue
        assert all(c['checks'].values())
        for x in c['effects']:
            body+=f'|{c["seed"]}|{x["branch"]}|{x["actual_Adam"]}|{x["actor_parameter_l2_change"]:.8f}|{x["critic_parameter_l2_change"]:.8f}|{x["mean_Gaussian_KL_pre_to_post"]:.9f}|\n'
    body+='\nR1固定点actor裁剪梯度小于R0，但实际first KL未同比减小。R3只把所有R1项及floor除30，保留旧critic/Adam；两父actor L2变为R1的1.887/1.953倍，Gaussian KL却为2.576/0.230倍。单位缩放会改变实际优化，但参数距离不决定函数KL，也不直接决定native命令、任务或保持。GAE、value误差、joint clip及Adam状态尚未分别隔离，不能给唯一优化归因。证据为audit/FOUR_REWARD_FIRST_ROLLOUT_IDENTITY.json、audit/CONTROLLED_R3_FIRST_UPDATE.json及R3_CONTROLLED_UNIT_EFFECT.json。\n\n'
    body+='## Reward与完整任务取舍\n\nR1/R2各在10/30两父mean/sample均完成；R3仅10窗口四模式完成。R3的149 mean JF−0.279504%/JM+1.368140%，163 JF+0.325382%/JM−1.241229%，并非一致force改善。R3的149采样172、优化152、完整pending20；163采样/优化160、pending0。遵守共同终末30协议，没有为十集筛选额外flush；旧模块R0/R1/R2输出与新增R3模块逐项相同，实际源SHA均单独保存。不同Reward回报和值函数loss尺度不用于质量排名。\n\n'
    body+='完整剂量仅在成功、同父、同模式且19.03秒等时长的mean参照上计算变化。下表取每家族/父最新开发mean；失败保留partial原值，不列剂量收益。\n\n'
    history=[json.loads(l) for l in (ROOT.parent/'rl_b_autonomous_replication_v1/ALL_EVALUATION_LOG.jsonl').read_text().splitlines()]
    parents={x['training_seed']:x for x in history if x['kind']=='checkpoint050_first' and x['training_seed'] in SEEDS}
    body+='|家族|父seed|端点|完整|TASK s|JF|JM|对父JF%|对父JM%|\n|---|---|---|---|---|---|---|---|---|\n'
    for branch,xs in sorted(joined['groups'].items()):
        for seed in SEEDS:
            ee=[x for x in xs if x['mode']=='evaluation' and x['seed']==seed and x['policy_mode']=='deterministic' and cfg(x).get('evaluation_split','development')=='development']
            if not ee:continue
            x=max(ee,key=lambda z:z['index']);p=parents[seed];ok=x['success'] and abs(x['task_s']-p['task_s'])<1e-7
            fj=f'{(x["JF"]/p["JF"]-1)*100:+.6f}' if ok else '不可比';mj=f'{(x["JM"]/p["JM"]-1)*100:+.6f}' if ok else '不可比'
            body+=f'|{branch}|{seed}|{x["index"]-1}|{x["success"]}|{x["task_s"]:.3f}|{x["JF"]:.6f}|{x["JM"]:.6f}|{fj}|{mj}|\n'
    body+='\nJF/JM沿用原5ms传感器左端值、按真实已执行native区间时长积分，零时长边界0剂量；不冒称0.25ms force求积。真实Human q/dq与native/5ms/20ms加速度、native jerk用0.25ms原生状态和pre-TASK锚；jerk仅诊断，没有人为通过阈值。H2/60的163 knee tracking RMS0.629999°较父0.580361°高，RETURN knee overshoot2.653867°，moment也上升；低force不能抵消任务失败或运动代价。全部峰值和terminal误差在TASK_FORCE_MOTION_COMPARISON.md/逐run COMMON_MOTION_METRICS.json。\n\n'
    body+='## 动作分布、恢复与证据边界\n\nGaussian std仍接近1，sample+clip与mean+clip分布不同。std0.2/0.1只做数学提议反事实，没有真实方差策略试验；不能把网络输出平滑当Human平顺。H2/60最新dev1模式均完成也不删除163/30随机失败，最终未见动作流只提供固定nominal场景噪声诊断。\n\n'
    held=[x for x in rows if x['mode']=='evaluation' and cfg(x).get('evaluation_split','development')!='development']
    if held:
        body+='最终动作流已记录结果：\n\n|父seed|完整/已记录|固定checkpoint|\n|---|---|---|\n'
        for seed in SEEDS:
            x=[z for z in held if z['seed']==seed];body+=f'|{seed}|{sum(z["success"] for z in x)}/{len(x)}|{sorted({z["parent"] for z in x})}|\n'
        body+='\n只描述实际固定策略动作流，不将不同父模型合成患者泛化率；看到最终流后不再训练、改Reward/PPO/std或换候选。\n\n'
    else:body+='最终2026102191–2194动作流尚未打开，固定选择须先保存模型/SHA并遵循FINAL_SELECTION_PROTOCOL.md。\n\n'
    body+='正常完整pending通过policy/Reward/data SHA与边界恢复，真实R1与R2的59条完整转移加新增24条组成83更新已逐项按序核对；连续30对10+20合成恢复也逐状态一致。emergency partial在接口/预留前拒绝；pre-Adam checkpoint和COMPLETE_UPDATE_INPUT可支持显式恢复，实际partial-Adam故障重放没有运行，不能声称已通过。早期Control旧导入Reward按原创建记录精确恢复，后续保存时磁盘SHA不能证明模块重载；R0语义和严格复演一致，后续作业使用独立内容地址源码包。\n\n'
    body+='所有结论限制在已选成功父的nominal开发和明确动作流。独立合法初态BLOCKED；G4严格自然路径/全矩阵未闭合、新PPO缺原同父prefix/B/H150可移植live matched链。原scorer离线复现不代替新链；Stage2与正式Campaign未就绪，不自动启动后续包或Campaign。\n'
    target.write_text(body)
    atomic(ROOT/'audit/OPTIMIZATION_DIAGNOSIS_REFRESH.json',dict(time_utc=now(),source_sha256=sha(Path(__file__)),report_sha256=sha(target),observed_rows=len(rows),horizon_evidence=horizon,final_action_streams_observed=len(held),new_physics=0,new_Adam=0,scope='Current actual-data reconstruction, not formal qualification'))
    print('Current optimization diagnosis refreshed from',len(rows),'real rows')
if __name__=='__main__':main()
