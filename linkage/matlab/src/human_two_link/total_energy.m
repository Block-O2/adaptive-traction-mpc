function energy = total_energy(q, dq, p)
%TOTAL_ENERGY Kinetic plus gravitational potential energy.

[M, ~, ~, ~] = dynamics_terms(q, dq, p);
dq = dq(:);
energy = 0.5 * dq' * M * dq + potential_energy(q, p);
end
