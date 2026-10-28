# 最终 Campaign 资格

**FINAL_CAMPAIGN_READY=NOT_READY；不得自动启动。**

- DEVELOPMENT_TRAINING_VALID：PASS；Observed isolated development attempts only; inherited + affected tests。
- PPO_STABILITY_IMPROVED：SUPPORTED_NOMINAL_DEVELOPMENT；Two selected successful050 parents retained mean completion at the explicitly tested nominal endpoints; longer continuation, stochastic robustness and independent initial-state qualification remain separate。
- REWARD_SEARCH_COMPLETED：PASS；Bounded development search; success of a reward is a separate question。
- RUNTIME_TASK_SUCCESS：PASS；Only explicitly listed frozen checkpoints and nominal action streams。
- FORCE_IMPROVEMENT：SUPPORTED_NOMINAL_MEAN_ONLY；Listed equal-duration COMPLETE nominal mean tasks versus each selected parent050; JM tradeoffs remain, no original B/H150 live matched or generalization qualification。
- MOTION_QUALIFIED：OBSERVED_EPISODE_AUDITS_PASS；No independent generalization, full matched or all-action qualification; jerk diagnostic only。
- G4_STRICT_PASS：FAIL；Historical natural extreme paths and complete strict safety matrix remain unclosed。
- NEW_LIVE_MATCHED_READY：NOT_READY；New PPO lacks original same-parent-prefix portable fork/B/H150 live matched chain。
- STAGE2_READY：NOT_READY；G4/live matched/independent legal initial-state and retained stability gates not closed。
- FINAL_CAMPAIGN_READY：NOT_READY；Final large-scale Campaign not authorized or started。

开发nominal成功与正式资格分离；历史离线B/H150复现PASS不等于新live matched链就绪。
