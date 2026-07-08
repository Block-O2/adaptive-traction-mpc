# Results

Results are organized by experimental stage. Each retained stage folder keeps the final report or summary table plus a small set of representative figures. Raw logs, videos, duplicate plots, and intermediate diagnostics are archived under `results/_archive/`.

| Stage | Method | Status | Main conclusion | Key retained files |
|---|---|---|---|---|
| Stage 1 | Spring2D adaptive MPC setup | Retained baseline evidence | Established Spring2D simulation, adaptive MPC logging, and initial fixed/adaptive comparisons. | `stage1_spring2d/figures/`, `stage1_spring2d/tables/` |
| Stage 2 | CEM solver | Retained baseline evidence | CEM improved planning capability but still exposed safety constraint issues. | `stage2_cem/figures/`, `stage2_cem/tables/` |
| Stage 2 | CEM feasibility-first | Retained comparison evidence | Feasibility-first comparison retained as solver-selection evidence. | `stage2_cem_feasfirst/figures/`, `stage2_cem_feasfirst/tables/` |
| Stage 3 | Filtering comparison | Retained estimator evidence | Filtering was evaluated under noisy and biased observations. | `stage3_filtering/figures/`, `stage3_filtering/tables/` |
| Stage 4 | UKF / UKF-bias | Retained mainline estimator evidence | UKF-bias became the mainline estimator for later stages. | `stage4_ukf/figures/`, `stage4_ukf/tables/` |
| Stage 5 | Estimator-identifier coupling | Retained mainline coupling evidence | Filtered UKF-bias plus filtered Windowed NLS became the mainline data flow. | `stage5_coupling/figures/`, `stage5_coupling/tables/` |
| Stage 6 | One-step runtime safety filter | Negative baseline | Runtime filter is retained as negative baseline evidence; it often destroys target reaching. | `stage6_safety_filter/closeout/` |
| Stage 6b | Sign diagnosis | Closed diagnostic | Sign convention and `F_tan` reversal issues were ruled out. | `stage6b/closeout/` |
| Stage 7A | Alpha-soft CEM | Closed, not carried forward | Better than runtime filtering, but not robust enough as the main safety method. | `stage7a_alpha_soft/stage7a_final_report.md`, `stage7a_alpha_soft/stage7a_final_summary.csv` |
| Stage 7B | Fixed-rate progress governor | Failed / mixed | Fixed-rate governor failed; target reaching and safety were mixed. | `stage7b_progress_governor/stage7b_minimal_report.md`, `stage7b_progress_governor/stage7b_minimal_summary.csv` |
| Stage 7C | Gatekeeper-lite | Closed / mixed | Preserves target reaching and reduces omega, but fails alpha tail risk. | `stage7c_gatekeeper_lite/stage7c_report.md`, `stage7c_gatekeeper_lite/stage7c_summary.csv` |
| Stage 7C | Alpha-tail gatekeeper revision | Closed / failed | Tail-aware scoring revision did not fix alpha p95/max severity. | `stage7c_gatekeeper_alpha_tail/stage7c_alpha_tail_report.md`, `stage7c_gatekeeper_alpha_tail/stage7c_alpha_tail_summary.csv` |
| Stage 7D | Safety-aware command governor | Closed / failed | Failed target reaching (`0/3`) and worsened safety in the minimal validation. | `stage7d_safety_aware_governor/stage7d_report.md`, `stage7d_safety_aware_governor/stage7d_summary.csv` |

Next planned direction: Stage 8 smoother / acceleration-aware CEM action generation.

These outputs are simulation evidence only. They are not formal safety guarantees.
