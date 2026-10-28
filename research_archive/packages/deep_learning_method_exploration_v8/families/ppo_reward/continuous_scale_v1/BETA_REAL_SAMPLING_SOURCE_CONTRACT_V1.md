# Beta真实采样source候选：尚未授权真实调用

本批新增源码/合同/schema，0Beta初始化、0restore、0sample/forward/score/fit/update、0env/physics。既有BetaArm V2、beta_policy、axis_mapping、所有旧onpolicy/categorical/worker及Gate1 V1保持原SHA。没有创建实际launch authorization、Gate1 PASS证明、初始化clock或真实checkpoint。未来使用先由root审查并取得Gate1真实PASS与独立主批准；source候选不是授权。

## 方法与比较范围

仍是OUT0 commissioned25/QA的一次连续recipe选择，原任务/guard/scorer不变。Beta在标量λ∈(0,1)采样，α/β=1+softplus(raw)。旧18D、H150 posture/early/timing由冻结axis映射，native plateau/T terminal repair保留。λ0不是B；Beta没有原B的point mass，不能输出原B。B只是独立安全/反馈锚控制，不能把“能优于B”当成同权限性能比较。

性能必须与相同λ曲线上预冻结grid/pattern及固定λ控制、原H150比较。λ1与原H150的精确raw等效只在实际Gate1证据覆盖的条件成立；缺同dev case的传统控制结果不能从knownheavy工程Gate1补造。采样job仅执行B+8训练child，同轴grid/pattern/H150若需新执行，必须root另登记/派发/记物理账。该一维曲线不能声称修复旧41D native-event actor，也不是18D joint-action策略或ambient18D密度。

old scalar logdensity是Beta(α,β)对Lebesgue dλ的logpdf，标量[0,1]仿射Jacobian=1。曲线在18D内是奇异支撑，不能套18D determinant或给applied torque density。样本不clip、不重采样改值；数值端点/非有限则保留RNG前后、attempt reservation和0物理失败。mean部署λ=α/(α+β)另行冻结，不能当训练sample，也不是平均物理轨迹。

## 门、clock和原case routes

root未来创建v8.beta_axis_gate1_main_review.v1，绑定轴SHA、真实λ1/H150逐raw PASS、原B/H150完整资格及λ0/.5原执行/qualification审查、真实hard安全状态和证据文件SHA。初始Beta(2,2)的mean λ=.5必须原完整合格，字段mean_lambda05_full_original_qualified=true，否则不初始化/派发真实Beta。status须为PASS_ENGINEERING_MAPPING_REVIEWED_FOR_REAL_SAMPLING。root决定整个轴工程门是否可用；box合法/Gate0通过不能替代Gate1，缺失不得伪造PASS。

root未来创建v8.beta_real_sampling_authorization.v1，明确sampling授权；真实updates需要独立approved_for_real_updates=true。绑定唯一原ACTIVATION.json SHA、完整source闭包、已审合同、Gate1 review、axis、freeze/ONPOLICY_V1_CASE_ROUTES.json以及authorized_job_groups。仍用原两dev logical routes和case SHA，不改变物理方程/参数包。case/group/hash仅属归属切分元数据，不输入actor。本批未打开任何dev或sealed新结果/条件payload；只读了root adapter/driver源。

local clock只在Gate1真实审查且主批准之后由root初始化。要求reviewed_unix≤approved_unix≤initialized_unix<local_stop≤原硬截止2026-10-27T15:25:40Z，窗口长度≤主登记max；建议按现有实测约2小时注册，但当前未启动此clock，也未获得该物理预算。原worker dispatch margin/timeout和全局资源门继续生效。source允许超时后只做pending归档/全组metadata cancellation，禁止再sample/gradient。T0/硬截止不重置。

## 一case只采样：B→四arm×2独立child

baseworker source薄wrapper在import前把continuous_scale_v1加入sys.path，再转发beta_sampling_sequence_candidate_v1.sequence(study,config)。root负责真实wrapper/config与物理dispatch；本模块从不launch worker/env。

输入四个直接BetaArm V2 snapshot，固定arm_id顺序BETA_RF_RAW/BETA_PPO_RAW/BETA_RF_SCALED/BETA_PPO_SCALED。算法对应REINFORCE/PPO；raw gain1、scaled gain20。两case各2样本的expected_context_counts与原development_routes一致；四臂固定normalization、batch generation和首batch权重相同。future初始化来源/次数/RNG种子须root冻结；不能复用Gate0 SYNTHETIC父模型。BetaArm.restore会构造逻辑arm与Random对象再恢复state，即使beta.initialize API=0也必须记恢复/复制工作。

每case原B完整原合格后，按四arm各2样本顺序真实fork完整child；每sample保存causal25、QA、old scalar λ logdensity、α/β、完整axis/recipe/action SHA、source policy SHA、RNG前后。proposal在真实START前落盘并绑定prediction中的proposal文件SHA。RNG tuple经JSON变list仅作canonical roundtrip，所有跨保存比较用canonical JSON digest，不用内存tuple/list直接相等；V2恢复以_tuple_tree还原Random state。

