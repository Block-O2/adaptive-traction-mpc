function p = human_two_link_v2_parameters(height_m, body_mass_kg)
%HUMAN_TWO_LINK_V2_PARAMETERS Anthropometric two-link patient parameters.

if nargin < 1
    height_m = 1.72;
end
if nargin < 2
    body_mass_kg = 75.0;
end
if ~isscalar(height_m) || ~isfinite(height_m) || height_m <= 0 || ...
        ~isscalar(body_mass_kg) || ~isfinite(body_mass_kg) || ...
        body_mass_kg <= 0
    error('HumanTwoLinkV2:InvalidAnthropometry', ...
        'Height and body mass must be positive finite scalars.');
end

p = struct();
p.model_name = "human_two_link_v2";
p.height_m = height_m;
p.body_mass_kg = body_mass_kg;

p.L1 = 0.254 * height_m;
p.L2 = 0.233 * height_m;
p.m1 = 0.099 * body_mass_kg;
p.m2 = (0.046 + 0.014) * body_mass_kg;
p.lc1 = 0.433 * p.L1;
p.lc2 = 0.430 * p.L2;
p.I1 = p.m1 * (0.30*p.L1)^2;
p.I2 = p.m2 * (0.30*p.L2)^2;
p.g = 9.81;

p.sc = 0.90 * p.L2;
p.q_rest = deg2rad([5; 10]);
p.K_passive = diag([10, 10]);
p.B_passive = diag([5, 5]);
p.q_min = deg2rad([0; 0]);
p.q_max = deg2rad([80; 100]);
p.soft_limit_margin = deg2rad(5);
p.soft_limit_numerical_tolerance = 1e-9;

% Low-end engineering assumptions, not clinical constants.
p.soft_limit_boundary_torque_Nm = 25.0;
p.soft_limit_damping_Nms_rad = 2.0;

human_two_link_v2_validate_parameters(p);
end
