# Safe Action-Space & Horizon Exploration v1 contract

Frozen before action perturbation on `codex/safe-action-horizon-exploration-v1` from baseline `1f6308b820b64fc2cc7d8a01baa42e433835e68e`.

This is exploratory counterfactual simulation, not RL training or a claim of statistical significance. Each branch starts from a verified V3 checkpoint and leaves that checkpoint untouched. Rep2, 6, 16 and 26 cover EARLY, POST-EARLY, MID and LATE adaptation. Each state first requires an unmodified matched replay.

The primary outcome is `J_F_task = integral ||F_cuff_measured|| dt` over OUTBOUND, HOLD and RETURN. `Benefit = matched baseline J_F_task - exploration J_F_task`; positive is lower interaction cost. J_F_session, force and moment peaks/integrals, clearance, completion time, smoothness, physical and scientific validity remain separate. No weighted reward is introduced.

The existing ROM, velocity/acceleration, force/moment, clearance, controller, constrained scheduler and Scientific Simulation gates are hard. Rejected or invalid action samples stay in the record. The proposed waypoint deviations span slower/faster, hip/knee lead and strong coordination differences at locally scaled amplitudes. H1 affects one OUTBOUND decision; H2 three; H3 all OUTBOUND; H4 OUTBOUND and RETURN. All accepted segments pass the existing quintic/reference continuity checks.

Target 80 coarse valid rollouts, at least 60 total valid and ideally 100–160 with refinement and cross-state validation. Preserve progress every 25 rollouts. At most five infrastructure repair cycles. Stop only for the frozen systemic conditions or after 8 hours, finishing the current run. Baseline late SD 0.642500 N s and range 1.914894 N s are descriptive effect-size references.

All four states are exploratory; reuse for refinement means cross-state replication is not an independent held-out study. Simulation truth is evaluation-only and cannot enter action selection. No learner architecture or planner objective is selected in this campaign.
