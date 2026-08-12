function plan = hybrid_tube_v1_build_plan(p, config)
%HYBRID_TUBE_V1_BUILD_PLAN Deterministic force-aware spatial task plan.

s = linspace(0, 1, config.plan_node_count);
nominal = hybrid_tube_v1_task_path(s);
tube = hybrid_tube_v1_tube_schedule(s, nominal.q, config);
n = numel(s);
q_governed = zeros(2, n);
force = NaN(2, n);
force_norm = NaN(1, n);
hold_feasible = false(1, n);
residual_norm = NaN(1, n);
rom_margin = NaN(2, n);
previous_delta = zeros(2, 1);
previous_force = zeros(2, 1);

for index = 1:n
    cap_deg = rad2deg(tube(:, index));
    offsets1 = candidate_offsets(cap_deg(1), config.candidate_step_deg);
    offsets2 = candidate_offsets(cap_deg(2), config.candidate_step_deg);
    best_score = Inf;
    best_fallback_score = Inf;
    best_q = nominal.q(:, index);
    best_force = [NaN; NaN];
    best_feasible = false;
    for d1 = offsets1
        for d2 = offsets2
            candidate = nominal.q(:, index)+deg2rad([d1; d2]);
            if any(candidate < p.q_min) || any(candidate > p.q_max)
                continue;
            end
            [~, passive] = human_two_link_v2_passive_torque( ...
                candidate, zeros(2, 1), p);
            if any(passive.soft.active)
                continue;
            end
            point = single_arm_quasistatic_hold_point(candidate, p, [], ...
                config.svd_relative_tolerance);
            if point.rank_deficient || any(~isfinite(point.force_local))
                continue;
            end
            delta = candidate-nominal.q(:, index);
            margin = min(candidate-p.q_min, p.q_max-candidate);
            score = candidate_score(delta, tube(:, index), ...
                point.force_local, previous_delta, previous_force, margin, ...
                p, config);
            exact_feasible = all(abs(point.force_local) <= ...
                config.force_bound_N+config.bound_tolerance_N);
            overflow = norm(max(abs(point.force_local)- ...
                config.force_bound_N, 0)/config.force_bound_N);
            fallback_score = score+1e3*overflow^2;
            if exact_feasible && score < best_score
                best_score = score;
                best_q = candidate;
                best_force = point.force_local;
                best_feasible = true;
            elseif ~best_feasible && fallback_score < best_fallback_score
                best_fallback_score = fallback_score;
                best_q = candidate;
                best_force = point.force_local;
            end
        end
    end
    bounded = single_arm_quasistatic_hold_point(best_q, p, ...
        config.force_bound_N, config.svd_relative_tolerance);
    q_governed(:, index) = best_q;
    force(:, index) = best_force;
    force_norm(index) = norm(best_force);
    residual_norm(index) = bounded.bounded_residual_norm(1);
    hold_feasible(index) = best_feasible && ...
        residual_norm(index) <= config.plan_residual_tolerance_Nm;
    rom_margin(:, index) = min(best_q-p.q_min, p.q_max-best_q);
    previous_delta = best_q-nominal.q(:, index);
    previous_force = best_force;
end

% Smooth the force-aware spatial deviation while retaining the tube and ROM.
delta = q_governed-nominal.q;
if config.tube_cap_deg > 0
    kernel = [1, 2, 3, 2, 1]/9;
    for pass = 1:3
        for joint = 1:2
            padded = [repmat(delta(joint, 1), 1, 2), ...
                delta(joint, :), repmat(delta(joint, end), 1, 2)];
            filtered = conv(padded, kernel, 'same');
            delta(joint, :) = filtered(3:end-2);
        end
        delta = min(max(delta, -tube), tube);
    end
    q_governed = nominal.q+delta;
end

