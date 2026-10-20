# Expert Strength Challenge & Multi-Step Value Adequacy Audit v1

STATUS: COMPLETE; STOP: DECLARED_CHALLENGES_COMPLETE

E CURRENT: B = 1438.613498467; frozen E_SEARCH_v1 = 1360.602793031 N·s (CURRENT_BEST_K2_DIFF, unchanged).

SAME-SPACE CHALLENGE: 3 independent restarts; best J_F = 1356.7907977308016; improvement = 0.28016959248424866%. Restart bests: [1356.7907977308016, 1391.661809890699, 1356.8426086881657]; spread fraction = 0.0256290905314153.

RICH DIFFERENTIAL: K=3 run = True; best J_F = 1348.371552200081; improvement vs frozen E = 0.8989574983919634%; vs best K2 = 0.6205264322843027%. Material threshold = 0.5%, engineering screening only.

COMMON-MODE: COMMON_MODE_DIAGNOSTIC_NOT_RUN. native planner exclusively preserves nominal common target; adding common authority requires new planner/serialization/runtime compatibility and certification, estimated >40 min; do not change B law. Whether B m(t) is restrictive remains untested.

E STRENGTH: UPGRADE_REQUIRED. Best-known high-budget expert within the declared tested scope; no mathematical optimality claim.

BEST-KNOWN EXPERT: RICH_DIFF_K3, J_F = 1348.371552200; F peak = 109.8508500027553; M integral / peak = 124.17075763592105 / 15.115817354553595; clearance = 0.011795173624249155; timing = {'HOLD': 1.0200000000048703, 'OUTBOUND': 9.005000000000718, 'RETURN': 9.005000000042997}. Confirmation = True.

MULTI-STEP VALUE AUDIT: 4 completed snapshot groups; verdict = MIXED; sign/ranking flips = 1. Prefix expert is K2_DIFF with J_F = 1356.7907977308016; these tests do not establish K3 continuation adequacy. Prefix groups and full costs are in VALUE_CONTINUATION_VERDICT.json. All prefix samples are DESIGN_DIAGNOSTIC_ONLY, excluded from future target-Human few-shot counts.

| Snapshot | L1 benefit | L2 benefit | L3 benefit | Full benefit | Sign / ranking flip |
|---|---:|---:|---:|---:|---|
| OUTBOUND_1 | 9.247482 | 8.659656 | 3.480216 | 58.450431 | False / False |
| OUTBOUND_3 | -5.179440 | -7.564072 | 1.074288 | 49.790775 | True / False |
| RETURN_0 | 8.638360 | 25.052396 | 48.534964 | 57.354847 | False / False |
| RETURN_2 | 23.482569 | 32.302451 | 32.302451 | 32.302451 | False / False |

V protocol implication: permanently fixed one-step Q^B is inadequate for the detected states. Future V must use a multi-step planned chunk, improved continuation policy, or policy iteration/data aggregation. The minimum tested clear improving prefix per snapshot is recorded in VALUE_CONTINUATION_VERDICT.json.

K3 interpretation: K=2 cannot yet be treated as the final V action contract.

INVALID / UNMATCHED: [{"name": "LHS_broad_g0_c2", "complete": false, "J_F": 1304.0323517364789, "status": "ABORTED", "timing": {"HOLD": 1.0200000000048703, "OUTBOUND": 9.005000000000718, "RETURN": 6.675000000031872}}, {"name": "LHS_broad_g3_c3", "complete": true, "J_F": 1345.739205912589, "status": "COMPLETE", "timing": {"HOLD": 1.0200000000048703, "OUTBOUND": 9.20000000000165, "RETURN": 9.005000000042997}}]

SECONDARY TRADE-OFF: M integral changes 23.655% vs frozen B and 1.209% vs frozen E. J_F remains the sole primary ranking metric. Full tracking and existing safety evaluation are preserved in each RESULT.

IMPORTANT NEGATIVE RESULTS:

- same-space restart bests remain initialization-sensitive; no same-space material improvement
- one ABORTED search candidate and one unmatched 9.200s OUTBOUND candidate are excluded and retained
- common-mode diagnostic not run; instantaneous common-mode restrictivity remains untested
- best expert M integral rises 23.655% vs B; K2 prefix diagnostics do not establish K3 continuation adequacy

ACCOUNTING: 106 NEW complete physical tasks (search, confirmations, prefix branches and parent counted); 108 attempts including one aborted physical search and one failed pre-physics planner startup; elapsed through closeout 9920.3s / 14400s; old rollouts excluded. Failed attempts retained. One sequential physics owner, fresh process per cold task. No V/SAC training.

INTEGRITY: 0 protected changes; HEAD unchanged = True; staged diff unchanged = True; branch = codex/expert-strength-value-adequacy-v1. No staging, commit or push. Existing dirty state recorded in GIT_BEFORE.json. New research adapter, search/branch/logging harness and their diagnostic outputs only; no B/Human/physics/safety/timing/J_F edits.

PROVENANCE: PLAN_FROZEN.json, ENVIRONMENT.json, per-candidate REQUEST / RESULT / DECISIONS and worker logs; native trace, summary and reference npz under /home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/results/expert_strength_value_adequacy_v1. Research authority: the supplied user work package. Full fork manifest includes native integration, mutable model, lifecycle, requests, RNG, planner, observer, references, cost prefix and audit action state; parent waits for child and equality is checked before branching and after return. Source selection uses actually activated expert graphs, rejected source graphs mapped explicitly to B. DATA_CONTAMINATION_MANIFEST.json covers every prefix sample and its raw trace/snapshot. The failed spawn/import startup and provisional closeout are preserved; the operational retry uses a unique module name and the original deadline.

CAUSAL LIMIT: The K3 result establishes a better expert in that declared search scope. It does not independently establish that K2 is mathematically unable to represent the executed route: the frozen native planner samples each submitted graph at its selected nominal waypoint. Search coordinates and initialization can also affect the result. The preregistered material-improvement decision still requires expert upgrade and review of the final V action contract.

NEXT: 先在升级后的 action authority 下验证覆盖已发现协同依赖的 multi-step planned-prefix 标签协议，再冻结 V continuation。

REPORT PATH: /mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/expert_strength_value_adequacy_v1/output/EXPERT_STRENGTH_VALUE_ADEQUACY_V1_REPORT.md
