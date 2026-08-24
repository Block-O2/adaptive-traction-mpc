# Stage 9G Crossing-Alpha Feasibility Frontier

This is an offline oracle feasibility study, not a new online controller.

## Setup

- Command: `python scripts/run_spring2d_stage9g_crossing_alpha_frontier.py`
- Script: `scripts/run_spring2d_stage9g_crossing_alpha_frontier.py`
- Initial state override: theta=0.02 rad, omega=-0.15 rad/s.
- Target crossing: theta_N >= theta_target + 0.100 deg.
- Oracle assumptions: true state, true physical parameters, no estimator, no identifier, no observation noise, no fallback.
- Optimization: scaled CasADi multiple shooting with explicit X, U, and scalar alpha_peak.
- Primary objective: minimize alpha_peak; secondary action/action-rate/terminal-omega costs use small coefficients.
- Hard constraints: |F_tan|<=35, |F_rad|<=1, |r-L0|<=0.06, |omega|<=1.2, terminal crossing, dynamics equality.
- Alpha slack was not used in the primary frontier problem.

## Minimum-Alpha Frontier

| mode | N | time_s | alpha_limit | success | alpha_peak | terminal_theta_deg | cross_margin_deg | omega_margin | delta_r_margin | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| min_alpha | 18 | 0.54 | nan | False | nan | nan | nan | nan | nan | Infeasible_Problem_Detected |
| min_alpha | 24 | 0.72 | nan | False | nan | nan | nan | nan | nan | Infeasible_Problem_Detected |
| min_alpha | 30 | 0.9 | nan | False | nan | nan | nan | nan | nan | Infeasible_Problem_Detected |
| min_alpha | 40 | 1.2 | nan | False | nan | nan | nan | nan | nan | Infeasible_Problem_Detected |
| min_alpha | 60 | 1.8 | nan | True | 1.5084 | 90.1 | 1.4597e-06 | 1.1662e-06 | 0.045184 | Solve_Succeeded |

## Fixed-Alpha Feasibility Check

| mode | N | time_s | alpha_limit | success | alpha_peak | terminal_theta_deg | cross_margin_deg | omega_margin | delta_r_margin | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| fixed_alpha_feasibility | 18 | 0.54 | 3 | False | 3 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 18 | 0.54 | 4 | False | 4 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 18 | 0.54 | 5 | False | 5 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 18 | 0.54 | 7 | False | 7 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 18 | 0.54 | 10 | False | 10 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 24 | 0.72 | 3 | False | 3 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 24 | 0.72 | 4 | False | 4 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 24 | 0.72 | 5 | False | 5 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 24 | 0.72 | 7 | False | 7 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 24 | 0.72 | 10 | False | 10 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 30 | 0.9 | 3 | False | 3 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 30 | 0.9 | 4 | False | 4 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 30 | 0.9 | 5 | False | 5 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 30 | 0.9 | 7 | False | 7 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 30 | 0.9 | 10 | False | 10 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 40 | 1.2 | 3 | False | 3 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 40 | 1.2 | 4 | False | 4 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 40 | 1.2 | 5 | False | 5 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 40 | 1.2 | 7 | False | 7 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 40 | 1.2 | 10 | False | 10 | nan | nan | nan | nan | Infeasible_Problem_Detected |
| fixed_alpha_feasibility | 60 | 1.8 | 3 | True | 3 | 90.235 | 0.13513 | 0.020392 | 0.046934 | Solve_Succeeded |
| fixed_alpha_feasibility | 60 | 1.8 | 4 | True | 4 | 90.46 | 0.36037 | 0.022886 | 0.046931 | Solve_Succeeded |
| fixed_alpha_feasibility | 60 | 1.8 | 5 | True | 5 | 90.601 | 0.50149 | 0.022609 | 0.04693 | Solve_Succeeded |
| fixed_alpha_feasibility | 60 | 1.8 | 7 | True | 7 | 90.746 | 0.64646 | 0.022176 | 0.04693 | Solve_Succeeded |
| fixed_alpha_feasibility | 60 | 1.8 | 10 | True | 10 | 90.843 | 0.74321 | 0.021462 | 0.04693 | Solve_Succeeded |

## Prior Reference Values

| reference | alpha max [rad/s^2] | note |
|---|---:|---|
| Stage 9D nmpc_base | 3.138 | no target crossing |
| Stage 9F baseline CEM | 9.142 | crossed |
| Stage 9F weighted crossing NMPC | 27.07 | crossed with spike |
| Stage 9F lexicographic crossing NMPC | 72.25 | crossed with large spike |

## Required Answers

1. Low-alpha target crossing is feasible under the tested hard constraints, but only accepted at N=60 in this horizon set.
2. The lowest accepted alpha_peak is 1.508 rad/s^2 at N=60 (1.800 s).
3. Minimum alpha versus horizon among accepted solves: N=60: 1.508.
4. Alpha around 3-4 is compatible with crossing in at least one fixed-alpha check.
5. Baseline CEM alpha max around 9 appears unnecessarily aggressive relative to the oracle frontier.
6. Stage 9F crossing spikes were not forced at their observed magnitude by the offline oracle problem; the online formulation contributed substantially.
7. Recommended next step: reachability-aware online crossing constraint or trajectory planner plus NMPC tracking.

## Conclusion

Low-alpha crossing is feasible in the tested oracle problem when enough crossing time is allowed; the online crossing formulation is the main suspect.

No formal safety guarantee is claimed.
