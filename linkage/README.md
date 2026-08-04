# Linkage Research Workspace

This directory contains the preserved professor reference, the active Human
Model V2 and single-arm V2 implementations, frozen baseline reports, and the
current trajectory/contact-mechanics studies. The removed V1 implementation
is recoverable from annotated tag `linkage-pre-v1-code-cleanup`.

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
│   ├── src/                      Active V2 and single-arm implementations
│   └── tests/                    Retained active MATLAB regression tests
└── results/                      Local-artifact policy and ignored outputs
```

The professor source remains byte-preserved and ignored under
`matlab/reference/professor_original/`. Generated MATLAB workspaces, logs,
figures, animations, and CSV files remain ignored under `results/local/`.

No result directory is an implicit current-state authority: use
`docs/CURRENT_STATE.md`, then follow its links to the relevant frozen report
and reproduction command.

## Active tests

Run the retained Human Model V2 and single-arm V2 regression suite headlessly:

```text
matlab -batch "addpath(genpath('linkage/matlab')); run_linkage_tests"
```

The former V1 plant and ideal endpoint-force source, runners, and tests are not
part of the active workspace. Their tracked implementation remains available
at tag `linkage-pre-v1-code-cleanup`; ignored V1 local results are retained.
