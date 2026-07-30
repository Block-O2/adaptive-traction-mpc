function tests = test_human_two_link_contact
tests = functiontests(localfunctions);
end


function testDampingContactDissipativity(testCase)
p = default_parameters("nominal");
q_values = deg2rad([ ...
    0, 20, 50, 80; ...
    0, 30, 70, 110]);
dq_values = deg2rad([ ...
    -40, 0, 35, 55; ...
    50, -30, 0, -70]);
robot_velocities = [ ...
    0.10, -0.15, 0.00, 0.20; ...
   -0.05,  0.10, 0.12, 0.00];

for index = 1:size(q_values, 2)
    [~, ~, details] = damping_contact_force( ...
        q_values(:, index), dq_values(:, index), ...
        robot_velocities(:, index), p, true);
    verifyLessThanOrEqual(testCase, details.relative_power, 1e-12);
end
end


function testZeroRelativeNormalVelocityGivesZeroForce(testCase)
p = default_parameters("nominal");
q = deg2rad([35; 55]);
dq = deg2rad([20; -15]);
contact = shank_contact_kinematics(q, dq, p);
tangent = [cos(contact.phi); sin(contact.phi)];
vr = contact.velocity - 0.25*tangent;
[Fc, tau_contact, details] = damping_contact_force(q, dq, vr, p, true);

verifyLessThanOrEqual(testCase, abs(details.relative_normal_velocity), 1e-12);
verifyLessThanOrEqual(testCase, norm(Fc, inf), 1e-12);
verifyLessThanOrEqual(testCase, norm(tau_contact, inf), 1e-12);
end


function testDisabledContactIsExactlyZero(testCase)
p = default_parameters("nominal");
q = deg2rad([45; 60]);
dq = deg2rad([30; -40]);
vr = [0.2; -0.1];
[Fc, tau_contact, details] = damping_contact_force(q, dq, vr, p, false);

verifyEqual(testCase, Fc, zeros(2, 1));
verifyEqual(testCase, tau_contact, zeros(2, 1));
verifyEqual(testCase, details.relative_power, 0);
end


function testZeroDampingIsExactlyZero(testCase)
p = default_parameters("nominal");
p.cn = 0;
validate_parameters(p);
[Fc, tau_contact, details] = damping_contact_force( ...
    deg2rad([20; 30]), deg2rad([10; 15]), [0.1; 0.2], p, true);

verifyEqual(testCase, Fc, zeros(2, 1));
verifyEqual(testCase, tau_contact, zeros(2, 1));
verifyEqual(testCase, details.relative_power, 0);
end
