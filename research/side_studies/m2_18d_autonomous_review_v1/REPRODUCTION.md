# 复核与复现入口

canonical新包：/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1；指定Python=/home/hank/envs/adaptive-online-rl-v1/bin/python，运行带-B。Windows为审阅镜像，不含完整source/results。

本包已关闭，不可原目录重跑physics或重置账本。新物理复现须建立新的兄弟版本目录，复制source/code/deps/weights、完整候选、两个RETURN plateau、共享动作合同和motion协议；迁移根路径、冻结新的RUN_PLAN和manifest后，依序preflight→own_campaign reproduction→独立raw复核→N2→事前开发选择→development→U1/U2/U3。原RUN_PLAN和research_sequence记录实际条件分支；失败分支不跳过门限继续验证。不能从保存q/qvel恢复Human隐藏状态，必须原cold commissioning与live fork。

无physics复核入口：control/independent_recompute.py 后跟已完成组名；读取存档，仅向derived/audit写核算结果。control/diagnostic.py、tracking_chain.py、causal_features.py为诊断。为保护本次报告，建议复制分析脚本到新输出目录后改输出根，禁止向历史包写入。全部完整raw在source/results/<id>下trace.npz/summary.json/runtime_artifacts.json.gz/native_reference.npz；原始数据来源SHA与执行身份在manifest、MEASURED和账本。
