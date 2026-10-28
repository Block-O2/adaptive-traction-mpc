# Gate1源码候选与优化器合成检查

Gate1只完成源码、合同和冻结axis；没有运行生成器、worker、环境或物理。独立Beta RF/PPO优化器的获批≤60s合成检查已通过，wall 0.547158s、CPU 0.547162s。真实训练/rollout/环境初始化/新物理均0，研究结果读取0。v1优化器、已通过的Gate0数学文件、原categorical API和worker均未改动。

## Gate1待主Agent审查派发

`gate1_sequence_candidate_v1.py`通过AST，root wrapper/config尚未创建。本候选使用原worker的同活OUT0完整父状态分叉：B→原H150→λ1→λ0→λ.5。原H150用family:H150而不先改为old18d。λ1提交原`repeat_of=H150`完全逐raw门，并要求完整原合格，成功后才提交后两点。每条新物理成本单计；父prefix由root统一闭包只计一次。

冻结轴文件`FROZEN_AXIS_GATE1_V1.json`与Gate0实际检查的axis逐字节相同，文件SHA `66cee45dc9b3c3fb66fddb277e054bb9f2b80e91b35cd17ba9391542f26b664c`，对象SHA `ad1e44aca095b872ba673d077124841058f4ae55c9002b016f19253d22131faf`。`GATE1_SOURCE_MANIFEST_V1.json`绑定生成器、轴和合同。λ0保留native plateau、T terminal repair及原零/单位intent检查，不是B/zero-noop。完整原qualification/JF/JM、motion失败、learning_records/decisions、activation/rejection/fallback、lineage与实际receipt原文件SHA均保留。任何真实hard安全仍走原worker停机。knownheavy仅作已暴露工程检查，不能称独立泛化。

## 明确隔离的优化器合成模式

新文件`beta_optimizer_candidate_v2.py`保留v1候选，并添加显式MATH_ONLY入口。MATH_ONLY只接收合成特征、Beta样本和手写scalar reward；实际physical propose/accept接口均拒绝，真实训练approval/Gate1/split字段必须为null，checkpoint恢复模式必须一致。不存在伪造研究START/END或genuine回执。GENUINE_ON_POLICY路径仍须主Agent训练合同、Gate1真实证明、独立切分、实际receipt和源绑定；本轮未执行该路径。

RF/PPO各有raw/scaled两个合成arm，四者初始52权重、种子和采样RNG完全相同。每arm两个合成context各两样本，使用真实Beta采样函数，合成reward明确手写；没有调用single_force_feedback或读取真实控制收益。这一检查证明更新/恢复机械一致，不证明真实反馈收益。

52权重×8个RF/PPO符号/ratio分支，共416个中央差分分量、832次扰动objective求值，epsilon=1e-6，最大解析梯度误差`1.0008534001570979e-9`。PPO ratio1.5与.5分别覆盖正/负优势下截断与非截断分支；不clip Beta样本，不改写old scalar logdensity。RF一epoch、PPO三epoch，所有合成正常SGD均触发预登记梯度norm门（maxnorm=.001，scale约.008589–.014211）。

四arm各更新一次，并从完整JSON pending snapshot恢复后各重放一次，共8次成功合成finish：RF四实例共4步，PPO四实例共12步，合计16步提交到合成对象。另在PPO第二epoch的首个score调用注入异常，已执行的1步私有SGD和梯度轨迹保留，live权重0提交、pending4条保留。总实际合成SGD17步，不能只报最后成功checkpoint的16步。

11项负例按预期拒绝：old density不匹配；第二epoch私有异常；hard=True优先于缺样本/工程censor；局部及全局时钟；合成模式接收物理receipt/proposal；恢复时权重或依赖篡改；合成checkpoint恢复成真实模式；极端ratio停止且不重写。完整pending、post-update快照JSON往返一致，恢复后的权重、计数、RNG与逐epoch轨迹一致；辅助RNG比较另计64次uniform draw。

## 实际调用账

| 项目 | 尝试/完成 |
|---|---:|
| beta.initialize | 5 / 5 |
| Beta actor forward | 961 / 961 |
| Beta action sample / Beta RNG draw | 16 / 16 |
| 底层score_for_weights | 76 / 76 |
| 额外注入异常的score入口 | 1 / 0 |
| log_density | 1037 / 1037 |
| raw_shape_score | 76 / 76 |
| shapes_from_raw | 1037 / 1037 |
| surrogate_coefficient | 909 / 908（1极端ratio预期拒绝） |
| BetaArm构造 | 18 / 18 |
| restore | 17 / 14（3篡改/模式预期拒绝） |
| snapshot | 24 / 24 |
| sample_math_fixture | 16 / 16 |
| finish_batch | 13 / 8（5负例） |
| preflight_batch_metadata | 11 / 10（1hard优先拒绝） |
| physical propose / accept API | 各1 / 0（合成隔离预期拒绝） |
| 合成SGD实际执行 | 17（16合成对象提交+1私有未提交） |
| 真实fit / rollout / env / physics | 0 / 0 / 0 / 0 |

961次forward分解：832次中央差分objective、8次解析梯度检查、16次采样、96次成功更新工作、1次错误old-density工作、8次注入异常前私有工作。76次底层score分解：8次解析梯度检查、64次成功更新、4次异常前私有梯度；第77个逻辑score入口被注入异常阻止，未执行底层函数。所有checkpoint与实际错误轨迹均仅在`optimizer_synthetic_fixture_v1/END.json`合成档案，不能作为研究部署模型。

执行前核对前一清单18个本地文件与15个原源码/配置SHA，结束后再次核对未变。`OPTIMIZER_SYNTHETIC_SOURCE_MANIFEST_V1.json`记录执行前实际源码闭包；结果原START/END不覆盖。整条连续轴仍NOT_FULLY_EXPLORED：Gate1可执行/逐raw等效、实际原motion资格、真实收益和新独立验证尚未完成。
