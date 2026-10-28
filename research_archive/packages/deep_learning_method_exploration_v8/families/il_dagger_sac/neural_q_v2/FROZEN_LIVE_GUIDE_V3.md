# NeuralQ V3：独立只读固定模型接口（待批）

全部108head固定0/25/200端点和3ridge原值冻结，原合同主法TANH16/RETURN_GREEDY/final200三seed分别报告。当前仅新source/API/合同/AST静态，0只读restore/forward。训练clock未延长、训练head模块不导入，新API不存在step/fit/initialize/梯度。

最小runtime库存60head+3ridge：RETURN/RISK在2arch×3seed×3endpoint共36；4独立cost heads只用2arch×3seed final200共24；ridge RETURN/JFcenter/JMcenter3。每context63模型forward/63restore，105矩阵乘、30tanh、18sigmoid、315标量输出，195参数数组+2共用norm数组。输出68固定selector：36 RETURN风险开/关、24 JFfixed/center风险开/关、8ridge（RETURN/JFcenter各1greedy+3匹配LINEARfinal风险）。JMfixed/center及ridgeJMcenter只诊断、不混分数。剩余48个cost parent/early模型保存不多跑；无CV挑best。

frozen_live_api_candidate_v3.py：restore_fixed(document, authority=新只读主授权, expected_bundle_object_sha256=..., expected_source_manifest_sha256=..., accounting=...)；predict_fixed(restored, feature_names, commissioned25, qa_validated=True, authority=..., accounting=...)。restore63次逻辑model deepcopy；adapter68次actioncopy；继承A3 proof/menu11次成功逻辑copy，合计142显式逻辑copy（不是递归copy/JSON对象分配总数）。每模型入口/完成分别计账；异常JSONpaidprefix被genericcomposer原error记录保存，未完成细操作未知有界，不能报0。

frozen_live_adapter_candidate_v3.py 提供 predict_before_B(P,C,study)，可接generic parallel_selector_adapters。实际7role证明来自job/SOURCE_MANIFEST、savedconfig/payload、实际文件/loadedmodule路径和callback，而非caller自填证明；之后合法25转换进入模型。不得读当前evalcase内容/身份作为模型输入、不得native truth/未来标签mask，原77INVALID。所有68选择在B前，risk无可行动作时明确Bfallback且不授予原资格；仍共享5recipe物理。

root须另写新v8.neuralq.readonly_fixed_models_authorization.v3，批准status及scope=READ_ONLY_FROZEN_OUT0，authorized_groups、approved/expires<=原global，并config comparative_validation.neuralq_readonly_authorization指实际path/SHA；模板状态NOT_APPROVED/expiry0不可调用。authority绑定新source manifest、bundle、精确readonly合同、feature/menu、实际e50…binary与NumPy2.2.6。所有相关artifact须root冻结到config。训练executionapproval不会被接受。

建议先另批30s单CPU1GiB已知12context只读parity：一次63restore、12batchpredict=756模型forward，1260矩阵乘/3780输出；比较既存full预测和选择，不额外调用旧head。当前该parity未批未跑，源静态相同数学公式不冒充动态parity。之后真实OUT0/物理仍root另批；两sealed条件未打开。原开发主法负结果和cost追溯posthoc限制均保留，不选seed。
