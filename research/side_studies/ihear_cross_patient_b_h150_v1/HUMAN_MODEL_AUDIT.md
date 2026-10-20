# Human V2 实际模型与跨患者可行性审计

审计范围：源码/XML生成链与非步进模型检查。本文本身不是完整物理实验结果。未运行 `mj_step`、`mj_step1`、`mj_step2` 或任何 physics owner。正式患者合法性仍需独立冷初始化、commissioning、真实稳定性和完整任务门。

## 1. 实际执行模型的识别

不能把基类 `HumanV2Parameters` 的默认 80°/100° ROM 当成本轮执行的 ROM。历史 B/H150 工作包通过 `code/study_common.py:15,53–70` 进入 `runtime_coordination_residual_v2`；原始执行路径还可进入 `runtime_sac_expert_v1`。`sac_env.py:147–150` 实际加载 `configs/high_rom_v1/high_rom_nominal_sync_120_v1.json`。该 case 的 `research_model=high_rom_v1` 会同时选择已有的高 ROM 结构先验与 plant ROM：髋、膝均 0–125°；原任务起止为 [5°,10°]，外展目标 [120°,120°]。这不是本轮扩大 ROM。

源码根路径记号 `S3` 为 `source/stages/stage3_full3d/src/traction_mpc_stage3`；`S5` 为 `source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5`；`CFG` 为 `source/stages/stage5_personalized_motion_learning/configs`。审计首先读取了历史包的保留源码镜像；正式执行包应以根协调器的 canonical WSL 源码 hash 清单为准，不能把路径相似当作 hash 相等。

## 2. Reference Human 的实际参数

| 量 | 大腿 | 小腿（含已有等效足质量） | 源码依据 |
|---|---:|---:|---|
| 长度 m | 0.43688 | 0.40076 | `S3/human.py:33–38`，0.254/0.233 × 1.72 m |
| 质量 kg | 7.425 | 4.5 | `S3/human.py:41–46`，0.099/0.060 × 75 kg |
| COM 距近端 m | 0.18916904 | 0.1723268 | `S3/human.py:49–54`，0.433/0.430 × 长度 |
| 局部 y 主惯量 kg m² | 0.1275449578128 | 0.065046473928 | `S3/human.py:57–62`，m × (0.30L)² |
| 局部 x/z 主惯量 | 0.51 × Iy | 0.51 × Iy | `S3/coupled.py:174–206` |
| 被动刚度 Nm/rad | 10 | 10 | case physical + `S3/human.py:23` |
| 被动阻尼 Nms/rad | 5 | 5 | case physical + `S3/human.py:24` |
| 静息角 | 5° | 10° | case physical + `S3/human.py:22` |

惯性矩阵使用显式 inertial，不能从可视 capsule 的体积重新推定质量。基线各主惯量正，最大主惯量小于另两者之和（1 < 0.51+0.51）；新患者也必须保持该性质。长度变化时 COM 按 L 缩放，Iy 按 mL² 缩放。质量变化时 Iy 按 m 缩放。COM fraction 与 gyration fraction 属于独立的工程模型参数，不能把其范围标为临床人群分布。

重力 9.81 m/s²。髋关节轴局部 `[0,-1,0]`，膝轴 `[0,+1,0]`；因此小腿平面角是 `q_hip-q_knee`，不能错误使用二者之和。来源：`S3/coupled.py:188–204`、`S5/geometry.py:51–79`。

## 3. 软、硬限位与被动力学

实际高 ROM 的 joint range 为两个关节均 [0°,125°]，XML compiler 沿用 `angle=radian, autolimits=true`（`source/stages/stage3_full3d/models/ur10e_torque.xml:2`）。硬 range 由 `S3/coupled.py:189,201` 写入；MuJoCo 硬限位使用原模型/引擎解析的约束默认值，不能另换 solver/solref 制造患者变化。

额外软限位开始于下界+5°、上界−5°，即本执行模型中为 5°与120°；数值容差 1e−9 rad；边界扭矩系数 25 Nm，软限位阻尼系数 2 Nms/rad。越界尺度 z 后，恢复项为 ±25z³，向外运动阻尼项为 2z²×向外速度。来源 `S3/human.py:25–30,121–152`。关节线性弹簧/阻尼直接写入 MuJoCo joint stiffness/damping/springref（`S3/coupled.py:188–204`）。软限位通过 `self.human` 每步进入 qfrc_applied（`S3/coupled.py:481–485`），不是另一个冻结名义对象。

已有加速路径 `code/native_soft_limits.py:2–13` 从 `self.human` 收集 ROM、soft margin、tolerance、boundary torque、damping，并按参数键更新缓存。因此用完整患者 human 实例构建 plant 能保留一致的软限位语义；仅改 XML、却不改 self.human 的做法不安全。本轮建议保持软限位参数和硬 ROM 全部不变，单因素 k/d 为真实被动关节变化。

