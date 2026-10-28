# 恢复、停止与只读复算

ACTIVATION.json 是本轮唯一时钟。任何恢复都沿用原 T0、hard_stop_unix、累计 START/native 账本；END 后不自动恢复。原用户授权范围结束后，新的物理研究需要新的明确任务。

## 已部署服务器队列

source/acl2_supervisor_v2.py 读取 queue 中有限、唯一 ID 的 job，保存 START/END、PID、deadline、精确命令与源码 SHA。它能接管仍存活的旧 job PID；本轮已经在 RETIMED job 中完成一次真实接管，见 OWNER_ADOPTION.json，未重启物理或重置 T0。SSH 和 Agent 界面断开不终止这些服务器进程。

Watchdog 在 T0+10h关闭本轮身份进程；独立 finalizer 在 T0+9h20优先封包。STOP_REQUESTED 阻止新派发并令原物理边界停止；CLOSE_REQUEST 请求受控最终封包。它们只影响本轮 owned 身份，保护其它作业。

## 原状态与物理恢复边界

Linux os.fork 保留完整原生、observer、belief、scheduler、pending/lifecycle、RNG及原生句柄。fork 是进程地址空间能力，不是可移植的永久物理 checkpoint。PID 尚存且身份/源码/截止一致时由队列接管；PID 已死后，禁止从 q/dq或hash伪造活状态。

如在原窗口内恢复一个失败 worker，应建立新唯一 group/job/attempt ID，重新执行原 cold commissioning 和同一合法 prefix，单独计入新增 native。使用原 B/强父完整raw对照确认物理状态复现。保留旧完整、partial和失败；不得覆盖旧目录或再次计入旧 native。

## 搜索 checkpoint

CORE 的 PROGRESS、CHECKPOINT_016/032、逐attempt RESULT、事前 prediction/pool、每次模型训练ID与 SOURCE_MANIFEST 保存完整决策依据。A/B/C各臂历史隔离，不能把其它臂反馈作为恢复时的额外隐含数据。固定search_seed和已保存候选池可重放纯优化器状态，恢复到下一个未执行的唯一attempt；重新commissioning的成本额外计账。不得把已完成的物理结果再次派发或抹去。

## PPO checkpoint

每个generation BEFORE保存冻结mu/logSTD/value、pre-tanh z、精确tanh动作、行为密度ID和采样后的RNG；AFTER保存三组Adam的t/m/v、actor/critic、RNG和已完成episode数。只能在相同动作语义/物理条件、source和原T0下作语义兼容恢复，不使用旧历史PPO checkpoint。

优先从完整AFTER恢复所有参数、Adam与RNG，并用新job身份继续generation/episode累计编号。若有未更新的BEFORE batch，只有行为参数、源码、条件与动作接口均未改变时，才可按其原行为密度保存已完成rollout，完成其余已冻结动作后更新。若任一身份改变，该pending batch不得混入新policy更新；旧物理成本和失败仍保留，不能改成零样本。当前队列不会盲目自动重试死worker；恢复先保存明确版本与账本。

## 独立只读复算

source/legacy_independent_audit.py 与 acl2_failure_audit.py 用完整JSON解码重算force/moment、native receipt/torque所有权与真实Human导数。source/acl2_scorer_replay.py直接调用未改写的原evaluate，绕过SAC_PHYSICAL_AUDIT缓存，以只读gzip路径适配器提供原JSON，再从native独立重建motion/dose并重跑原比较门。所有复算输出写audit，不改原raw或scorer。

PPO_ON_POLICY_REPLAY用独立密度式、固定seed、原任务结果、单步returns/advantage、五点数值梯度和Adam重放核验采样/更新。它是同一Agent的另一条代码路径，不是另一位研究者或独立患者数据。
