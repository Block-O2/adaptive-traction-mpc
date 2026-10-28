from pathlib import Path
import os,sys,json,hashlib,inspect,datetime
ROOT=Path(__file__).resolve().parents[1];H=ROOT.parent/'rl_b_autonomous_stability_reward_v1'
assert not (ROOT/'configs/STD_PLAN.json').exists(),'PRESERVE_FROZEN_PROTOCOL_DO_NOT_REPREPARE'
os.environ.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',IHEAR_GUARDED='1',IHEAR_RUN_DIR=str(ROOT/'audit/interface'))
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'runtime'))
from research_common import atomic,sha,now
(ROOT/'audit/interface').mkdir(parents=True,exist_ok=True)
import common
from runtime_setup import install
install()
import numpy as np,torch
from pilot_env import PilotEnv
from checkpoints import load,policy_hash,contract
from functional_smoke import snapshot,state_hash
from stable_baselines3.common.distributions import DiagGaussianDistribution
torch.set_num_threads(1);torch.set_num_interop_threads(1)
selection=json.loads((H/'FINAL_FROZEN_SELECTION.json').read_text());audit=[]
for item in selection['checkpoint_pair']:
 for p,h in item['files'].items():assert sha(H/p)==h,p
 env=PilotEnv(ROOT/f'runtime/audit/interface/seed{item["seed"]}')
 model,record=load(item['checkpoint'],env);actual=snapshot(model)
 assert actual==record['state_snapshot']==item['state_snapshot']
 env.close();params=model.policy.state_dict();sub=lambda prefix:state_hash({k:v for k,v in params.items() if any(k.startswith(p) for p in prefix)})
 dist=type(model.policy.action_dist)
 audit.append(dict(seed=item['seed'],checkpoint=item['checkpoint'],files=item['files'],snapshot=actual,actor_sha256=sub(['mlp_extractor.policy_net','action_net']),critic_sha256=sub(['mlp_extractor.value_net','value_net']),log_std=model.policy.log_std.detach().numpy().tolist(),std=model.policy.log_std.detach().exp().numpy().tolist(),distribution_class=f'{dist.__module__}.{dist.__name__}',action_low=model.action_space.low.tolist(),action_high=model.action_space.high.tolist(),squash_output=model.policy.squash_output,use_sde=model.use_sde,observation_shape=list(model.observation_space.shape),contract_sha256=contract(),load_identity_pass=True))
atomic(ROOT/'audit/CHECKPOINT_IDENTITY.json',dict(time_utc=now(),cases=audit,new_physics=0,gradient_updates=0))
(ROOT/'audit/GAUSSIAN_IMPLEMENTATION.py.txt').write_text(inspect.getsource(DiagGaussianDistribution))
# Fixed input stream, independent of policy or physical state. Save all 128 indices up front.
ids=[202610213001]+list(range(202610213101,202610213107))
for rng in ids:
 p=ROOT/f'noise/z_{rng}.npy';assert not p.exists();np.save(p,np.random.Generator(np.random.PCG64(rng)).standard_normal((128,2)).astype(np.float32))
configs=[]
def cfg(seed,arm,rng,split):
 item=next(x for x in selection['checkpoint_pair'] if x['seed']==seed)
 job=f'{split}_seed{seed}_{arm}_{rng}'
 p=ROOT/'configs'/f'{job}.json';noise=ROOT/f'noise/z_{rng}.npy'
 x=dict(job_id=job,branch='STD_ABLATION',seed=seed,parent_checkpoint=item['checkpoint'],start_episode=60,episodes=1,mode='evaluation',policy_mode='deterministic' if arm=='C' else 'stochastic',evaluation_rng=rng,arm=arm,reward='R1',learning_rate=0.,rollout='episode',target_kl=None,evaluation_split=split,noise_path=str(noise) if arm!='C' else None,noise_sha256=sha(noise) if arm!='C' else None)
 atomic(p,x);configs.append(dict(config=str(p),sha256=sha(p),split=split,seed=seed,arm=arm,rng=rng))
for arm in ['A','B']:cfg(1495656323,arm,202610213001,'pilot')
for seed in [1495656323,1630784693]:cfg(seed,'C',202610213100,'identity')
for i,rng in enumerate(range(202610213101,202610213107)):
 for seed in [1495656323,1630784693]:
  for arm in (['A','B'] if i%2==0 else ['B','A']):cfg(seed,arm,rng,'preregistered')
protocol=dict(time_utc=now(),status='FROZEN_BEFORE_PILOT',arms={'A':'loaded checkpoint Gaussian STD; a=mean+std*z','B':'temporary evaluation scale .2; a=mean+.2*z; parameters unchanged','C':'mean only'},streams=ids[1:],pilot_stream=ids[0],plans=configs,new_attempts=28,ceiling=32,noise_algorithm='numpy.PCG64.standard_normal float64 cast float32, saved npy; index=RL decision 0..127',inference='Paired decision indices remain aligned after state divergence; not equal trajectories or time aligned disturbances',selection='No post-result scale search or checkpoint substitution; pilot is excluded from main success statistics',comparisons='Per parent. Success first; failed partial excluded from complete JF/JM comparisons. Unequal task duration reported separately.',scope='Known nominal initialization and two selected trained parents; no patient/initial-state generalization',training_effect='Evaluation-only STD ablation cannot establish training STD advantage',hard_stop=json.loads((ROOT/'START.json').read_text())['hard_stop_utc'])
atomic(ROOT/'configs/STD_PLAN.json',protocol)
lines=['# STD 冻结评价预注册协议','',f'冻结时间 UTC：{protocol["time_utc"]}。模型身份见 audit/CHECKPOINT_IDENTITY.json；每份配置与噪声均在 pilot 前写入并校验 SHA。','', 'A 为 checkpoint 实际 Gaussian STD；B 仅在采样算式中使用 0.2；C 取 mean。所有网络、critic、Adam、执行合同保持。raw Gaussian → [-1,1] clip → 原协调参数映射 → planner准入 → applied receipt 分别保存。','', '每父6条新流 202610213101–202610213106，24个正式配对attempt。pilot流202610213001的A/B两个attempt先运行且单列；两父C各一次做历史身份回归。预定28次，上限32。单环境，单Torch/BLAS线程；每attempt最多165000 native、128 decisions、300秒。最后15分钟不启动物理。','', 'A/B共享同一已保存128×2标准正态数组，按决策索引配对；闭环状态分歧另报，不把相同noise当作相同轨迹。每条流交替A/B顺序。旧2191–2194仅作已见历史。','', '主要结果为逐父完整成功/几何拒绝及配对discordance；pilot排除。另报告时长、phase、JF/JM、实际Human q/dq/a/jerk、tracking、overshoot、source-age、receipt、clip。失败partial剂量单列；不对不同任务时长的JF差值宣称控制效率提升。样本量仅支持开发信号。','', 'pilot要求恢复全状态身份、无梯度/权重/Adam变化、噪声映射正确、原native/receipt/force/motion审计通过；任务失败可作为科学结果继续。完整性/安全失控才全局阻断。不得因B失败追加STD网格。']
(ROOT/'STD_ABLATION_PROTOCOL.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(audit,ensure_ascii=False));print('plan',sha(ROOT/'configs/STD_PLAN.json'),'attempts',len(configs))
