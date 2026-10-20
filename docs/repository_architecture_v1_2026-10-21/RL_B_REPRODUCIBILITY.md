# RL-B 可移植 CPU 部署基础

规范包为research/rl_b_cpu_handoff_v1，450项封存文件，内部source/414项、vendor28项。完整SHA256_MANIFEST和VENDOR_COPY_MANIFEST保留。414项中412项与当前主树同路径相同，2项差异如下：

- `source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/rl_native_proposal.py`：当前主树没有同路径文件；封存SHA `191e26e1042673e81298e9fd3fad47fab63607d311bd35891bc7080626bc69b2`。
- `source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py`：当前主树存在但字节不同；封存SHA `cb955c5f10c42b4989c6cdfc4f6d5716da2149d7c9fe214d1c26d1f4b7b0b78f`。

因此本轮保留原版本，不用主树文件替换。新catalog指向原包，新静态校验在忽略的scratch临时副本执行原测试，这不是另一套长期源码。evidence/RL_B_SOURCE_RELATION.json提供逐项关系；历史side_studies的重复另见上轮DUPLICATE_SOURCE_IDENTITIES.csv。历史Git对象去重不会消除工作树文件重复；未来新开发应引用Stage主源码，冻结capsule仍独立版本化。

## 安装与轻量验收

```bash
bash deployment/install_rl_b.sh
python3.12 -B deployment/check_rl_b.py \
  --config deployment/configs/rl_b_cpu_handoff_v1.json \
  --python "$PWD/.deployment-work/rl-b-env/bin/python" \
  --work-dir .deployment-work/rl-b-import-check-001
.deployment-work/rl-b-env/bin/python -B deployment/check_models.py \
  --output .deployment-work/model-check-001.json
```

Linux x86_64 / CPython3.12，35 wheel全部传递依赖锁定、require-hashes安装，pip check。可选PIP_BOOTSTRAP_PYTHON只用于缺ensurepip的系统。原requirements/安装脚本字节保留，维护层锁是已验证CPU profile，不宣称全Stage历史环境已锁定。

实际检查原verify_package、test_guard、test_g4、test_execution_contract、preflight；物理API mj_step/step1/step2/forward/inverse被拒绝调用。preflight仅建立空间/导入，41D observation / 2D native-event action；不reset、不step、不qualify、不训练。模型验证只编译XML，不运行动态物理。原READINESS=NOT_RUN、配置enabled=false保留。

## 训练与恢复接口（本轮未执行）

原train.py通过--enable --profile pilot --seed --out进入；原evaluate.py用--enable --checkpoint --seed --out；checkpoint恢复用train.py --resume <generation>。均须先满足原target资格和resource_guard，不绕过READINESS。原CLOUD_TRAINING_CONFIG是权威PPO配置：CPU、单physics env/单thread、seeds20261021/22/23、32x32网络、gamma1.0、native planner event计数；不通过catalog重定义算法。

checkpoints.py以最后写入JSON作为原子generation标记，核对policy/model/RNG/contract/counters；恢复policy、Adam、RNG和计数，但开启新物理episode，不恢复半个PPO rollout或MuJoCo中途状态。本轮没有载入真实RL-B训练checkpoint，恢复执行NOT_RUN，不能因为接口存在声明checkpoint可恢复。

原安全/执行合同、certificate、admission、40ms bridge、100ms生命周期、governor和receipt owner均封存原字节。28个UR10e OBJ/XML和CR12 STL资产已在包内；90项模型身份总清单覆盖当前和封存三个上下文。

当前结论：可移植源码/依赖/导入/轻量单测基础PASS；目标机物理资格、PPO性能、训练/恢复执行、近期服务器源码和checkpoint均NOT_RUN或UNVERIFIED。德国服务器近期未同步PPO修改未合并，须后续单独只读回收原版本；本轮未连接服务器。
