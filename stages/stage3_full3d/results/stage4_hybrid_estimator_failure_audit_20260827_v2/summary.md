# Stage 4 dynamics-estimator bound-hit diagnosis

Offline reconstruction from the saved registered A/B traces. Estimator logic, bounds, and gates are unchanged.

| mode | attempts | accepted | first trust wall/phase | bound-hit components | rejection reasons |
|---|---:|---:|---:|---|---|
| existing_cem | 51 | 3 | 6.500/3.250 s | {'a_inertia_combination': 39, 'b_distal_inertia_combination': 27, 'bv1_viscous_damping': 10, 'bv2_viscous_damping': 3, 'd_mass_length_com_combination': 9, 'rho1_stiffness_rest_combination': 14, 'rho2_stiffness_rest_combination': 22} | {'bound_hit': 48, 'non_positive_definite_mass_matrix': 21} |
| cem_plus_smooth_local_refinement | 52 | 0 | - | {'a_inertia_combination': 47, 'b_distal_inertia_combination': 38, 'bv1_viscous_damping': 27, 'bv2_viscous_damping': 7, 'd_mass_length_com_combination': 47, 'rho1_stiffness_rest_combination': 18, 'rho2_stiffness_rest_combination': 10} | {'bound_hit': 52} |
