# Stage 10D: MHE Sanity Audit

## Scope

- No closed-loop simulation, controller change, or broad weight tuning was performed.
- Each of the 24 saved replay runs contributes its first two full 70-transition windows (48 audit windows). Every selected audit window is logged.
- A confirmed Stage 10C rolling-arrival indexing bug was fixed before this audit: after a deque advance, the saved multiple-shooting trajectory is shifted so the arrival prior advances one state per dropped transition.

## Results

- Replay alignment: **PASS**; the maximum true dynamics replay error is 0.
- Hard-dynamics single/multiple equivalence: **PASS** across 48 windows.
- Noise-free oracle sanity: **PASS**; state max error=1.85e-05, inverse-mass error=7.94e-07, alpha RMSE=6.1e-05.
- Bias audit: the UKF-bias model uses `y = x + b`, with four random-walk bias states. The MHE uses `y = x` and has no bias decision variables. This is a structural mismatch; it was recorded, not corrected.
- Mean optimized objective is dominated by `measurement_cost` (0.00499427); see `objective_decomposition.csv` for every selected window and before/after residual magnitudes.

- Optimized state-to-measurement RMS=0.00971409, measurement-to-true RMS=0.00925475, and optimized-state-to-true RMS=0.0027461. The optimized states depart from the noisy measurements and are closer to truth on these replay windows. However, because the MHE has no bias decision variable, any persistent measurement offset must be redistributed among state, process, and parameter residuals rather than identified explicitly.

## Decision

The formulation and implementation sanity checks pass after the arrival-index correction. Stage 10C's pre-fix failure cannot be used to close the MHE route. The replay still has an unmodelled measurement-bias mismatch relative to the UKF-bias observer, so the next evidence-required step is a corrected offline multiple-shooting benchmark before any branch-closing decision. Do not implement a bias estimator, smoother, or EM in this stage.
