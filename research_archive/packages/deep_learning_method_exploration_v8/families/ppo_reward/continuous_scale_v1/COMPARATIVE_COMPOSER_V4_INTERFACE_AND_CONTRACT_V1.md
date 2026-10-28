# Comparative composer V4 候选

私有源码 `comparative_composer_v4_candidate_v1.py`，入口 `sequence(study, config)`。仅source/schema/合同交付，未import/调用generator、扩展或模型，未建立actual config/inventory，未读Beta正在运行的run或sealed outcome。root以后另建薄wrapper、实际冻结inventory和物理审批；现有V3、Beta和root源全部保留。

V4包装原冻结V3源码874fd52...，不改写其推理/C5函数。先调用V3的`next`，让其完成原55个pre-B决定、保存原记录、交出尚未物理执行的B提案；此时study.metrics仍为空。可选冻结core-only hook先插入，然后独立Beta mean扩展4dd92a...完成12个mean及5个固定λ。V4保存完整pre-B选择/执行计划后才yield原B。之后逐条转发V3提案：B、原C5 after-B决定、条件HISTORY_B、LATE_H150、EARLY_H150、LATE_PHASE、EARLY_PHASE的相对顺序原样保留。原C5仍是原三recipe权限，未扩为五/连续动作。

完成原core动作后，连续部分先新付费执行 `BETA_AXIS_L100_REPEAT`，显式`repeat_of=EARLY_H150`，交给原worker_v2执行原compare_raw门。EARLY_H150必须complete，允许motion-qualified=false；绝不用H资格筛掉可能恢复任务的λ。λ1也须complete，其新原始raw门PASS且原JF/JM/axes/qualified与EARLY_H150一致，才运行其余grid/mean；root在完整job闭合后仍须做原scorer replay/activation/receipt/父prefix/成本审核。EARLY_H150或λ1 partial时其余continuous均NOT_RUN；任何true硬违规或UNKNOWN硬状态停全部后续，不补成功。其余core PHASE工程partial若原11硬条件全部true，原error/native步数保留后按既有V3次序继续；其余continuous出现工程partial则停后续continuous。完整motion失败保留原资格失败，不伪装工程partial或低成本成功。

连续mean及grid使用独立schema，不塞进仅五core hash的adapter，不与五动作/三动作方法汇总为同动作权限排名。λ1和原EARLY_H150绝不静态alias，二者都是真实新START/END；λ1在其他continuous之前。剩余连续配方仅按实际完整recipe SHA合并匹配评价，父四mean=.5可与grid.5别名，first/last若同实际权重仍分别计12次forward。共用轨迹不是新独立replication或节省attempt；真实训练rollout永不去重。本composer明确拒绝onpolicy_sampling配置，不构造learner、不更新。

Beta条件mean只由冻结policy和本次合法commissioned25得出。原B不在Beta曲线上，λ0不是B/noop；B结果只作原wholejob安全门、原C5输入及之后独立评价参照，绝不拼进mean预测或据B结果重选λ。输出的physical mean动作也不称平均物理轨迹。

owner PID在generator入口锁定。所有写/legacy.next/显式legacy.close只允许原owner；child GeneratorExit静默return且不关闭父generator，不写shared close/error。parent取消或原worker repeat异常时保留最后yield的未reconcile标签、原可读RESULT/STARTEND、安全三值和已耗推理；不会生成成功回执。实际worker负责环境/物理dispatch及原native计数，V4只yield已冻结提案。

未来config继续原V3的`comparative_validation`和原actions五条、history_snapshot、全部模型/source冻结，并新增独立：

- `comparative_composer_v4.schema=v8.comparative_composer_v4_job.v1`、status=APPROVED_BY_MAIN_AGENT、no_training/no_outcome_reselection/root_postclosure_raw_and_scorer_review_required均true。
- `preserved_v3={path:source/v8_comparative_validation_candidate_v3.py,sha256:874fd52f71852480a23fef3aae6b91e494f1e9f6ed7974a6537e38d9b360c2a9}`。
- `beta_mean_extension={path:families/ppo_reward/continuous_scale_v1/beta_frozen_mean_extension_candidate_v1.py,sha256:4dd92a133c1cc7eecd60b7c51aea66cc360e0692e103a68d65ed02df09f26876}`。
- 可选`future_frozen_core_extensions=[]`。每项`{label,source:{path,sha256},frozen_inventory:{path,sha256},output_schema}`。这是Neural/E2以后可接的位置，当前不虚构adapter/model或调用它们。
- 原`config.beta_mean_extension`遵循已交mean扩展job schema，绑定未来真正存在的parent/first-completed/last-actual-updated四臂checkpoint，禁止best。root实际Beta endpoint inventory须在training owners全部闭合后冻结，不读CURRENT/PENDING/sampling动态状态。

未来core-only hook入口也是`predict_before_B(P,config,study)`，返回指定schema、非空`decisions`、实际`frozen_inventory`ref、mutable_run_state_read=false、no_fit_restore_or_RNG=true、actual_counts字典。每条必须提供真实五menu之一的choice_recipe_sha256/tag/action，完整action与原recipe逐项相等；不得覆盖原55标签、引入连续hash、动态run读取或未冻结模型。其调用/完成/失败耗用另账，共用core轨迹不冒充新重复或省试。

未来正常一次V4新增调用为：Beta extension entry/return各1；内部12次deploy_mean forward、12份policy copy、5次fixed map加mean内部12次map；A3原seven-role proof一次、39子集准备一次、25投影一次。原55是原逻辑决定数，不能冒称55个等成本API；其实际wrapper/nested forward计数继承原记录，C5仍after-B记账。额外core hooks默认0。fit/init/restore/RNG/梯度均0。实际物理次数由core/HISTORY_B与连续完整recipe去重后的执行表、mapping/安全门、原START/END/native记录决定，不能从12推理数推断12独立rollout。

新输出：`*_V4_ALL_PRE_B_DECISIONS.json`保存原55记录SHA、core hooks、Beta完整独立结果和冻结计划；逐原child`*_V4_BRANCH_<tag>.json`保存原RESULT/事件/安全证据；`*_V4_CONTINUOUS_MAPPING_GATE.json`保存新付费λ1门；最终`*_V4_SELECTOR_EXECUTION_LINK.json`按core5/C3/continuous权限分列。owner close/异常独立保留未完成标签，不将NOT_RUN或partial当成功。当前所有这些都是未来接口，未生成任何真实job输出。
