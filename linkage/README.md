# Linkage Research Workspace

This directory contains the preserved professor reference, the independently
implemented human two-link plants, frozen single-contact baselines, and the
current single-arm trajectory/contact-mechanics studies.

The single source of truth for the current project status, accepted evidence,
open gates, and next-stage boundary is:

- [Linkage Project Current State](docs/CURRENT_STATE.md)

The complete document index separates current guidance from frozen and
archived evidence:

- [Linkage Documentation Index](docs/README.md)

## Layout

```text
linkage/
├── docs/                         Current state and experiment reports
├── matlab/
│   ├── audits/                   Tracked reproducibility/audit tools
│   ├── reference/                Preserved-reference policy and local source
│   ├── runners/                  Headless test and experiment entry points
│   ├── src/                      V1, V2, and single-arm MATLAB implementations
│   └── tests/                    MATLAB regression tests
└── results/local/                Ignored local workspaces and generated media
```

The professor source remains byte-preserved and ignored under
`matlab/reference/professor_original/`. Generated MATLAB workspaces, logs,
figures, animations, and CSV files remain ignored under `results/local/`.

No result directory is an implicit current-state authority: use
`docs/CURRENT_STATE.md`, then follow its links to the relevant frozen report
and reproduction command.