## 4. cuff 与床面是真正耦合约束

Stage-5 cuff 位于小腿近端起 0.72L，即 reference 为 0.2885472 m（`S5/human.py:13–29`）。这覆盖 Stage-3 默认 0.90L，不能误用后者。袖筒半长 0.04 m、外半径 0.058 m；大腿/小腿 capsule 半径 0.050/0.045 m（`S3/coupled.py:43–53,211–216`）。cuff site、袖筒端点、膝 body 原点、大腿和小腿几何、两个显式 inertial 均由同一个 human 参数对象生成。改变腿长时必须一起重建，不能单改 length 常数或控制器几何。

床为 z=0.012 m 的无限 collision plane，XML 的 `size=1.6 1.0 0.05` 不是有限碰撞边界。名义髋 z=0.062 m，实际 reference case 上移 0.0001 m，因此近端大腿 capsule 最小固定间隙为 0.0001 m。冻结床摩擦 `[0.70,0.01,0.001]`，contact solref `[0.020,1]`，solimp `[0.90,0.98,0.003]`。来源 `S3/coupled.py:43–53,177–210`、reference case physical.hip_translation_xz_m。

碰撞域：robot self=1，Human=2，bed=4；Human–bed 相互接触，robot–bed/robot–Human 没有被配置成动态碰撞对，袖筒和 cuff bar 的 contype/conaffinity 为零。必须继续保留原接触机制，同时用已有几何检查识别穿透；“没有 contact event”不能证明不存在几何重叠。来源 `S3/coupled.py:105–113,183–214`、`S5/cr12_plant.py:146–195`。

实际连接为有限刚度 Kelvin–Voigt，而非激活 XML weld：`S3/spring_damper_interface.py:114–135,151–159,194–200`、`S5/cr12_plant.py:350–376` 禁用 weld，按两个 site 的相对位姿/速度施加相反力及正确作用点力矩。实际加载 `CFG/stage5_geometry_mechanics_v2.json`，不是旧 v1 stiff surrogate：

- 平移 K = [25000,25000,25000] N/m；D = [346.19104557,377.33911767,343.90028453] Ns/m。
- 转动 K = 320 Nm/rad；D = 10.02820618 Nms/rad；rest translation/rotation 均零。
- 原生 timestep = 0.00025 s，命令/积分周期 = 0.005 s。

腿长、质量、关节刚阻尼变化不得重新计算 cuff 阻尼以“维持阻尼比”，否则同时改变了接触机制。

## 5. 机器人、安装和 cold initialization

执行机器人是 CR12 V0。`S5/cr12_plant.py:54–195` 替换 donor robot subtree，Human 与床生成链不变。固定 T_WB 平移 [0.6,−0.62,0.04] m，T_EC 平移 [0,0.14,0] m，cuff bar 长0.08 m/半径0.012 m；安装旋转矩阵见 `CFG/stage5_geometry_mechanics_v1.json`。各患者不改变机器人质量、惯量、armature=0.1、关节范围、执行器限制或接口。

力矩绝对限值 [436,436,194,102,66,66] Nm，关节速度约束 [120,120,180,234,240,240]°/s（`CFG/full3d_adaptive_integration_v1/development_v1_1.json`、`models/cr12_v0.xml:111–122`）。工作空间通过确定性 full-pose 多起点 IK 检查，不能用臆测球形半径替代。初始 IK 以最小奇异值选分支、数值平局再按名义距离/字典序选择（`S5/cr12_plant.py:199–276`）。IK 搜索失败只是 `INITIALIZATION_OR_IK_SEARCH_FAILED`，不证明数学上绝对不可达。

真实冷启动在 `runtime_coordination_residual_v2.py:240–316`：nominal control model 与 physical human/geometry 分开；先 `plant.reset(start)`，将原名义 loaded-support preload 作为 cuff-relative offset 放到实际 cuff 位姿，重求 robot IK；这属于允许的机械安装/初始预载，不是 controller 读 truth。第一次主动 epoch 前才允许初始 qpos/qvel 装配，之后必须通过原生动力学前进。

每位患者运行完整 commissioning：原请求节点 [5,10]→[14,19]→[9,27]→[16,22]→[5,10]°，每段1.5 s，原 settle1 s 及原调度/延迟逻辑。请求节点不是必然实际执行目标：已有 `choose_feedback_commissioning_target` 和 clearance 逻辑按冻结合同选有效目标，必须审计 effective targets 与真实物理轨迹。在线 observer/拟合只能从合法传感器数据获得信息。本轮 P0 冻结算法和初始先验，保留 B 原有 commissioning/估计流程，不把 P0 误解释为禁止原算法估计。

