# 连续工作状态（供上下文恢复）

用户明确授权10小时无人值守研究；原任务逐字存于TASK_CONTRACT.md。当前goal active，不能在普通失败或阶段报告后宣布完成。

- T0服务器/UTC：2026-10-20T18:52:04+00:00；北京时间10月21日02:52:04。
- 不再启动新训练：UTC 2026-10-21T04:07:04（北京时间12:07:04）。
- 硬截止：UTC 2026-10-21T04:52:04（北京时间12:52:04）。
- 所有新工作仅此包。原历史包、原checkpoint、GitHub固定commit均只读，无Git写操作。
- 工具默认sandbox因bwrap网络命名失败；已自动审阅允许require_escalated读取/写本包及启动授权本地job。使用exec_command时继续明确scope，不需要普通科研确认。
- Python科学依赖：`/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/cpu-env/bin/python`。系统python没有numpy；非科学orchestrator可用系统python。
- 单Agent；用户未请求subagents，禁止自行spawn。报告写作skill已读，沿用用户给定结构，无外部风格材料。

## 已完成

447项冻结runtime按SHA复制至runtime/；原合同不改。历史保护起始清单约69k文件，复用上轮已核验保护清单并加入最新包和GitHub科学证据。固定HEAD=1adb1de177d6f5f32de6d01c4e629cbfae9ce121。未改物理/安全/task/原scorer。

三项原无物理测试通过；R1/R2 12个terminal/loop算术测试通过；owned独占进程组停止测试通过。原五集Control在两seed逐transition及更新后policy完全一致，checkpoint055 policy/Adam/RNG/计数也完全一致；strict paired Control051–080可复用，见audit/CONTROL_REUSE_DECISION.json。

启动有一次missing native_boundary_motion_audit模块导致导入失败，没有物理attempt；已从历史包逐字复制此独立工具到新runtime，修复后Control成功。所有程序失败日志保留。

最小source-return两patch已在本包scratch精确应用验证，未写GitHub。

## 持久化进程

脚本均在scripts/，PID及START身份文件在根目录；不要依赖固定PID，应使用pid_identity/same_pid启动ticks校验。

- campaign.py：有限队列，先两Control（已完成），H1两seed各30集、每10集det/sample冻结；H2聚合64各30集及final det/sample；在稳定性最好PPO配置上R1/R2各seed先10集，有任一冻结完成才延续至30集。最终写FINITE_QUEUE_COMPLETE.json，等待Agent实际reflection，不无限生成新reward。
- run_job.py：外层守护、每job独立进程组、超时/RAM/disk、内容地址source bundle。每worker只一个环境，每episode300秒/128决策/165k native，原子checkpoint。源代码变更后新job自动保存新bundle；已运行campaign导入的run_job函数不会自动热更新。
- watchdog.py：独立硬截止/孤儿ownedworker停止。
- report_status.py：LIVE_STATUS.json及2/4/6/8h内部阶段报告。
- failsafe_close.py：若Agent不能继续，T0+9h50m启动finalize.py，给10分钟安全封存窗口。到STOP后自身退出。不是启动下一包。

训练/评价预算以LEDGER.json锁定预留和结算为准，全部attempt含提前失败。上限450训练、60评价、50M native；默认单环境；6GiB RAM与10GiB磁盘余量。异常不明native按165k全额保守计数。所有raw均无损gzip并验证roundtrip，没有删除唯一失败证据。

## 已准备的分析与报告

- build_reports.py从ALL_ATTEMPTS.jsonl等重建所有主要交付，当前REPORT为RUNNING；最终需按实际结果改写20个答案为具体数值和结论，不要只交泛泛路径。
- motion_metrics.py只读保存raw，产出COMMON_MOTION_METRICS.json和实际Human series npz。已用Control完整episode测试通过。**现有campaign进程在最新run_job motion自动分析改动之前导入了模块，所以早期冻结评价可能需要手动批量补算**；不消耗物理预算。finalize.py也会补算但要提前完成以免deadline。
- checkpoint_diagnosis.py用科学venv运行，比较所有已冻结checkpoint在共同050因果观测上的mean/std/entropy/GaussianKL、actor/critic参数漂移，不启动物理。
- finalize.py停止物理、写END使monitor退出、核验全部历史SHA/447源/GitHub身份、重建报告、manifest、STOP。只在所有有价值分支完成或临近9–10h时运行；不能因单个失败提前全局STOP。

## 后续必做

1. 每分支结束/异常读简明日志和QUEUE_FAILURE，普通错误修复并用新job身份继续；不要改历史。H1/H2/R1/R2由finite queue预注册执行。
2. 依据实际结果，最多一个有证据R3候选（推荐思路只能在共同失败证据后考虑：更低量级、terminal-only、成功后有上界的force/moment成本，失败恒负，消除transient credit和大critic target；尚未加入代码或授权其具体公式）。最多两轮reflection，总候选≤3。
3. 保留最成功checkpoint版本；用剩余预算做跨seed后续10–20集保持/必要reward消融；训练总目标250–350而非KPI。
4. 预留最后未见动作流2026102191–2194，版本冻结后运行；不能用它们调reward，也不能称独立物理初态。开发rng2026102101/02历史已见。
5. 当前reset不支持经准入的独立物理初态，GENERALIZATION=BLOCKED；G4_STRICT_PASS=FAIL；新PPO无原同父prefix/B/H150 live matched链；Stage2/最终Campaign均NOT_READY。
6. 跑保存raw的common motion、policy诊断、训练曲线PNG/PDF。更新PPO_OPTIMIZATION_DIAGNOSIS、REWARD_CANDIDATES及manifest反思；完善资格各项证据和范围。
7. 最终报告中文20问要有实际训练/评价/native/Adam计数、具体分支结果、parent变化、force/JM/motiontradeoff和唯一下一建议。
8. 9h15m后不新训练，9–10h封存，10h所有owned计算退出。最终root复核finalizer退出、manifest真实性、所有进程退出后才goal complete和简短中文最终答复。

