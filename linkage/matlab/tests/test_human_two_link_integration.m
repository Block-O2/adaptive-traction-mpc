function tests = test_human_two_link_integration
tests = functiontests(localfunctions);
end


function testUnforcedIntegrationConvergence(testCase)
p = default_parameters("nominal");
p.B = zeros(2, 2);
initial_state = [deg2rad([20; 30]); deg2rad([5; -3])];
t_final = 2.0;

[coarse_final, coarse_energy_error] = integrate_unforced( ...
    initial_state, 0.04, t_final, p);
[fine_final, fine_energy_error] = integrate_unforced( ...
    initial_state, 0.02, t_final, p);
[reference_final, ~] = integrate_unforced( ...
    initial_state, 0.0025, t_final, p);

coarse_state_error = norm(coarse_final - reference_final, inf);
fine_state_error = norm(fine_final - reference_final, inf);
fprintf(['INTEGRATION CONVERGENCE: coarse_state=%.9e ' ...
    'fine_state=%.9e coarse_energy=%.9e fine_energy=%.9e\n'], ...
    coarse_state_error, fine_state_error, ...
    coarse_energy_error, fine_energy_error);

verifyLessThan(testCase, fine_state_error, coarse_state_error);
verifyLessThan(testCase, fine_energy_error, coarse_energy_error);
end


function testRK4IsDeterministic(testCase)
p = default_parameters("nominal");
initial_state = [deg2rad([15; 25]); deg2rad([2; -1])];
rhs = @(~, state) continuous_dynamics( ...
    state, zeros(2, 1), zeros(2, 1), p, false);
first = rk4_step(rhs, 0, initial_state, 0.01);
second = rk4_step(rhs, 0, initial_state, 0.01);
verifyEqual(testCase, first, second);
verifyTrue(testCase, all(isfinite(first)));
end


function [final_state, maximum_energy_error] = integrate_unforced( ...
        initial_state, dt, t_final, p)
step_count = round(t_final / dt);
x = initial_state;
initial_energy = total_energy(x(1:2), x(3:4), p);
maximum_energy_error = 0;
rhs = @(~, state) continuous_dynamics( ...
    state, zeros(2, 1), zeros(2, 1), p, false);

for step_index = 1:step_count
    x = rk4_step(rhs, (step_index-1)*dt, x, dt);
    energy_error = abs(total_energy(x(1:2), x(3:4), p) - ...
        initial_energy);
    maximum_energy_error = max(maximum_energy_error, energy_error);
end
final_state = x;
end
