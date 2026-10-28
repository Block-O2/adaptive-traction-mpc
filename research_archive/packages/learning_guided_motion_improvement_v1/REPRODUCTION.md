# 复现与只读审阅

本包是唯一ACTIVATION和唯一attempt名称的有限研究。T0、硬截止、上限见START.json；原请求保存在USER_REQUEST.txt。不得原地重启physical脚本或复用旧PID/attempt/raw路径。

源码起点为已在云端恢复并校验的GitHub commit `1adb1de177d6f5f32de6d01c4e629cbfae9ce121`；实际闭包恢复和路径差异见audit/CLOSURE_RELOCATION.json、MISSING_NONCODE_ASSETS_RESTORED.json、SOURCE_RECOVERY_AUDIT.json及CAMPAIGN_SOURCE_MANIFEST.json。历史研究目录未作为新输出目录。

使用既有Python：`/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/cpu-env/bin/python`。线程环境为`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1`，没有安装依赖。精确版本见audit/ENVIRONMENT_IDENTITY.json。

执行顺序：长期日志反思→零physics诊断→recovery_worker→study_worker→validation_worker→独立raw重算→分析与保护封包。所有物理结果保存在runtime/source/results，每次有独立trace、summary、runtime_artifacts.json.gz，科学结果/预测/模型分别在attempts、predictions、models；原scorer报告在runtime/reports。

审阅者可只读解析JSON/CSV/NPZ或查看REPORT.md及figures，无需启动MuJoCo。只读重算也应写新的审阅输出目录，不覆盖本包已冻结报告。新的物理复现必须使用新目录、新时钟、新账本、新source/config SHA和明确预算，不从q/dq回放构造活状态。

Linux完整address-space fork仅用于本轮scientific simulation；它不是持久化跨ABI序列化恢复，也不赋予host硬实时或真实患者克隆能力。原native0.25ms、service5ms、bridge40ms和lifecycle100ms合同不同，须分别保持。
