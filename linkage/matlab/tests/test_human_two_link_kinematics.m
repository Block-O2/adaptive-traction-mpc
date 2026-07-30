function tests = test_human_two_link_kinematics
tests = functiontests(localfunctions);
end


function testRecordedCoordinateConvention(testCase)
p = default_parameters("nominal");
q = deg2rad([35; 50]);
geometry = kinematics(q, p);
verifyEqual(testCase, geometry.phi, q(1)-q(2), 'AbsTol', 1e-14);
verifyEqual(testCase, norm(geometry.knee - geometry.hip), ...
    p.L1, 'AbsTol', 1e-14);
verifyEqual(testCase, norm(geometry.ankle - geometry.knee), ...
    p.L2, 'AbsTol', 1e-14);
end


function testContactJacobianFiniteDifference(testCase)
p = default_parameters("nominal");
q_values = deg2rad([ ...
    -5, 0, 25, 50, 85; ...
    -5, 15, 45, 90, 120]);
finite_difference_step = 1e-7;
maximum_residual = 0;

for index = 1:size(q_values, 2)
    q = q_values(:, index);
    contact = shank_contact_kinematics(q, zeros(2, 1), p);
    numerical_jacobian = zeros(2, 2);
    for coordinate = 1:2
        perturbation = zeros(2, 1);
        perturbation(coordinate) = finite_difference_step;
        plus = shank_contact_kinematics( ...
            q + perturbation, zeros(2, 1), p);
        minus = shank_contact_kinematics( ...
            q - perturbation, zeros(2, 1), p);
        numerical_jacobian(:, coordinate) = ...
            (plus.position - minus.position) / ...
            (2*finite_difference_step);
    end
    maximum_residual = max(maximum_residual, ...
        norm(numerical_jacobian - contact.J, inf));
end

verifyLessThanOrEqual(testCase, maximum_residual, 1e-8);
end


function testContactVelocityFiniteDifference(testCase)
p = default_parameters("nominal");
states = deg2rad([ ...
    5, 25, 55, 80; ...
    10, 35, 75, 110; ...
    -30, 0, 25, 50; ...
    40, -20, 0, -60]);
finite_difference_step = 1e-7;
maximum_residual = 0;

for index = 1:size(states, 2)
    q = states(1:2, index);
    dq = states(3:4, index);
    contact = shank_contact_kinematics(q, dq, p);
    plus = shank_contact_kinematics( ...
        q + finite_difference_step*dq, dq, p);
    minus = shank_contact_kinematics( ...
        q - finite_difference_step*dq, dq, p);
    numerical_velocity = (plus.position - minus.position) / ...
        (2*finite_difference_step);
    maximum_residual = max(maximum_residual, ...
        norm(numerical_velocity - contact.velocity, inf));
end

verifyLessThanOrEqual(testCase, maximum_residual, 1e-8);
end


function testContinuousNormalHasUnitLength(testCase)
p = default_parameters("nominal");
q_values = [ ...
    deg2rad([0; 89.999]), ...
    deg2rad([0; 90.001]), ...
    deg2rad([85; -5]), ...
    deg2rad([-5; 120])];
for index = 1:size(q_values, 2)
    contact = shank_contact_kinematics( ...
        q_values(:, index), zeros(2, 1), p);
    verifyEqual(testCase, norm(contact.normal), 1, 'AbsTol', 1e-14);
end
end
