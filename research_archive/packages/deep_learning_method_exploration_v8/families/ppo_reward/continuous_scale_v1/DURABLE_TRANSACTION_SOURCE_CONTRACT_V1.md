# Beta根事务候选：source-only，真实调用0

本批新增三个源，旧Beta/common/sequence/adapter/draft/axis/optimizer/categorical及root脚本均不修改。未创建真实plan、launch authorization、Gate1 PASS、Beta clock或checkpoint。唯一ACTIVATION与2026-10-27T15:25:40Z全局截止保持原样。主Agent审查后自行创建薄wrapper/配置、登记预算并派发。

`beta_durable_transaction_candidate_v1.py`提供持久化存储和CLI，不import actor；`beta_transaction_evidence_candidate_v1.py`只核对JSON/文件/event/RNG链；`beta_transaction_backend_candidate_v1.py`只有未来init/compute在durable intent之后lazy import实际Beta。真实physics launcher为0，任何接口均不自动派发物理。

每次操作用同run的独占flock，所有写还核对owner PID。源/API默认拒绝覆盖run、intent、computed文件和generation。CURRENT只是一次os.replace的四臂指针；临时文件、每个checkpoint、manifest、目录均fsync。任一部分STAGING保留，绝不作为CURRENT。

## 状态顺序

1. init先只读验证主授权、源、实际Gate1 mean.5能力门和已由root初始化的原窗口；写RUN_IDENTITY和TRANSACTION_ATTEMPT_0000后才允许1次Beta.initialize、3次显式policy copy、4次BetaArm构造（构造内部copy另由构造次数体现）。所有四臂相同权重/normalization/seed，各自独立RNG。wrapper不创建或重置clock。
2. prepare只做原证据核对，写不可覆盖PREPARED；无actor初始化/restore/forward/梯度。commit再次核对相同证据proof，确认CURRENT未变且无旧intent。
3. commit/cancel先durable TRANSACTION_ATTEMPT，再调用冻结draft函数：4实际restore+4private copy；完整组做原RF/PPO更新，工程censor组做4取消、0梯度，不倒RNG。任何失败都保留private结果/计数；全四臂不发布。
4. 四endpoint全部成功才保存TRANSACTION_COMPUTATION中的精确四checkpoint UTF-8字节及SHA，再写COMPUTATION_SEAL（绑定intent/bytes SHA），再构建immutable GENERATION，最后一次替换CURRENT。
5. 任意已有intent拒绝再运行init/update。无完整COMPUTATION和seal不能自动恢复，须主审已付费工作；不允许借此重新fit。recover只使用已存字节，无backend参数，无actor import/initialize/restore/forward/score/optimizer。已有完整孤立generation仅恢复指针；指针已发布则核对后幂等返回。

## 真实输入合同（未来由root创建）

真实plan的schema为`v8.beta_durable_run_plan.v1`，含原`launch_spec`（仍`v8.continuous_beta_sampling_job.v1`）、`normalization_source={path,sha256}`、`normalization_keys`、`feature_names_keys`（JSON对象键路径列表）、`initialization_seed`、`sampling_seed`、`optimizer={learning_rate,max_gradient_norm,ppo_clip_range}`、`expected_context_counts`、`local_stop_unix`、`beta_initial_shapes=[2,2]`、`same_initial_weights_and_sampling_seed=true`。normalization只读既有冻结源，无fit。

现有main sampling authorization除原字段外，必须显式增加`approved_for_real_initialization=true`和`durable_initialization_parameters_sha256`。后者为上述normalization_source/两键路径/两seed/optimizer/expected_context_counts/local_stop_unix/beta_initial_shapes/same_initial_weights_and_sampling_seed共10键子对象canonical SHA，避免plan/auth互相引用形成hash循环；实际更新仍另要求`approved_for_real_updates=true`。authorization source闭包须包括本批三个新源。不能用本source合同或stub授权代替真实授权。

