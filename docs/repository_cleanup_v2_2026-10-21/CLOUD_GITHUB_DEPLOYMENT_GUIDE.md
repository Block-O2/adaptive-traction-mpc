# GitHub 优先恢复指南

已验证的源码提交：`a60686f30aaee5e950fa7e9ae7e802cd74df4cc2`，分支 `codex/local-research-sync-20261020`。验证发生在用户本地 WSL，不是德国服务器。服务器操作、物理资格、训练均为 **UNVERIFIED / NOT_RUN**。文档收尾提交是该源码提交的后继；最终分支 SHA 见交付的 `GIT_SYNC_VERIFICATION.json`。

## 1. 精确取得源码

在新的目录执行；需要 GitHub 读取权限、Linux x86_64、CPython 3.12。CPU wheel 使用 manylinux，目标 glibc 至少 2.28。不要覆盖服务器已有研究目录。

```bash
BRANCH=codex/local-research-sync-20261020
COMMIT=a60686f30aaee5e950fa7e9ae7e802cd74df4cc2
git init ihear-github-source
cd ihear-github-source
git remote add origin git@github.com:Block-O2/adaptive-traction-mpc.git
git fetch --depth=1 origin "refs/heads/$BRANCH"
git fetch --depth=1 origin "$COMMIT"
git checkout --detach "$COMMIT"
test "$(git rev-parse HEAD)" = "$COMMIT"
python3.12 deployment/verify_repository.py --expected-commit "$COMMIT" \
  --output .deployment-work/source-verification.json
```

`verify_repository.py` 校验 3079 个当前源码/资产文件、450 个 RL-B 封存文件、完整 v6 的 1426 个执行来源、16 个历史来源锚点和 Stage-3–5 XML 引用。报告另列旧 Stage-1 Mac/UR5e 缺失资产；主输出的 PASS 只适用于明确声明的当前范围。

若需本轮完整审计索引，另取最终文档提交；它是上述源码提交的后继。可用最终核验 JSON 的完整 SHA 替换 `COMMIT`，同样精确 fetch / checkout / 校验，禁止仅凭浮动分支名声明版本身份。

## 2. 恢复原始 matched 离线 scorer

```bash
bash deployment/install_offline.sh
```

该脚本建立新的虚拟环境并按 wheel SHA256 安装 NumPy 2.2.6 / SciPy 1.15.3。系统需提供 `python3.12-venv` / ensurepip；若已有受信的现代 pip，也可通过 `pip --python <新环境/bin/python> install --require-hashes -r deployment/requirements-offline.lock` 引导安装。旧 pip 23 不能引导 Python 3.12。现有研究环境不会被改写。

先取得独立 fixture 归档，再执行：

```bash
python3.12 deployment/restore_external.py \
  --archive /path/to/b_h150_original_fixture_v1.tar.gz \
  --dest .deployment-work/original-fixture
.deployment-work/offline-env/bin/python -B deployment/score_b_h150.py \
  --fixture-dir .deployment-work/original-fixture \
  --work-dir .deployment-work/original-score-001
```

两个输出目录必须不存在。原 scorer 的全部断言保持启用，禁止 `python -O`。入口验证 32 个原始文件和 23 个来源身份；按原文件显式加载依赖，只重绑定路径，在新目录保存输出，不覆盖冻结 reports。

归档身份由 `deployment/b_h150_fixture_manifest.json` 固定。原件本地位置为：

`/home/hank/research_archives/repository_cleanup_v2_2026-10-21/b_h150_original_fixture_v1.tar.gz`

该归档 **129608743 bytes**，SHA256：

`4d57c25005da7ac02c6f9d206c661399b8babd229066c2d468e07fc1234c8001`

当前没有已发布的下载 URL，manifest 的 `url` 为 null；因此“仅 clone GitHub 即可完成全量评分”为 FAIL。数据所有者后续授权传输归档或提供 HTTPS 下载地址后，可运行：

```bash
python3.12 deployment/restore_external.py \
  --url "$AUTHORIZED_FIXTURE_HTTPS_URL" \
  --dest .deployment-work/original-fixture
```

下载器验证完整归档 SHA、全部成员路径/大小/SHA，拒绝链接、路径穿越、重复成员和覆盖已有目标。本轮未执行任何服务器传输。