每次工具更新后不要忘记持续向用户说明有意义进展。用户离线不需要普通科研确认。新安全/因果/证据/资源停止漏洞才是GLOBAL_BLOCKER；一般FAIL只停止局部分支。

## T0+约50分钟更新

原Control两seed严格复演PASS已复用。H1延续10集的结果：149 mean失败15.825s（RETURN候选预测几何不可行），sample成功19.945s；163 mean成功19.03s，sample失败15.03s。每seed/模式只有一次，不能当稳定率/泛化。现正执行H1_seed1495656323_to020，进程需重新验identity，不能凭旧pid重启。

顶层RESEARCH_STATE原来滞后PREPARING，已替换只读状态monitor并记录旧进程退出；现在状态RUNNING/phase实时，counts权威为LEDGER。新状态monitor每15s读取ALL_ATTEMPTS，包含尚在进行job中已完成的episode。

新增：audit/GENERALIZATION_INTERFACE_AUDIT.json复核原native初始化确实绑定spec.start_return_target；case.task.start同时是RETURN目标，改变它会改任务。当前BLOCKED限于冻结PPO接口/准入合同，不是宣称未来无法支持初态。

新增execution_comparison.py和audit/NEW_EXECUTION_CAUSAL_COMPARISON.json：H1首失败与parent050准备物理prefix一致；TASK10ms reference分叉，10.25ms torque、14.5ms Human q分叉；actual clearance正0.019m/无接触，FAILED发生于planner candidate construction，不是activation validator。该反例共享观测Gaussian KL仅0.000956，不能假设小KL就保留任务。

H2合成工程测试PASS（65 transitions、3个完整episode、4epochs、无singleton/样本遗漏、GAE独立边界）。16个synthetic Adam单独标记，不计MuJoCo训练。离线gradient probe无physics/Adam；长episodecritic梯度占比>99.7%，singleton失败actor postclip范数0.3455，长批0.0077–0.0274。

worker已加before_update_checkpoint + COMPLETE_UPDATE_INPUT，更新异常保留PARTIAL_UPDATE实际Adam计数；recover_update.py可以无新物理重放完整rollout，不直接晋级部分更新emergency权重。新job源码内容地址保存，旧job已加载版本不热更新。

finalize.py强化：END后等服务退出，仍活跃则按PID启动身份关闭其独占会话；最后重算图表；自身SIGALRM在10h前5秒硬终止；decision日志旧稀疏schema在所有append停止后enrich_decisions.py补注，原始log完整存档，预算来自timestamped ledger重建且明确为后注，不冒充预注册。尚未运行finalize，研究仍继续。

后续可考虑而未启动：若H1/H2和Reward继续表现mode错配，单独研究较低初始Gaussian std（如有物理尺度理由的0.2）以减少sample+clip和mean部署差异，保持动作空间/安全不变，作为独立新初始化分支，不冒称同一个H1实验；必须根据最终结果再预注册，不盲搜。R3仍需实际Reward反思后生成。

## T0+约1小时检查点

1495656323延续20集的mean仍失败16.020s，RETURN候选预测几何−73.134783mm；sample成功19.975s，不能与19.03s父策略直接比较JF收益。共同行为KL约0.005294、mean漂移[0.098815,0.011957]。当前H1_seed1630784693_to020已核验live，按原计划继续，不重启。上一次wait_progress统一exec session22580已600秒正常退出，无需重连/重启该观察器。实际当前计数与进程身份保存于GOAL_TURN_CHECKPOINT.json。

新增预算/资源十项负向工程测试通过，见audit/BUDGET_RESOURCE_GUARD_TESTS.json，影子ledger无物理、未改实账。plot_results已版本化并改善4×2冻结图：统一x轴、加入0点历史parent050，直接显示任务时长，completeJF/JM排除partial；图已视觉检查legible。build_reports支持SCIENTIFIC_REVIEW.md作最终具体20问正文，最终root必须实际写此文件，否则只生成运行中框架。finalize重建报告不会覆盖单独review正文。

## T0+约1h50m：H1已完整闭合，H2真实进行中

H1 60次继续训练+12次冻结评价全部完成，status COMPLETE_DEVELOPMENT。两seed Control原051–080可严格复用：149训练19/30成功、561 decisions、220 Adam、3,184,080 native；H1为14/30、446 decisions、200 Adam、2,751,320 native。163 Control为11/30、424 decisions、188 Adam、2,828,240 native；H1为15/30、451 decisions、204 Adam、2,891,140 native。

H1 mean端点10/20/30：149全部失败；163全部成功19.03s。sample dev1端点：149成功/成功/失败，最后14.68s失败；163全部失败，最后15.205s。Control080 mean两seed均失败，所以只支持163一个父策略的nominal mean保持，不能授一致两seed稳定性或关闭mode差异。H1_STABILITY_ANALYSIS.json已独立保存原control/新H1成本、完整父比较及限制。PPO_OPTIMIZATION_DIAGNOSIS.md有完整量化结论。

