# Independent formal case-bundle audit — V1

Date: 2026-09-23. Scope: read-only generation-side review before any
controller outcome. Audited
`results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1`.
This audit is an execution-release check, not a qualification result.

**Disposition: PASS for formal paired execution.**

- The bundle seed equals the independent `SEED_MANIFEST.json` uint64 root,
  which remains bound to `FREEZE_MANIFEST.json` SHA-256
  `8545edac3f6d2febbac1c129fc86021a3547b96c5d62dbeae41d23d84044fa9c`.
  The seed-manifest SHA-256 is
  `e6352b342f63ac20582b631597ec37fbe5bc0e05ee840f6cd359ba8da44a3b9c`.
- The frozen dependency manifest still has zero mismatched file hashes;
  branch and HEAD are unchanged. The exact 24 case keys are unique, match
  their JSON paths, and cover every one of 4 task families × 3 ROM cells
  with exactly 2 replicates.
- There are 34 generation proposals: 24 accepted and 10 rejected by the
  preregistered, arm-independent static mechanics screen. Every accepted
  case equals the corresponding accepted proposal. Proposal indices respect
  the 30-per-cell cap; no cell was exhausted, omitted, or replaced.
- I independently called the frozen `generate_cases(root_seed)` and compared
  both complete accepted-case records and all proposal/screen records to the
  saved bundle: exact equality. The saved canonical SHA-256 values also
  match: cases
  `ea0479b23cbba1648c76fd09f03d74396debac81aa22620341a1a580f1b3496c`,
  proposal ledger
  `a1900e29ac85d17f811edc4c4201e5d1529cf6d633b4af12c338a72d2b2620f5`.
  Byte SHA-256: `generation_summary.json`
  `0eded0925bd9e23ac9b506c55cb2dc5dd5f21b9e769767db9db8634a6476899d`;
  `proposals.json`
  `0c97c9072b401c80360d9a35935e4215571caef86d48b179752cc1b8ae956bfb`.
- `mechanical_screen` uses hidden geometry only before outcome to test static
  true shank/bed clearance, initial shank contact, and start/goal CR12 IK.
  It is not a dynamic safety guarantee. Source inspection confirms the
  physical hidden Human/geometry values are used to construct the MuJoCo
  plant/initial condition and are not introduced into the deployable
  controller inputs; task start/goal are registered task data. Post-outcome
  truth-firewall and safety claims remain subject to the independent result
  audit.

No formal controller rollout or outcome was executed or inspected here. The
pre-freeze negative development predictor (nominal dq RMSE 7.903 deg/s versus
unchanged gate 5 of 5 deg/s) remains in force; this generation-side PASS does
not imply that any formal promotion gate will pass.
