"""Additional offline scientific diagnostics; every input is already saved and causal."""
from pathlib import Path
import os,sys,json,math,collections,statistics
R=Path(__file__).resolve().parents[1];os.environ['IHEAR_RESEARCH_ROOT']=str(R);sys.path[:0]=[str(R/'scripts'),str(R/'runtime')]
from research_common import atomic,read,sha,now
from stream_json import read_evidence
import numpy as np

def evidence(p):
 with read_evidence(p,encoding='utf8') as f:return json.load(f)
def moments(mu,sigma):
 phi=lambda z:math.exp(-z*z/2)/math.sqrt(2*math.pi)
 Phi=lambda z:.5*math.erfc(-z/math.sqrt(2))
 a=(-1-mu)/sigma;b=(1-mu)/sigma;pa=Phi(a);pb=Phi(b);f=phi(a);g=phi(b);mass=pb-pa
 mean=mu*mass+sigma*(f-g)-pa+(1-pb)
 second=(mu*mu+sigma*sigma)*mass+2*mu*sigma*(f-g)+sigma*sigma*(a*f-b*g)+pa+(1-pb)
 return dict(mean=mean,second_moment=second,variance=max(0,second-mean*mean),lower_boundary_mass=pa,upper_boundary_mass=1-pb,total_clip_mass=pa+1-pb)

