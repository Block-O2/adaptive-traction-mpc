# Architecture Recovery V2 Related Work

This file records only literature that materially affects a design or audit
decision. Primary paper/publisher or institutional records were checked; search
snippets are not treated as evidence.

| Work | Method/claim used | Difference/limitation here | Decision influenced |
|---|---|---|---|
| Lu & Cannon (2023), *Robust adaptive MPC with persistent excitation conditions*, Automatica 152, 110959, DOI 10.1016/j.automatica.2023.110959 | Set-membership adaptation can couple constrained MPC with explicit persistent excitation and retain recursive feasibility under its linear/bounded-disturbance assumptions | V2 Human dynamics are nonlinear, the cuff geometry is also unknown, and this campaign does not inherit the paper's guarantee assumptions | Supports a bounded safe-probe phase and explicit excitation diagnostics; does not justify claiming guarantees for the present controller |
| Parsi et al. (2023), *Dual adaptive MPC using an exact set-membership reformulation*, IFAC-PapersOnLine 56(2), DOI 10.1016/j.ifacol.2023.10.1132 | Predicted identification benefit can be incorporated into worst-case MPC rather than treating parameter convergence as a separate objective | The method is developed for uncertain linear models/tube MPC; direct use would add major complexity | Reserved as a repair path if the simple control-effective estimator is insufficient; complexity discipline favors passive/bounded probing first |
| Yang, Choset & Manchester (2022), *Online Kinematic Calibration for Legged Robots*, IEEE RA-L, DOI 10.1109/LRA.2022.3186501 | Kinematic parameters can be estimated online from sensor histories while explicitly treating observability | Different robot/contact sensors and no rehabilitation cuff-equivalence problem | Reinforces estimating only observable effective geometry and recording conditioning rather than forcing anatomical recovery |
| Du et al. (2018), *An Advanced Adaptive Control of Lower Limb Rehabilitation Robot*, Frontiers in Robotics and AI 5:116, DOI 10.3389/frobt.2018.00116 | Hierarchical adaptation can separate reference/task adjustment from a lower-level tracking controller | Uses sEMG/plantar pressure and human experiments unavailable to this campaign; not an MPC result | Supports the Phase-3 separation between event-driven Human-waypoint planning and the lower execution/tracking layer, without importing its sensor assumptions |
| Bradford et al. (2020), *Stochastic data-driven model predictive control using Gaussian processes*, Computers & Chemical Engineering 139, 106844, DOI 10.1016/j.compchemeng.2020.106844 | MPC model mismatch and uncertainty may be state-dependent, and a learned model can be evaluated along predicted states | Uses offline GP sampling and chance-constraint backoffs absent here; its guarantees and application do not transfer | Supports testing one bounded state-conditioned residual rather than declaring method exhaustion after constant/phase residual failures |
| Maiworm, Limon & Findeisen (2021), *Online learning-based Model Predictive Control with Gaussian Process Models and Stability Guarantees*, International Journal of Robust and Nonlinear Control, DOI 10.1002/rnc.5361 | Online recursive updates can refine an MPC prediction model while limiting retained data | The published guarantees require a different output-feedback GP architecture and assumptions not established for Human V2 | Supports causal online model refinement as a method class only; the V2 NLMS residual remains an empirical control-effective candidate with no inherited guarantee |

## Current design consequence

The frozen V2.1 candidate is a structured effective geometry plus an 11-base
dynamics model and bounded task-wide torque residual. After its fresh formal
median-benefit failure, one preregistered V2-local state-conditioned residual is
authorized for development. It keeps the same probe, sensors, beta estimator,
MPC objective, and constraints, and adds no literature-derived guarantee. No
GP, dual, or set-valued MPC layer is added unless later evidence and a new
contract justify that complexity.
