# FULL-3D CR12 Dependency Manifest

Captured 2026-09-23 on branch `codex/stage5-architecture-recovery`, recorded
HEAD `bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`.

## Reproducibility boundary

The delivered runtime depends on untracked/dirty working-tree files. None of
the CR12 XML, vendor assets, full-3D runtime, config, runner, or result files is
present in recorded HEAD. Therefore **a clean checkout of that commit cannot
run this validation**. This is an unresolved publication blocker, not a
simulation failure. The current task forbids staging, committing, or pushing,
so the blocker is preserved rather than hidden.

## Core files and SHA-256

| Path | SHA-256 |
|---|---|
| `models/cr12_v0.xml` | `42cde4bc93e80131e190c27d0e3af04beeaa760b177f6ca01a880e66a124f326` |
| `src/traction_mpc_stage5/cr12_robot.py` | `000e680da128fb21f1372f204d9cdb1974404c5fe50893b6746d386951c9daeb` |
| `src/traction_mpc_stage5/cr12_plant.py` | `23ed3a0756d5066f44345051abc0ec35d1ec5e7f12c5db338863c98c11b835de` |
| `src/traction_mpc_stage5/cr12_validation.py` | `aa9dd37ff8ab280c9c9ab31fdd644fadc2e4d9df0a67b366fd40af79ff5e8028` |
| `src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py` | `857abe0edd90766529514b1298d5edef016a14921e74952fbc59c547cb24ec02` |
| `src/traction_mpc_stage5/full3d_adaptive_integration_v1/time_contract.py` | `ad9e1c912bbe2789de5ccb457d4bc54629235ef97d9690dfeac61a7aeb5ff2f7` |
| `src/traction_mpc_stage5/human_waypoint_feedback_mpc.py` | `6b10ae9c846b1b764b86eefe82d2e0a5296d664d3af21aab9c282761b6bb71de` |
| `src/traction_mpc_stage5/human_waypoint_scheduler.py` | `0bfcd6bc8fcb5bf942563d29b9d721988ae6d5f60e4798f0705ea796d5b4aa70` |
| `src/traction_mpc_stage5/controller_interface.py` | `104e4219432fea8875c790423c790ac110d07d3a0c363cbf3ba657091dbdfb0b` |
| `src/traction_mpc_stage5/architecture_recovery_v2/effective_model.py` | `b183c55082f710bb0a7ace8961eb54ae0cfa29b9c1d8ea3acebecc6af5e0053f` |
| `src/traction_mpc_stage5/architecture_recovery_v2/phase3_human_waypoint.py` | `a4ca989f2b281c245c8964833b795533ef87d76859ae08f9150824f9108e0ad1` |
| `src/traction_mpc_stage5/architecture_recovery_v2/functional_benchmark.py` | `80b9f0bab109e2599f1503ee5ce7b218c663e68e76d5d0fb961af8544d797124` |
| `configs/full3d_adaptive_integration_v1/development_v1_1.json` | `13956fb00b7e283ffaccc52d272b598aad307c0588aba61fb6ecce2060023d95` |
| `configs/full3d_adaptive_integration_v1/phase2_v22_corrected_time_replication_v1_2.json` | `f624c83755b889e84eed053d01019363ead8ea159387f3461035104f206ba3e4` |
| `configs/stage5_controller_nominal_interface_v1.json` | `0b8a36868c6647c2456dcda5eafcdb06d0adb97f634e7aaec4002c0b8ca2196f` |
| `configs/stage5_goal_task_v1.json` | `b7c89182ad190a65060b426533a7575c666c6660f04f37505def294ace088a05` |
| `scripts/run_full3d_adaptive_integration_v1.py` | `a8b45157639bf7cec7dbb3e5a95f56023731dce151b07d6acd3ab0e53c67bcc1` |
| `scripts/render_full3d_evidence_v1.py` | `d5bfd6454434c1934340f147c073014a3f31be8ec203903e573914deb40bcc46` |
| `scripts/architecture_recovery_v2/run_functional_campaign.py` | `23cdae528e9468b517586ab5dbc6bd9d529e12324284c37d13c7ae9b5eb9d1f1` |
| `../stage4_adaptive_control/src/traction_mpc_stage4/measurement.py` | `1c8dd08e7bb94988eba36ad59fca0ad33e1566d1734c108efaee53a4777a70ab` |
| `../stage3_full3d/src/traction_mpc_stage3/spring_damper_interface.py` | `e5119f2b3f39ed37db49b29449d5f66dec20848418225daed19402445fcdee44` |
| `../stage3_full3d/src/traction_mpc_stage3/human.py` | `0f82749aeda1208bcd79ecf336bbb39df88308c51f465596f7a8b2923946aec4` |

All paths in this document are relative to
`stages/stage5_personalized_motion_learning/`.

