# 复现入口

本包已STOP，不在原目录重跑或重置计数。新运行必须建立新的版本化兄弟目录，复制source/code/deps/weights、FROZEN_18D、motion合同与output/SHARED_COORDINATION_ACTION_CONTRACT，按新根路径迁移并重新冻结预算/manifest。

本轮命令使用指定`/home/hank/envs/adaptive-online-rl-v1/bin/python -B`：control/preflight.py；control/own_campaign.py reproduction；复现门和control/independent_recompute.py reproduction通过后，分别own_campaign.py N1、N2、N3、N4。每个owner等待全部fork结束，物理串行；日志/command和返回码见各OWNER.json。没有更改既有Git分支。

只读重新计算：control/independent_recompute.py reproduction N1 N2 N3 N4（向本包derived/audit写新计算输出；不启动physics）。正式指标由冻结code/analyze_matched.py和explore_common.py给出；独立计算不导入plant/runner/controller。

完整raw在source/results/<id>/{trace.npz,summary.json,runtime_artifacts.json.gz,native_reference.npz}；参数、代码、model/config、版本身份和各次START manifest见本包相应JSON。完整live状态由os.fork继承，不是从hash恢复隐藏状态；保存的hash仅作审计，不能用来替代完整fork。
