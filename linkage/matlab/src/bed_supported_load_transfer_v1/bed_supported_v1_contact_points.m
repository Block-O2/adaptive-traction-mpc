function points = bed_supported_v1_contact_points(q, dq, h_hip, p, config)
%BED_SUPPORTED_V1_CONTACT_POINTS Regular lower-surface support candidates.

q = q(:); dq = dq(:); phi = q(1)-q(2);
e1 = [cos(q(1)); sin(q(1))]; e2 = [cos(phi); sin(phi)];
n1 = numel(config.thigh_support_fractions);
n2 = numel(config.shank_support_fractions);
n = n1+n2;
position = zeros(2, n); J = zeros(2, 2, n); link = strings(1, n);
fraction = zeros(1, n); surface_offset = zeros(1, n);
index = 0;
for a = config.thigh_support_fractions
    index = index+1;
    position(:, index) = a*p.L1*e1+[0; h_hip-config.thigh_surface_offset_m];
    J(:, :, index) = [-a*p.L1*sin(q(1)), 0; ...
                       a*p.L1*cos(q(1)), 0];
    link(index) = "thigh"; fraction(index) = a;
    surface_offset(index) = config.thigh_surface_offset_m;
end
for b = config.shank_support_fractions
    index = index+1;
    position(:, index) = p.L1*e1+b*p.L2*e2+ ...
        [0; h_hip-config.shank_surface_offset_m];
    J(:, :, index) = [ ...
        -p.L1*sin(q(1))-b*p.L2*sin(phi), b*p.L2*sin(phi); ...
         p.L1*cos(q(1))+b*p.L2*cos(phi), -b*p.L2*cos(phi)];
    link(index) = "shank"; fraction(index) = b;
    surface_offset(index) = config.shank_surface_offset_m;
end
velocity = zeros(2, n);
for index = 1:n, velocity(:, index) = J(:, :, index)*dq; end
points = struct('position_world', position, 'J', J, ...
    'velocity_world', velocity, 'link', link, 'fraction', fraction, ...
    'surface_offset_m', surface_offset, 'h_hip_m', h_hip);
end
