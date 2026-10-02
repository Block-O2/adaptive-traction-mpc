# Direct RL Expert Search v1

**DIRECT_RL_SAC_V1_BLOCKED** — stopped at the user-defined expanded-action safety gate, before Gym validation or SAC training.

Branch `codex/direct-rl-expert-v1` was created from clean `7bfe141308cacb2d23cf544aa5942e0337bccaed`. Frozen 365 physical/controller/config source files and 170 historical/audit evidence files remained identical at closeout. Original zero-value, coordination and value-learning HEADs match reachable origin branches. The latest best-known v2 branch is local-only; its HEAD and database/evidence hashes are pinned. No merge/force push or history rewrite occurred.

Resource preflight: host RAM 16,890,322,944 bytes; WSL 7.6 GiB total, ~7 GiB available, 2 GiB unused swap; C: ~85 GiB free, WSL ~878 GiB free, Linux process count 77 initially. GPU NVIDIA RTX 4060 Laptop, driver 560.94, 8188 MiB VRAM; WSL GPU query ~7957 MiB free. CPU/RAM/swap/disk/process/GPU records are in RESOURCE_PREFLIGHT.json. One environment maximum was planned; no environment worker was started, and two environments were not attempted.

The primary blocker is the authoritative action/safety representation. At 20 and 50 ms in both conditions/phases, reissuing the same target via the existing q/dq-only quintic creates a ddq discontinuity (0.076–2.070 rad/s² in first-segment probes). Existing rolling suffix rejects it; accepted endpoint suffixes defer effects 0.395–1.575 s. Live activation requires zero initial ddq while C2 requires matching nonzero moving-reference ddq. A naive standard-activation call would fail to compare the old ddq. Removing continuity checks, declaring this immediate direct control, or restricting all actor commands to old endpoints would not satisfy the request. Probe assertions passed; environment A–I gates did not run or pass.

User section 18: “If current safety layer is demonstrably tied to the old action representation and cannot correctly screen the expanded RL action: STOP main training and report the exact incompatibility.” This is the stop applied here. It does not establish that safe direct RL is impossible or that SAC failed to learn.

Secondary preflight issue: scientific Python lacks PyTorch/Gymnasium/SB3; existing capstone environment has CPU-only torch 2.14.0+cpu, despite visible WSL GPU. CUDA package setup remains unresolved. No packages were installed because the earlier safety stop blocks the main campaign. A supported CUDA wheel needs installation and verification in the scientific environment before a resumed training campaign. This is not an unavailable-GPU claim. CPU MuJoCo path is unchanged.

No Gym environment, reward audit, 100k pilot, checkpoint evaluation, second seed, action/path analysis, throughput benchmark or inference/full action timing was completed. Required downstream output files explicitly say NOT_RUN and contain null/empty values. Hyperparameters/action/observation/reward files are proposed designs, not validated/frozen training results. No 1M/2M estimate is invented from historical CEM or arithmetic probes.

## Final questions

1. **Is the new environment physically equivalent enough?** Not established. No Gym environment passed validation. Underlying protected physical/controller/config sources and historical evidence stayed hash-identical.

2. **Does the action interface express more coordination freedom?** Proposed independent continuous 2-D target changes would; no implemented safe interface demonstrates that freedom. Existing endpoint activation blocks immediate periodic commands.

3. **Can SAC reliably complete the full task?** Unknown; zero training/evaluation episodes.

4. **Best VALID SAC J_F?** Unavailable; no trained checkpoint.

5. **Comparison with controller/fixed/CEM?** Only historical frozen reference inventory is available. No SAC comparison or benefit capture.

6. **Different hip/knee coordination path?** Unknown; no learned path.

7. **Gain from coordination or timing?** Unknown; no gain measured. Native historical references may include timing.

8. **Moment outcome?** Historical comparator moment metrics retained; no SAC moment outcome.

9. **How often does safety modify/reject SAC?** Unmeasured. Eight reference splice failures are diagnostic probes, not learned-policy intervention frequency.

10. **Does safety suppress much RL behavior?** Current interface demonstrably cannot immediately realize these periodic reference replacements. Closed-loop suppression fraction is unmeasured; no global safety-layer verdict.

11. **Learning curve still improving?** No learning curve.

12. **More training justified?** Training cannot be judged before environment/safety compatibility. More steps on current interface are not authorized.

13. **Environment/training throughput?** Unmeasured; no valid adapter. Probe throughput is not training throughput.

14. **GPU utilized?** GPU visible (RTX 4060 Laptop, 8188 MiB), no training utilization. Scientific Python has no torch; capstone Python has torch 2.14.0+cpu, CUDA runtime None, availability False. No CPU main training.

15. **CPU bottleneck?** Not measured. Source inspection shows CPU physics, mechanics/clearance certificates and reference control; do not assign dominance without profiling.

16. **1M/2M wall time?** Unavailable because Direct RL steps/s was not measured.

17. **Inference/full action latency?** Unmeasured; no evaluated actor/safe action pipeline.

18. **Next campaign priority?** Environment/safety action-realization redesign and revalidation first, CUDA package repair second, then the originally requested SAC pilot. No TQC/PPO/hardware or multi-day campaign launched.

## Required next work

Version an acceleration-aware reference realization interface carrying current receipt-owned q/dq/ddq through full continuous clearance/mechanics, midsegment activation and prevalidated fallback. Preserve all ROM, velocity/acceleration, clearance, deadline, task endpoint/HOLD/RETURN and physical interaction gates. Validate baseline equivalence and continuous action effects before reward-hacking/rate/throughput/SAC gates. Keep lattice/monotonic-progress preferences separate from physical constraints. This redesign was not silently performed in this workflow.

Official method sources consulted: [SB3 SAC](https://stable-baselines3.readthedocs.io/en/master/modules/sac.html), [Gymnasium Env](https://gymnasium.farama.org/api/env/), [PyTorch CUDA wheels](https://pytorch.org/get-started/previous-versions/). They informed proposed integration/package diagnostics, not a claim of completed training.

Git closeout: new campaign files may be staged individually under the user's stage instruction; commit and push were not explicitly authorized in this chat, and repository AGENTS.md requires separate exact authorization. No commit/push/merge was performed. Training and physical processes are absent. Compact evidence only; no raw training/replay buffer/checkpoint artifacts or destructive cleanup. See RAW_DATA_MANIFEST.json.