每个样本必须独立实际START/END、真实new native steps。即使同seed使四arm初始λ完全相同，也不缓存/共享其训练outcome，不省试；它们是独立物理child所有权，不因此增加独立context数或随机物理方差证据。两个case同当前未更新policy采样，case2加载case1已closed的pending snapshots。每job禁止finish_batch/update；最终只输出pending。当前case若已有pending，或任何先前proposal没回执，拒绝自动重跑，root先核对原START/END/raw。

## fork child GeneratorExit与写入owner

worker真实fork child可能GC继承的generator并注入GeneratorExit。新sampler入口固定owner_pid/startticks；mkdir/put/save/error/cleanup每次写前确认原owner。child GeneratorExit静默return，不写共享PENDING/ERROR，不误报parent停止。owner关闭保留现有pending，要求root核对已生成但未派发/未join的proposal。Gate1另有同修复的V2，旧源不改。

## 回执：只绑定原事件和执行证据

beta_onpolicy_receipt_adapter_candidate_v1.ADAPTER_SCHEMA为v8.reviewed_continuous_beta_receipt_adapter.v1，区别于categorical。它只读复用root/source/v8_onpolicy_receipt_adapter_v2.py的_binding；该参考已由root真实artifact roundtrip审查，但Beta adapter本身本轮未调用/roundtrip，不能继承其验证结论。

_binding核对原saved config、logical route/case SHA、原RESULT以及唯一真实START/END。Beta层另核对schema、actual λ→recipe/action、原pre-START proposal/prediction/文件SHA、policy SHA、old scalar logdensity、RNG canonical SHA和原parent PID/startticks。pending键是physical_receipt，不能用categorical physical_result/proposal_recipe/action_index代替。

回执保存原事件record+raw-line/canonical不同hash scope，原RESULT完整对象与source SHA，原MEASURED、lineage、execution_binding、summary、实际command_receipts流及container SHA。stream hash沿root V2定义：原顺序每个完整command_receipts对象sorted compact ensure_ascii=False UTF-8 JSON+newline。它包含继承prefix；其positive steps不冒称本child新步数。actual_new_native_steps只用原RESULT。START/END PID是fork parent event writer，不伪装child physical owner；null request/command IDs不补造，沿原lineage join_kind/ownership检查。

guard/fallback/rejection/activation保存原summary/audit/result实际命名字段与JSON pointer及原文件SHA，不填安全默认值。请求λ、实际activation和被guard拒绝/fallback分别报告；请求密度不等于执行18D/torque密度。原guard拒绝后的完整原合格任务是该完整recipe在原机制下的实际反馈，但不冒称请求全被执行。

hard安全三值：任一原common condition=false→true；全部明确true→false；缺项→unknown。hard=true在任何count/censor/gradient前全局停；unknown不是false。完整、工程/ownership通过但原motion不合格→reward−1，完整JF/JM仍保留不作合格收益。参考v2 engineering门要求完整原MEASURED/ownership，故partial（包括缺完整证据的protected partial）全组censor，不用partial低cost造teacher或reward。若未来要对有完整工程证明的protected incomplete赋−1，须另合同，不在此自动扩权。

raw/scaled均原qualified JF相对本case原B：clip(gain*(JF_B−JF)/max(abs(JF_B),1),−.9,.9)，完整资格失败−1；JM保持独立，不混权，不宣称双成本改善。失败floor比例、reward范围/advantages/梯度/clip/零更新与实际activation分列。

## 四臂事务与root原子发布

两个dev job都closed后，root审查全部原START/END、child join、两个parent unchanged、所有hard安全及final pending SHA，形成v8.beta_four_arm_root_closure_review.v1。没回执/未绑定的真实失败也必须先从原artifact审hard，不能缺回执就默认为safe censor。

beta_group_transaction_candidate_v1只返回draft，不写文件、不发布endpoint、不派发。它先对四臂扫描hard，再检查所有metadata；任一engineering partial/censor就全组cancel，保留RNG/seen IDs/pending/物理账，不给某臂补样本凑齐，也不倒回RNG。完整两context×2/arm后，四臂预审全通过才在四个私有copy上更新。RF1epoch、PPO3epoch，PPO三epoch共用实际采样old scalar logdensity和同λ，不重采样/clip action。

任一私有更新抛错，保留此前成功copy和失败arm私有trace/已消耗forward/SGD，live四臂一律不发布。全成功才返回四个对齐draft snapshots，由root统一记录generation清单并原子发布。snapshot字典检查忽略JSON key排序，执行顺序仍固定ARM_IDS。初始与终末checkpoint均由root冻结；没有自动循环下一batch、自动独立验证或追加物理权限。

## 拟工作账，当前均0

若未来一次完整两case batch：2原B control+16独立policy child，父prefix2次单计；Beta sample/forward/RNG16，job restore逻辑arm8次；sampling update0。四臂root metadata恢复4、私有copy4另账。成功一次组update：RF两臂各4 old-density/4 score forward，PPO两臂各4 old-density/12 score forward，总训练forward48、manual score32、SGD8（RF2+PPO6），Adam0。初始化、条件/axis解析、stream解析/哈希、source验证、全部失败私有工作另外据实际数登记，不能仅数最终成功checkpoint。

这些都是拟数量，不是已运行结果。当前source-only交付新增所有Beta actor/API/restore/physics计数0；既有Gate0数学、synthetic optimizer与D拟合的实际账保留原档，不能被本行“0”抹去。
