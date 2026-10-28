from pathlib import Path
import json,sys
from research_common import ROOT,RUNTIME,sha,atomic,now
sys.path.insert(0,str(RUNTIME))
from motion_metrics import metrics
from phase_dose import phase_dose
H=ROOT.parent/'rl_b_autonomous_stability_reward_v1';P=ROOT.parent/'rl_b_autonomous_replication_v1'
rows=[json.loads(s) for s in (H/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
originals=[json.loads(s) for s in (P/'ALL_EVALUATION_LOG.jsonl').read_text().splitlines()]
training=json.loads((H/'CHECKPOINT_COMPARISON.json').read_text())['branches'];cases=[]
for seed in [1495656323,1630784693]:
 old=next(x for x in originals if x['training_seed']==seed and x['kind']=='checkpoint050_first');old=dict(old,run=str(P/old['run']),branch='ORIGINAL_050',parent=str(P/f'seeds/{seed}/stage1/checkpoints/episode_050'))
 selected=[old]+[x for x in rows if x['seed']==seed and x['branch'] in ['RETENTION_H2','RETENTION_R1'] and x['index']==61 and x['policy_mode']=='deterministic']
 for x in selected:
  run=Path(x['run']);label=f'{x["branch"]}_{seed}';dest=ROOT/'audit/historical_recomputed'/label
  mm=metrics(run,dest);dose=phase_dose(run,x);checkpoint=Path(x['parent']);record=json.loads(checkpoint.with_suffix('.json').read_text())
  assert sha(checkpoint.with_suffix('.zip'))==record['model_sha256'];assert sha(checkpoint.with_suffix('.rng.pt'))==record['rng_sha256']
  src=run/'env/episode_0001/public_reward_contract.json';contract=json.loads(src.read_text())
  cases.append(dict(seed=seed,branch=x['branch'],run=str(run),checkpoint=str(checkpoint),checkpoint_sha256=record['model_sha256'],policy_sha256=record['policy_sha256'],checkpoint_metadata_sha256=sha(checkpoint.with_suffix('.json')),checkpoint_contract=record['contract_sha256'],public_reward_contract=contract,public_contract_sha256=sha(src),motion=mm,phase_dose=dose,original_metric_matches=abs(mm['JF']-x['JF'])<1e-7 and abs(mm['JM']-x['JM'])<1e-7,research_config=record.get('research_config'),new_physics=0,new_Adam=0))
  print(label,'recomputed',flush=True)
# Actual task identity fields should match: emitted contract includes all immutable targets/timing/reward identities.
comparisons=[]
for seed in [1495656323,1630784693]:
 a,b,c=[next(x for x in cases if x['seed']==seed and x['branch']==branch) for branch in ['ORIGINAL_050','RETENTION_H2','RETENTION_R1']]
 assert a['checkpoint_contract']==b['checkpoint_contract']==c['checkpoint_contract']
 assert a['public_reward_contract']==b['public_reward_contract']==c['public_reward_contract']
 comparisons.append(dict(seed=seed,same_task_contract=True,R1_vs_H2_JF_percent=100*(c['motion']['JF']/b['motion']['JF']-1),R1_vs_H2_JM_percent=100*(c['motion']['JM']/b['motion']['JM']-1),R1_vs_original_JF_percent=100*(c['motion']['JF']/a['motion']['JF']-1),R1_vs_original_JM_percent=100*(c['motion']['JM']/a['motion']['JM']-1)))
atomic(ROOT/'audit/H2_R1_COMPARISON.json',dict(time_utc=now(),cases=cases,comparisons=comparisons,all_metrics_match=all(x['original_metric_matches'] for x in cases),new_physics=0,Adam=0,restriction='Same original parent and method family; not strict same-trajectory reward-only causal contrast after first update; executed states, episode outcomes, update scheduling/data differ'))
lines=['# H2/R0 与 H2/R1 逐父对照','', '本轮从历史raw独立重算六条nominal mean轨迹的原5ms cuff积分与native Human运动，零新增物理/Adam。执行合同hash和public task contract逐字段一致。全部完整19.030秒，才允许下表描述性剂量比较。','', '|父seed|策略|JF N·s|JM Nm·s|knee tracking RMS °|RETURN knee overshoot °|hip/knee jerk RMS °/s³|','|---|---|---|---|---|---|---|']
for x in cases:
 m=x['motion'];lines.append(f'|{x["seed"]}|{x["branch"]}|{m["JF"]:.6f}|{m["JM"]:.6f}|{m["tracking_RMS_deg"][1]:.6f}|{m["RETURN_overshoot_below_goal_deg"][1]:.6f}|{m["jerk_RMS_deg_s3"][0]:.3f}/{m["jerk_RMS_deg_s3"][1]:.3f}|')
lines += ['', 'H2主要贡献是两个选定成功050父在已测30/60 mean端点保持完整任务。原Control继续30集后两父mean均失败；H1仅一个父保持。H2组合改变完整episode聚合、更新频率、优势归一化样本和minibatch结构，并未唯一识别哪一项造成保持。H2实际Adam总数并不更少，不能用“少更新”作唯一解释。', '', 'R1没有显示跨父一致的额外剂量优势：']
for x in comparisons:lines.append(f'- 父{x["seed"]}：R1相对H2，JF {x["R1_vs_H2_JF_percent"]:+.6f}%，JM {x["R1_vs_H2_JM_percent"]:+.6f}%。')
lines += ['', '两父R1均较H2减小RETURN knee overshoot，但149的knee tracking和jerk略升，163的knee tracking也略升而jerk下降。R1相对原050的force小幅下降同时moment上升；没有Pareto冠军。', '', '直接机制证据来自phase积分：两个H2及两个R1轨迹的force下降都集中在RETURN；OUTBOUND force反而略升。RETURN moment增加超过OUTBOUND moment下降，造成总JM上升。HOLD基本相同。相位内协调轨迹与实际施加参考发生改变；不能把force norm降低等同于moment降低。尚无已隔离证据证明具体cuff力臂、旋转变形或reward项是唯一根因。', '', 'R1与H2共享原050父及PPO方法家族；首批更新前可有共同样本，但更新后状态、成功/失败、聚合时点和训练样本分离。不是只差Reward的严格同轨迹因果对照。每支30→60都从030已flush状态延续，非无flush连续60。', '', 'online V仅为原causal估计器的归一化加速度平方积分；与native速度差分产生的实际a/jerk不同。原Reward并不直接惩罚native jerk，且actor不可读取未来/native truth。下一轮运动奖励须使用已发生的causal估计值，晋级另看native独立评价。', '', 'Gaussian原STD约0.97–1.00，与mean部署是不同执行分布。新的STD真实消融单列；不能把本表mean保持升级为随机可靠或跨患者泛化。G4严格矩阵、原B/H150同链live matched和独立合法初态仍未闭合。']
(ROOT/'H2_R1_COMPARISON.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(comparisons),flush=True)
