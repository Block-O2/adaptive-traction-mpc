# Phase-Banked Residual Development Result V1

Status: **REJECTED**

Result SHA-256:
`95fcb8d176f1d9f1de8ad11adf331a99063e4c9945b122c97afa02e49d013c32`.
The exact 24-case, four-arm matrix completed with no source/config or Git-status
drift.

| arm | completion | median | p95 | hold-entry 0.5 s | return-entry 0.5 s |
|---|---:|---:|---:|---:|---:|
| V2.1 constant | 23/24 | 0.4716 deg | 1.0244 deg | 0.0727 deg | 0.1257 deg |
| phase-bank | 23/24 | 0.4840 deg | 1.3172 deg | 0.1641 deg | 0.1925 deg |
| commissioning-only | 21/24 | 0.6224 deg | 4.2963 deg | 0.5304 deg | 0.5399 deg |
| oracle | 24/24 | 0.3915 deg | 0.6911 deg | 0.0023 deg | 0.0644 deg |

Although phase-bank median was 22.23% below commissioning-only, it was 2.64%
worse than V2.1 and its p95 was 28.58% worse. Both preregistered discriminator
conditions failed. The entry-window diagnostics also contradict the proposed
mechanism: discarding the task-wide bias at phase changes increased error.

One high-ROM case produced the same hidden ROM violation in V2.1, phase-bank,
and commissioning-only while oracle completed. It remains in every denominator;
therefore the zero-ROM absolute gate also failed. The phase-bank residual itself
remained finite and bounded, peaked at 3.898 Nm, and had zero cap hits.

No alpha, cap, phase boundary, detector, domain, gate, or controller parameter
will be changed on these cases. The representation is rejected and will not be
promoted or formally evaluated.

