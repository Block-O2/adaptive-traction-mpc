# Presentation Assets

[Home](../README.md) · [Demo notes](demos/README.md) · [Architecture](../docs/architecture.md)

Existing simulation media stays with its stage. This index avoids copying
large videos, raw traces or frozen evidence into a second assets tree.

| Asset | Source and role |
| --- | --- |
| [Control architecture](figures/control-architecture.svg) | New vector documentation diagram; shared control direction and explicitly optional later research |
| [Stage-4 MuJoCo GIF](../stages/stage4_adaptive_control/results/media/readme/hero_fixed_vs_adaptive.gif) | Existing 800×450, 80-frame visualization replay; reused by the root README |
| [Visualization source manifest](../stages/stage4_adaptive_control/results/controller_validation/visualization_sources/visualization_source_manifest.json) | Frozen source traces, controller identities and panel-selection provenance |
| [Professor-video manifest](../stages/stage4_adaptive_control/results/summaries/professor_video_manifest.json) | Existing renderer, camera, source hashes and replay-only semantics; full MP4 files remain outside this branch |
| [Stage-2 nominal GIF](../stages/stage2_linkage/results/final/nominal_full_cycle.gif) | Earlier planar linkage demonstration; not Stage-5 footage |
| [Later research figures](https://github.com/Block-O2/adaptive-traction-mpc/tree/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/figures) | Archived figures/CSVs derived from selected saved arrays; comparison conditions remain in the archive |

## Provenance and Reuse

The Stage-4 GIF is reused without modification. SHA-256:

```text
d8496ca2c5c00818afc7ee828cef1c1fbd688237c622737fb692b42d9fdb0bd8
```

Its renderer is documented as saved `qpos` → `mj_forward` → MuJoCo rendering,
with no new controller rollout. The GIF illustrates the simulation scene;
it does not qualify realtime execution, hardware performance or clinical use.

The robot mesh/model originates from the vendored MuJoCo Menagerie UR10e
snapshot. Preserve its [license](../stages/stage3_full3d/vendor/mujoco_menagerie/universal_robots_ur10e/LICENSE)
and [provenance](../stages/stage3_full3d/vendor/PROVENANCE.md).
A project-wide license remains an owner decision. The diagram does not
introduce externally sourced artwork or additional model assets.