## Vendor source and mesh assets

| Path | SHA-256 |
|---|---|
| `vendor/rokae_ros2_xmatecr12/xMateCR12.urdf.xacro` | `b7147ecde3951763521064dfe5d7f5a48520a0c9ffb82679a9bcb83a9357548a` |
| `vendor/rokae_ros2_xmatecr12/xMateCR12.srdf` | `59146659293d16051dedaa19754003af86bafe06dc1e2dd514208d3036d6d5bf` |
| `vendor/rokae_ros2_xmatecr12/LICENSE` | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |
| `vendor/rokae_ros2_xmatecr12/README.md` | `7d105c62ebf9aeb62c7f13bd86e4c64587f4483985f1e9dc9fd15ae0334cfede` |
| `vendor/rokae_ros2_xmatecr12/meshes/xMateCR12_base.stl` | `4320e53a37ee9be6fb00d0f7f3d5fd5059b94f740dd43d11990385638f2d7872` |
| `vendor/rokae_ros2_xmatecr12/meshes/xMateCR12_link1.stl` | `7689d7229491b15c3949c7c11eb5fd0d4d060e0ee658a04a026845f05f781391` |
| `vendor/rokae_ros2_xmatecr12/meshes/xMateCR12_link2.stl` | `e8fbd769d653fad162ceff6c3a4b276ca2110f519be4961e08178c5b01058e29` |
| `vendor/rokae_ros2_xmatecr12/meshes/xMateCR12_link3.stl` | `81c6c720c4ecc5a96a80bf2c278c70869a0a5df442ea7b77a41ba41197af00d3` |
| `vendor/rokae_ros2_xmatecr12/meshes/xMateCR12_link4.stl` | `e0249c5667c4c4299554fa7413fb29930b38feadc6454d5e8c26ec3fc5950ec6` |
| `vendor/rokae_ros2_xmatecr12/meshes/xMateCR12_link5.stl` | `36b37d6c8a51aa9c4b148b65124810a455ebc2021ca42973cfa7bdac5754cf54` |
| `vendor/rokae_ros2_xmatecr12/meshes/xMateCR12_link6.stl` | `498b45c51581e6fb6f8fdeb9cd3d72d36f82711252717725231faa33577f85f1` |

## Final artifact hashes

| Path | SHA-256 |
|---|---|
| `results/full3d_adaptive_integration_v1/nominal_timing_aware_attempt_14/summary.json` | `5f77eb35ec4f54053b09859f72a3a45bd7f8d626c39260b0dc690a53b58c84f0` |
| `results/full3d_adaptive_integration_v1/nominal_timing_aware_attempt_14/trace.npz` | `378e3e2c2588217e8fae9d8e6b494d3ec9bf3160ec7f933652a6ddabae61ea1b` |
| `results/full3d_adaptive_integration_v1/nominal_timing_aware_attempt_14/learning_transitions.jsonl` | `29f871007967b39725e850030c07b3fcd601d5e0a9e8ba9a59668ad7fc46ea7d` |
| `results/full3d_adaptive_integration_v1/no_task_actuation_diagnostic_06/summary.json` | `c1bc2ef266614a20d2135ea6434202bbe30b62e0dac2171d2ee6d2c0485a72a2` |
| `results/full3d_adaptive_integration_v1/phase2_v22_corrected_time_replication_v1_2/result.json` | `4bee95dc8bf76bbd8a10f0e9c0bebbb51772c8ec5310c0540e4dbbf17c88383a` |
| `results/full3d_adaptive_integration_v1/large_rom_mechanics_study_v1.json` | `c944cc6b4dcf8a0ded616a1596f643b27c4599e018edfb84abea5f659dba924f` |
| `results/full3d_adaptive_integration_v1/media_v5/nominal_trace_overview.png` | `921baac5a42623c8131e93cfb8136b5b19031ad433335f7d4073df5101cd74db` |
| `results/full3d_adaptive_integration_v1/media_v5/nominal_state_replay.mp4` | `9ca21c08e38bd88b1621cfcba05876f1b92d499d1a01b4f37814e10038fbbfa0` |
| `results/full3d_adaptive_integration_v1/media_v5/no_task_actuation_state_replay.mp4` | `f2bd6436a955a1c2c385d45f5ba35af6c46a3f2a6ac14b9e06cccb67b7ebed0d` |

## Runtime environment

Nominal run: Python from Conda environment `mpc_learn`; NumPy `2.2.6`;
MuJoCo `3.10.0`; physics step `0.00025 s`. The saved `summary.json`,
`config_snapshot.json`, and source/result hashes are the authoritative runtime
record. Hardware SDKs, OnRobot HEX conversion, and physical calibration files
are not dependencies because no hardware was actuated or claimed.