真实pending input schema为`v8.beta_root_bound_pending_input.v1`，含`job_configs=[{path,sha256},...]`、`root_expected_sampling_groups`、`final_pending_bundle={path,sha256}`、`root_closure_review={path,sha256}`。更新必须原两个不同dev context的两个closed jobs；取消允许一/两个closed partial jobs，不能据active半raw调用。原main review schema沿既有`v8.beta_four_arm_root_closure_review.v1`，必须绑定group_transaction_id、全四pending对象SHA、全部已启动child join、父prefix不变、全局hard原证据。

完整更新核对每job cold parent+B+8child的10个唯一START/END、实际config SHA、WORKER_DONE/supervisor/EXIT/parent RAW gate；case1输入必须CURRENT四checkpoint，case2输入必须case1完整直接pending文件，所有first-context proposal/receipt前缀原样保留。逐arm校验原checkpoint→每个sample rng_before/rng_after→最终JSON RNG，tuple/list以canonical JSON比较，16次实际policy attempt跨arm/context不复用。每proposal仍绑定old scalar λ logdensity/实际recipe/action/source；B独立原receipt；实际adapter从原RESULT/events/lineage/stream再次重建saved receipt并精确核对。没有伪造requestID、receipt或新步数。

hard=true始终先于clock/工程censor，不能取消掩盖。review hard unknown拒绝更新/取消。partial receipt hard unknown只有主审原证据显式`resolved_unknown_hard_attempts[attempt_id]={true_hard_safety_violation:false,original_evidence_files_sha256:{...}}`后才允许取消；实际true不能被false resolution覆盖。取消也保留numerical-no-proposal reservation与RNG消耗，链不回退。完整更新若过原局部窗口则拒绝；root可另准备有原安全闭包的cancel，不自动修改review。

恢复会重新核对run冻结输入、原pending input和review、原proof全部文件SHA，以及相关START/END原行SHA/canonical记录；允许其他job追加ATTEMPTS，不把整个活动event log hash当静态文件。原窗口过期后只允许已计算字节的metadata发布/取消证据归档，无新科学计算。

## CLI / API

CLI入口是本目录`beta_durable_transaction_candidate_v1.py`，可由root薄wrapper转发；全部路径相对唯一package，run只能在continuous_scale_v1下新目录。无stub CLI选项。

```text
<python -B> <candidate> init    --package <P> --run <new-run> --input <approved-plan> --input-sha256 <sha>
<python -B> <candidate> prepare --package <P> --run <run> --input <bound-input> --input-sha256 <sha>
<python -B> <candidate> commit  --package <P> --run <run> --input <returned-PREPARED> --input-sha256 <sha>
<python -B> <candidate> prepare --prepare-cancel --package <P> --run <run> --input <cancel-bound-input> --input-sha256 <sha>
<python -B> <candidate> cancel  --package <P> --run <run> --input <returned-cancel-PREPARED> --input-sha256 <sha>
<python -B> <candidate> recover --package <P> --run <run> --generation <explicit-index>
```

这些是未执行模板，不是本批授权。API对应`DurableRun.initialize/prepare/commit/recover`；只有前三者接收backend，recover无backend。CLI只选`RealBetaBackend`，fixture仅显式依赖注入`STUB_ONLY`。run identity绑定backend_mode，不能在stub与真实run间混用。

真实adapter roundtrip为metadata读取，仍有CPU/stream解析成本，必须另记：一次完整prepare最多2个baseline重建+16个policy receipt重建；commit重复核对再18次，两次合36 adapter调用，0actor调用。失败/重试/取消据实际次数计账。未来完整更新仍原RF/PPO四臂48 training forward、32 score、8 SGD，外加冻结draft实际检查和采样本身，不能把API包装称节省物理试验。

## 获批stub故障检查范围

只运行一次≤60s STUB_ONLY fixture。stub actor/adapter使用明确非Beta schema、非真实receipt、非真实job；不import真实Beta/worker/adapter/MuJoCo。注入intent后、第三private arm、COMPUTATION后、部分STAGING、rename后、pointer前/后故障，检查全四/前一CURRENT、旧intent不重fit、精确computed bytes恢复0stub optimizer、四臂取消0stub optimizer。也机械检查实际hard_gate源码true/unknown优先。通过不等于真实两job、完整Beta restore、adapter artifact、physics、资格或on-policy学习已验证。
