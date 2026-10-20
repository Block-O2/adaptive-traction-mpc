# B Runtime Qualification Decoupling and Frozen M2 Host Clock Validation v1

STATUS: **STOP_CURRENT_HOST_FAST_SERVICE / NOT_FROZEN**。三轴判定已拆开，历史 R2 FAIL 不变。旧 047/048 的原始证据按新增合同复核均为 runtime PASS；本轮四次完整 host-clock 确认均 physical、安全、current admission、因果、有界 backlog PASS，但 FAST 服务尾延迟未达预注册门槛，因此不能把旧 evidence 的 PASS 当作当前 host 持续服务通过。B 未冻结，M2 未运行。

t0：2026-10-08 02:34:42 +08；hard stop：06:34:42；停止新重任务时间：06:04:42。提前停止原因是同类服务问题在最后安静复核仍出现，继续需要本轮禁止的 B 优化或放宽已冻结门槛。未耗尽4小时/50次预算。

QUALIFICATION SPLIT

- B_RUNTIME_MOTION_EXISTING_EVIDENCE = PASS（047/048，回顾性新增轴，不改原标签）。
- B_RUNTIME_MOTION 当前确认 = FAIL（4/4），B_RUNTIME_FROZEN = FALSE，B_RUNTIME_BASELINE_V1 = NOT_FROZEN。
- LEGACY_R2_MATCHED = FAIL（旧结果及本轮4次）。
- LEGACY_STRICT55 = FAIL（本轮4次 TASK 最大 activation age 均 >=55ms）。旧047仅 standalone <55ms age metric PASS（52.634693ms），旧048 FAIL（86.010587ms）；历史含R2/服务的 engineering composite 两次仍 FAIL。两种指标单列，避免重新耦合。

新增合同在任何新 physics 之前保存。实际采用旧 practical runtime 服务门槛：p50<=5.5ms，p95<=7.5ms，p99<=10ms，gap>10ms比例<=5%，miss fraction<=15%，rolling1s平均最大<=6ms，最大 unresolved backlog<=100ms；这些属于本合同 engineering qualification，不声称它们是运动完成的必要物理条件。没有在观察失败后修改门槛。原100ms lifecycle/current-state safety和native数学不变。

B STATUS / MOVEMENT / RUNTIME

| Run | Runtime | OUT / HOLD / RETURN s | FAST p50 / p95 / p99 ms | Rolling 1s mean max ms | Miss fraction | TASK activation max ms |
|---|---|---|---|---|---|---|
| 002_B_confirm_deviation | FAIL | 9.010000 / 1.030000 / 9.011750 | 5.184 / 9.584 / 14.241 | 8.520 | 15.03% | 98.700 |
| 003_B_confirm_nominal_harness_retry | FAIL | 9.010000 / 1.030000 / 9.011750 | 5.071 / 8.182 / 11.960 | 8.216 | 9.03% | 57.608 |
| 004_B_quiet_retest_nominal | FAIL | 9.005000 / 1.040000 / 9.008250 | 5.111 / 9.481 / 14.110 | 7.300 | 11.86% | 72.524 |
| 005_B_quiet_retest_deviation | FAIL | 9.010000 / 1.035000 / 9.011500 | 5.050 / 7.868 / 11.008 | 6.887 | 7.75% | 85.568 |

四次完整 OUTBOUND、RETURN 和真实受控 HOLD 全部通过原独立 physical scorer；HOLD dwell0.5s、shared minimum1s、两段reference completion及目标保持不变。HOLD 1.030–1.040s 只影响旧R2，当前runtime失败来自FAST服务门槛。最大backlog范围 17.777–18.402ms，未发现无限等待或失控backlog；每次 meaningful B native计划10或11个。所有 468,793 个真实native steps归属核对，causal violation=0，expired actual write=0。拒绝/取消、合法旧command承担等待区间及fallback逐request保存在各RUNTIME_QUALIFICATION和MULTIRATE，未用ACTIVATED冒充physical执行。

已有证据：047/048 FAST p50约5.004ms、p95约5.4ms，原始117046/116985步全部重审；旧raw文件 60 个核验封存hash。当前四次与旧测量不同，不能据此推断硬件/未来资源状态的一般能力。

FORCE / MOMENT ATTRIBUTION

