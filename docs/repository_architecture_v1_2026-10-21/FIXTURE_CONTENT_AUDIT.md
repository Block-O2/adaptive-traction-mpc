# 129.61 MB 历史 fixture 内容审计

原归档仍在同机历史目录，未更名、重压缩或删除。bytes=129608743，SHA256=`4d57c25005da7ac02c6f9d206c661399b8babd229066c2d468e07fc1234c8001`。完整逐成员bytes/SHA/数据结构、分类与用途见 evidence/FIXTURE_ARCHIVE_AUDIT.json。

原TAR包含32个常规文件、无目录/符号链接/路径穿越/重复成员名；解包后146542129bytes（139.75MiB）。最大成员为 parent/runtime_artifacts.json.gz，34310122bytes（32.72MiB）。归档129608743bytes为129.61十进制MB，约123.60MiB。

## 实际内容

3个完整历史实验臂 parent/B/H150。每臂都有trace、summary、config、native reference、runtime、metric、DATA、MEASURED、receipt报告与motion_series；只有B/H150另有小型CAUSAL_STATE摘要。没有训练checkpoint或可恢复的父进程地址空间，没有科学源码。所有JSON和gzip JSON内容及NPZ结构已检查；NPZ使用allow_pickle=False加载，无object数组，类别字符串扫描无凭证/邮箱；未发现真实凭证或人员标识。这是当前32成员内容审计，不是全Git历史敏感扫描。

| runtime原生文件 | Git保存bytes | gzip内部JSON bytes |
|---|---:|---:|
| `source/results/D01R_B/runtime_artifacts.json.gz` | 34306027 | 145009873 |
| `source/results/D01R_H150/runtime_artifacts.json.gz` | 34234559 | 145308258 |
| `source/results/D01R_parent/runtime_artifacts.json.gz` | 34310122 | 145194405 |

| 实验臂 | 原生数组位置 | 行数 |
|---|---|---:|
| `D01R_B` | `/wall_physics/command_receipts` | 5817 |
| `D01R_B` | `/wall_physics/native_states_evaluation_only` | 116320 |
| `D01R_H150` | `/wall_physics/command_receipts` | 5817 |
| `D01R_H150` | `/wall_physics/native_states_evaluation_only` | 116320 |
| `D01R_parent` | `/wall_physics/command_receipts` | 5817 |
| `D01R_parent` | `/wall_physics/native_states_evaluation_only` | 116320 |

gzip内部JSON超过100MiB，但原生scorer直接stream读取原.json.gz，正常运行无需手动解压。保留原字节和原格式可以保留真实数据身份；不将其改装成新的传输分卷，不把历史TAR提交Git。

## 完整成员表