def build():
 rows=[json.loads(s) for s in (R/'ALL_ATTEMPTS.jsonl').read_text().splitlines()] if (R/'ALL_ATTEMPTS.jsonl').exists() else [];actions=[];rewards=[];advantages=[]
 for row in rows:
  run=Path(row['run']);samples=evidence(run/'RESEARCH_TRANSITIONS.json');summary=evidence(run/'env/episode_0001/summary.json');decisions=summary['decisions']
  # Analytic bounded moments are proposal moments, never applied torque moments.
  initial=samples[0];bound=[moments(float(mu),float(sd)) for mu,sd in zip(initial['mean'],initial['std'])]
  last=samples[-1];raw=np.asarray([s['raw_action'] for s in samples]);clip=np.asarray([s['action'] for s in samples]);mean=np.asarray([s['mean'] for s in samples]);std=np.asarray([s['std'] for s in samples]);z=(raw-mean)/std
  counts=collections.Counter();byphase={}
  for d in decisions:
   if d['activation_outcome']=='ACTIVATED':continue
   reason=d.get('activation_rejected_reason') or d.get('planning_exception') or '';kind='GEOMETRY' if 'geometry' in reason.lower() else 'EMITTED_REFERENCE_REGRESSION' if 'regress the emitted reference' in reason.lower() else 'OTHER'
   counts[kind]+=1;byphase.setdefault(d['phase'],collections.Counter())[kind]+=1
  assert sum(counts.values())==row['rejections']
  a=dict(run=str(run),branch=row['branch'],seed=row['seed'],mode=row['mode'],policy_mode=row['policy_mode'],success=row['success'],evaluation_rng=row.get('evaluation_rng'),scope='Nominal saved trajectory; no counterfactual physics',initial_mean=initial['mean'],initial_std=initial['std'],initial_clipped_proposal_moments=bound,initial_preclip_joint_differential_entropy=sum(math.log(float(s))+0.5*math.log(2*math.pi*math.e) for s in initial['std']),empirical_clip_fraction=float((abs(raw)>1).mean()),empirical_clip_by_dimension=(abs(raw)>1).mean(0).tolist(),network_mean_outside_box_fraction=float((abs(mean)>1).mean()),standardized_noise_mean=z.mean(0).tolist(),standardized_noise_std=z.std(0).tolist(),refusals=dict(counts),refusals_by_phase={p:dict(v) for p,v in byphase.items()},terminal=dict(reason=row['abort_reason'],raw=last['raw_action'],clipped=last['action'],mean=last['mean'],std=last['std'],log_prob=last['logp'],interior_raw=all(abs(v)<=1 for v in last['raw_action'])),native_receipt_audit='env/episode_0001/CLOUD_CASE_AUDIT.json',fallback_events=row.get('fallback_events',[]))
  actions.append(a)
  if row['mode']=='training':
   totalJM=last['reward_after']['moment'];JF=last['reward_after']['force'];V=last['reward_after']['variation'];cost1=.0005*JF+.005*totalJM+.02*V;cost4=.0005*JF+.020*totalJM+.02*V
   # Counterfactual rescoring of identical saved transitions; never a new policy outcome.
   terminal_last=last['terminal'];p0=samples[0]['reward_before']['phi'];p1=last['reward_after']['phi'] if row['success'] else 0.
   ret1=2*(p1-p0)+(20-cost1 if row['success'] else -15-max(15,cost1));ret4=2*(p1-p0)+(20-cost4 if row['success'] else -15-max(15,cost4))
   rewards.append(dict(run=str(run),branch=row['branch'],seed=row['seed'],success=row['success'],full_or_partial=row['integral_scope'],R1_rescore=ret1,R4_rescore=ret4,delta=ret4-ret1,moment_price_contribution=-.015*totalJM,floor_compensation_change=(max(0,15-cost1)-max(0,15-cost4)) if not row['success'] else 0.,both_failed_floors_active=not row['success'] and cost1<15 and cost4<15,JF=JF,JM=totalJM,online_V=V,identity='Same saved executed transition rescore, not training outcome'))
  p=run/'ppo_rollout.npz'
  if p.exists():
   with np.load(p) as zbuf:
    adv=zbuf['advantages'].reshape(-1);ret=zbuf['returns'].reshape(-1);vals=zbuf['values'].reshape(-1);rew=zbuf['rewards'].reshape(-1);starts=zbuf['episode_starts'].reshape(-1)
   reconstructed=np.zeros_like(adv);last_gae=0.
   for t in range(len(adv)-1,-1,-1):
    nonterminal=0. if t==len(adv)-1 else 1.-float(starts[t+1])
    next_value=0. if t==len(adv)-1 else float(vals[t+1])
    delta=float(rew[t])+nonterminal*next_value-float(vals[t])
    last_gae=delta+.95*nonterminal*last_gae;reconstructed[t]=last_gae
   gae_error=float(np.max(np.abs(reconstructed-adv)))
   return_error=float(np.max(np.abs((reconstructed+vals)-ret)))
   assert gae_error<1e-4 and return_error<1e-4, 'GAE_RECONSTRUCTION_MISMATCH'
   update=read(run/'UPDATE.json',{});density=read(run/'SAMPLING_DENSITY_OWNERSHIP.json',{})
   advantages.append(dict(GAE_max_abs_error=gae_error,returns_max_abs_error=return_error,run=str(run),n=len(adv),episodes=int(starts.sum()),advantage_mean=float(adv.mean()),advantage_std=float(adv.std()),advantage_min=float(adv.min()),advantage_max=float(adv.max()),returns_mean=float(ret.mean()),value_mean=float(vals.mean()),reward_sum=float(rew.sum()),finite=bool(np.isfinite(adv).all() and np.isfinite(ret).all()),old_density_max_error=density.get('max_abs_old_logp_error'),distribution=update.get('distribution_diagnostics'),losses=update.get('losses'),singleton_minibatches=update.get('singleton_minibatches'),GAE='gamma=1, lambda=.95; terminal bootstrap=0; whole terminal episodes; SB3 per-minibatch advantage normalization'))
 result=dict(time_utc=now(),source_sha256=sha(Path(__file__)),new_native_steps=0,new_optimizer_steps=0,action_records=actions,proposal_moment_definition='Raw Gaussian then original Box clip; boundary mass plus interior density. These are proposals, not applied receipt torques.',inference_limit='Closed-loop states differ; last failed action alone cannot identify causal role of STD, clipping or prior path')
 atomic(R/'ACTION_EXECUTION_DIAGNOSTICS.json',result);atomic(R/'PPO_ADVANTAGE_AUDIT.json',dict(time_utc=now(),updates=advantages,all_finite=all(x['finite'] for x in advantages),scope='Saved actual update inputs; no gradient replay'))
 atomic(R/'REWARD_CREDIT_ASSIGNMENT_AUDIT.json',dict(time_utc=now(),records=rewards,scope='Saved-trajectory counterfactual reward arithmetic only; no additional policy outcomes',new_native_steps=0,new_optimizer_steps=0))
 failed=[r for r in rewards if not r['success']];flat=sum(r['both_failed_floors_active'] for r in failed);complete=[r for r in rewards if r['success']]
 text=['# Reward credit assignment 与执行机制诊断','','本项只读保存轨迹，不启动物理或 Adam。完整与失败 partial 分开；同轨迹重评分不是 R4 训练效果。','', 'R1/R4 对任意完整 episode 的总式为 `2(phi_terminal−phi_initial)+20−C`；失败为 `−2phi_initial−15−max(15,C)`。R4−R1 在成功轨迹上等于 `−.015*JM`。失败且两种成本均低于15时，终末 floor 补偿会抵消此前增加的 moment 成本，总回报不变。', '',f'实际保存训练轨迹 {len(rewards)} 条，失败 {len(failed)} 条，其中两版本失败 floor 同时激活 {flat} 条；完整 {len(complete)} 条。','', '这说明当前 moment 价格主要改变成功轨迹的总代价排序；不能只凭失败 partial moment 小就期待更高总回报。单步 GAE/critic/优势归一化仍可能因成本的时间分布变化而改变，总代价相同不等于梯度相同。gamma=1 的 potential 总和 telescoping；lambda=.95 的近似优势与继承 critic 仍影响有限样本学习。','',f'已审计实际 PPO 更新 {len(advantages)} 次；逐批保存 finite advantage、value/return 范围、旧密度误差、KL/ratio、mean 漂移和 log_std。此项不把 critic 数值变化误写为真实任务收益。','', '几何与 emitted-reference 拒绝采用原 summary.decisions 中所有非 ACTIVATED disposition，包含 FAILED 和 REJECTED，逐相位计数并与 runtime rejections 对齐。原始失败最后一步的 mean/std/raw/clip 保留；内部 raw 的失败不能归咎于边界 clip。','', '降低 STD 会改变 clip 后的一阶矩和边界点质量，尤其 network mean 已越界的维度；这不是 bounded action 上仅改变方差。解析 clipped Gaussian 均值/方差只描述提议分布，不是已应用 torque 分布。原 native/receipt 审计另行证明实际执行归属。','', '结论限制：没有固定失败状态的 planner/mean 物理反事实，不能唯一归因；没有把动作 RNG 当作独立患者或物理初态。']
 (R/'REWARD_CREDIT_ASSIGNMENT_AUDIT.md').write_text('\n'.join(text)+'\n')
 return dict(actions=len(actions),reward_rescores=len(rewards),updates=len(advantages),failed_floor_flat=flat)
if __name__=='__main__':print(json.dumps(build()))
