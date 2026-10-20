# 多方向研究决策日志

T0：2026-10-18 15:55:26 +08:00。硬截止21:55:26；21:10:26前结束物理阶段，60 START上限，全部串行。预留18 START用于对照、重复和真正未见prefix验证；不要求耗尽预算。

## D0 — 建立证据全貌
先审查A终末响应、B状态可靠性、C真实运动平顺性、D力矩及跟踪代价、E执行与学习接口。以原native/receipt/metrics作只读分析，不重跑历史来替代数据阅读。
最新ER110_R4_120是失败研究候选，不能因降力升级。先量化真实终末overshoot，独立于excursion差。
所有新干预保留父候选参数；新名称/manifest/原证书/完整资格分别记录。A最多两个有机制依据的候选，随后停止或切换；不进行微小Waypoint盲搜。
冻结W2为有条件未见验证候选；需复核历史START。无开发合格方案则不消费验证。
正式B、历史代码/证据、plant、安全/因果链均只读；仅新独立包可写。单agent执行，最后使用分离计算复核，不声称独立人员审计。

## D1 — 五方向历史审计完成
量化A真实下冲，B分母/共同历史问题，C微小shape低收益，D力矩代价与E执行缺口。优先A有界R3膝通过速度干预；B/C/D/E继续只读深入，不强行各跑physics。W2已复核无历史START，保留为条件验证。

## D2 — Track B额外受控背景诊断
在A结果前登记R0/Bmap固定B/T/D/ER完整同父配对（5 START）。目的检验W1开发的Early RETURN时间规则是否在已暴露R0仍具相同运动效应。所有参数不变，不把R0当未见状态，不按结果重调。这一独立方向在A失败时仍继续。

## D3 — Track A开发选择冻结
{
  "status": "NO_ELIGIBLE_NEW_CANDIDATE",
  "frozen_unix": 1792311643.8691854,
  "primary": null,
  "development_id": null,
  "execution_manifest_sha256": "3c3e57cf41f180382ced66df82e24d65cacba8eba5da23f0da2787bee03af91c",
  "selection_rule_sha256": "5f74afd2f15ba3719684056f32d8d48dfed49691f08ea9e212702341dce929ab",
  "development_results_sha256": "3237d61f6dc1105c6c72d27476ddd113b9b26a1a847492eaa26af2bc4828a449",
  "development_outcomes": [
    {
      "id": "Adev_AV090",
      "eligible": false,
      "qualified": false,
      "failed": [
        "excursion"
      ],
      "overshoot_change_vs_ER_deg": -0.003153621970605869
    },
    {
      "id": "Adev_AV080",
      "eligible": false,
      "qualified": false,
      "failed": [
        "excursion"
      ],
      "overshoot_change_vs_ER_deg": -0.006344743029165656
    }
  ],
  "validation_used_for_selection": false
}

## D4 — 跨Track结论与停止决策
A两次缩放真实作用小、未过excursion，停止继续缩速；B完成已暴露R0固定ER对照；C不重开低收益Waypoint，D保留力矩/跟踪代价，E交付合同/schema不重构。无新开发合格候选，W2和重复未触发。下一步只建议新的髋终末时序受控协议，本包不执行。