| Run | Raw full J_F N s | OUT / HOLD / RETURN J_F N s | Moment integral Nm s / peak Nm | Force peak N |
|---|---|---|---|---|
| 002_B_confirm_deviation | 1486.848 | 766.079 / 54.953 / 665.816 | 102.352 / 15.303 | 107.687 |
| 003_B_confirm_nominal_harness_retry | 1497.399 | 785.544 / 54.929 / 656.926 | 99.911 / 15.801 | 110.963 |
| 004_B_quiet_retest_nominal | 1456.803 | 753.364 / 55.451 / 647.988 | 95.791 / 15.817 | 115.958 |
| 005_B_quiet_retest_deviation | 1449.844 | 737.608 / 55.183 / 657.054 | 104.029 / 15.309 | 107.254 |

逐阶段时长、积分覆盖时长、mean force、F/M peak、tracking和clearance见PACKAGE_RESULTS。分解使用原TASK trace左端force/moment积分，按实际transition拆分跨边界interval，三阶段和闭合原raw J_F；没有裁掉或补造HOLD。最后一个evaluation sample与实际COMPLETE commit的原始小间隔单列，不向raw J_F补未来样本。无M2，因此无coordination gain或moment tradeoff比较；不能把这四个B run互相比作学习收益。

M2

Frozen Q SHA256：3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9，前后核验一致，Q/G更新0。120D feature/selection replay NOT_RUN（用户要求B冻结后执行）；native M2 proposal、learning receipts和nonzero learning physical executions均0；M2 VALID/attempts=0/0；2smoke、paired matrix和B/M2 J_F均NOT_RUN，非零学习执行未证明。

Strict55 guard source audit已保存。历史E5 `min(40,55-reserve36)=19ms` 为strict55派生提前proposal拒绝，可在后续冻结B后的版本化M2 adapter单独关闭；本轮未关闭。100ms原生expiry/current ownership/current-state/safety/causal write保留；40ms bridge和mixed shadow budget职责未明的部分没有混删。历史count是issued modifiable proposal slots，不是执行次数；没有偷偷改成committed count，没有开发或反复修M2。

REPETITION SMOKE

NOT_RUN。B gate未通过；已有persistent session wrapper明确只支持SCIENTIFIC_SIMULATION，不能冒充actual host persistent session。不重构状态机或session接口。

NEGATIVE RESULTS

1. 001缺少隔离包action contract，在physical入口前startup失败；保留START/END及traceback，已仅复制原不可变输入文件修复，retry用新ID。
2. 四次新完整host确认的p95/p99/rolling1s服务门槛均FAIL；其中002的miss fraction也FAIL。安静复核仍失败，未挑选或删除失败。
3. HOLD仍使旧R2 FAIL；未做HOLD优化或放宽R2。
4. B未冻结，因此M2、paired force收益和repetition稳定性均未验证。

ACCOUNTING / PRESERVATION

5 attempts = 1 pre-physics startup failure + 4 complete host tasks；START=END=5。Added native steps=468,793，physical simulation=117.1983s；已导出main model API calls=85,135，native worker calls=14,133。warm/import/advisory未完整counter的部分标UNKNOWN；没有把缺失当0。所有TASK实际owner exitcode0/JOIN核对，commissioning close evidence保存，无当前task-owned运行进程。No auto-resume。

15条资源采样；WSL available最低5.621GiB，Windows available最低0.942GiB，commit headroom最低5.106GiB，swap稳定且无新增swap I/O/OOM。短时Windows内存低仅记录；没有持续真实压力，因此无需backoff，没有更改RAM/swap/power/WSL或终止无关进程。服务变慢的具体原因未被证实。

主repo branch/HEAD/status/index/staged diff与起点完全一致（见preservation/GIT_BEFORE与FINAL_PRESERVATION），未staged/commit/push/reset/delete。C13 1150文件逐位一致，133文件仅精确package路径/名称替换，controller/Human/physics/safety/task数学/原expiry没有改变。历史封存包报告/ledger/manifest和frozen Q保护hash不变。新报告与新账本只在本包写入。

完整源/config/runner/source relocation/contract及输出hash、gzip CRC、compute/resource ledger保留在canonical包；Windows保留作者脚本、紧凑报告/manifest/账本/复核结果。新增文件范围仅本包装配、qualification audit、报告与最少确认配置；无B architecture/control或Q修改。

TOTAL：当前报告生成wall约29.2min；最终close时间和added-data bytes见PACKAGE_CLOSED及FULL_PACKAGE_VERIFICATION。50attempt预算未耗尽，4小时预算未耗尽，不声称B原理上不可能通过。

NEXT：只读审查当前host的FAST服务尾延迟与原5ms反馈计算预算，定位它与047/048性能差异的来源，再决定下一包是否具备冻结条件。

REPORT PATH：C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_runtime_qualification_decoupling_v1/REPORT.md

STOP。
