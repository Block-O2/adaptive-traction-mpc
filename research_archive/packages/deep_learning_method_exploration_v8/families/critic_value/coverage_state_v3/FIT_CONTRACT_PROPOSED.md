# A3 拟合合同候选：25 / KIN33 / WRENCH39

状态 `PROPOSED_SOURCE_ONLY_NOT_TRAINED`。主Agent仅授权本轮数据/source准备和可用性审计；本合同拟合待另批。原77D仍INVALID，TASK历史缺失仍缺失，A1/A2模型/API与当前on-policy源码均不修改。唯一硬截止2026-10-27T15:25:40Z，不重置。

数据为同一48行/10parent/31原合格目标，动作仍精确B/LATE_H150/EARLY_H150/LATE_PHASE/EARLY_PHASE。新 `data/STATE_JOINED_DATASET_V1.json` SHA `54b017803ae55575e1284dda2156d7534eaa9a2ebb6796d512709b439a2e863a`；与A2标签、recipe、parent切分逐值身份 SHA `d8eb9c8003d02eaf2b92c821ab221650bda7eb4864d6b3b5d643e116bbed069e`。唯一替换row字段是context，改为原raw77与实际job source proof的严格envelope。新增状态可用性数据SHA `7a1ba773…3f68d`，字段来源/时间/QA见AVAILABILITY_REPORT与schema；没有把未来TASK结果放进context。

仅MERGED cohort，表示为25、KIN33（+估计q/dq与请求参考q/dq）、WRENCH39（再+瞬时测量wrench）。原TASK积分、emitted reference、scheduler/governor不准入。GUARD43只作已审软件历史先验的可选schema，不进入本轮任何拟合/primary，也不升级物理risk。

同A2的ABS与DELTA_B独立JF/JM成本头、λ=.1/1/10、risk logistic λ=.3、risk阈值.5、support至少2context及RMS≤3、10parent整组LOCO、risk ON/OFF、JF_QUALIFIED/JM_QUALIFIED/STRICT_JM分别保留。primary事前固定 `MERGED/ABS_WRENCH39/RISK_ON/JF_QUALIFIED`，不以CV best替换。缺历史反事实仍UNKNOWN，不把本context未来资格作mask。normalization、target scale仅用训练parent。

前25字段scale floor严格沿A2；额外8个运动/请求参考字段floor=.005rad或rad/s，force三轴1N、moment三轴.1Nm。这是事前数值条件规则，不是已验证传感器噪声模型；本轮不按CV调尺度。任意训练context列std≤1e−12即冻结该列z=0，if stump也跳过该列，nearest使用相同变换。请求参考dq约1e−16不能被放大成case区分信息，未来该列偏离也不外推未训练信号。额外常量与零规则每fold保存。RMS在不同维数下有分母效应，支持门参数不改但须单列支持集合变化，不能据padding授予信息增益。

强对照固定B、best fixed、if stump、nearest按25/33/39各自同表示权限独立构造；WRENCH39主法必须比较WRENCH39强规则。规则只看训练反馈，索引/path/hash不进输入矩阵。保留A2主法失败，A3的25D新source基线与A2 MERGED相应LOCO选择/分量/risk作数值一致性审计；若产生漂移先报工程/规范差异，不能归功新增状态。

未来pure API必须输入实际新OUT0 raw77和owner对实际加载文件计算的source_proof，验证capture/callback/runtime/observer/observation-contract/history-guard/runtime-loader SHA属于冻结profile，再核原checksum、OUT0、age=0、QA、有限性后提取。只给离线数组或抄expected SHA不构成运行证据；主driver仍须绑定本实际payload文件和SOURCE_MANIFEST。四个profile覆盖已审历史worker及已读v8_worker_v2候选，实际执行前由主Agent锁其真实source/config。纯API不读文件，不创建env，不调用observe/model；旧scoped25数组不作为新scope证明。

申请一次前台、单CPU、≤180s、AS硬上限1GiB、BLAS/OMP/MKL各1线程、0physics，固定唯一fit_run_v1且失败不自动重试，内部预留5s审计。预计11个唯一训练集合×3表示=33次risk logistic、198次ridge二RHS求解（396标量输出头），99次objective-specific stump构造；LOCO360次模型predict+360次control predict=720次。不是增加物理/episode，也不是完整机器人Q学习。使用已存在只读offline-env，批准时重核binary/version/NumPy/SciPy；逐risk迭代/nfev/njev、ridge、API、PID/start_ticks及初末wall/CPU/RSS记账。

输出所有表示/目标的checkpoint、LOCO逐预测、风险/成本/严格JM负诊断、常量列和支持变化、资源账，不挑best。两个插值validation结果继续sealed，须所有A3checkpoint/规则/API冻结后才由主Agent打开。当前仅AST语法核对；拟合、模型forward与新物理均 `NOT_RUN`，方法家族 `NOT_FULLY_EXPLORED`。
