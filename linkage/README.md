# Linkage Model Intake

This directory is the next research phase after the frozen single-link
Spring2D archive. It begins from a professor-supplied MATLAB reference model.
The original source remains preserved and ignored; publishing permission is no
longer a blocker for the intake branch and its derived documentation.

The intake now covers preservation, reproducible baseline execution, and an
independent dynamics-consistency audit. Controller implementation has not
started.

## Structure

```text
linkage/
├── docs/                         Intake state, source audit, system draft
├── matlab/
│   ├── reference/                Local original and its tracked preservation note
│   ├── runners/                  Non-invasive baseline wrappers
│   └── src/                      Future derived/clean MATLAB implementations
└── results/local/                Ignored local baseline outputs
```

## Baseline status

The unmodified professor baseline runs successfully in MATLAB R2025b Update 1
through the tracked runner:

```bash
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab \
  -batch "addpath('linkage/matlab/runners'); run_professor_reference_capture"
```

Generated logs, workspaces, diagnostics, and figures remain ignored under
`linkage/results/local/professor_reference_baseline/`.

## Documents

- [Current intake state](docs/CURRENT_STATE.md)
- [MATLAB source audit](docs/MATLAB_CODE_AUDIT.md)
- [Independent dynamics-consistency audit](docs/DYNAMICS_CONSISTENCY_AUDIT.md)
- [Draft system definition](docs/SYSTEM_DEFINITION_DRAFT.md)
- [Reference preservation note](matlab/reference/README.md)
