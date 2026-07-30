function tests = test_human_two_link_dynamics
tests = functiontests(localfunctions);
end


function testMassSymmetryAndPositiveDefiniteness(testCase)
p = default_parameters("nominal");
[q_values, dq_values] = deterministic_grid();
minimum_eigenvalue = inf;
maximum_symmetry_residual = 0;

for index = 1:size(q_values, 2)
    [M, ~, ~, ~] = dynamics_terms( ...
        q_values(:, index), dq_values(:, index), p);
    maximum_symmetry_residual = max(maximum_symmetry_residual, ...
        norm(M - M', inf));
    minimum_eigenvalue = min(minimum_eigenvalue, ...
        min(eig((M + M')/2)));
end

verifyLessThanOrEqual(testCase, maximum_symmetry_residual, 1e-12);
verifyGreaterThan(testCase, minimum_eigenvalue, 0);
end


function testCoriolisVectorConsistency(testCase)
p = default_parameters("nominal");
[q_values, dq_values] = deterministic_grid();
maximum_residual = 0;

for index = 1:size(q_values, 2)
    [~, h, C, ~] = dynamics_terms( ...
        q_values(:, index), dq_values(:, index), p);
    maximum_residual = max(maximum_residual, ...
        norm(C*dq_values(:, index) - h, inf));
end

verifyLessThanOrEqual(testCase, maximum_residual, 1e-12);
end


function testManipulatorSkewSymmetry(testCase)
p = default_parameters("nominal");
[q_values, dq_values] = deterministic_grid();
finite_difference_step = 1e-7;
maximum_residual = 0;

for index = 1:size(q_values, 2)
    q = q_values(:, index);
    dq = dq_values(:, index);
    [~, ~, C, ~] = dynamics_terms(q, dq, p);
    M_plus = dynamics_terms(q + finite_difference_step*dq, dq, p);
    M_minus = dynamics_terms(q - finite_difference_step*dq, dq, p);
    M_dot = (M_plus - M_minus) / (2*finite_difference_step);
    skew_candidate = M_dot - 2*C;
    maximum_residual = max(maximum_residual, ...
        norm(skew_candidate + skew_candidate', inf));
end

verifyLessThanOrEqual(testCase, maximum_residual, 1e-8);
end


function testGravityMatchesPotentialGradient(testCase)
p = default_parameters("nominal");
[q_values, dq_values] = deterministic_grid();
finite_difference_step = 1e-6;
maximum_residual = 0;

for index = 1:size(q_values, 2)
    q = q_values(:, index);
    [~, ~, ~, G] = dynamics_terms(q, dq_values(:, index), p);
    numerical_gradient = zeros(2, 1);
    for coordinate = 1:2
        perturbation = zeros(2, 1);
        perturbation(coordinate) = finite_difference_step;
        numerical_gradient(coordinate) = ( ...
            potential_energy(q + perturbation, p) - ...
            potential_energy(q - perturbation, p)) / ...
            (2*finite_difference_step);
    end
    maximum_residual = max(maximum_residual, ...
        norm(numerical_gradient - G, inf));
end

verifyLessThanOrEqual(testCase, maximum_residual, 1e-7);
end


function testFiniteTermsAcrossProfiles(testCase)
profiles = ["nominal", "short_light", "tall_heavy"];
[q_values, dq_values] = deterministic_grid();

for profile = profiles
    p = default_parameters(profile);
    validate_parameters(p);
    for index = 1:size(q_values, 2)
        [M, h, C, G] = dynamics_terms( ...
            q_values(:, index), dq_values(:, index), p);
        values = [M(:); h; C(:); G; ...
            potential_energy(q_values(:, index), p); ...
            total_energy(q_values(:, index), dq_values(:, index), p)];
        verifyTrue(testCase, all(isfinite(values)));
    end
end
end


function [q_values, dq_values] = deterministic_grid()
q1 = deg2rad([-5, 0, 30, 60, 85]);
q2 = deg2rad([-5, 0, 30, 75, 120]);
dq1 = deg2rad([-60, 0, 60]);
dq2 = deg2rad([-80, 0, 80]);
[q1_grid, q2_grid, dq1_grid, dq2_grid] = ndgrid(q1, q2, dq1, dq2);
q_values = [q1_grid(:)'; q2_grid(:)'];
dq_values = [dq1_grid(:)'; dq2_grid(:)'];
end
