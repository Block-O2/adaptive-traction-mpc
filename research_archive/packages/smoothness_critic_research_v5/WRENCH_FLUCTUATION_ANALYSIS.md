# cuff施力波动与采样

原JF/JM始终为原5ms TASK左积分，不用新采样口径制造积分收益。早期组只有200Hz actual cuff stream，不据此解析亚毫秒瞬态。后续原native step已经计算Human-site实际接口wrench，评价日志只复制其缓存，不另调用observe/refresh/step；4kHz流必须与原5ms重合点逐分量吻合。它是仿真真实接口wrench，不是新增硬件传感器能力。

| 身份 | 原门 | 权限 | JF N·s | JM Nm·s | native jerk RMS 髋/膝 °/s³ | 200Hz ‖F‖ rate RMS N/s | 4kHz ‖F‖ rate RMS N/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BRANCH02_ANT9 | PASS | original domain | 1400.161839 | 107.803159 | 320.04/677.34 | 17.8620 | 19.4422 |
| BRANCH02_ANTC19 | PASS | original domain | 1399.930374 | 108.081086 | 319.49/675.71 | 17.8724 | 19.4477 |
| BRANCH02_BEST | PASS | original domain | 1398.034615 | 107.971017 | 320.15/678.37 | 17.7435 | 19.3341 |
| BRANCH02_BLINDM9 | PASS | original domain | 1400.329015 | 107.786894 | 320.07/677.43 | 17.8659 | 19.4461 |
| BRANCH02_BLINDMC19 | PASS | original domain | 1399.930374 | 108.081086 | 319.49/675.71 | 17.8724 | 19.4477 |
| BRANCH02_BLINDP9 | PASS | original domain | 1400.161839 | 107.803159 | 320.04/677.34 | 17.8620 | 19.4422 |
| BRANCH02_BLINDPC19 | PASS | original domain | 1399.762839 | 108.097513 | 319.49/675.65 | 17.8723 | 19.4478 |
| BRANCH02_B | PASS | original domain | 1436.456498 | 101.253695 | 305.08/714.73 | 19.3905 | 20.9137 |
| BRANCH02_C19 | FAIL | original domain | 1399.857062 | 108.090021 | 885.97/1955.25 | 26.2841 | 43.2456 |
| BRANCH02_FAIL9 | FAIL | original domain | 1400.243102 | 107.796737 | 559.01/681.05 | 20.9639 | 28.2218 |
| COMPOSE01_B | PASS | original domain | 1436.456498 | 101.253695 | 305.08/714.73 | 19.3905 | 20.9137 |
| COMPOSE01_PAIR01 | PASS | original domain | 1406.093249 | 106.066137 | 296.04/633.96 | 16.7600 | 18.2222 |
| HANDOFF01_BEST | PASS | original domain | 1398.034615 | 107.971017 | 320.15/678.37 | 17.7435 | 19.3341 |
| HANDOFF01_BOTHHALF | PASS | original domain | 1399.794462 | 107.906134 | 309.76/656.28 | 17.5036 | 19.0283 |
| HANDOFF01_BOTHLOW | PASS | original domain | 1401.756380 | 107.779354 | 299.53/635.53 | 17.2949 | 18.7538 |
| HANDOFF01_B | PASS | original domain | 1436.456498 | 101.253695 | 305.08/714.73 | 19.3905 | 20.9137 |
| HANDOFF01_OLOW | PASS | original domain | 1400.392567 | 108.128124 | 306.80/654.35 | 17.3199 | 18.8462 |
| HANDOFF01_RLOW | PASS | original domain | 1399.398428 | 107.622247 | 313.20/660.23 | 17.7192 | 19.2440 |
| OPT01_BEST | PASS | original domain | 1398.034615 | 107.971017 | 320.15/678.37 | 17.7435 | 19.3341 |
| OPT01_BO001 | PASS | original domain | 1401.756380 | 107.779354 | 299.53/635.53 | 17.2949 | 18.7538 |
| OPT01_BO002 | PASS | original domain | 1400.029756 | 106.479327 | 312.20/659.36 | 17.4917 | 19.0220 |
| OPT01_BO003 | PASS | original domain | 1399.006623 | 107.797229 | 314.27/662.17 | 17.7528 | 19.2855 |
| OPT01_BO004 | PASS | original domain | 1403.011541 | 108.154129 | 310.99/661.44 | 17.5168 | 19.0487 |
| OPT01_BO005 | PASS | original domain | 1401.169727 | 106.784869 | 306.90/650.23 | 17.3398 | 18.8435 |
| OPT01_BO006 | PASS | original domain | 1404.653372 | 107.569040 | 297.68/634.84 | 17.0674 | 18.5252 |
| OPT01_BO007 | PASS | original domain | 1400.555838 | 105.644256 | 311.55/659.07 | 17.3534 | 18.8859 |
| OPT01_BO008 | FAIL | original domain | 1398.285886 | 106.365594 | 323.75/690.20 | 17.6416 | 19.2702 |
| OPT01_BO009 | PASS | original domain | 1401.566887 | 107.770618 | 304.74/650.15 | 17.2102 | 18.7233 |
| OPT01_BO010 | PASS | original domain | 1399.959986 | 106.197193 | 312.57/660.71 | 17.4455 | 18.9826 |
| OPT01_BO011 | PASS | original domain | 1399.478007 | 107.888047 | 318.03/671.75 | 17.8275 | 19.3879 |
| OPT01_BO012 | PASS | original domain | 1399.653608 | 108.174672 | 319.64/676.10 | 17.8737 | 19.4508 |
| OPT01_B | PASS | original domain | 1436.456498 | 101.253695 | 305.08/714.73 | 19.3905 | 20.9137 |
| OPT01_PATTERN001 | PASS | original domain | 1401.756380 | 107.779354 | 299.53/635.53 | 17.2949 | 18.7538 |
| OPT01_PATTERN002 | PASS | original domain | 1400.516916 | 107.693800 | 306.35/647.59 | 17.5023 | 18.9943 |
| OPT01_PATTERN003 | PASS | original domain | 1401.173116 | 107.916038 | 302.37/642.82 | 17.2850 | 18.7717 |
| OPT01_PATTERN004 | PASS | original domain | 1404.830459 | 108.029536 | 297.95/635.18 | 17.1428 | 18.5984 |
| OPT01_PATTERN005 | PASS | original domain | 1399.293048 | 107.607655 | 313.37/660.25 | 17.7234 | 19.2492 |
| OPT01_PATTERN006 | PASS | original domain | 1402.464352 | 106.735303 | 298.36/634.59 | 17.0686 | 18.5314 |
| OPT01_PATTERN007 | PASS | original domain | 1401.844551 | 106.692459 | 301.75/640.55 | 17.1705 | 18.6499 |
| OPT01_PATTERN008 | PASS | original domain | 1402.144459 | 106.841212 | 299.85/638.28 | 17.0786 | 18.5549 |
| OPT01_PATTERN009 | PASS | original domain | 1403.996889 | 106.857835 | 297.43/634.35 | 16.9835 | 18.4444 |
| OPT01_PATTERN010 | PASS | original domain | 1400.001021 | 106.563605 | 312.25/659.35 | 17.5025 | 19.0326 |
| OPT01_PATTERN011 | PASS | original domain | 1402.725729 | 106.179593 | 297.82/634.25 | 16.9715 | 18.4351 |
| OPT01_PATTERN012 | PASS | original domain | 1402.334549 | 106.148105 | 299.60/637.25 | 17.0292 | 18.5012 |
| PPOCHECK_BEST | PASS | original domain | 1398.034615 | 107.971017 | 320.15/678.37 | 17.7435 | 19.3341 |
| PPOCHECK_B | PASS | original domain | 1436.456498 | 101.253695 | 305.08/714.73 | 19.3905 | 20.9137 |
| PPOCHECK_FROZEN_MEAN | PASS | original domain | 1399.918272 | 107.492306 | 319.39/676.46 | 17.7838 | 19.3655 |
| PPOCHECK_FROZEN_PLUS_RULE | PASS | original domain | 1401.225670 | 107.091388 | 313.38/660.87 | 17.7330 | 19.2597 |
| STRICT01_ANTREF | FAIL | original domain | 1397.930115 | 108.149856 | 321.88/682.92 | 17.8026 | 19.4086 |
| STRICT01_ANT | PASS | original domain | 1398.007158 | 107.973664 | 320.15/678.36 | 17.7435 | 19.3341 |
| STRICT01_BEST | PASS | original domain | 1398.034615 | 107.971017 | 320.15/678.37 | 17.7435 | 19.3341 |
| STRICT01_B | PASS | original domain | 1436.456498 | 101.253695 | 305.08/714.73 | 19.3905 | 20.9137 |
| STRICT01_REF025 | PASS | original domain | 1397.949604 | 108.076996 | 320.80/680.17 | 17.7690 | 19.3659 |
| STRICT01_REF050 | FAIL | original domain | 1397.957504 | 108.147215 | 321.88/682.93 | 17.8027 | 19.4086 |
| STRICT01_REF100 | FAIL | original domain | 1398.084987 | 108.241982 | 323.28/686.75 | 17.8689 | 19.4872 |


