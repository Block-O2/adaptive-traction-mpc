# Targeted pre-diagnostic source/dependency snapshot

Captured on 2026-09-23 before DGN instrumentation. Branch
`codex/stage5-architecture-recovery`; HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. The source is dirty and
newer than HEAD; these are hashes of the *actual local files* that produced
the failed V1 qualification. The complete 309-path source/config/asset/native
snapshot remains the untouched sibling `fresh_qualification_v1/FREEZE_MANIFEST.json`
(SHA-256 `8545edac3f6d2febbac1c129fc86021a3547b96c5d62dbeae41d23d84044fa9c`).

| Repository-relative dependency | SHA-256 |
|---|---|
| `src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py` | `777ec6efa6762b84ba53995fdbc553ef6bac22ddab4e543436f53643420c4e2b` |
| `src/traction_mpc_stage5/cr12_plant.py` | `f983aba07057a5178cb325fb839484b28c0be685e750b029f2c62d85c8f695de` |
| `src/traction_mpc_stage5/fresh_qualification_v1/scenario.py` | `08b3b7a583438a2d6f8c38346bab1302032b79c8cbdc5c7291a63742f796eaca` |
| `src/traction_mpc_stage5/fresh_qualification_v1/domain.py` | `037fb6fa75e178c2f6c1751050fa9454a372f1ea53d454888e92b6d2b06d6197` |
| `src/traction_mpc_stage5/fresh_qualification_v1/physics_monitor.py` | `6b30a43b274497c239b17797f73fe48c097dfbb04a0c40672e4fd965c77f12df` |
| `src/traction_mpc_stage5/architecture_recovery_v2/effective_model.py` | `512b50ec30b901788c26dfeda7377a25b0ac8176d2cfaf6cf7b172e81505427f` |
| `src/traction_mpc_stage5/architecture_recovery_v2/phase3_human_waypoint.py` | `ec952d8a6559938fc05aef1752feea4dc97c03ba90ef5b2b3eef7a2a59927a12` |
| `src/traction_mpc_stage5/task.py` | `d5ee754402a19918885bdd65cfdca945eb2b35fc4bb7176ba5f9d2e630b26bef` |
| `src/traction_mpc_stage5/human_waypoint_scheduler.py` | `5e9e28c791efe48a2d64af534bb86ccd129029cfef0ef76b1e4489f9e9c895a4` |
| `src/traction_mpc_stage5/human_waypoint_feedback_mpc.py` | `6b10ae9c846b1b764b86eefe82d2e0a5296d664d3af21aab9c282761b6bb71de` |
| `src/traction_mpc_stage5/human_waypoint_shadow.py` | `1e919dab19505893dc0901fb8fdf056a3f661dc6febe524f08deb35a1665659f` |
| `configs/stage5_goal_task_v1.json` | `b7c89182ad190a65060b426533a7575c666c6660f04f37505def294ace088a05` |

The table paths are relative to `stages/stage5_personalized_motion_learning/`.
No production file is planned for modification during DGN; separate diagnostic
code and output will be versioned. Any exception must be called out explicitly.
