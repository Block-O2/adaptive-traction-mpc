# Contact validity metrics

- `immutable_proximal_thigh_gap_m`: fixed hip world z minus thigh capsule
  radius minus bed-plane world z. Negative means geometric overlap of the
  fixed proximal sphere. A 1e-9 m tolerance is numerical classification only,
  not a new physical safety margin.
- `contact_wrench_local_n_nm`: MuJoCo `mj_contactForce`, force xyz followed by
  torque xyz. First local axis is normal; contact frame rows are world axes.
  `F_world=frame.T@F_local`; force is applied from geom1 toward geom2.
- `human_generalized_contact_nm`: equal/opposite contact forces mapped with
  `mj_applyFT`; compare to MuJoCo constraint generalized force separately
  from the compliant cuff generalized input.
- `normal_peak_n`: maximum actual interval contact normal force for one geom
  pair; sum simultaneous contacts for that pair first. Checkpoint diagnostics
  also retain every individual contact to avoid aggregate ambiguity.
- `normal_impulse_n_s`: sum normal force times actual executed interval dt;
  not an endpoint Riemann estimate from refreshed future boundary forces.
- `tangent_norm_integral_n_s`: analogous norm integral, not signed impulse.
- `contact duration`: sum dt when pair is present. Zero-force detected contacts
  are not automatically active loads; positive-force duration is also retained.
- `minimum_distance_m`: minimum detected pair contact distance, or zero sentinel
  with zero contact intervals. It is not positive separation when no contact.
- `true q`: evaluation-only qpos at interval start; ctrl is the actual CR12
  command for that interval. Native mj_step2 advances exactly one 0.25 ms step.
- Historical physical clearance remains **shank-only**. The new proximal
  diagnostic is additional coverage; no historical field is silently renamed.

Final integration-vector equality verifies final MuJoCo physical state and
warm-start/control state covered by `mjSTATE_INTEGRATION`. It does not certify
every intermediate full controller state byte. Historical planner wait steps
are replayed to prevent host latency from perturbing causal comparisons.