163最终mean完整同19.03s比较：JF+0.353088%，JM−1.220504%；tracking RMS[0.505625,0.580361]→[0.491994,0.461454]°，jerk RMS[388.444809,810.606011]→[374.027438,802.416697]°/s³。不是force改善；所有峰值/terminal/overshoot在TASK_FORCE_MOTION_COMPARISON里由build_reports自动列出，不能把部分RMS好转当全面motion资格。

H2_AGG64_seed1495656323_to030在原050/R0/LR3e-4真实运行，PID需重新核验，最近为186598。首个实际更新在episode004：4完整episodes、80 transitions、20 Adam、0singleton；parent Adam/RNG恢复通过。见audit/H2_FIRST_LIVE_UPDATE.json。不要重启该job或原campaign进程。

新精确Gaussian诊断：audit/GAUSSIAN_CLIP_PROPOSAL_DIAGNOSIS.json在原050已见合法obs上算Eclip(sample) vs clip(mean)，预计clip分量比例149=35.369%、163=39.517%；mean proposal差显著。反事实std0.2预计0.769%/5.794%，std0.1预计0.013%/1.628%，尚未训练或建立policy variant，不能当任务成功。若主线结果仍有价值才独立预注册单一STD实验，不盲搜，作用于准入前提议而非实际torque。R3仍待真实R1/R2结果后决定；可考虑稀疏终末、仅成功时有界剂量成本来消除partial收益，但未写新版本。

新source_import_audit.py无物理probe通过103个实际加载科研模块路径/SHA，见audit/ACTUAL_IMPORT_IDENTITY.json。新audit_accounting.py独立联结ledger/episode summaries/Adam/native，live51个settled已通过；合成工程16Adam明确不进实际MuJoCo训练ledger。finalize已加入final accounting audit。

Reward版本新增reward_versions/R0,R1,R2各自完整源码+SELECTED_CONFIG+独立DEFINITION SHA，REWARD_VERSION_MANIFEST已注解保留旧manifest。代码/公式/权重未变，尚未执行R1/R2。冻结评价继续用原R0算术审计；build_reports在FROZEN_RESULTS明确区分trained_policy_reward_version与evaluation_reward_contract，避免把候选训练Reward误解成R0。

build_reports资格更新：如只有部分父seed在所有已测mean端点保留到30，PPO_STABILITY_IMPROVED=PARTIAL_NOMINAL_PARENT_RETENTION；不授统一PASS。正式G4/live matched/Stage2/finalCampaign仍分别FAIL/NOT_READY。

COMPLETION_REQUIREMENTS.json把完整任务分为20组具体核验要求；当前OPEN，最终必须逐项检查内容/真实执行，不只看文件名。最终具体20问必须写SCIENTIFIC_REVIEW.md，build_reports会嵌入，不能只交运行中框架。

下一关键时间：UTC20:52:04（T0+2h，北京时间04:52:04）PHASE_2H自动报告。应补入具体H1结论、H2实际聚合进度、当前仍保留原050两seed参考、未形成一致新候选、预算和替代路线。阶段报告不是STOP。观察器1090已900s正常结束；70811已H1 target30完成正常退出。当前live身份/精确计数在GOAL_TURN_CHECKPOINT.json。

## T0+2h阶段报告与Reward聚合对照修复

PHASE_2H.md由monitor于UTC20:52:06（elapsed2.001h）生成，快照训练86/eval12/native9,375,440/RL1528/Adam532，剩364训练/48eval/40,624,560已结算native。root已保留原auto报告到audit/phase_reports并补入具体H1结论、原050共同参考、H2状态、后续计划与阻碍。它不是STOP。

重要科学对照缺陷已在Reward物理前修复：如选择H2，原先R1/R2的10+20 job末端各强制flush会不同于连续30的baseline聚合节奏。现在worker只对REWARD_*且aggregate64读取不可变configs/REWARD_ROLLOUT_PROTOCOL_v1.json：global terminal30，>=64完整transitions更新，29集保留终末余量；10集不额外flush，pending完整episodes随checkpoint/source SHA保存，下一段恢复且验证policy/reward/输入SHA一致。EFFECTIVE_CONFIG.json和meta effective config SHA明确派生参数。原live H2已加载旧source，未改它；后续单job30 H2的规则数学等价旧规则，源版本独立保存。

test_pending_equivalence.py无物理测试PASS：连续30与10+20在10集恢复12个pending transitions，29集达到阈值不提前更新，最后65样本无singleton；最终policy/Adam/Python-Numpy-Torch RNG/所有计数完全一致。64个synthetic Adam（两路径各32）只为工程验证，加上原批测试16，总80；已修正audit_accounting/build_reports显式分开。首次测试有一个括号SyntaxError，零physics/Adam，立即修复，单独保存工程失败记录。源码/结果见audit/PENDING_BUFFER_EQUIVALENCE_TEST.json、PENDING_EQUIVALENCE_SOURCE_IDENTITY.json及source_versions/engineering_*。

若Reward10集筛选拒绝而尚有pending，必须保留并明确报告未用于梯度更新的数据，不能假装全部已优化。若继续至30，所有pending统一进入最终更新。worker紧急异常计数也补取env.steps/budget以计入已尝试决策。Reward函数/权重和硬安全没有变化。

