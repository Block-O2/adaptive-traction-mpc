# 独立审查修正：V2根事务，仍0真实Beta调用

保留V1所有源、manifest和stub结果。C独审发现两处确定问题：V1取消工程partial仍无条件读取完整PARENT_RAW_GATE PASS；V1创建run后未立即fsync(run.parent)。V1 stub通过只覆盖其当时机械范围，未覆盖这两处；不能把它当作真实partial取消已验证。

新增`beta_durable_transaction_candidate_v2.py`、`beta_transaction_evidence_candidate_v2.py`、`beta_transaction_backend_candidate_v2.py`，三者内部相互绑定V2。原sampling/common/BetaArm/axis/adapter/draft均不改；真实主授权未来须将三个V2源SHA加入closure，不能沿用V1源码hash代替。CLI/API沿V1合同，入口换durable V2；没有真实plan/authorization/clock创建、没有真实actor import/init/restore/forward/update或physics。

V2 initialize在run.mkdir之后立即实际fsync(run.parent)，先于RUN_IDENTITY、durable intent和actor。该修正绑定真实core流程，不只是文档补充；未来run上层目录仍由root负责预建与相应持久化。

commit仍要求两个完整closed jobs、完整原B、10 START/END每job、parent raw PASS、16原proposal/receipt、精确旧policy与RNG链。V2不为commit放松任何门。

cancel只接受已closed的原工程partial：WORKER_DONE可FAILED_PRESERVED；supervisor必须STOP且无survivor、EXIT存在、每一个实际START必须唯一END且joined。实际parent也必须join，worker/child非零returncode保留。取消不要求完整B、10个START/END、SAMPLING_DONE或完整parent raw gate；没有policy proposal时不读取B receipt、不调用任何adapter。

每个已join child必须原END `parent_hash_equal=true`，或主审绑定原parent_checks证据（唯一id、unchanged=true、非空before==after）；原END显式false始终拒绝，不能被另一文件的true覆盖。原完整parent raw gate如存在就保留实际status/SHA，如缺失则原样null/absent，不能创造PASS。partial取消只证明已消费操作安全闭合，不授予完整task原资格。

新的主closure review须含`cancel_started_attempt_safety`，其key精确等于本次输入所有实际START id（包括parent、B和任意policy child），每项`{true_hard_safety_violation:false,original_evidence_files_sha256:{...}}`。这就是主Agent对实际缺失/partial安全状态基于原证据的显式resolution，不能拿global false布尔代替逐attempt审查。`resolved_unknown_hard_attempts`仍用于pending receipt unknown的原证据审查。任何review/该两map/pending中true都在工程/clock前停；unknown不默认safe。没有真实hard安全豁免。

有缺receipt或numerical-no-proposal时，已记录proposal、native cost和RNG reservation按原样保留；本次metadata核验不改对象，取消不倒RNG。source只允许主审后四臂同组cancel；不拟合partial、不补伪造result/receipt/native steps/requestID、不读active。

获批≤60s STUB_ONLY fixture仅在隔离的STUB_ONLY_PACKAGE中构造原格式START/END与FAILED worker闭包，明确非真实raw、非真实receipt/job/模型。验证缺parent raw且B失败/未开始时可安全取消、原prefix证据可审、未知/true不能被false覆盖、未join拒绝、numerical RNG不变，以及core实际mkdir→父目录fsync→identity→intent→stub initializer顺序。真实Beta/adapter/raw/physics全0。执行前冻结三V2、fixture及原闭包SHA；失败不重试，实际次数单列。