% A cubic interpolant can overshoot between nodes. Uniformly contract the
% spatial deviation until dense samples remain inside the continuous tube.
if config.tube_cap_deg > 0
    dense_s = linspace(0, 1, max(5001, 10*n+1));
    for containment_pass = 1:5
        dense_nominal = hybrid_tube_v1_task_path(dense_s);
        dense_tube = hybrid_tube_v1_tube_schedule( ...
            dense_s, dense_nominal.q, config);
        dense_q = zeros(2, numel(dense_s));
        for joint = 1:2
            dense_q(joint, :) = ppval( ...
                spline(s, q_governed(joint, :)), dense_s);
        end
        ratio = max(abs(dense_q-dense_nominal.q)./ ...
            max(dense_tube, deg2rad(1e-9)), [], 'all');
        if ratio <= 0.995
            break;
        end
        delta = (q_governed-nominal.q)*(0.99/ratio);
        q_governed = nominal.q+delta;
    end
end

% Re-evaluate the smoothed plan and construct C2 cubic spatial interpolants.
for index = 1:n
    point = single_arm_quasistatic_hold_point(q_governed(:, index), p, ...
        config.force_bound_N, config.svd_relative_tolerance);
    force(:, index) = point.force_local;
    force_norm(index) = point.force_norm;
    residual_norm(index) = point.bounded_residual_norm(1);
    hold_feasible(index) = ~point.rank_deficient && ...
        all(abs(point.force_local) <= config.force_bound_N+ ...
        config.bound_tolerance_N) && ...
        residual_norm(index) <= config.plan_residual_tolerance_Nm && ...
        ~any(point.passive_details.soft.active);
    rom_margin(:, index) = min(q_governed(:, index)-p.q_min, ...
        p.q_max-q_governed(:, index));
end

pp_q = cell(2, 1); pp_q_s = cell(2, 1); pp_q_ss = cell(2, 1);
for joint = 1:2
    pp_q{joint} = spline(s, q_governed(joint, :));
    pp_q_s{joint} = differentiate_pp(pp_q{joint});
    pp_q_ss{joint} = differentiate_pp(pp_q_s{joint});
end
pp_force = {spline(s, force(1, :)), spline(s, force(2, :))};
plan = struct('s', s, 'nominal', nominal, 'tube_rad', tube, ...
    'q', q_governed, 'force_local', force, 'force_norm', force_norm, ...
    'hold_feasible', hold_feasible, 'residual_norm', residual_norm, ...
    'rom_margin', rom_margin, 'pp_q', {pp_q}, 'pp_q_s', {pp_q_s}, ...
    'pp_q_ss', {pp_q_ss}, 'pp_force', {pp_force}, 'config', config);
end


function offsets = candidate_offsets(cap_deg, step_deg)
if cap_deg <= 1e-12
    offsets = 0;
else
    offsets = unique([-cap_deg:step_deg:cap_deg, 0, cap_deg]);
end
end


function score = candidate_score(delta, tube, force, previous_delta, ...
        previous_force, margin, p, config)
w = config.plan_weights;
tube_scale = max(tube, deg2rad(1));
path_term = sum((delta./tube_scale).^2);
parallel_term = (force(1)/config.force_bound_N)^2;
force_term = (norm(force)/(sqrt(2)*config.force_bound_N))^2;
force_change = norm((force-previous_force)/ ...
    max(config.force_bound_N, 1))^2;
posture_change = norm((delta-previous_delta)./tube_scale)^2;
safe_margin = min(margin, p.soft_limit_margin);
margin_term = sum((1-safe_margin/p.soft_limit_margin).^2);
score = w.path*path_term+w.parallel_force*parallel_term+ ...
    w.force_norm*force_term+w.force_change*force_change+ ...
    w.posture_change*posture_change+w.rom_margin*margin_term;
end


function derivative = differentiate_pp(pp)
[breaks, coefficients, ~, order, dimension] = unmkpp(pp);
powers = order-1:-1:1;
derivative_coefficients = coefficients(:, 1:end-1).*powers;
derivative = mkpp(breaks, derivative_coefficients, dimension);
end