新增USED_SOURCE_BUNDLE_VERIFICATION：20个已使用内容地址bundle全部字节SHA匹配，初始Control5份checkpoint记录的worker源码SHA也均能在已保存版本中找到，无关键源码身份缺口。已完成H1的源码不覆盖。

当前首H2仍是同一186598进程，必须重验启动ticks后继续观察，不能重启。下一个有价值结果是H2首seed30集mean/sample冻结，然后另一seed30。继续有限R1/R2队列。做可选扩展前应在剩余60eval预算中为最终4未见动作RNG×2seed保留8attempt，native至少保守1.32M；它们不是独立物理初态，不得用结果再调Reward。此为后续分配注意，不改变用户硬上限。

## T0+约2h20m：H2首seed已完成，另seed运行中

H2 seed1495656323训练30集15/30完成，450采样transitions全部进入更新一次各4epochs；7次PPO.train、28内部epochs、120实际Adam、0singleton、2,771,040 native。首seedmean冻结COMPLETE19.03s，sample dev1 COMPLETE19.905s；后一不同duration不可与父19.03直接列力收益。H2_FIRST_SEED_ANALYSIS.json保存全比较。

H2首seedmean完整同19.03s对父：JF1440.2152776 vs1446.7929247，−0.454636%；JM102.6291124 vs101.5328034，+1.079758%。tracking[0.487327,0.501623]°，jerk RMS[397.250251,910.920881]°/s³。共享原050 obs KL0.00236686、mean漂移[0.0128107,0.0650633]；initialmean[0.714029,0.588846]，std仍约[0.9885,0.9833]。这个mean与sample都成功的nominal正信号不能代替另一seed、继续训练保持或独立初态验证；moment增加必须报告tradeoff。

已重读历史同dev RNG对照：149原050 rng2101成功19.93s、rng2102失败5.725s；原080两个都失败（rng2101 14.745s）。新H2 rng2101成功19.905s。这是已见动作流的具体配对结果，不是成功率或泛化。

当前H2_AGG64_seed1630784693_to030进程启动，最近PID194508（需重新验ticks），原050 full Adam/RNG恢复PASS，EFFECTIVE_CONFIG确认R0/LR3e-4/aggregate64，未使用Reward筛选协议修改它。当前真实预算/身份在GOAL_TURN_CHECKPOINT。等待其30集+2冻结后，原finite campaign自动选PPO（最终mean数优先、sample数次之）并跑R1/R2，仍无需普通确认。

观察器41105在2h文件就绪正常退出；93928在H2第一mean结果就绪正常退出。不要重复启动原训练，不需要重连已结束观察器。PHASE_4H下一时间UTC22:52:04（北京时间06:52:04），按实际结果补充具体候选/预算/替代路线，不能因局部失败停止。

## T0+约3h20m：H2双seed正信号，R1筛选与源码补审

H2已双seed30集闭合：mean2/2完成19.03s，sample dev1为149成功19.905s、163失败15.0s。149/163训练分别15/30、11/30完成，450/448 transitions全部各4epochs入更新，120/120 Adam，0singleton。两mean同父JF −0.454636%/−0.199720%，JM +1.079758%/+0.351936%。预注册端点lexicographic排序选H2=(2,1)而H1=(1,0)，Reward从各自原050开始，不从H2已训练030串接。H2只测30端点，非10/20保持或独立初态资格。

R1 seed149十集完成3/10训练、40Adam，完整pending0；mean完成19.03s JF1444.617266/JM102.122544，sample完成19.925s（时长不同不算收益）。另一seed十集实际运行，需重新核验PID/startticks，随后4次共同冻结筛选和按原门延长双方至30。R1实际effective globalterminal30/carrypending true、protocolSHA a3e042...已核实。第一seed10无pending不代表第二也无；真正10→20续段时再核查pending恢复。R2尚未训练。

新增只读scripts/saved_action_execution.py、phase_dose_attribution.py、reward_reflection_evidence.py、shared_first_rollout_probe.py及audit对应JSON/MD。不增加物理或Adam。H2 mean无请求拒绝，sample clip44%/47.22%；原149父mean有一次planner失败仍完整，不能把请求拒绝等同任务失败。H2 RETURN JF变化−11.050978/−3.199644N·s，OUTBOUND+4.473353/+0.329568；RETURN JM+2.185846/+0.399594，HOLD几乎不变。TRAINING_CURVES/H2_phase_dose_tradeoff.png/.pdf已视觉核验legible。明确JF/JM原5ms传感器左积分/实际执行区间，真实Human导数0.25ms native；不把前者冒称逐native force求积。

首个实际聚合rollout：同seedR0/H2与R1的obs/actions/oldvalues/logp/边界/preupdatepolicy精确相同（149 n80，163 n77）。固定minibatch、未更新参数处，R1 actor裁剪后均值0.017922/0.022218 vsR0 0.044943/0.082165，critic占比99.788%/99.740% vs98.712%/95.752%。只是共同样本局部gradient竞争，不模拟actualshuffle/Adam后续或唯一根因，仍以真实冻结任务选优。R1首十集失败均−30、成功约24.74，failedpartial cost0.0005–1.032<floor15，不是失败正回报漏洞。

