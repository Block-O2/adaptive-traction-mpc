function target = bed_supported_v1_preposition_target(p, config, h_hip, previous_force)
%BED_SUPPORTED_V1_PREPOSITION_TARGET Search initial tube for viable suspension.

if nargin < 4, previous_force = zeros(2,1); end
nominal = hybrid_tube_v1_task_path(0);
tube = hybrid_tube_v1_tube_schedule(0, nominal.q, config);
step = config.candidate_step_deg;
offset1 = offsets(rad2deg(tube(1)), step);
offset2 = offsets(rad2deg(tube(2)), step);
best_score = Inf; found = false;
best = struct();
for d1 = offset1
    for d2 = offset2
        q = nominal.q+deg2rad([d1;d2]);
        if any(q < p.q_min) || any(q > p.q_max), continue; end
        [~, passive] = human_two_link_v2_passive_torque(q, zeros(2,1), p);
        if any(passive.soft.active), continue; end
        soft_lower = p.q_min+p.soft_limit_margin+ ...
            config.preposition_soft_clearance_rad;
        soft_upper = p.q_max-p.soft_limit_margin- ...
            config.preposition_soft_clearance_rad;
        soft_margin = min(q-soft_lower, soft_upper-q);
        if any(soft_margin < 0), continue; end
        hold = bed_supported_v1_robot_only_hold(q, p, config);
        point = hold.point;
        force_margin = config.force_bound_N-max(abs(point.force_local));
        robust = hold.feasible && force_margin >= ...
            config.preposition_force_margin_N && ...
            point.bounded_residual_norm(1) <= ...
            config.plan_residual_tolerance_Nm;
        if ~robust, continue; end
        bed = bed_supported_v1_contact(q, zeros(2,1), h_hip, p, config);
        if bed.total_normal_force_N < config.contact_force_threshold_N
            continue;
        end
        normalized_deviation = (q-nominal.q)./max(tube,deg2rad(1));
        score = sum(normalized_deviation.^2)+ ...
            3*(point.F_parallel/config.force_bound_N)^2+ ...
            2*(point.force_norm/(sqrt(2)*config.force_bound_N))^2+ ...
            0.5*(norm(point.force_local-previous_force)/ ...
            config.force_bound_N)^2+ ...
            sum((config.preposition_soft_clearance_rad./ ...
            max(soft_margin,config.preposition_soft_clearance_rad)).^2);
        if score < best_score
            best_score = score; found = true;
            best = struct('q',q,'force_N',point.force_local, ...
                'force_norm_N',point.force_norm, ...
                'bounded_residual_Nm',point.bounded_residual_norm(1), ...
                'sigma_min',point.sigma_min,'condition_number', ...
                point.condition_number,'force_margin_N',force_margin, ...
                'rom_margin_rad',min(q-p.q_min,p.q_max-q), ...
                'soft_margin_rad',soft_margin,'bed_force_N', ...
                bed.total_normal_force_N,'score',score);
        end
    end
end
target = struct('found',found,'nominal_q',nominal.q, ...
    'tube_rad',tube,'searched_count',numel(offset1)*numel(offset2));
if found
    names = fieldnames(best);
    for k=1:numel(names), target.(names{k})=best.(names{k}); end
else
    target.q = [NaN;NaN]; target.force_N = [NaN;NaN];
    target.force_norm_N = NaN; target.bounded_residual_Nm = NaN;
    target.sigma_min = NaN; target.condition_number = NaN;
    target.force_margin_N = NaN; target.rom_margin_rad = [NaN;NaN];
    target.soft_margin_rad = [NaN;NaN]; target.bed_force_N = NaN;
    target.score = Inf;
end
end


function values = offsets(cap, step)
if cap <= 1e-12
    values = 0;
else
    values = unique([-cap:step:cap,0,cap]);
end
end
