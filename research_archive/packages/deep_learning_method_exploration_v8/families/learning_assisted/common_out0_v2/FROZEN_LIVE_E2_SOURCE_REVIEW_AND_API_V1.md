# E2 最小冻结 live API：SOURCE_ONLY 交审

本轮未 import/call 新 API、模型或数学 fixture，未实际 OUT0 推理/部署，0fit/physics。V1 fit/model、原数据和两个 frozen bundle 保持不变。新源码 `frozen_live_e2_candidate_v1.py` SHA `650c089fe51cc9d0b38c2ccbe94f0fb770512d9de6fb4e9e890c511fb475228f`，合同 SHA `85c1ea344c5f972e183164cca8833ef56222d92f78fe868233a8c349f9e5ef30`，source manifest SHA `55f3bfb8fad54da14c76a53cb948b306ce37a36440761a0462a22ee955919ffe`。

调用入口只返回结果，root 负责持久化和独立物理调度：

```python
receipt = api.predict_before_B(
    package, config, actual_parent_study,
    approval_path=actual_absolute_readonly_approval,
    approval_sha256=actual_approval_bytes_sha256,
    owner_deadline_monotonic=existing_owner_deadline,
)
```

新 approval 必须为 schema `v8.E2.frozen_live_inference_approval.v1`、status `ROOT_APPROVED_FROZEN_E2_ACTUAL_OUT0_ONCE_V1`，精确绑定 source manifest/contract SHA、operation、唯一实际 group；实际 config/job SHA 另由原 A3 proof 与 root owner 的审批闭包绑定。review-only 模板不可调用。本 helper 不授予 physics 或 fit 权限。调用前后模型/source/bundle SHA 重核，既有 parent deadline 与原全局 stop 只减不重置；统一局部推理上限5秒，继承 root 的单CPU/线程1/AS1GiB，不改 owner alarm 或资源限制。

只取 D4/DFull 的 RIDGE_CONTEXT_ACTION 与 MLP_PAIRED，各 rawgreedy 和同一 A3 risk 门，外加 fixed EARLY_H150-if-risk<0.5-else-B，共9个 selector。所有选择先于任何 B 或其他 candidate 结果完成。core5真实试验共享只用于公平反事实比较，不能计为省试或独立重复。

| 来源 | 调用 | query vectors | 说明 |
| --- | ---: | ---: | --- |
| D4 ridge | 2 matrix API | 10 | 3.5/4秒节点，按原末区间算式外推到19.03，明确 OOD |
| DFull ridge | 1 matrix API | 5 | 原19.03训练末节点 |
| D4 paired MLP | 2 forward API | 10 | A/B各5行真实计算 |
| DFull paired MLP | 2 forward API | 10 | A/B各5行真实计算 |
| E2 合计 | 7 backend API | 35 | 无dense、interpolation backend或积分调用 |
| 独立 frozen A3 | 1 predict API | 5 recipes | 内部5个risk dot/logit及sigmoid、30个cost dot输出，原support计算亦执行 |

A3 API 实际返回的是5个 `qualification_failure_score` sigmoid 分数，内部计算5个原始 risk logits；合同 `returned_risk_logits` 字段是这5次 risk-head 计算的计数标签，不代表原始 logits 被返回。source `A3_risks` 正确读取风险分数字段。A3没有从旧V3结果缓存取数；新调用通过原纯推理接口计一次完整 API，不隐去其未用于选择的30个cost dot及support工作。其 choice/support 仅作为完整receipt保留，不参与E2准入。

非B仅 strict risk<0.5 才允许，risk==0.5拒绝；B始终允许作fallback。成本排序精确 `min(valueJF, recipeindex)`，没有1e−6平手floor。固定H门使用完全同一风险分数与严格阈值，检验模型是否只复现固定H偏好。JF使用原16头第14列物理输出；JM独立保留，不混奖励。risk未校准，门不授予原任务资格。

真实39来自原cold-parent OUT0 payload与冻结 A3 W39用途限定 QA；不升级原77D。源证明读取实际 loaded module 路径/SHA、绑定 callback code、job/config 和保存 payload，不收caller自造proof字符串。未来 callback 必须匹配 frozen A3 四条已登记 profile之一；新callback不匹配会在模型调用前停止，不能伪填旧 SHA。core5完整recipe、resolved candidate、FROZEN18D与planner source一并核对。训练数据 SHA从已冻结模型元数据绑定，live不打开训练INDEX/NPZ/raw；未来真实B轨迹从不进入输入或重构。

私有 namespace 复用冻结 A3 topo loader，限定变换为本地 ImportFrom 名称，函数体不改；不导入 worker、运行时控制器或同名公共模型模块。API无输出文件/日志FD、dispatch、GC/atexit写回钩子。调用失败抛 `InferenceFailure`，root须保存其 `.receipt`：E2 backend按原函数计attempt；A3若中途未返回，dot部分工作明示UNKNOWN，不能补成完成，也不能静默重试。

数学 parity 尚未执行，需另批 SYNTHETIC_ONLY：只构造固定合成权重和输入，候选helper7API/35vectors对照原数值函数 reference18API/50vectors，共25backend/85vectors，0真实权重、0实际A3、0fit/init/update/physics。reference含两域各两个ridge节点（4matrix/20vectors）、五recipe各一次原插值（10API/10vectors）、两域原paired A/B（4forward/20vectors）。核4种16head解码、D4 OOD/DFull端点代数、exact tie与小于1e−6的真实cost gap、strict0.5/nextafter门、Bfallback。实际source proof另由真实OUT0审批核验，不把synthetic provenance称为实际证明。此前已通过的E2梯度/Adam门不被重跑或重计。

全部14个E2全开发模型与LOCO输出继续冻结；此最小live实验范围不是CV选最佳，也没有删去 action-only/绝对wrench积分的离线强对照。paired积分仍 N/A。本函数是 conditional trajectory surrogate 的成本头策略比较，不是Markov simulator/PETS复现或planner控制授权。
