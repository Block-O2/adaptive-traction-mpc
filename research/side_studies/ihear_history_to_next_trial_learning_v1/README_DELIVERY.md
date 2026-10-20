# 交付与复核

先读 REPORT.md，再查 PACKAGE_VERIFICATION.json。完整证据同时保存在本 Windows 文件夹和 ENVIRONMENT.json 指向的 WSL canonical 文件夹。

EVIDENCE_MANIFEST.json 对本包除临时缓存、manifest/seal 自身外的每个证据文件保存 SHA256 和大小；DELIVERY_SEAL.json 封存 manifest。原始 trace/native/receipt、失败、模型权重和版本代码全部保留。镜像中原始 provenance 的绝对路径仍指向原 WSL canonical，未为迁移而改写历史证据。

用 Python 3.9+ 运行 verify_package.py 可只读校验整个 Windows 或 WSL 封存包，不需要 MuJoCo 或其他依赖，不产生新文件或 physics。

如需重新计算而非仅核对 SHA，可在保留封存原件后，在原 WSL 环境的另一个审计副本中运行 analyze_study.py --independent、final_audit.py 和 make_figures.py；这些脚本会刷新派生报告或审计时间戳，原始 provenance 的绝对路径仍指向 canonical 数据。不要运行 physics 入口继续本包；PHYSICS_STOP.json 已阻止新 START。若需另一次研究，应另建版本化研究包，不能覆盖本次结果。
