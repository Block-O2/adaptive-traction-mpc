# GitHub 固定源码恢复审计

T0：2026-10-21T02:08:05.854196+08:00。实际 checkout：`github/`，远端 `https://github.com/Block-O2/adaptive-traction-mpc.git`，指定研究分支 `codex/local-research-sync-20261020`，精确 HEAD `1adb1de177d6f5f32de6d01c4e629cbfae9ce121`。SSH 因本机未配置 GitHub known-host 记录退出；未修改 SSH/凭据，随后 HTTPS ls-remote 与真实全新 clone 成功。clone/checkout 日志见 `logs/`；最终 HEAD、tracked-tree 和 clean 状态见 `audit/GITHUB_FINAL_IDENTITY.json`。

|恢复轴|状态|直接依据|
|---|---|---|
|GITHUB_SOURCE_RECOVERY|PASS|远端分支与 detached HEAD 均为指定 1adb1de…|
|FROZEN_SCORER_IDENTITY|PASS|23 来源、16 锚点、v6 1426 项、9 合同均按原 SHA|
|FIXTURE_INTEGRITY|PASS|32 原件 / 146,542,129 bytes，全部来自此次 clone|
|HISTORICAL_OFFLINE_REPRODUCTION|PASS|全部原字段、receipt、motion 数组与冻结参考一致|
|FULL_FORK_REPLAY|NOT_RUN / UNVERIFIED|无可移植完整父 checkpoint；未构造替代状态|
|NEW_LIVE_MATCHED_EVALUATION|NOT_RUN|8 次新增仅为 nominal 开发冻结诊断|

先核验后运行：`deployment/verify_repository.py --expected-commit 1adb1de177d6f5f32de6d01c4e629cbfae9ce121`；`verify_b_h150.py`；原 `score_b_h150.py --work-dir <新目录>`。所有评分均用 `python -B`，无 `-O`；原断言启用。精确命令、工作目录、退出码与 wall 在 `audit/jobs/*/START.json`、`END.json`。原 install 脚本经读取后执行，使用受信现代 pip 的 `--python` 向两个全新 CPython3.12 venv 安装；没有复用历史 site-packages。offline 为 2 项 hash lock；CPU 为 35 wheel 的完整 hash lock；pip check 均通过。

仓库中的旧 CLOUD_GITHUB_DEPLOYMENT_GUIDE/B_H150_EVALUATOR_READINESS 保留了“还需外部 TAR”的早期状态；同一固定 commit 的最新架构/FRESH_CLONE_VALIDATION、data_catalog、score 入口和实际文件表明 32 项已原生进 Git。本轮按真实入口与 SHA 解析该时间差，没有取用旧 TAR/ZIP，也没有创造缺失 fixture。

3,079 当前源码/资产、2,237 Python 语法项、141 Stage3–5 XML 引用、450 原封存载荷及28 vendor身份核验通过；90 模型身份与6份原 XML 编译通过，编译检查禁止 mj_step/forward/inverse。原 RL-B 五个导入/单测入口通过；5项维护完整性失败测试通过。这些均不产生物理步、不授权训练。详见 `audit/REPOSITORY_VERIFICATION.json`、`MODEL_VERIFICATION.json`、`rlb-check-001/RL_B_ENVIRONMENT_CHECK.json`。

原 scorer 使用独立 offline 环境，Python 访问门禁止旧五个云端包及旧 coding 根，两个 open/scandir 预期拒绝 probe 通过；实际 scorer 无旧根拒绝事件。它是 Python audit hook，不是 OS/C 库文件系统沙箱。fixture 全部 SHA 与模块 __file__ 路径另行确认。`scorer/original-001/RUN_PROVENANCE.json` 记录实际 commit、source_dirty=false、输入/lock/config/模型/候选身份；最终原 checkout 内容未修改。

完整 parent 地址空间、MuJoCo/planner/传感历史及不透明句柄没有被可移植恢复；`D01R_parent_CAUSAL_STATE.json` 仍缺失。两份历史 _prefix_native 二进制仅保存 CPython3.10 平台身份，不作为3.12扩展加载。历史原运行 Git commit 若未记录，仍为 UNKNOWN；本轮源码提交不能冒称历史生成提交。离线链已恢复，不代表 full fork 或新 PPO live matched 已就绪。
