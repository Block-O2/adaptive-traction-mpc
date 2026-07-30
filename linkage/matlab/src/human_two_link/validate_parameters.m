function validate_parameters(p)
%VALIDATE_PARAMETERS Validate the human two-link engineering parameter set.

required = {'L1', 'L2', 'm1', 'm2', 'lc1', 'lc2', 'I1', 'I2', ...
    'g', 'sc', 'cn', 'B', 'q_min', 'q_max', 'dq_max', ...
    'reference_ddq_max'};
for field_index = 1:numel(required)
    if ~isfield(p, required{field_index})
        error('HumanTwoLink:MissingParameter', ...
            'Missing parameter field: %s', required{field_index});
    end
end

scalar_values = [p.L1, p.L2, p.m1, p.m2, p.lc1, p.lc2, ...
    p.I1, p.I2, p.g, p.sc, p.cn];
if ~all(isfinite(scalar_values))
    error('HumanTwoLink:NonfiniteParameter', ...
        'All scalar parameters must be finite.');
end
if any([p.L1, p.L2, p.m1, p.m2, p.I1, p.I2, p.g] <= 0)
    error('HumanTwoLink:NonpositiveParameter', ...
        'Lengths, masses, inertias, and gravity must be positive.');
end
if p.lc1 <= 0 || p.lc1 > p.L1 || p.lc2 <= 0 || p.lc2 > p.L2
    error('HumanTwoLink:InvalidCOM', ...
        'Each COM distance must lie inside its link.');
end
if p.sc < 0 || p.sc > p.L2
    error('HumanTwoLink:InvalidContactDistance', ...
        'The shank contact distance must lie on the shank.');
end
if p.cn < 0
    error('HumanTwoLink:NegativeContactDamping', ...
        'Normal contact damping must be nonnegative.');
end
if ~isequal(size(p.B), [2, 2]) || any(~isfinite(p.B), 'all')
    error('HumanTwoLink:InvalidPassiveDamping', ...
        'Passive damping B must be a finite 2-by-2 matrix.');
end
if norm(p.B - p.B', inf) > 1e-12 || min(eig((p.B + p.B')/2)) < -1e-12
    error('HumanTwoLink:InvalidPassiveDamping', ...
        'Passive damping B must be symmetric positive semidefinite.');
end

vector_fields = {'q_min', 'q_max', 'dq_max', 'reference_ddq_max'};
for field_index = 1:numel(vector_fields)
    value = p.(vector_fields{field_index});
    if ~isequal(size(value), [2, 1]) || any(~isfinite(value))
        error('HumanTwoLink:InvalidRange', ...
            '%s must be a finite 2-by-1 vector.', vector_fields{field_index});
    end
end
if any(p.q_min >= p.q_max)
    error('HumanTwoLink:InvalidJointRange', ...
        'Each minimum joint angle must be below its maximum.');
end
if any(p.dq_max <= 0) || any(p.reference_ddq_max <= 0)
    error('HumanTwoLink:InvalidRateRange', ...
        'Velocity and acceleration limits must be positive.');
end
end
