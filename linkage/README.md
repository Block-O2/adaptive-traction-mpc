# Linkage Model Intake

This directory is the next research phase after the frozen single-link
Spring2D archive. It begins from a professor-supplied MATLAB reference model.
The original source remains private/local until publishing permission is
confirmed.

Current scope is preservation, code audit, and baseline reproduction. No
Python port, adaptive identifier, MPC design, or final controller architecture
has been selected.

## Structure

```text
linkage/
├── docs/                         Intake state, source audit, system draft
├── matlab/
│   ├── reference/                Local original and its tracked preservation note
│   ├── runners/                  Future non-invasive baseline wrappers
│   └── src/                      Future derived/clean MATLAB implementations
└── results/local/                Ignored local baseline outputs
```

## Baseline status

MATLAB was not installed or callable on the intake machine, so no baseline was
executed and no runner is claimed to be validated. Once MATLAB is available,
the unmodified source is expected to be assessed with a command of this form:

```bash
matlab -batch "run('linkage/matlab/reference/professor_original/singleArmDual.m')"
```

This command is provisional, not yet verified. The source creates interactive
figures and an animation, so headless compatibility remains unresolved.

## Documents

- [Current intake state](docs/CURRENT_STATE.md)
- [MATLAB source audit](docs/MATLAB_CODE_AUDIT.md)
- [Draft system definition](docs/SYSTEM_DEFINITION_DRAFT.md)
- [Reference preservation note](matlab/reference/README.md)