扩展audit_source_versions.py逐job bundle和全部训练checkpoint核验发现最早Control001奖励源码cd4adb...缺归档；从本会话原AddFile JSON字符串精确恢复2539bytes，SHA完全相等，保存source_versions/recovered_early_reward_cd4adb.../rewards.py及audit/EARLY_CONTROL_REWARD_SOURCE_RECOVERY.json。后续Control002–005元数据磁盘SHA410742...不能当已import模块重加载；两份源码保留、R0行为同原baseline且严格复演通过，旧R1/R2只是未训练draft。当前全部已用bundle/checkpoint0 mismatch；旧验证快照存audit/source_verification_snapshots。最终必须再跑全新jobs。

finalize尚未运行。已增加最终全usedsource/checkpoint/pending核验、savedaction/reflection/phase图分析；将audit/observers/*/START.json观察器纳入进程关停及核验，避免封存后写日志。wait_progress新源码遇END退出；当前旧观察器若收尾仍活跃会按identity关闭并诚实外部END。9个脚本AST检查通过。最终仍需实际9–10h、具体SCIENTIFIC_REVIEW.md二十问、全部completionmatrix内容审核、protected历史完整SHA、最终manifest退出后独立重核验，不可只因本阶段完成就STOP。

下一：看R1两seed10冻结与延长，R2后actualreflection再决定R3；优先候选双seed更长续训保持边界，必要reward消融/动作探索尺度分支取决于真实结果，不盲搜。为最终4新动作RNG×2seed保留8eval/至少1.32M native，最终streams不得用于回调Reward。PHASE4H于UTC22:52:04（北京06:52:04）到点，需补具体结果/当前候选/预算/替代路线。

### R1十集筛选已四次完成并延长

R1_SCREEN10_RESULTS.json：149 mean19.03/sample19.925，163 mean19.03/sample19.385，四个已见nominal dev1均完整，不是泛化率。149训练3/10、152transitions、40Adam、pending0；163为3/10、136transitions、20Adam、优化77/pending59来自4完整episodes。source auditor原glob误把pending JSON当metadata已修复exactfilename，实际pendingSHA/policy/count/episode boundaries全部核验PASS，见audit/REAL_PENDING_CHECKPOINT_AUDIT.json。新sourceverifier30bundles87checkpoints0mismatch（后续应再更新）。

REWARD_R1_seed1495656323_to030已实际启动（PID208142/startticks6218462需重验），从10 checkpoint fullstate恢复PASS，pending0，全局30/effective protocol保持；之后另一seed延长必须实际恢复59，不可丢弃。观察器54460已632.78s正常结束，不应重新连接该session。当前ledger与liveidentity在GOAL_TURN_CHECKPOINT。R2未训练，未开holdout、R3、STD或更长保持分支。研究继续，不最终STOP。

## T0+约3h50m：R1首seed30完成，真实pending恢复证明通过

R1 seed149的30训练13/30完成，431 sampled=431 optimized transitions，6次PPO.train/24epochs、116实际Adam、native2,703,420、0singleton、pending0。30端点mean COMPLETE19.03s，JF1439.053717830/JM102.896411676，同父050 JF−0.53492153%/JM+1.34302234%；对H2 R0三十端点JF−0.08065181%/JM+0.26045167%。sample COMPLETE19.915s，JF1456.671794916/JM108.320296503，不同时长不列force收益。完整比较、motion、policy drift在R1_FIRST_SEED30_ANALYSIS.json。另seed未完成，不能提前宣布R1双父30稳定。

REWARD_R1_seed1630784693_to030已真实启动PID213078/startticks6367080（需重验），fullstate恢复PASS，真实恢复59 pending transitions/4完整episodes。scripts/audit_real_pending_continuation.py已在真实第11集更新后PASS：旧59+新增24=83，完整输入JSON按顺序完全相等，批量/episode计数、未更新生成policy和Adam一致；实际24Adam，非本审计产生，见audit/REAL_PENDING_CONTINUATION_AUDIT.json。无需重启/重放恢复。观察器1455已因首seed30 job END正常结束1033.4s；不要重连旧session。

新增SCIENTIFIC_REVIEW_WORKING.md为二十问具体运行中底稿，不能当最终稿；最终必须根据完整结果生成SCIENTIFIC_REVIEW.md。纠正父149motion：原jerk RMS[416.435,1061.284]，H2[397.250,910.921]，原加速度峰[74.849,150.069]→H2[81.490,154.784]；父163 jerk原[388.445,810.606]，不能把两seed的父指标混用。

RETENTION_EXTENSION_PLAN.md为条件性方案，未执行：优先在R1/R2实际30结论后，R0/H2及合适Reward各两seed从30继续至60（每cohort60训练/4eval，最多120/8）。REWARD_*筛选worker会固定terminal30，不能静默拿来60；应独立RETENTION_*身份显式terminal60、一次30集整段、原Reward/其他PPO不变。必须最终按30→60谱系判断退化，不能让新branch名遮蔽60失败而继续笼统授稳定性。启动前重新决策与预算，不因有方案就自动执行。

新增scripts/reward_unit_counterfactual.py、audit/REWARD_UNIT_COUNTERFACTUAL.json/.md：只测试R1/30（30为公开failure15+floor15），在已存第一聚合样本重算完整边界GAE，divisor1逐字节复原原returns/advantages，0physics/0Adam。R1 actor裁剪后均值149 .0179216→.0884271，163 .0222175→.2009601；critic占比99.788/99.740%→96.525/82.980%。只是单位/旧critic/GAE/joint clipping共同影响的离线动机，不能预测成功或唯一归因，不是实际R3。global gain保持完整轨迹reward排序但不保证PPO优化不变；GAE targets仍可超出归一化episode回报范围。须等真实R1/R2 reflection和预算后再决定是否第三候选/必要scale-only消融，不盲搜多个scale。当前R3、STD、holdout、更长保持均未开。

PHASE4H将于UTC22:52:04生成，需要补具体H2双父30、R1首父30/另一真实进展、预算和下一R2/保持路线，保留原auto快照。最终builder目前elapsed取生成时clock；最终二十问实际时长须读取START/END，必要时修正final prefix，不能把报告生成时间冒充物理停止时刻。finalizer未运行；goal仍active，必须9–10h和最终内容/全历史保护/所有进程退出/独立manifest复核后再complete。

### T0+4h正式阶段报告已闭合（研究仍运行）

PHASE_4H.md auto于UTC22:52:06.030343、elapsed4.001h生成：训练182、eval22、native19,269,780、RL3087、实际Adam892；一个在途165k reserve，native未占用30,565,220，另预留最终8eval/1.32M后可分配约29,245,220。root于22:54:10补科学判断和下一路线，原auto完整归档audit/phase_reports/PHASE_4H_AUTO_<sha>.md，补注JSON标明cutoff/实际补注时间，不回填后来的科学结果。cutoff时R1第二seed已结算21集、22在途；首seed30 mean/sample均完整，R2尚未开始。不是STOP。

观察器20260已因phase文件正常结束466.66s，不再重连；当前无该观察器。第二R1 to030仍同PID213078/startticks6367080，需要重新验证再等终点（预计不久），随后campaign自动R2。live accounting新核验PASS：206 admitted/205settled、realAdam912、native19,465,400、80syntheticAdam独立；usedsource新核验35 bundles/94metadata全部PASS，含真实pending新checkpoint。

报告生成器已版本化修改：final且ROOT/END.json.status=STOP时elapsed取正式END.unix，而非后续报告生成clock，AST通过；运行中仍按当前clock。最终实际研究/物理停止/封存时间要分别从真实记录说明，不能以报告生成时刻冒称实验终点。finalizer仍未运行、SCIENTIFIC_REVIEW.md尚未最终填写，20completionmatrix仍OPEN。下一PHASE6H UTC00:52:04，不要因4h报告结束研究。

## T0+约4h20m：R1完整共同结果与reflection，R2真实启动

R1_REWARD_RESULTS.json/R1_REWARD_REFLECTION.md已完整保存。两seed的10/30 mean/sample共8次已见nominal开发评价均COMPLETE，不能合并成单策略泛化率。149三十mean19.03s，JF1439.053717830/JM102.896411676（对父−0.53492153%/+1.34302234%）；163三十mean19.03s，JF1432.032828932/JM103.407842552（对父−0.34939508%/+0.64077329%）。两sample19.915/19.910s，后者JF1443.445769182/JM113.726366705，duration不同不列force收益。R1比H2 R0三十mean再降JF0.0806518%/0.1499749%，但JM又增0.2604517%/0.2878243%。163 knee tracking RMS0.6275866° vs父0.5803606/H2 0.5985309；真实motion全指标在JSON和共同table，不能只看force或jerkRMS。

R1训练149为13/30、431sampled=optimized、6PPO.train/24epochs/116Adam、native2,703,420；163为14/30、424sampled=optimized、6/24/116Adam、native2,821,160。均0singleton/terminalpending0。真实59+24=83跨段更新证明PASS保持。R1保留为nominal开发候选，尚无更长保持/未见动作流/独立初态/正式资格；下一先完成R2，不修改R1权重。REWARD_CANDIDATES/PPO_OPTIMIZATION_DIAGNOSIS已加入真实结论和引用。

R2 seed149 first10已启动，最近PID218284/startticks6524706（需重验），从原050 full Adam/RNG恢复PASS，effective R2/LR3e-4/aggregate64/globalterminal30/carrypending true，protocolSHA a3e042...未变。首个实际更新n80；scripts/audit_first_reward_inputs.py可重复验证R0/H2、R1、R2第一聚合rollout的obs/rawaction/oldvalues/logp/episode边界及preupdatepolicy完全相同，seed149 PASS；seed163还没开始，标AWAITING，不能补称双seed通过。R2仍按原2seed10+冻结anycompletion→双方至30队列自动推进，当前无需另启worker。

观察器60911已因第二R1最后sample END正常结束630.97s，不应重连。当前live R2和预算见GOAL_TURN_CHECKPOINT。finale8动作RNG2026102191–2194仍未运行，至少保留8eval/1.32M native。

文档精确性补正：REWARD_CANDIDATES现在区分f(p)连续映射与实际phase估计p在容差切换可能跳变；gamma1真实前后差仍telescopes，不能声称phase数值严格连续。仅改表述，reward/physics/权重/版本定义未改，旧doc归档。

未来如启动新的持久extension/optional supervisor，必须把其START身份纳入finalize.py服务关停与最终独立进程审计；当前只含原5服务+audit/observers。新branch做30→更长保持时必须连接谱系修正资格，不能由新branch名掩盖后续失败。若增R3/改manifest，应先按hash归档当前REWARD_VERSION_MANIFEST，保持R1_REWARD_RESULTS记录的旧manifest SHA仍可追溯。R3/STD/retention/holdout目前均未执行。

## T0+约4h45m：R2共同筛选完成；真实受控更新修正梯度解释；父状态准入强化

R2_SCREEN10_RESULTS.json：两seed10集mean/sample四次均完整。149 mean19.03/JF1444.446939819/JM102.093164945，sample19.93/JF1452.588234189/JM108.536064032；163 mean19.03/JF1434.047937343/JM103.318870481，sample19.38/JF1456.031460671/JM103.116378661。皆已见nominal dev1，不是泛化率。训练各3/10，149采样=优化152/40Adam/pending0；163采样136/优化77/20Adam/pending59来自4完整episodes。按原门双方延长30；第一R2to030真实在跑，最近PID223924/startticks6692781，需重验。fullstate恢复PASS、R2/LR3e-4/aggregate64/global30和原protocolSHA不变。

新的实际first-update证据很重要：scripts/controlled_reward_update.py，audit/CONTROLLED_FIRST_REWARD_UPDATE.json/.md。两seed的R0/H2、R1、R2 first80/77物理输入、pre policy/Adam/Python-Numpy-Torch RNG/所有计数、PPO超参数和update函数AST完全一致，各真实20Adam/4epochs；ZIP SHA核验。149 actualKL R0 .000215932/R1 .000236095/R2 .000233133；163为.001311418/.001525888/.001499790。虽然初始固定参数处R1 actor裁剪后梯度较小，完整实际Adam更新KL并未同比减小，R1反而略高；不能把R1任务保持唯一归因为“较弱actor更新”。这只是受控首更新Reward效应，不是后续闭环根因/泛化。PPO_OPTIMIZATION_DIAGNOSIS已有两个阶段说明，旧一seedMD按hash归档。audit_first_reward_inputs.py当前两seed都PASS。

checkpoint恢复入口现有明确工程强化：原worker已标partial emergency但普通入口未强制拒绝；现在在任何interface/model/物理reserve前，若parent.partial_attempt或resume_requires_explicit_offline_pending_recovery则报PARTIAL_PARENT_REQUIRES_EXPLICIT_RECOVERY（missing metadata另报清楚）。旧worker7314e741...已保存，新worker SHA784ebd356d10cdeb707615bf89cb2c26733f89c47017be4ff6db5d1b1741a29b。只影响不合格父准入，不改PPO update/Reward/动作/447冻结科学源；live旧worker不热更新，新job内容地址保存。

真实负向启动probe PASS：audit/PARTIAL_PARENT_ADMISSION_PROBE.json，synthetic metadata无ZIP，在interface/episode/reserve前拒绝，0physics/0Adam，输出runtime/jobs/ENGINEERING_PARTIAL_PARENT_PROBE_v1仅为工程拒绝，无物理ledgerattempt，不能误计为漏记的评价。实际R2 seed163 ten checkpoint带完整pending59、无partial标记，新guard frozenworker正常放行/fullstate恢复PASS，证据NORMAL_PENDING_PARENT_ADMISSION.json。affectedLevelA追加该源码版本两个检查并按hash归档旧门。recover_update.py实际故障重放仍没调用，不可声称已实际故障恢复通过。

SOURCE_RETURN_PLAN新增完整pending/partial-replay范围及guard；patches/worker_partial_parent_admission.patch只针对隔离研究worker旧版本，在新scratch应用并与当前字节相等，update AST不变，audit/SOURCE_RETURN_PARENT_ADMISSION_PATCH.json。不是固定GitHubmain patch（该树没有新worker），无主树apply/Git写。P0原两patch不变。最新usedsource44bundles100checkpoint PASS，live accounting240admitted239settled PASS（realAdam1004/native22,831,820，80syntheticAdam独立）。

wait_progress.py新增可选--only-new及START源码SHA，可跳过已知历史冻结结果；旧版本已存source_versions/orchestration_<sha>。当前80342观察器已正常结束274.44s，不重连。后续observer加--only-new，仍有独立identity/时限/END/STOP退出，不启动physics。

后续仍须完成R2真实30和全部reflection，再用实际剩余时间/预算决定R3单一单位消融和/或更长保持。离线R1/30只是动机，实际Adam数据证明不能直接预言更新或成功；不能盲搜scales。若增加持久可选queue记得将其START身份纳入finalize服务关停；retention新分支必须连接30→更长谱系，不能遮蔽退化。最终8RNG(2191–2194)×两seed仍完全未运行，至少预留8eval/1.32M native。新训练UTC04:07:04截止，硬停04:52:04；下一PHASE6H UTC00:52:04。finalizer未运行，SCIENTIFIC_REVIEW.md和20completionmatrix最终审阅仍open。

观察器76608已实际启动（--only-new，最多1800s，target第一R2to030外层END），首次输出23:40:03确认PID223924仍live且无旧结果噪声。下一turn可poll该session；观察到时限不等于训练终止，任何重启前仍需核验实际job/identity。

## T0+约5h10m：R2首父30完整；具体二十问运行稿；有界后续执行器已备但未执行

R2_FIRST_SEED30_ANALYSIS.json：149三十训练15/30，450sampled=optimized、7PPO.train/28epochs/120Adam、native2,771,140、0singleton/pending0。mean COMPLETE19.03s JF1439.974194104/JM102.740283563，对父JF−0.47129969%/JM+1.18925124%；对H2 JF−0.01673940%/JM+0.10832319%；对R1 JF+0.0639640%/JM−0.15173329%。sample COMPLETE19.905s，JF1457.129742450/JM108.464887765，不对原mean父列sample剂量收益。不能据一父终点评价R2双父一致性。

第二R2to030现同PID228894/startticks6843827（必须重验），fullstate恢复PASS，真实恢复59pending/4完整episodes，policy cd3b5ec3...与R2父匹配，已出现83-transition实际更新/24Adam，继续同global30。预计本原finite queue在不久后R2两模式都完才结束，之后必须Agent做实际R2完整reflection，不因finite文件存在就停止10小时研究。观察器76608已因第一R2train END正常退出979.62s，不重连旧session。

SCIENTIFIC_REVIEW.md现已创建为具体20问的RUNNING审阅（截点UTC23:56:36，约5.076h），REPORT会嵌入具体数字，不再只是通用框架。SCIENTIFIC_REVIEW_STATUS.json为RUNNING_REVIEW_INCOMPLETE/required_final_update=true/goal_complete=false。它仍缺后续结果/关闭证据，不能当最终稿；最终要按全部实际数据逐题重写、状态和SHA更新。finalize要求两个review文件存在，并将scientific_review_status、review SHA、completion_requirements_status写入PACKAGE_VERIFICATION，文件存在不冒充内容最终通过。FINAL_REVIEW的实际START/END、保护、所有进程、manifest和20requirements仍待核验。

已准备 scripts/followup_queue.py（未启动真实queue），schema FINITE_FOLLOWUP_QUEUE_v1，计划字段queue_id/phase(OPTIONAL_RESEARCH或FINAL_VERIFICATION)/purpose/required_sources(worker.py,rewards.py,research_common.py各SHA)/jobs[{config:absolute ROOT/configs路径,sha256}]。不生成Reward、不无限搜索。exclusive .followup_queue.lock防双scheduler，原FINITE_QUEUE_COMPLETE和CAMPAIGN_QUEUE_END都存在且原PID已退出、无liveworker/其他followup/在途预留，资源和时间门满足才执行。整份未运行列表按165k/attempt保守上界检查450/60/50M，OPTIONAL_RESEARCH额外保留8eval/1.32M native；FINAL_VERIFICATION只能eval且reserve0。预算不足先重做有界科学分配，不私改cap。

命令先`python3 scripts/followup_queue.py PLAN --validate-only`，然后实际科学选择后用detached Popen(start_new_session=True)启动CLI，stdout/stderr存新queue文件，核验followup_queues/<id>/START.json真实PID/startticks。脚本保存PLAN/source/逐job结果/START-END，每job复查cfg/SHA和三份worker源码一致，调用现有run_job；TASK FAIL是正常完成物理尝试，工程异常只停局部queue返回Agent。正常完成只标AWAITING_AGENT_RESEARCH_REVIEW，不STOP、不另起Campaign。每个queue唯一ID不可覆盖。

仅做了read-only验证：audit/FOLLOWUP_QUEUE_READONLY_VALIDATION.json PASS，one projected eval、final reserve8、当前主队列阻挡start、wrongcfgSHA被拒、无queue目录/worker/ledgerentry创建，0physics/0Adam，actual_followup_execution_tested=false。configs/ENGINEERING_FOLLOWUP_NEVEREXEC_v1.json和audit下两个验证plan只作只读probe，绝对不要执行为科学实验。详FOLLOWUP_EXECUTION_CONTRACT.md。

finalize.service_sources已自动包括followup_queues/*/START.json及原5服务/observers；source异步SIGTERM关闭group并保留诚实END，最终进程审计包括这些服务。wait_progress已识别live后续queue，在原FINITE_QUEUE_COMPLETE后仍继续观察；--only-new仍可用。三个orchestration源码按SHA存source_versions；旧live observer76608的only-new源码已用inverse编辑仅在SHA精确匹配START里的16b286c...后归档，见audit/ORCHESTRATION_SOURCE_PROVENANCE.json，非盲重建。

