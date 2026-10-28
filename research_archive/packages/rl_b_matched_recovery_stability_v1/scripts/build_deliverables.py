from pathlib import Path
import json,hashlib,datetime,collections,platform,sys,os
r=Path(__file__).resolve().parents[1];c=r.parent/'rl_b_autonomous_replication_v1';g=r/'github';sc=r/'scorer/original-001'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(n,o):(r/n).write_text(json.dumps(o,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def md(n,s):(r/n).write_text(s.strip()+'\n')
def table(headers,rows):return '|'+ '|'.join(headers)+'|\n|'+'|'.join(['---']*len(headers))+'|\n'+'\n'.join('|'+ '|'.join(str(x) for x in row)+'|' for row in rows)
start=read(r/'audit/STUDY_START.json');zone=datetime.timezone(datetime.timedelta(hours=8));now=datetime.datetime.now(zone);t0=datetime.datetime.fromisoformat(start['T0']).astimezone(zone)
scorer=read(sc/'OFFLINE_SCORER_RESULT.json');identity=read(r/'audit/FIXTURE_CONTRACT_VERIFICATION.json');source=read(r/'source_diff/FILE_SHA256_COMPARISON.json');lineage=read(r/'source_diff/CODE_LINEAGE_AND_CONFIG.json');optimization=read(r/'stability/TRAINING_OPTIMIZATION_AUDIT.json');reward=read(r/'stability/REWARD_CREDIT_AUDIT.json');cp=read(r/'CHECKPOINT_050_080_COMPARISON.json');ev=read(r/'stability/FROZEN_ACTION_EXECUTION_AUDIT.json');native=read(r/'stability/HISTORICAL_NATIVE_EXECUTION_AUDIT.json');plan=read(r/'physical/EVALUATION_PLAN.json')
physical=[]
for case in plan['cases']:
 p=r/'physical/runtime/evaluations'/case['id'];x=read(p/'RESULT.json');x.update(run_path=str(p.relative_to(r)),native_config_sha256=sha(p/'env/episode_0001/config_snapshot.json'),evaluation_plan_sha256=sha(r/'physical/EVALUATION_PLAN.json'),evaluation_harness_sha256=sha(r/'scripts/frozen_evaluation.py'),model_vendor_manifest_sha256=sha(r/'physical/runtime/audit/VENDOR_COPY_MANIFEST.json'));physical.append(x)
assert len(physical)==8 and all(x['gradient_updates']==0 and x['frozen_state_unchanged'] and x['independent_audit_pass'] and x['force_audit_pass'] for x in physical)
physgroups=[]
for seed in [1495656323,1630784693]:
 for ep in [50,80]:
  q=[x for x in physical if x['case']['training_seed']==seed and x['case']['checkpoint_episode']==ep];physgroups.append({'seed':seed,'checkpoint_episode':ep,'successes':sum(x['success'] for x in q),'attempts':len(q),'rng_seeds':[x['case']['evaluation_rng_seed'] for x in q]})
put('PHYSICAL_EVALUATION_RESULTS.json',{'status':'COMPLETE','category':plan['category'],'new_attempts':8,'native_steps':sum(x['native_steps'] for x in physical),'task_native_steps':sum(x['task_native_steps'] for x in physical),'RL_decisions':sum(x['rl_decisions'] for x in physical),'gradient_updates':0,'original_checkpoint_mutations':0,'matched_evaluation':False,'all_observed_physical_audits_pass':True,'groups':physgroups,'evaluations':physical,'interpretation':'Known nominal development only. n=2 stochastic replicates per checkpoint cannot estimate stability or generalization; partial JF/JM must not be compared as full-task benefits.'})
measurements={n:read(sc/'reports'/f'{n}_MEASURED.json') for n in ['D01R_parent','D01R_B','D01R_H150']}
put('HISTORICAL_MATCHED_REPRODUCTION.json',{'status':'PASS','scope':'ORIGINAL_ARCHIVED_D01R_W1_OFFLINE_ONLY','fixed_github_commit':start['requested_commit'],'fixture_contract_identity':identity,'original_scorer_result':scorer,'measurements':measurements,'run_provenance':read(sc/'RUN_PROVENANCE.json'),'all_measurement_fields_match_frozen_reference':True,'all_receipt_fields_match_frozen_reference':True,'all_motion_arrays_elementwise_equal':True,'numeric_tolerance':1e-8,'metadata_only_relocations':['sources','execution_lineage_path'],'new_physics_in_historical_reproduction':0,'full_fork_replay':'NOT_RUN_UNVERIFIED_NO_PORTABLE_PARENT_CHECKPOINT','new_live_matched_evaluation':'NOT_RUN'})
statuses={
 'OFFLINE_SCORER_READY':{'status':'PASS','evidence':['audit/FIXTURE_CONTRACT_VERIFICATION.json','scorer/original-001/OFFLINE_SCORER_RESULT.json']},
 'HISTORICAL_MATCHED_REPRODUCTION':{'status':'PASS','evidence':['HISTORICAL_MATCHED_REPRODUCTION.json']},
 'CLOUD_SOURCE_DIFF_COMPLETE':{'status':'PASS','scope':'Five existing cloud packages; actual 447-file training closure; exact GitHub capsule and same-path active-main overlap','evidence':['source_diff/FILE_SHA256_COMPARISON.json','source_diff/CODE_LINEAGE_AND_CONFIG.json']},
 'PPO_STABILITY_CAUSE_IDENTIFIED':{'status':'PARTIAL','reason':'Policy drift -> different admitted references/torques -> late RETURN geometric infeasibility is directly identified. A unique optimizer/reward/exploration cause is not identified without controlled training ablations.','evidence':['stability/HISTORICAL_NATIVE_EXECUTION_AUDIT.json','CHECKPOINT_050_080_COMPARISON.json','stability/TRAINING_OPTIMIZATION_AUDIT.json','PHYSICAL_EVALUATION_RESULTS.json']},
 'NEW_PPO_MATCHED_EVALUATION_READY':{'status':'NOT_READY','reason':'Historical offline scorer restored; no original matched same-parent B/H150/PPO live fixture chain or portable complete parent state; new stochastic runs use existing nominal development contract.','evidence':['scorer/original-001/OFFLINE_SCORER_RESULT.json','physical/EVALUATION_PLAN.json']},
 'G4_STRICT_PASS':{'status':'FAIL','reason':'Historical failure retained. Natural HOLD/absolute-safety/full matrix remain unclosed; this study does not run that matrix.','evidence':[str(c/'G4_NATURAL_PATH_UPDATE.json'),str(c/'LEVEL_A.json')]},
 'STAGE2_READY':{'status':'NOT_READY','reason':'Three-seed/final-parent repeated runtime gates failed; new development samples do not replace those gates. Stage2 NOT_RUN.','evidence':[str(c/'STAGE2_GATE_DECISION.json'),str(c/'STAGE2_RESULTS.json')]},
 'FINAL_CAMPAIGN_READY':{'status':'NOT_READY','reason':'No formal live matched/G4/independent initial-state stability qualification and no campaign authorization.','evidence':['NEXT_RESEARCH_DECISION.md','STATUS.json']}}
put('STATUS.json',{'terminal_state':'STOP','generated_at':now.isoformat(),'statuses':statuses,'new_training_episodes':0,'new_gradient_updates':0,'Stage2':'NOT_RUN','final_campaign':'NOT_RUN','new_physical_evaluations':8})
axes=[['GITHUB_SOURCE_RECOVERY','PASS','远端分支与 detached HEAD 均为指定 1adb1de…'],['FROZEN_SCORER_IDENTITY','PASS','23 来源、16 锚点、v6 1426 项、9 合同均按原 SHA'],['FIXTURE_INTEGRITY','PASS','32 原件 / 146,542,129 bytes，全部来自此次 clone'],['HISTORICAL_OFFLINE_REPRODUCTION','PASS','全部原字段、receipt、motion 数组与冻结参考一致'],['FULL_FORK_REPLAY','NOT_RUN / UNVERIFIED','无可移植完整父 checkpoint；未构造替代状态'],['NEW_LIVE_MATCHED_EVALUATION','NOT_RUN','8 次新增仅为 nominal 开发冻结诊断']]
md('GITHUB_RECOVERY_AUDIT.md',f'''# GitHub 固定源码恢复审计

T0：{t0.isoformat()}。实际 checkout：`github/`，远端 `https://github.com/Block-O2/adaptive-traction-mpc.git`，指定研究分支 `codex/local-research-sync-20261020`，精确 HEAD `{start['requested_commit']}`。SSH 因本机未配置 GitHub known-host 记录退出；未修改 SSH/凭据，随后 HTTPS ls-remote 与真实全新 clone 成功。clone/checkout 日志见 `logs/`；最终 HEAD、tracked-tree 和 clean 状态见 `audit/GITHUB_FINAL_IDENTITY.json`。

{table(['恢复轴','状态','直接依据'],axes)}

先核验后运行：`deployment/verify_repository.py --expected-commit {start['requested_commit']}`；`verify_b_h150.py`；原 `score_b_h150.py --work-dir <新目录>`。所有评分均用 `python -B`，无 `-O`；原断言启用。精确命令、工作目录、退出码与 wall 在 `audit/jobs/*/START.json`、`END.json`。原 install 脚本经读取后执行，使用受信现代 pip 的 `--python` 向两个全新 CPython3.12 venv 安装；没有复用历史 site-packages。offline 为 2 项 hash lock；CPU 为 35 wheel 的完整 hash lock；pip check 均通过。

仓库中的旧 CLOUD_GITHUB_DEPLOYMENT_GUIDE/B_H150_EVALUATOR_READINESS 保留了“还需外部 TAR”的早期状态；同一固定 commit 的最新架构/FRESH_CLONE_VALIDATION、data_catalog、score 入口和实际文件表明 32 项已原生进 Git。本轮按真实入口与 SHA 解析该时间差，没有取用旧 TAR/ZIP，也没有创造缺失 fixture。

3,079 当前源码/资产、2,237 Python 语法项、141 Stage3–5 XML 引用、450 原封存载荷及28 vendor身份核验通过；90 模型身份与6份原 XML 编译通过，编译检查禁止 mj_step/forward/inverse。原 RL-B 五个导入/单测入口通过；5项维护完整性失败测试通过。这些均不产生物理步、不授权训练。详见 `audit/REPOSITORY_VERIFICATION.json`、`MODEL_VERIFICATION.json`、`rlb-check-001/RL_B_ENVIRONMENT_CHECK.json`。

原 scorer 使用独立 offline 环境，Python 访问门禁止旧五个云端包及旧 coding 根，两个 open/scandir 预期拒绝 probe 通过；实际 scorer 无旧根拒绝事件。它是 Python audit hook，不是 OS/C 库文件系统沙箱。fixture 全部 SHA 与模块 __file__ 路径另行确认。`scorer/original-001/RUN_PROVENANCE.json` 记录实际 commit、source_dirty=false、输入/lock/config/模型/候选身份；最终原 checkout 内容未修改。

完整 parent 地址空间、MuJoCo/planner/传感历史及不透明句柄没有被可移植恢复；`D01R_parent_CAUSAL_STATE.json` 仍缺失。两份历史 _prefix_native 二进制仅保存 CPython3.10 平台身份，不作为3.12扩展加载。历史原运行 Git commit 若未记录，仍为 UNKNOWN；本轮源码提交不能冒称历史生成提交。离线链已恢复，不代表 full fork 或新 PPO live matched 已就绪。
''')
histrows=[]
for n,d in measurements.items():histrows.append([n,f"{d['J_F_N_s']:.13f}",f"{d['moment_integral_Nm_s']:.11f}",'/'.join(f'{v:.6f}' for v in d['tracking_RMS_deg']),f"{d['dose']['duration_s']:.9f}",'/'.join(f'{v:.3f}' for v in d['motion']['raw']['full']['jerk_deg_s3']['rms'])])
md('FROZEN_SCORER_VALIDATION.md',f'''# 原 B/H150 冻结 scorer 云端独立复核

**OFFLINE_SCORER_READY=PASS；HISTORICAL_MATCHED_REPRODUCTION=PASS。** 这是原 D01R/W1 历史 raw 的新云端算术复核。

原 `analyze_matched.measure/compare` 与 `control/independent_recompute.measure` 分别执行；只在维护入口重绑定 S/P 和输出路径。原 5ms TASK 左积分、0.25ms native Human、prefix+suffix、motion/dose/边界、receipt/实际 torque/step ownership、100ms 科学时钟 source age 和 promotion assert 均保持启用。独立模块来源记录在 `scorer/original-001/OFFLINE_SCORER_RESULT.json`。

{table(['原 fixture','JF N·s','JM Nm·s','tracking RMS ° hip/knee','TASK s','raw jerk RMS °/s³ hip/knee'],histrows)}

H150 相对 B 的 JF 改善 **2.353937394034738%**，JM 增加 **5.74653333830843%**；原 motion acceptance_pass=true，failed_requirements=[]。原 burden_sensitivity 的1.0门不通过而1.05门通过，也完整保留，不把“force下降”表述为所有指标均改善。tracking、原始/SG5/SG21 motion、dose、阶段代价和所有诊断字段见 `HISTORICAL_MATCHED_REPRODUCTION.json`。

逐字段与原冻结 MEASURED、原 receipt 报告比较；全部 motion_series key/数组逐元素相等；comparison 全部字段相等。数值绝对容差1e-8，只允许 sources/execution_lineage_path 元数据随新路径变化。32 fixture、23 scorer来源、16恢复锚点、完整v6的1426项、九合同、90模型身份全部通过；未因 JF 接近而跳过任何门。

三个原件的 PHYSICAL_TASK_VALID、SCIENTIFIC_EXECUTION_CAUSAL_VALID、LEGACY_R2_MATCHED 均为 PASS；HOST_EXECUTION_CAUSAL_VALID 均为 NOT_EVALUABLE。原 raw_scorer_v2 的 host plan_age/历史 RSS_RUNTIME_QUALIFICATION_NOT_MET 记录仍保留；原 mode-aware 科学执行绑定 PASS 不将其改为 host实时通过。该绑定来自恢复的原冻结 scorer，不是本轮改阈值。

本轮历史重算新增物理步=0。完整父进程 checkpoint/parent_CAUSAL_STATE 缺口影响 full fork，不影响已经验证的历史离线评分。8个新 PPO 开发评价没有原同父 prefix/B/H150 条件，因此 NEW_LIVE_MATCHED_EVALUATION=NOT_RUN，NEW_PPO_MATCHED_EVALUATION_READY=NOT_READY。
''')
changed=[x for x in source['science'] if x['status']!='IDENTICAL'];wrows=[]
for x in source['wrappers']:
 if x['status']!='IDENTICAL':wrows.append([Path(x['cloud_path'] or x['github_path']).name,x['status'],x.get('exact_diff','逐文件 SHA 清单')])
md('CLOUD_GITHUB_SOURCE_DIFF.md',f'''# 云端与 GitHub 真实源码差异

240集/3-seed 的实际入口是 `rl_b_autonomous_replication_v1/replication_run.py`，不是 GitHub 封存 `train.py`。240条训练记录、51代 checkpoint 和各 RESUME/START 将它们绑定到实际源码；447项 FROZEN_CONTRACT 全部重新 SHA 通过，合同 `{lineage['actual_frozen_contract_sha256']}`。训练配置/seed/阶段来自该包 PPO_TRAINING_CONFIG 和 REPLICATION_PROTOCOL，不能用 GitHub 示例训练命令代替历史身份。

|范围|相同|云端修改|云端新增/同路径缺于GitHub|GitHub独有|
|---|---:|---:|---:|---:|
|414项科学/配置/模型闭包 vs GitHub sealed source|412|2|0|0|
|同414路径 vs GitHub active main|411|2|1|0（仅交集范围）|
|根目录 Python 包装代码|13|5|27|10|

414项包括161份Python、222 JSON、3XML、20OBJ、7STL和1份AGENTS。真正 Python 源码共216个对照路径：172相同、7修改（2科学+5包装）、27云端新增、10GitHub独有。云端参与对照的206份Python、GitHub封存189份Python；该数字不包括整个GitHub其他历史研究，也不把生成报告当训练源码。未发现当前447项中来源hash不明项；历史生成commit未知另列，不伪装已知。

两份科学修改：`activation_validation.py` 将原 HOLD-only超时优先检查扩展到 OUTBOUND/HOLD/RETURN；`runtime_sac_expert_v1.py` 只按实际拥有的native区间计force（拒绝前零时长零积分）、保留失败边界，并修复moment积分的边界范围。它们来自 cloud_v1→g4_repair_v1；其后 readiness→pilot→3-seed 的414项树hash一致。`rl_native_proposal.py` 已在 GitHub capsule，未在 active main 的对应位置，不能因“源码都在GitHub”就遗漏长期主树对接。

native_rl_env/ready_env/pure_rl_env、41D因果观测、两个native事件进度分数、planner/certificate/admission、governor/bridge/lifecycle以及全部模型/vendor均已逐字节对照；这些在 capsule 对照中相同，只有上述两份科学修复不同。根包装层5修改为 checkpoints.py、audit_reward_physical.py、independent_physics_audit.py、resource_guard.py、stream_json.py。云端新增 pilot_env 的v3失败cost floor、replication_run的单完整episode更新、原始rollout/真实Adam计数及冻结评价；这不是 GitHub 原train.py的默认rollout配置。

{table(['文件','分类','精确 diff / 身份'],wrows)}

全路径SHA256、active-main对照和两版本精确diff见 `source_diff/FILE_SHA256_COMPARISON.csv/json`；五包的逐文件科学树、配置原文与28 vendor复核见 `CODE_LINEAGE_AND_CONFIG.json`；相邻包装代码的diff见 `source_diff/lineage__*.diff`。仅复制差异/隔离运行必要闭包；没有覆盖云端训练目录，没有把云端代码提交GitHub。
''')

# Explicit configuration comparison is generated separately in source_diff/CLOUD_CONFIG_SEMANTIC_DIFF.json.
md('CLOUD_CODE_RETURN_PLAN.md',r'''# 云端代码回流审核方案

本轮只生成可审核差异，不应用到长期仓库，不自动 commit/push。保留 GitHub 原 sealed capsule 和D01R合同身份；修复进入新的 active 开发版本，历史研究包继续可复现。

|优先项|云端证据/拟目的地|审核与进入条件|
|---|---|---|
|P0：force/moment实际拥有区间积分|`source_diff/sealed_science__...runtime_sac_expert_v1.py.diff` → active Stage5 同模块；`force_audit.py`、independent_physics_audit、stream_json → 通用审计工具|分别覆盖未施加拒绝、零时长重复边界、partial异常、正常完整任务；与实际native步/receipt积分回归，再逐字段确认正常任务旧指标不变。保留失败边界而不伪造积分。|
|P0：G4期限优先级|`activation_validation.py` 原精确diff → active Stage5；历史g4_repair的边界测试|确切边界前/等/后以及所有三个phase；保留原10s期限、1e-12边界约定。自然HOLD失败、绝对安全触发和完整矩阵未闭合，必须单独科学回归，不能用当前8次替代。|
|P1：native RL接口在主树的显式版本|capsule已有 `rl_native_proposal.py`，active main缺对应文件；native_rl_env/ready_env接口|与原planner/certificate/admission/40ms bridge/100ms lifecycle、因果41D输入完整回归；不得把多个不同 source 树隐式混在 sys.path 中。|
|P1：可复用checkpoint/恢复和资源工具|checkpoints的显式冻结allowlist合同、原model/Adam/RNG、gzip reader、6GiB资源门|单独模块/配置schema；破损/未完成generation/合同变更拒绝、跨进程恢复、仅新目录写入。不要把历史绝对T0/STOP/预算作为长期默认。|
|P1：训练/冻结评价与证据分离|`replication_run.py`、rollout npz、真实Adam统计、sampled raw→clip→proposal及frozen hash检查|抽取通用入口后独立回归。保留gamma=1有限终止和所有transition；本轮没有为新入口赋训练资格。|
|需另审的科学版本：reward v3 floor|`pilot_env.py` 与 `test_pilot_reward.py`，对应独立reward审计|修复失败partial成本偏好有明确历史动机，但floor及其界限是研究合同，非通用最佳reward。作为显式版本保留；本轮172失败均−11.5，未证明它导致或解决退化。|
|仅历史实验特化|campaign_manager/replication_analysis/build_reports/stage2_*、seed列表、80集门、budget/停止文件、临时cache路径和脚本|归档于本研究版本/工具数据层，不直接替代长期算法入口；Stage2门仍关闭。|

精确配置和逐文件hash见 `source_diff/CODE_LINEAGE_AND_CONFIG.json`。原cloud_v1→g4_repair只有两份科学源码改变；后续414科学闭包未再改变。`independent_physics_audit.py`的零时长拒绝处理和`audit_reward_physical.py`终止通知例外需要按明确事件模式审核，不能成为任意重复时间戳的通行证。模型/vendor无需“修复回流”，已逐文件一致。

审核顺序为 P0科学回归、P1通用基础设施、再单独授权有界训练验证；不得在回流时顺便换reward、物理、action或放宽G4。当前源码恢复/离线评分通过，只是回流审查的证据。
''')
segments=[x for x in optimization['segments'] if x['episode_range']==[51,80]]
optrows=[[x['seed'],x['successes'],x['decisions'],x['adam_updates'],f"{x['losses']['train/approx_kl']['mean']:.7f} / {x['losses']['train/approx_kl']['max']:.7f}",f"{x['losses']['train/value_loss']['mean']:.3f}",f"{x['losses']['train/explained_variance']['mean']:.4f}",x['single_transition_episodes'],x['singleton_minibatch_episodes']] for x in segments]
frozenrows=[]
for x in ev['evaluations']:
 if x['kind'] in ['checkpoint050_first','checkpoint080_first']:
  frozenrows.append([x['seed'],x['episode_checkpoint'],x['status'],f"{x['task_s']:.3f}",f"{x['accepted']}/{x['rejections']}",str(x['actions'][0]['bounded_proposal']),x['failure_reason'] or '完整完成'])
physrows=[[x['case']['training_seed'],x['case']['checkpoint_episode'],x['case']['evaluation_rng_seed'],x['status'],f"{x['task_s']:.3f}",x['rl_decisions'],f"{x['JF_N_s']:.3f}"+(' partial' if not x['success'] else ''),f"{x['JM_Nm_s']:.3f}"+(' partial' if not x['success'] else ''),x['abort_reason'] or '完整完成'] for x in physical]
grouptxt='；'.join(f"seed{x['seed']}/cp{x['checkpoint_episode']:03d}={x['successes']}/{x['attempts']}" for x in physgroups)
md('TRAIN_EVAL_SEMANTICS_AUDIT.md',f'''# PPO 训练/冻结执行语义审计

**已复核240训练rollout、51代checkpoint、19历史冻结评价及8新增冻结开发评价。新增训练/gradient update均为0。** 真实代码身份来自447项冻结合同，原始tensor/Adam/RNG及文件SHA均再次核对通过。

训练用未截断对角Gaussian sampled raw action；环境收到 clip(raw,−1,+1)。PPO RolloutBuffer存raw action和其原始Gaussian log_prob，240/240与实际有界proposal一一一致；未发现“用clip动作却配raw log_prob”的身份错配。冻结执行用Gaussian mean后同样clip，不随机采样；policy mean不是施加torque。动作是每个原native planner事件的两关节最大进度分数 `(a+1)/2`，不是50ms或物理步，HOLD动作不允许跳过强制HOLD。

链条为41D因果观测 → raw mean/sample → clip proposal → 单个native waypoint候选 → 原证书/当前态准入 → reference/40ms bridge/governor → 实际6轴torque receipt → 每0.25ms native步。planner拒绝后可能沿旧合法参考/fallback继续；ACTIVATED次数、policy proposal和applied torque必须分别读。完整证据在 `stability/FROZEN_ACTION_EXECUTION_AUDIT.json`、`HISTORICAL_NATIVE_EXECUTION_AUDIT.json` 以及新run的POLICY_SAMPLES/native_rl_requests/runtime_artifacts/native_journals。

三个seed所有历史冻结起始41D观测的SHA相同：`24a9d24aa053acbd1c174ecbac4209f94d6bba66a1f5389cc9d47af61c85a820`。六条050/080轨迹（3个配对）的原native数值准备prefix和config分别完全相同；18次PPO确定性proposal由对应checkpoint重新forward全部复现，另1次固定合法[+1,+1]基线单列核验。没有VecNormalize/running observation normalization；手动单位归一化源码相同。网络没有dropout/BatchNorm，train/eval模式差异不能解释均值策略变化。历史训练reset seed递增但nominal物理初态确定，不能把seed数字不同当独立物理初态。

每完整episode建立变量长度RolloutBuffer；gamma=1、GAE lambda=.95、terminal last_value=0；240份GAE逐元素重算最大误差0，return=advantage+value恒等式核对。有限任务deadline为terminated，不是truncated；资源异常不伪装任务失败。全失败172集总回报均约−11.5，成功回报约35减已测成本。失败potential归零、cost floor1.5已独立按online ticks重算。107个失败episode有正中间reward，48个有正raw advantage；这是局部信用分配的诊断信息，不能等价为失败总目标为正或已证明reward hacking。

训练LR恒3e−4，n_epochs=4，batch_size=16，target_kl=None。65/240集只有1个transition；76/240集的N mod16=1，因此每epoch出现singleton minibatch。SB32.6.0源码仅在len(advantage)>1时标准化；这带来不同rollout长度的梯度权重/噪声差异。实际mini-batch置换、分actor/critic梯度和裁剪前范数均UNAVAILABLE，没有重放训练来伪造。记录的gradient_l2在clip_grad_norm之后测量，接近0.5不能证明裁剪前梯度爆炸。

`train/approx_kl`真实有记录，但该SB3实现每epoch重置列表，输出只聚合最后epoch；`clip_fraction`聚合已执行minibatch且本轮240条全为0。它与“raw action被Box clip”的比例是不同指标。`train/explained_variance`在singleton return方差为0时为NaN，被原runner有限值筛选省略，按实际可用n报告，不补曲线。现有log含entropy、policy/value loss、std；原记录与本轮离线Gaussian 050||080 KL严格分开。

新增随机评价加载并校验原checkpoint RNG后，显式重设两组预注册evaluation RNG；环境仍用同一nominal seed20261020。内存RNG随抽样前进是预期行为，原rng.pt文件/weights/Adam均不变；PPO.learn/train、backward和Adam.step被封锁。每次都保存真实初态hash、raw/mean/std/bounded proposal、准入、force/moment、native/decision数和完整START/END。

随机结果：{grouptxt}。这仅补充部署语义证据，n=2且已知nominal，不是稳定完成率或独立泛化估计；已观察到的一次成功也不替代冻结门。
''')
md('PPO_STABILITY_DIAGNOSIS.md',f'''# PPO 050→080 稳定性诊断

**结论：执行层直接原因已定位，唯一学习根因尚未确定。** 两个曾成功的deterministic策略在继续30集后，均值动作及两关节协调发生漂移，改变了被准入的参考和实际torque，最终在RETURN提出原shank-table几何不可行waypoint，被保留的原门拒绝并ABORTED。不能据此预先命名catastrophic forgetting，或把所有退化都归因于单一stochastic/deterministic mismatch。

## 1. 原冻结050/080的事实

{table(['seed','checkpoint episode','runtime','TASK s','accepted/rejected','第一个bounded mean','terminal reason'],frozenrows)}

每个原050/080都有两次相同nominal重复；对应episode的actions由权重重新forward复现，真实native准备prefix/config一致。六条原轨迹的独立ownership/torque/step/source-age/force/moment复核PASS。在TASK **10ms**时reference和实际receipt torque首次分叉，在**15ms**的5ms边界Human实际状态已可测分叉；这证明权重漂移经过执行层施加了实际物理影响，不止是模型权重不同。具体值与逐request准入见 `HISTORICAL_NATIVE_EXECUTION_AUDIT.json`。最后的负mm为候选预测几何，不是已发生物理碰撞；实际观测安全审计通过不能升级为全动作安全。

## 2. 更新强度、分布及信用分配

{table(['seed','51–80成功/30','decisions','Adam更新','最后epoch KL均值/最大','value loss均值','explained variance均值','1-transition集数','singleton minibatch集数'],optrows)}

相同预存causal观测上，1495656323的050→080平均绝对raw mean变化为[0.177006,0.147412]，Gaussian KL均值0.028598；1630784693为[0.634878,0.138427]，KL均值0.216017。control seed1106823814也漂移[0.063288,0.223793]、KL0.035114，但050/080一直失败。该KL由两份冻结分布离线计算，不是重建历史更新KL。两退化seed的std始终约0.98–1.00；050成功mean仍位于高随机探索分布中，80的1630784693起始mean被clip到[1,1]。

1495656323的随机训练完成从21–50的8/30升至51–80的19/30，仍未保住确定性最终能力；1630784693为8/30→11/30。训练正在优化带大量噪声和边界clip的动作分布回报，部署检查的是mean闭环完成，两个目标没有单调等价保证。小的单次记录KL和全零surrogate clip_fraction没有阻止30集累计漂移。没有target_kl，也没有成功checkpoint保护门；这些是实现事实，未证明设置target_kl即可修复。

240份独立reward重算全部通过；172失败总回报−11.5，没有失败正总回报漏洞。65个single-transition episode、76个singleton minibatch episode，加上弱value explained variance，支持“局部advantage/小rollout梯度噪声”候选机制；107失败有正中间reward、48失败有正raw advantage。它们不证明reward公式本身错了。没有对loss/梯度做训练消融，也没有可用裁剪前梯度曲线，不能给出确定统计归因。

## 3. 8次有界新冻结评价

为区分“变化中策略的随机训练成功”与“固定checkpoint的随机能力”，先冻结两退化seed×050/080×两个共同RNG。没有添加/替换样本，所有负结果保留。与历史deterministic比较时，只称同nominal开发诊断。

{table(['seed','checkpoint','evaluation RNG','runtime','TASK s','decisions','JF N·s','JM Nm·s','reason'],physrows)}

汇总：{grouptxt}。其中seed1630784693的080为mean历史0/2而随机样本2/2，seed1495656323的080两种执行均0/2；这支持采样会改变可达闭环路径，同时反对把统一根因简单归为采样模式。小样本只能证明这些特定随机轨迹的结果，不估计稳定概率；不把随机成功作为deterministic回退已解决。成功时长若与19.030历史不同，不列JF/JM相对改善；失败partial积分也不作为降force收益。新增native总步数 {sum(x['native_steps'] for x in physical):,}，RL decisions {sum(x['rl_decisions'] for x in physical)}；0梯度更新，8次独立物理/奖励审计均通过。原scorer没有给这些新run授予matched资格。

## 4. 候选机制与证据等级

|候选机制|支持证据|反证/未测|置信程度|
|---|---|---|---|
|均值/协调漂移跨过RETURN可行边界|相同准备初态与软件；mean→已准入reference→实际torque→Human路径的直接分叉；最终两次几何规划失败|未做固定中途状态反事实替换；不保证某个单一action独立足以造成终止|高：执行层原因|
|单episode高噪声更新未保护成功mean|固定LR、120epoch继续更新、target_kl=None、Gaussian累计漂移；随机训练成功可升而mean失败|记录单次KL小、clip fraction0；没有LR/epochs/rollout消融|中：学习机制候选|
|训练随机分布与mean部署目标不一致|std约1、实际clip；训练与冻结语义不同；新增两组固定RNG直接证据|Gaussian平均动作不代表分布最佳动作本来就可能；8次不足分离唯一原因/估计成功率|中：贡献因素，非唯一根因|
|GAE/value和singleton梯度信用分配|GAE精确复算；65单transition、76 singleton、value解释力弱；局部正advantage与失败并存|数学实现未发现错配；总failure目标没有正收益；无精确minibatch轨迹/梯度消融|中低：需要最小对照|
|checkpoint/RNG/归一化恢复错误|本轮没有支持证据|51代model/actor/critic/Adam/RNG身份、19评价forward、原resume记录均通过；无VecNormalize|低：已检查范围不支持|
|执行门异常放行或硬安全被放宽|本轮没有支持证据|原拒绝/bridge/lifecycle与native审计通过；失败是拒绝而不是错误施加非法候选；G4全矩阵尚未闭合|低：不能据局部审计排除所有未测动作|

**PPO_STABILITY_CAUSE_IDENTIFIED=PARTIAL**。不声称统计显著性、患者泛化、已完成算法修复或确定catastrophic forgetting。

![已有记录的策略漂移和优化曲线](stability/PPO_STABILITY.png)

![原确定性050/080实际Human运动](stability/RETURN_REGRESSION.png)

源数据及PNG/PDF独立文件均在stability/；图只用真实历史点，没有从最终权重伪造历史loss。唯一下一研究建议见 `NEXT_RESEARCH_DECISION.md`。
''')
md('NEXT_RESEARCH_DECISION.md',r'''# 下一研究决策

唯一下一步：审阅本包后，单独授权 **H1：小步继续更新能否保留成功均值策略** 的有界开发验证。当前STOP，不执行下述方案。优先改训练策略，保留原reward/动作/安全合同；证据尚不足以先大改reward或替换PPO。成功checkpoint应始终保留为版本化父策略，开发选择按预先冻结完成门进行，不能覆盖原80集失败或追认3-seed成功。

## H1（首选）：固定小学习率减少累计漂移

- 支持证据：050→080 mean/实际动作链已改变，RETURN可行性丢失；每seed继续120epochs、188–220 Adam步而无成功策略保留门。单次记录KL小、clip fraction0，故先检验累计更新步幅，不预设“爆炸”。
- 最小实验：从原3份050 checkpoint做paired continuation，原LR3e-4对照与LR3e-5实验，其他PPO/reward/rollout/动作完全相同；每5episode保存父子checkpoint和固定观测Gaussian KL，定时评价deterministic与预注册sampled RNG；不按JF挑seed或checkpoint。
- 训练预算：3 training seeds ×2 arms ×30episode=180episode（失败也计）；原两个成功seed为主要终点，1106823814为预注册失败control。不能把只挑两个成功父策略的验证叫从零3-seed复现。若资源/开发准入不足则先停止，不自动缩小到有利seed。
- 成功标准：两原成功seed的最终30集后mean在nominal均保持2/2完整原runtime；预注册4个真正独立且合法的初态，每初态两次，实验臂每个退化seed至少7/8完成且不低于其050父策略；所有原安全/causal审计通过。其余control描述性报告。只有同时优于对照的保留结果才支持该机制，不据任一seed偶然成功推广。
- 失败标准：任一主要seed nominal丢失完成、独立初态显著掉出预注册门、审计异常或比对照无保留优势；全部负结果留存。若对照也不退化，结论为对该训练随机性下的机制不确定，不强行判PASS。
- 初态：需要4个未用于本轮诊断/调参的合法独立物理初态；先冻结生成规则并做工程准入。现有reset(seed)不改变nominal物理，不能用四个seed数字冒称四初态；如果当前接口不支持合法独立初始化，该部分BLOCKED，不放松门。不得借此更改ROM/torque/cuff/Human/任务期限。
- 合同影响：只改变PPO学习率的开发配置；原2D进度动作、物理、安全、task、reward不变。新配置需版本化开发准入，不能继承原冻结hash或正式资格。

## H2（仅H1审查后再考虑）：聚合完整episode减少singleton权重噪声

- 支持证据：65/240单transition；76/240出现singleton minibatch；原SB3对singleton跳过advantage标准化，critic解释力弱。reward/GAE的存储算术本身已通过，不先改reward系数。
- 最小实验：同原LR3e-4，收集完整episode累计至少64 transitions再更新，保留所有episode边界与terminal=0；minibatch16，并使用预注册划分保证无单样本批。对照仍单episode更新。每transition仍4epochs，单列真实Adam步和更新次数，承认更新节奏改变也是该机制的一部分，不能伪称优化暴露完全相同。
- 训练预算：3 seeds×2arms×30episode=180episode，独立授权、与H1不自动串行。30集结束的未更新余量必须按预注册终末批规则处理并保留；不能静默丢transition。
- 成功/失败：沿用H1的父策略保留、nominal和独立初态标准；只有无singleton且保留完成更好才支持假设，singleton消除本身不是学习成功。完整分布和失败必须公开。
- 初态及合同：同H1，先准入真正独立初态；动作/安全/物理/task/reward不变。只改rollout组织和advantage/批组织的开发版本，需重新冻结配置。

Stage2低force/平顺优化继续NOT_RUN；正式campaign为NOT_READY。原B/H150离线评分已恢复，但新live matched同父状态链、full-fork可移植性、G4严格矩阵和独立初态稳定性仍是独立门，不能用本轮PASS替代。没有扩容依据，不调整Hetzner或发起收费计算。
''')
statusrows=[[k,v['status'],'、'.join(v['evidence'])] for k,v in statuses.items()]
md('REPORT.md',f'''# iHEAR Lab — GitHub原评价器恢复与PPO稳定性诊断 v1

本轮结论：**原D01R/W1完整历史离线scorer已在云端从指定GitHub commit独立复现；云端代码差异已定位；050→080退化的执行链原因已确定，但唯一优化/奖励根因尚未识别。NEW_PPO_MATCHED_EVALUATION_READY、Stage2和正式campaign仍未就绪。**

T0：{t0.isoformat()}；报告生成：{now.isoformat()}；当前elapsed约{(now-t0).total_seconds()/60:.2f}min，硬上限T0+5h，最后45min不启动新长物理任务。全部新工作位于本目录；没有新PPO训练、backward或Adam更新。独立offline/CPU环境按GitHub hash locks安装。新增8次冻结MuJoCo开发评价已用尽上限，不再启动其他物理任务。

{table(['独立结论','状态','直接证据'],statusrows)}

## 1–5. GitHub、原scorer、冻结指标与剩余缺口

1. **真正恢复指定commit：是。** 远端研究分支和独立detached checkout均为`{start['requested_commit']}`；没有在旧研究目录git pull。SSH主机信任缺失保留失败日志，后用HTTPS clone成功，无凭据/SSH配置更改。最终源码身份见`audit/GITHUB_FINAL_IDENTITY.json`。
2. **原完整离线scorer云端复现：是。** 23来源、16锚点、完整v6 1426项、九合同、32原native fixture和90模型身份先核验，再运行原measure/compare与独立recompute，全部原断言开启。原fixture直接来自此次clone，不取旧ZIP/TAR，也不新造scorer。
3. **parent/B/H150冻结指标一致：是。**

{table(['历史输入','JF N·s','JM Nm·s','tracking RMS ° hip/knee','TASK s','raw jerk RMS °/s³ hip/knee'],histrows)}

原H150/B force改善2.353937394034738%，moment增加5.74653333830843%；全部motion/dose、任务/安全/科学执行/matched轴及receipt字段与冻结参考一致。原PHYSICAL_TASK_VALID、SCIENTIFIC_EXECUTION_CAUSAL_VALID、LEGACY_R2_MATCHED=PASS，HOST_EXECUTION_CAUSAL_VALID=NOT_EVALUABLE；保留原host-age失败记录，未换成实时通过。

4. **缺口：** 已运行离线scorer所需matcher、32fixture和九合同无缺失；完整可移植parent checkpoint与`D01R_parent_CAUSAL_STATE.json`仍缺失，历史native扩展ABI不作为3.12 live恢复PASS。FULL_FORK_REPLAY=NOT_RUN/UNVERIFIED，未构造替代父状态。
5. **新PPO完整matched评价：尚不可用。** 现有PPO nominal开发轨迹没有原同父prefix/B/H150匹配链。旧文档“scorer源码/fixture缺失”的阻碍已在本轮消除到离线层，不能因此给PPO授FULL资格，也不能把历史2.35%收益套给当前PPO。

详见`GITHUB_RECOVERY_AUDIT.md`、`FROZEN_SCORER_VALIDATION.md`和`HISTORICAL_MATCHED_REPRODUCTION.json`。

## 6–7. 真实云端源码及回流

实际240集由`rl_b_autonomous_replication_v1/replication_run.py`和447项冻结合同生成。414项科学闭包相对GitHub capsule为412相同+2修改；根Python为13相同+5修改+27新增+10GitHub独有。Python合计216个对照路径，172相同、7修改、27云端新增、10GitHub独有；不是仅按文件名或Git状态比较。active-main对应路径还缺capsule已有的rl_native_proposal.py。五个云端包证实两科学修复发生在早期g4_repair，其后414项源码树一致。

应优先审核回流：真实native区间force/moment积分修复、三phase期限优先级、相应独立审计；再抽取显式checkpoint合同/Adam/RNG、资源/gzip、训练与冻结证据工具。reward_v3 floor和单episode PPO属于需单独科学回归的研究版本；campaign/stage2/报告脚本保留历史特化身份。所有SHA与精确diff已交付，未自动覆盖、提交或推送。详见`CLOUD_GITHUB_SOURCE_DIFF.md`、`CLOUD_CODE_RETURN_PLAN.md`。

## 8–11. PPO为什么退化、训练/评价差异及证据边界

两个成功seed的050确定性冻结均2/2成功，080均0/2。相同准备native prefix、config和初始41D观测下，重新forward复现18次PPO历史确定性评价动作，另1次为固定合法[+1,+1]基线；51代actor/critic/model/Adam/RNG与原meta一致，无VecNormalize错配。050→080 mean漂移通过准入参考改变实际torque（TASK10ms已有分叉）及Human运动（15ms边界已有分叉），最终RETURN的候选进入原预测shank-table禁区，被拒绝并ABORTED。这是直接执行链证据，负mm不表示已经发生物理碰撞。

训练抽Gaussian sample再clip，冻结用mean再clip；两者不是同一个闭环目标。std约1且原动作常被clip，planner只评估单个候选，局部协调变化可以改变后续可行性。1495656323在51–80集随机训练19/30成功而最终mean失败，不能用训练曲线代替冻结完成率。两退化seed在共同causal观测上的mean绝对变化分别[.177006,.147412]、[.634878,.138427]；离线Gaussian KL分别.028598、.216017。

LR固定3e−4，继续120epochs/seed，target_kl=None；实际记录单次近似KL较小，clip fraction全为0，未见明确KL爆炸。value loss较大、解释力弱；65/240集只有1个transition，76/240有singleton minibatch，SB3对singleton跳过advantage标准化，是优先测试的高噪声/信用分配线索。日志KL只含最后epoch；梯度范数为裁剪后测量，缺裁剪前/分actor-critic梯度、精确minibatch历史，均标UNAVAILABLE，不伪造曲线。

所有240份reward及GAE再次重算通过。172失败总回报约−11.5，没有失败正总回报漏洞；107失败含正中间reward、48含正raw advantage，只能作为局部信用分配证据。原执行准入、source-age、bridge及实际native审计没有显示非法放行；G4全矩阵未闭合仍不能授予严格资格。最可能的解释是**未保护的累计策略漂移在高随机训练分布/均值部署差异和局部信用噪声下，破坏了RETURN协调可行性**；优化层归因置信中等，不能宣布唯一根因或catastrophic forgetting已证实。

本轮8次预注册随机冻结评价：{grouptxt}；seed1630784693的080为mean 0/2而sample 2/2，seed1495656323的080两种均0/2；这不是单一模式解释。仅两个共同RNG、同一已知nominal。新run全部独立物理/奖励审计PASS、原weights/Adam/checkpoint文件不变；0梯度更新。各次完整/partial JF/JM、实际动作与失败见`PHYSICAL_EVALUATION_RESULTS.json`。不同TASK时长不列相对force收益；随机一次成功也不是稳定性结论。

详见`PPO_STABILITY_DIAGNOSIS.md`、`TRAIN_EVAL_SEMANTICS_AUDIT.md`和两份PNG/PDF科学图。PPO_STABILITY_CAUSE_IDENTIFIED=PARTIAL，执行原因高置信，唯一优化根因未定。

## 12–14. 下一优先项、独立初态、正式资格

优先训练策略而非先换算法或reward：唯一下一步是审阅后单独授权H1的小学习率paired continuation；其次才考虑H2完整episode聚合/消除singleton。每个方案都有明确180训练episode/3seed上限、父checkpoint、对照、成功/失败门和独立初态要求，均只设计未执行，见`NEXT_RESEARCH_DECISION.md`。保留成功checkpoint，但不改写原3-seed/80集失败结论。

需要真正新增独立合法初态评价；reset seed变化不改变现有nominal物理，不能冒称泛化。初态族生成和工程准入须先冻结，接口不支持则该部分BLOCKED。患者泛化仍未测试。

**Stage2_NOT_RUN、STAGE2_READY=NOT_READY；FINAL_CAMPAIGN_READY=NOT_READY。** 原三seed/父策略重复门失败、G4 HOLD/绝对安全矩阵未闭合、新live matched链和独立初态稳定性缺口均保留。没有买算力或调整Hetzner。

## 审计、保护与STOP

原五研究包、checkpoint/raw/414科学源码、原ZIP及历史归档共13,683文件（15,484,480,779 bytes）在工作前记录SHA，封包后逐项重算，结果见`audit/HISTORICAL_PROTECTION_END.json`。GitHub checkout及原D01R合同保持不变。所有实际计算job、8个物理attempt和episode均有START/END；lossless raw压缩前后SHA相同，未丢弃新失败证据。CPU/RAM/磁盘/wall见`RESOURCE_USAGE.json`；最终身份、manifest、进程退出与封包验证见`PACKAGE_VERIFICATION.json`。

复核由同一Agent采用分离证据读取/原独立算术完成，没有第二Agent或人工独立审稿。没有Git stage/commit/push/merge/rebase/reset/stash/clean；只有新clone和指定detached checkout。没有修改历史控制器、任务、物理、安全、reward或权重；原执行闭包仅按hash复制到本轮隔离运行目录。新budget只配置资源/时间guard，不改变任务期限或物理参数。

**本轮最终STOP。不得自动启动训练、Stage2、后续研究包或大规模campaign。**
''')
put('audit/REPORT_GENERATION.json',{'generated_at':now.isoformat(),'report_elapsed_minutes':(now-t0).total_seconds()/60,'physical_results':len(physical),'new_training_episodes':0,'new_gradient_updates':0,'code_diff_complete':True,'historical_scorer_pass':scorer['status']=='PASS','same_agent_audit':True})
print(json.dumps({'reports_written':True,'physical_groups':physgroups,'status':{k:v['status'] for k,v in statuses.items()}},ensure_ascii=False))
