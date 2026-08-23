function near_extension_protective_mode_create_gif(result, gif_path)
%NEAR_EXTENSION_PROTECTIVE_MODE_CREATE_GIF Synchronized sanity visualization.

p = result.parameters; t = result.t; c = result.config;
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [20 20 1500 820]);
layout = tiledlayout(fig, 3, 2, 'TileSpacing', 'compact', 'Padding', 'compact');
ax = nexttile(layout, 1, [3 1]); hold(ax, 'on'); axis(ax, 'equal'); grid(ax, 'on');
reach = p.L1+p.L2; xlim(ax, [-0.1 reach+0.15]); ylim(ax, [-0.1 reach+0.2]);
plot(ax, [-0.15 reach+0.2], [0 0], 'k-', 'LineWidth', 5);
leg = plot(ax, nan, nan, 'o-', 'LineWidth', 5, 'MarkerSize', 9);
command_leg = plot(ax, nan, nan, '--', 'LineWidth', 2, 'Color', [.2 .6 .9]);
info = text(ax, .02, .98, '', 'Units', 'normalized', ...
    'VerticalAlignment', 'top', 'Interpreter', 'none');
title(ax, 'Command-interface sanity (not contact dynamics)');

qax = nexttile(layout, 2); hold(qax, 'on'); grid(qax, 'on');
plot(qax, t, rad2deg(result.q_cmd(2, :)), 'Color', [.85 .75 .75]);
plot(qax, [t(1) t(end)], c.q_switch_deg*[1 1], 'k--');
plot(qax, [t(1) t(end)], c.q_terminal_deg*[1 1], 'k:');
q1 = plot(qax, nan, nan, 'b-', 'LineWidth', 1.5);
q2 = plot(qax, nan, nan, 'r-', 'LineWidth', 1.5);
ylabel(qax, 'angle (deg)'); title(qax, 'Measured state and issued q2 command');

vax = nexttile(layout, 4); hold(vax, 'on'); grid(vax, 'on');
v1 = plot(vax, nan, nan, 'b-', 'LineWidth', 1.3);
v2 = plot(vax, nan, nan, 'r-', 'LineWidth', 1.3);
ylabel(vax, 'command velocity (deg/s)'); title(vax, 'Smooth kinematic command');

sax = nexttile(layout, 6); hold(sax, 'on'); grid(sax, 'on');
mode_values = mode_codes(result.mode); stairs(sax, t, mode_values, ...
    'Color', [.6 .6 .6]); state_line = stairs(sax, nan, nan, 'k-', 'LineWidth', 1.8);
force_line = plot(sax, nan, nan, 'm-', 'LineWidth', 1.2);
ylabel(sax, 'state code / |F|inf / 50'); xlabel(sax, 'time (s)');
title(sax, 'State machine and independent force monitor');
for panel = [qax vax sax], xlim(panel, [t(1) t(end)]); end

frames = unique(round(linspace(1, numel(t), min(180, numel(t)))));
for frame_index = 1:numel(frames)
    k = frames(frame_index);
    [actual_points, command_points] = leg_points(result.q(:, k), ...
        result.q_cmd(:, k), p);
    set(leg, 'XData', actual_points(1, :), 'YData', actual_points(2, :));
    set(command_leg, 'XData', command_points(1, :), ...
        'YData', command_points(2, :));
    set(info, 'String', sprintf(['t=%.2f s  segment=%s\nstate=%s\n' ...
        'command=%s\nq=[%.2f %.2f] deg\n|Fmeas|inf=%.1f N  inversion=%d'], ...
        t(k), result.segment(k), result.mode(k), result.actuation_mode(k), ...
        rad2deg(result.q(1, k)), rad2deg(result.q(2, k)), ...
        norm(result.measured_force_N(:, k), Inf), ...
        result.force_inversion_called(k)));
    set(q1, 'XData', t(1:k), 'YData', rad2deg(result.q(1, 1:k)));
    set(q2, 'XData', t(1:k), 'YData', rad2deg(result.q(2, 1:k)));
    set(v1, 'XData', t(1:k), 'YData', rad2deg(result.dq_cmd(1, 1:k)));
    set(v2, 'XData', t(1:k), 'YData', rad2deg(result.dq_cmd(2, 1:k)));
    set(state_line, 'XData', t(1:k), 'YData', mode_values(1:k));
    set(force_line, 'XData', t(1:k), ...
        'YData', max(abs(result.measured_force_N(:, 1:k)), [], 1)/50);
    frame = getframe(fig); image_data = frame2im(frame);
    [indexed, map] = rgb2ind(image_data, 256);
    if frame_index == 1
        imwrite(indexed, map, gif_path, 'gif', 'LoopCount', Inf, ...
            'DelayTime', .08);
    else
        imwrite(indexed, map, gif_path, 'gif', 'WriteMode', 'append', ...
            'DelayTime', .08);
    end
end
close(fig);
end


function [actual, command] = leg_points(q, q_command, p)
hip = [0; 0.08];
actual = points(q, p, hip); command = points(q_command, p, hip);
end


function value = points(q, p, hip)
knee = hip+p.L1*[cos(q(1)); sin(q(1))];
ankle = knee+p.L2*[cos(q(1)-q(2)); sin(q(1)-q(2))];
value = [hip knee ankle];
end


function codes = mode_codes(modes)
names = ["BED_START", "KINEMATIC_TAKEOFF", "BLEND_TO_NORMAL", ...
    "NORMAL_REHAB", "BLEND_TO_LANDING", "KINEMATIC_LANDING", ...
    "TERMINAL", "PROTECTIVE_STOP"];
codes = zeros(size(modes));
for index = 1:numel(names), codes(modes == names(index)) = index; end
end
