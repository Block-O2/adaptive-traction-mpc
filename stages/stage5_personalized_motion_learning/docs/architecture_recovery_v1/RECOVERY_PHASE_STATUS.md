# Architecture Recovery V1 Phase Status

Terminal status: `BLOCKED_IDENTIFIABILITY`

## Startup checkpoint

- Campaign start: 2026-09-22, Asia/Shanghai.
- Active instruction sources: repository `AGENTS.md`; user Master Contract in
  `/Users/hankli/.codex/attachments/8dc13592-18f8-49eb-b5f3-616f9c16740c/已粘贴的文本.txt`;
  system/developer safety and workspace instructions.
- Starting branch: `codex/stage5-cr12-sim`.
- Starting HEAD: `4caea258ec1450f082bb7cb8097cc1441bdf589f`.
- Campaign branch: `codex/stage5-architecture-recovery`.
- Starting worktree: dirty, with pre-existing modified Stage 4/5 files and a
  large set of pre-existing untracked Stage 4/5 artifacts. All are protected;
  this campaign will only add files under its namespace unless an existing file
  is explicitly required and separately audited.
- Nothing was reset, stashed, staged, committed, pushed, or deleted.
- Formal simulation/offline experiments: authorized.
- Real hardware/human experiments: not authorized.

## Immutable contract

- File: `ORIGINAL_SYSTEM_CONTRACT.md`
- SHA-256: `d6a6bcffd6bc05e84016c9a903f8eefa9d41b6a2e42320030b0230015e096e05`
- After the hash is filled, the contract file must not be edited.

## Current phase

- Phase 0: PASS after independent audit and one repair cycle.
- Phase 1: stopped at identifiability gate before estimator implementation or
  held-out evaluation.
- Independent Auditor: approved Phase-0 audit completeness, rejected the current
  architecture, and confirmed `BLOCKED_IDENTIFIABILITY`.
- Phase 2: not started.
- Phase 3 entry: not reached.

## Scientific change ledger

- Scientific variables changed: none.
- Controller/estimator parameters changed: none.
- Configurations changed: none.
- Assumptions changed: none.
- Formal held-out data inspected: none.
- Analytical audit added: `identifiability_audit_v1`; no controller inputs or
  scientific parameters were changed.

## Terminal evidence

- `L2/f` observation rank: 1.
- Second singular value: `4.375321456094446e-17`.
- Equivalent-pair cuff pose/J/generalized-effect residuals: exactly zero.
- Control-critical ankle discrepancy: `59.24 mm`.
- Absolute-q1 17-degree gauge residuals: approximately `1.3e-16` to `2.3e-16`.
- Audit spec SHA-256:
  `2e12a112930a3c9600533b36ae948992a125d2ce0c486a30df26bcb058f9f489`.
- Result SHA-256:
  `7f5fa59d6886d84f2d4f3c67f5bf880c51ce4531b37d532e92a8835cc4516a39`.
- Final report: `ARCHITECTURE_RECOVERY_FINAL.md`.
