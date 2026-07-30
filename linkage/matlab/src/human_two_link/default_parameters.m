function p = default_parameters(profile_name)
%DEFAULT_PARAMETERS Nominal or deterministic synthetic engineering profile.

if nargin < 1
    profile_name = "nominal";
end
profile_name = string(profile_name);

switch profile_name
    case "nominal"
        length_scale = 1.00;
        mass_scale = 1.00;
    case "short_light"
        length_scale = 0.85;
        mass_scale = 0.65;
    case "tall_heavy"
        length_scale = 1.15;
        mass_scale = 1.35;
    otherwise
        error('HumanTwoLink:UnknownProfile', ...
            'Unknown parameter profile: %s', profile_name);
end

p = struct();
p.profile_name = profile_name;
p.length_scale = length_scale;
p.mass_scale = mass_scale;

p.L1 = 0.45 * length_scale;
p.L2 = 0.40 * length_scale;
p.m1 = 8.5 * mass_scale;
p.m2 = 3.8 * mass_scale;
p.lc1 = p.L1 / 2;
p.lc2 = p.L2 / 2;
p.I1 = p.m1 * p.L1^2 / 12;
p.I2 = p.m2 * p.L2^2 / 12;
p.g = 9.81;

p.sc = 0.50 * p.L2;
p.cn = 35.0;
p.B = zeros(2, 2);

p.q_min = deg2rad([-5; -5]);
p.q_max = deg2rad([85; 120]);
p.dq_max = deg2rad([60; 80]);
p.reference_ddq_max = deg2rad([120; 160]);

validate_parameters(p);
end
