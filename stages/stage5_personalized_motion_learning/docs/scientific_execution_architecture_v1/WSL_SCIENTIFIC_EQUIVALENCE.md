# Y9000P / WSL Scientific Mode cross-host equivalence

Terminal status: **SCIENTIFIC_CROSS_HOST_EQUIVALENCE_FAIL**.

## Source and environment

- Mac source branch: `codex/scientific-simulation-v1`.
- Fetched remote HEAD and validation HEAD: `cc41ccf0f1d150ef710855ee850bad7a12d6d4e2`.
- Frozen implementation checkpoint: `8da559fd579e32e53516f909527a25c3de22fc98`.
- Production fingerprint: `0b3c66bcf853255f70b59f8196ccfe5ea554c18fe3690be327c831fc9f52e358` (618/618 files matched).
- WSL: Ubuntu 24.04.3 LTS, WSL 2.6.3.0, kernel 6.6.87.2-microsoft-standard-WSL2, x86_64.
- CPU/RAM visible to WSL: Intel Core i9-14900HX, 32 logical CPUs / 16 cores, 8,176,910,336 bytes RAM.
- Python 3.10.21; MuJoCo 3.10.0; NumPy 2.2.6; SciPy 1.15.3. Mac Python was 3.10.20; scientific package versions match.
- Every test/run used OMP/OPENBLAS/MKL thread count 1. No GPU scientific path was used.

## Gates

- Production/config/XML/mesh/import gate: PASS.
- Focused scorer-v2 and Scientific Mode deterministic gate: 39/39 PASS.
- Scientific sanity (`representative_120_sync_v1`): COMPLETE; mode, physical, scientific and raw scorer-v2 PASS; source/receipt/activation provenance present; worker-wait simulation freeze covered by deterministic tests.
- The first test command used a relative PYTHONPATH after changing directories and failed collection. It was corrected to an absolute repo-relative PYTHONPATH before any scientific case; production was untouched.

## Frozen cases

| Case | WSL mode result | Mac-summary comparison | Full scientific output | Wall s | Max wall age ms |
|---|---|---|---|---:|---:|
| low-ROM ordinary | COMPLETE / PASS / PASS | MISMATCH | MISMATCH | 39.505 | 58.366 |
| high-ROM hip | COMPLETE / PASS / PASS | WITHIN_PREDECLARED_TOLERANCE | INCONCLUSIVE_RAW_MAC_ARRAYS_UNAVAILABLE | 67.365 | 57.325 |
| 120/120 synchronous | COMPLETE / PASS / PASS | WITHIN_PREDECLARED_TOLERANCE | INCONCLUSIVE_RAW_MAC_ARRAYS_UNAVAILABLE | 68.753 | 73.377 |
| 120/120 variable-start | COMPLETE / PASS / PASS | WITHIN_PREDECLARED_TOLERANCE | INCONCLUSIVE_RAW_MAC_ARRAYS_UNAVAILABLE | 69.436 | 75.746 |

All four registered cases ran exactly once in `SCIENTIFIC_SIMULATION` with 0 ms injected host delay. All WSL runs were COMPLETE and passed physical, scientific-validity and scorer-v2 gates. Wall time is characterization only.

## Comparison finding

Exact trace-package equality failed for all four cases. For the three high-ROM cases, the registered summary metrics are within the preregistered `atol=1e-9, rtol=1e-9`, but the Mac raw arrays are not present on WSL, so Human/CR12 q/dq, reference, waypoint/phase sequence and native-state arrays cannot be checked value-by-value. They are therefore not promoted to full `WITHIN_PREDECLARED_TOLERANCE`.

The low-ROM ordinary case is a definite `MISMATCH`: goal dwell differs by about 0.01 s, peak force by 0.140647774 N, peak moment by 0.009414975 Nm and minimum session clearance by 0.0000653047 m. Those are far beyond the frozen tolerance. Its config SHA, request count, COMPLETE/RETURN states and scorer-v2 PASS status still match; the unfavorable numerical result is preserved.

Thus q/dq host equivalence is **not established**, force/moment/clearance host equivalence **fails on low-ROM**, while scorer-v2 physical semantics remain PASS on both hosts' registered summaries.

## Decision and boundaries

Y9000P WSL is **not recommended yet** as the bulk scientific simulation/dataset host under this failed equivalence gate. No optional 500 ms delay run, 3-rep, 30-repeat, value learning or RL was run. The next baseline is not authorized until the low-ROM mismatch is resolved as evidence and the matching Mac raw directories are made available for the frozen array-level comparison.

This result does not establish realtime qualification, hardware safety or clinical safety. Historical `RSS_RUNTIME_QUALIFICATION_NOT_MET` and `RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS` remain.

Account-wide quota was 37% used at task start and 37% at the final check; no extra case or diagnostic campaign was added.