后续科学实际决策仍待R2全完：优先成功checkpoint更长保持，必要时单一Reward单位消融R3（未创建）。若新增R3，当前build_reports的search_complete只看原FINITE_QUEUE_COMPLETE，必须同步扩展明确追加研究状态，避免R3尚未执行就说整个Reward搜索完成；生成新Reward源码/manifest前先按SHA归档当前版本（R1结果绑定旧manifestSHA），保存R0/R1/R2独立定义和实际使用源码身份。任何retention新branch必须按父子谱系复核资格，不能让60失败藏在独立label而仍笼统宣称保持。最终RNG2191–2194×两seed仍未用，绝不能据其结果再调Reward。

当前时钟已过UTC午夜到2026-10-21，不改变START里NO_TRAIN04:07:04/HARD04:52:04。下一PHASE6H UTC00:52:04、8H02:52:04。finalizer尚未运行、尚未STOP；goal必须仍active。

观察器11312已实际启动（当前followup-aware源码，--only-new，最多1800s，target原FINITE_QUEUE_COMPLETE.json），00:05:58确认第二R2 PID228894仍live。下turn可poll同一session，超时不是training终止；主要物理过程不应重启。后续runner的整份保守native预算若拒绝大批量，可在科学设计不变的前提下用明确逐seed/逐阶段的新plan，在先前实际结算后重新分配；不能增加硬预算或挪用最终8eval。
