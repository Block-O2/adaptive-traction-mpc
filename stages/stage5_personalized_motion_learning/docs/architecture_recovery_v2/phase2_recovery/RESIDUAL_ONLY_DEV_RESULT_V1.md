# Commissioning-Beta Plus Residual Development Result V1

Status: **REJECTED**

Result SHA-256:
`f93f2a8259dcc0cb442c5eb22714adfe88c1225c3c892b3f643dea1565d85bbd`.
The 24-case paired matrix completed without source/config or Git-status drift.

| arm | completion | median | p95 | full-episode force/moment | ROM samples |
|---|---:|---:|---:|---:|---:|
| V2.1 combined | 24/24 | 0.5142 deg | 1.1543 deg | 146.09 N / 47.31 Nm | 0 |
| residual-only | 22/24 | 0.4985 deg | 2.0807 deg | 172.62 N / 51.98 Nm | 2 |
| commissioning-only | 21/24 | 0.8503 deg | 4.3557 deg | 151.75 N / 52.50 Nm | 0 |
| oracle | 24/24 | 0.4136 deg | 0.6606 deg | 142.62 N / 33.03 Nm | 0 |

The candidate improved median by 3.06% versus V2.1 and by 41.38% versus
commissioning-only, but completion fell by 0.0833, p95 worsened by 80.25%, and
two hidden ROM violations appeared. It therefore fails the preregistered
completion, p95, and zero-ROM conditions.

The data-flow simplification was genuine: all 24 candidate rows reported zero
task beta attempts and zero accepted task beta updates. Residuals were finite
and bounded, but reached the exact 12 Nm cap and accumulated 396 cap hits. This
supports the conclusion that continual beta carries important tail/safety
authority; simply assigning all task mismatch to a constant residual is not a
valid simplification.

No cap, alpha, beta cadence, mechanics domain, or gate will be changed on these
cases. The candidate is rejected and will not be promoted.