| 原相对路径 | bytes | 主分类 | Git关系 |
|---|---:|---|---|
| `source/results/D01R_B/trace.npz` | 3725337 | ESSENTIAL_FIXTURE | 已在Git |
| `source/results/D01R_B/summary.json` | 2834454 | ESSENTIAL_FIXTURE | 已在Git |
| `source/results/D01R_B/config_snapshot.json` | 2895 | ESSENTIAL_FIXTURE | 已在Git |
| `source/results/D01R_B/native_reference.npz` | 148730 | HISTORICAL_RAW | 已在Git |
| `source/results/D01R_B/runtime_artifacts.json.gz` | 34306027 | ESSENTIAL_FIXTURE | 本轮补入 |
| `output/D01R_B.json` | 35255 | ESSENTIAL_FIXTURE | 已在Git |
| `output/D01R_B_DATA.json` | 39818 | ESSENTIAL_FIXTURE | 已在Git |
| `output/D01R_B_CAUSAL_STATE.json` | 1215 | HISTORICAL_RAW | 已在Git |
| `reports/D01R_B_MEASURED.json` | 101480 | ESSENTIAL_FIXTURE | 已在Git |
| `reports/D01R_B_EXECUTED_RESIDUAL_RECEIPTS.json` | 3247346 | ESSENTIAL_FIXTURE | 已在Git |
| `motion_series/D01R_B.npz` | 4351456 | ESSENTIAL_FIXTURE | 已在Git |
| `source/results/D01R_H150/trace.npz` | 3717440 | ESSENTIAL_FIXTURE | 已在Git |
| `source/results/D01R_H150/summary.json` | 3090424 | ESSENTIAL_FIXTURE | 已在Git |
| `source/results/D01R_H150/config_snapshot.json` | 2895 | ESSENTIAL_FIXTURE | 已在Git |
| `source/results/D01R_H150/native_reference.npz` | 155385 | HISTORICAL_RAW | 已在Git |
| `source/results/D01R_H150/runtime_artifacts.json.gz` | 34234559 | ESSENTIAL_FIXTURE | 本轮补入 |
| `output/D01R_H150.json` | 35284 | ESSENTIAL_FIXTURE | 已在Git |
| `output/D01R_H150_DATA.json` | 39857 | ESSENTIAL_FIXTURE | 已在Git |
| `output/D01R_H150_CAUSAL_STATE.json` | 1218 | HISTORICAL_RAW | 已在Git |
| `reports/D01R_H150_MEASURED.json` | 101637 | ESSENTIAL_FIXTURE | 已在Git |
| `reports/D01R_H150_EXECUTED_RESIDUAL_RECEIPTS.json` | 3245693 | ESSENTIAL_FIXTURE | 已在Git |
| `motion_series/D01R_H150.npz` | 4325704 | ESSENTIAL_FIXTURE | 已在Git |
| `source/results/D01R_parent/trace.npz` | 3725337 | ESSENTIAL_FIXTURE | 已在Git |
| `source/results/D01R_parent/summary.json` | 2834776 | ESSENTIAL_FIXTURE | 已在Git |
| `source/results/D01R_parent/config_snapshot.json` | 2895 | ESSENTIAL_FIXTURE | 已在Git |
| `source/results/D01R_parent/native_reference.npz` | 148730 | HISTORICAL_RAW | 已在Git |
| `source/results/D01R_parent/runtime_artifacts.json.gz` | 34310122 | ESSENTIAL_FIXTURE | 本轮补入 |
| `output/D01R_parent.json` | 35282 | ESSENTIAL_FIXTURE | 已在Git |
| `output/D01R_parent_DATA.json` | 38193 | ESSENTIAL_FIXTURE | 已在Git |
| `reports/D01R_parent_MEASURED.json` | 100267 | ESSENTIAL_FIXTURE | 已在Git |
| `reports/D01R_parent_EXECUTED_RESIDUAL_RECEIPTS.json` | 3250962 | ESSENTIAL_FIXTURE | 已在Git |
| `motion_series/D01R_parent.npz` | 4351456 | ESSENTIAL_FIXTURE | 已在Git |

27项 ESSENTIAL_FIXTURE 共146086851bytes：原算术输入、原config provenance和冻结输出对照。5项 HISTORICAL_RAW 共455278bytes：3份native_reference和2份CAUSAL_STATE，离线算术不读它们；已在Git且很小，保留历史身份。ESSENTIAL_SOURCE=0、CHECKPOINT=0、UNVERIFIED=0。GENERATED_DATA是来源角色：这些文件由旧实验生成，现已冻结作fixture，不能当临时产物清理；本轮新输出仅进忽略目录。

4组重复内容、27种唯一内容，冗余路径5项共8231313bytes。B/parent trace、native_reference、motion_series相同，三份config相同；Git blob天然去重，保留实验臂路径不改变历史身份。DUPLICATE是正交标签，不能取代ESSENTIAL/HISTORICAL用途。

29文件43691421bytes已在起始Git树。真正需要新增Git的只有3个runtime文件102850708bytes（98.09MiB总计），每文件约32.7MiB，远小于普通Git单文件100MiB限制。原生数据不是每个字节都参与评分，但原scorer读取其中native状态、receipt和host profile，按字段裁剪会改变原SHA；本轮保留三文件全部原字节。无需Release、LFS、分卷或重写scorer。

大小限制已核实 [GitHub官方说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)：普通Git超过50MiB提示，超过100MiB阻止；本轮三文件均低于50MiB。