force/moment向量与norm的峰值、RMS、变化率、TV、100ms分箱线性趋势残差以及phase统计分别保留在analysis/native_wrench和analysis/extended。趋势残差只是附加描述量，不替代raw、原motion或原积分。高低采样率的TV和导数不直接混为同口径排名。audit/NATIVE_WRENCH_UPDATE_CADENCE.json核对原step_native逐步post-refresh更新，三条代表轨迹相邻native wrench均真实变化；audit/NATIVE_WRENCH_LOGGING_PHYSICAL_IDENTITY.json验证新增日志前后B/BEST的所有原物理和参考字段精确一致。4kHz记录不等于硬件测量带宽或连续sub-step重建。


最终冻结验证、失败分母与补充反事实见[冻结验证汇总](FROZEN_VALIDATION_SUMMARY.md)、[补充执行反事实](SUPPLEMENTARY_EXECUTION_COUNTERFACTUALS.md)和[力／力矩波动分解](WRENCH_COMPONENT_TRADEOFF.md)。主结果不使用未来资格mask，不改变原积分、原阈值或开发固定预算。


CONFIRMED：同一已记录stream的0.25ms辅助左积分与原5ms JF最大绝对差约0.004803 N·s；四个可比tail菜单的完整合格最优选择保持一致。它只检验采样敏感性，不替代原JF/JM、训练标签或安全评价，也不是连续时间真值；早期5ms组仍无native force结论。见analysis/NATIVE_AUX_INTEGRAL_SAMPLING_AUDIT.json。
