# Experiment Navigation

[Home](../../README.md) · [Research notes](../research-notes/README.md)

This is a navigation index. Results, original tests, failure records and hash
manifests remain at their original paths. Follow the source study's task,
conditions and qualification scope before comparing any numbers.

## This Branch: Stage 1–4

| Material | Location |
| --- | --- |
| Single-link retained results | [Stage-1 final results](../../stages/stage1/results/final/) |
| Planar linkage validation | [Stage-2 summary](../../stages/stage2_linkage/docs/MUJOCO_STAGE2_VALIDATION_SUMMARY.md) |
| Full-3D plant and engineering validation entry points | [Stage-3 guide](../../stages/stage3_full3d/README.md) |
| Adaptive-control simulation studies | [Stage-4 evidence map](../../stages/stage4_adaptive_control/docs/research/STAGE4_EVIDENCE_MAP.md) |
| Baseline/generalization reporting | [Stage-4 report evidence map](../../stages/stage4_adaptive_control/docs/research/STAGE4_REPORT_VALIDATION_EVIDENCE_MAP.md) |
| Corrected High-ROM engineering checkpoint | [Compact package](../../stages/stage4_adaptive_control/results/summaries/phase3a_corrected_high_rom/README.md) |
| Failed preregistered PD gain-selection record | [Negative evidence](../../stages/stage4_adaptive_control/results/negative_evidence/pd_gain_selection_v1/) |

## Later Stage-5 and Research Packages

These links use the reviewed archive snapshot, not paths available on `main`:

| Material | Location |
| --- | --- |
| Stage-5 experiment/specification history | [Stage-5 docs](https://github.com/Block-O2/adaptive-traction-mpc/tree/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/stages/stage5_personalized_motion_learning/docs) |
| Isolated coordination, timing and learning studies | [Side studies](https://github.com/Block-O2/adaptive-traction-mpc/tree/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/research/side_studies) |
| Selected later research packages | [Versioned packages](https://github.com/Block-O2/adaptive-traction-mpc/tree/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/research_archive/packages) |
| Retained results and comparison conditions | [Experimental evidence](https://github.com/Block-O2/adaptive-traction-mpc/blob/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/EXPERIMENTAL_EVIDENCE.md) |
| File identities, selection and missing historical assets | [Archive manifest](https://github.com/Block-O2/adaptive-traction-mpc/blob/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/ARCHIVE_MANIFEST.md) |
| Environment and reproduction commands | [Reproduction guide](https://github.com/Block-O2/adaptive-traction-mpc/blob/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/REPRODUCTION_GUIDE.md) |
| Previously executed checks and remaining limitations | [Verification record](https://github.com/Block-O2/adaptive-traction-mpc/blob/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/ARCHIVE_VERIFICATION.md) |

Scientific simulation, offline trace analysis, interface smoke checks and
host-clock qualification answer different questions. A retained code package
does not imply that all original raw data, optimizer states or model weights
are available. Different parent states, task durations and motion contracts
must not be combined into a single performance ranking.

Start with the lightweight checks in [Getting Started](../../README.md#getting-started).
Use a new output directory for any separately authorized run and preserve the
original experiment contract, scorer and negative results. Do not resume a
stopped campaign merely because its launcher is archived.
