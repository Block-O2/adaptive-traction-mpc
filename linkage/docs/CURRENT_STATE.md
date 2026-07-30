# Linkage Intake Current State

## Phase status

- The single-link Spring2D phase is closed and tagged
  `single-link-spring2d-v1`.
- The linkage-model intake phase has started under `linkage/` in this
  repository.
- Source received: `singleArmDual.m`.
- The source is preserved locally at
  `linkage/matlab/reference/professor_original/singleArmDual.m`.
- The local source is ignored by Git and is not authorized for publication.

## Current task

Understand the professor's reference model, reconstruct its equations and
assumptions, and establish whether its original baseline can be reproduced
without changing the source.

No controller modification, equation correction, MATLAB-to-Python conversion,
adaptive identification, MPC work, or Spring2D experiment is authorized in
this intake.

## Baseline status

The intake machine returned `matlab not found`, and no MATLAB application was
found under `/Applications`. MATLAB was not installed automatically. The
reference baseline therefore remains unexecuted; this is an environment
blocker, not a classification of the model.

No MATLAB-to-Python conversion decision has been made. The possible
MATLAB-first, hybrid, and Python-port routes remain open pending source review,
professor clarification, and a reproducible MATLAB baseline.

## Immediate evidence

- Preservation SHA-256:
  `b8c95ab1df3507efd610a3a72057e31a33724626d37341bd5d5a4abaa833c19f`
- Source audit: [MATLAB_CODE_AUDIT.md](MATLAB_CODE_AUDIT.md)
- Draft equations:
  [SYSTEM_DEFINITION_DRAFT.md](SYSTEM_DEFINITION_DRAFT.md)