原始参考结果为 B `1436.456498145051 N·s`，H150 `1402.6432114861727 N·s`，gain `2.353937394034738%`。完整 TASK 5 ms 左积分、0.25 ms native Human、receipt/age、motion 阈值保持原样。此结果是历史输入的离线复核，不是新的物理、host realtime 或临床资格。

## 3. 恢复 RL-B CPU 源码和环境

```bash
bash deployment/install_rl_b.sh
python3.12 deployment/check_rl_b.py \
  --python "$PWD/.deployment-work/rl-b-env/bin/python" \
  --work-dir .deployment-work/rl-b-import-check-001
```

完整 CPU lock 固定 35 个 wheel 的版本、URL、SHA256，包括原 requirements 未固定的传递依赖 setuptools。原 `research/rl_b_cpu_handoff_v1/requirements.txt` 和封存包没有被改写。锁已在 Linux Python 3.12.3 / Torch 2.7.1+cpu 下实际安装，pip check、原单测和导入预检通过。

入口位于 `research/rl_b_cpu_handoff_v1/`：`train.py`、`evaluate.py`、`ready_env.py`、`native_rl_env.py`、`runtime_setup.py`、`checkpoints.py`、`resource_guard.py`、`CLOUD_TRAINING_CONFIG.json`。这是封存的本地 CPU handoff；德国服务器最近的 episode、checkpoint、dirty 源码及训练版本尚未审计。

本指南只检查导入和单测，不运行 `qualify.py`、smoke 物理或训练。原 `READINESS.json` 仍为 NOT_RUN，`train.py` 原资格门保持生效。恢复源码/环境 PASS 不授予训练资格。

## 4. 其他大型 raw/state/checkpoint

完整审计索引见 `EXTERNAL_DATA_MANIFEST.json`，按 root / 研究包拆分的 CSV 含原路径、大小、SHA。取相应审计文档提交后，例如：

```bash
python3.12 deployment/manage_external.py verify \
  --index "$INDEX_CSV" --root "$ORIGINAL_DATA_ROOT"
python3.12 deployment/manage_external.py pack \
  --index "$INDEX_CSV" --root "$ORIGINAL_DATA_ROOT" \
  --archive "$NEW_VERSIONED_ARCHIVE"
python3.12 deployment/manage_external.py restore \
  --index "$INDEX_CSV" --root "$NEW_RESTORE_ROOT" \
  --archive "$NEW_VERSIONED_ARCHIVE" --archive-sha256 "$RECORDED_ARCHIVE_SHA256"
```

工具逐文件验证，pack 后复核归档成员，始终保留原件。大型数据尚未全部新建独立物理备份；不能把在位 SHA 索引当成备份。外部 D 盘链接目标及云端新数据未被本轮完整内容审计。

524项历史密集证据的独立归档还可按其专用成员索引恢复；需要取得本轮最终审计文档提交：

```bash
python3.12 deployment/manage_external.py restore \
  --index docs/repository_cleanup_v2_2026-10-21/manifests/ARCHIVED_DIRTY_EVIDENCE.csv \
  --root .deployment-work/restored-historical-evidence \
  --archive /path/to/remaining_evidence_v1.tar.gz \
  --archive-sha256 cf6dd9d58102606cc59c2511552ce4fc1716511e0ad415c242089609882e6b4a
```

该归档44806727 bytes，成员还原到新目录的 main/ 前缀下；原路径继续保留。此恢复入口已对完整524成员实际验证。

完整原 B/H150 执行manifest的1426条目现均由Git提供。其两份历史 _prefix_native 二进制是原CPython3.10 Linux x86_64和Darwin arm64资产，不可当作Python3.12扩展；原C和setup.py保留。离线scorer无需加载这些库，完整fork的ABI与构建仍UNVERIFIED。

## 5. 明确停止边界

`OFFLINE_SCORER_REPRODUCIBLE = PASS`，前提是恢复上述已验证的真实归档。

`FULL_FORK_REPLAY_REPRODUCIBLE = UNVERIFIED`。未定位可移植完整父 checkpoint，`D01R_parent_CAUSAL_STATE.json` 也未找到；现有摘要、qpos/qvel、hash 均不能替代原 live `os.fork` 地址空间。重新冷 commissioning、合法 prefix、同父 fork 属于后续单独授权的物理重演。

部署时只安装、校验、离线评分，保存新日志后 STOP。服务器本轮状态和部署结果不得标 PASS。