控制任务：原120°目标、0.5 s HOLD、每 phase10 s timeout、完整 task timeout30 s；任务角/速度完成容差 1°/2°s⁻¹；速度门 [45,75]°/s、加速度门 [300,600]°/s²、force200 N/moment60 Nm。原控制器 completion margin 仍按冻结文件收紧在线完成判定。本轮不得降低任务目标或增加超时。

## 6. 推荐的隔离 plant-only 入口与 firewall

现有 `HiddenHumanV2`（`S5/fresh_qualification_v1/scenario.py:22–59`）已支持分段长度、质量、COM/gyration fraction。`hidden_plant(case)`（:62–146）将变化只传给物理模型，保留原数学形式。两个正式执行 runtime 在 :1959–1978 附近明确将 `control_human=high_rom_deployable_prior()` 与 `physical_human=hidden_plant(case)` 分开。

最小入口：新隔离运行封装给 `study_common.load_case_options` 返回该患者 case 的深拷贝及完全相同 options，再由原 `run()` 传 `qualification_case`。不修改 `STAGE5_HUMAN`、nominal_control_geometry、正式 runtime 或 control model 参数。reference P00 保持原 case 内容；患者 ID 在外层 manifest 标注。

不能把 physical dictionary、compiled joint state、真实 COM/惯量或真实腿长注入 planner、candidate、estimator、B/H150模型。已有合法传感器估计几何不算 truth 泄漏。P1若未来实施，必须另建协议并对 B/H150 同样提供合法已知参数；本轮不把 P1替代 P0。

## 7. 非步进检查与剩余物理资格

`audit_human/patient_models.py::model_static_audit` 生成完整 XML、编译并核查正质量、正惯量/三角不等式、COM 内部、cuff 内部、ROM、刚阻尼、采样 planar mass matrix SPD、0.46 m 冻结保守小腿上界及初始装配。保存 model/XML/case/physical hash，并对 robot/contact/equality/bed 生成不变量 hash。

严格不复用诊断状态：只执行一次原 `plant.reset(start)`；不在后续时刻写 Human qpos/qvel。末端 IK 使用独立 robot-only model。原 `assess_assembly(verify_robot=True)` 会把 Human 直接放到 goal 做几何诊断；本新封装没有使用该分支。末端完整 robot mesh clearance 因此显式留待原执行几何门与真实轨迹审计，不能把静态检查 PASS 写成完整患者可执行 PASS。

P0几何风险是实质科学问题：腿长变化会改变真实 cuff 坐标、初始 robot IK、观测反演误差和 controller 模型失配，0.46 m shank prior 必须覆盖真实长度。不能为了通过而只给 H150更新映射，也不能调整目标、ROM或强行加入 qpos 预设。

合格静态检查后，每患者仍需自身新 cold initialization + 完整 commissioning + 父状态形成，且父状态绝不跨患者 fork/native state 复用。同患者 B/H150 可以同一个 live parent fork。任一建模或 commissioning 失败必须保存具体原因；B失败也不能代替 H150执行证据。本文不宣称临床真实度或跨患者性能结论。

## 8. 已完成的 P00 canonical 源非步进验证

使用 canonical WSL 历史包源，只读导入且 `python -B`，在新包 `audit_human/test_reference_static/` 写出 model.xml、qualification_case.json、MODEL_STATIC_AUDIT.json。实际没有 physics START 或 native step；状态写入只有原 cold reset，后续 Human 写入数为零。

结果：模型 nq=nv=8，ROM [0,125°]×2，刚度 [10,10]、阻尼 [5,5]，全部 inertia/COM/质量检查通过，采样最小二维质量矩阵特征值 0.0590824755294 kg m²。初始 compiled geometry 间隙：大腿0.100 mm、小腿8.248 mm、袖筒1.763 mm、活动机器人130.738 mm；没有初始 contact。120°目标与返回目标的独立 robot IK 均成功。注意该几何 reset 尚未加入 runtime 的 loaded-support 预载，预载后必须重新审计实际执行状态。

发现需要保留的关键事实：原始请求 commissioning 节点静态最小小腿床面间隙为 −50.399 mm；历史静态检查明确只记录该项，不将其当作整位患者非法，因为原执行器包含 feedback/clearance 合法目标选择。此值不能冒充真实物理穿透，也不能抹掉。根执行器必须留存 commissioning 的实际目标、certificate和原生真实轨迹，以确认没有越过冻结安全门。

额外检查 native 加速路径：`code/native_interface_adapter.py` 以当前 model/data 地址及当前两个 site 计算 cuff；`code/native_single_step.py` 每步确认 interface 与 self.human soft-limit 参数键，再传当前 model 地址。未发现该入口用名义腿长/质量覆盖真实 MjModel 的做法。正式 source/native build hash 仍由 campaign provenance 核验。
