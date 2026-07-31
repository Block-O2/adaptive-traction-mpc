function [q_ref, dq_ref, ddq_ref, metadata] = ...
        rehabilitation_reference_trajectory(t, trajectory_name)
%REHABILITATION_REFERENCE_TRAJECTORY Smooth hold-move-hold-return profiles.

if ~isscalar(t) || ~isfinite(t) || t < 0
    error('IdealEndpointForce:InvalidReferenceTime', ...
        'Reference time must be a finite nonnegative scalar.');
end
trajectory_name = string(trajectory_name);

switch trajectory_name
    case "knee_dominant"
        q_start = deg2rad([20; 25]);
        q_peak = deg2rad([24; 75]);
        path_slope = NaN;
        task_description = ...
            "Knee-dominant flexion with limited hip following.";
    case "coordinated_path"
        q_start = deg2rad([18; 25]);
        q_peak = deg2rad([42; 75]);
        path_slope = (q_peak(2)-q_start(2)) / ...
            (q_peak(1)-q_start(1));
        task_description = ...
            "Coordinated hip-knee straight path in joint space.";
    case "conflicting_boundary"
        q_start = deg2rad([20; 25]);
        q_peak = deg2rad([78; 1]);
        path_slope = NaN;
        task_description = ...
            "Deliberately conflicting target near contact-map singularity.";
    otherwise
        error('IdealEndpointForce:UnknownTrajectory', ...
            'Unknown rehabilitation trajectory: %s', trajectory_name);
end

[progress, progress_rate, progress_acceleration, phase] = ...
    smooth_hold_move_return(t);
delta = q_peak - q_start;
q_ref = q_start + delta*progress;
dq_ref = delta*progress_rate;
ddq_ref = delta*progress_acceleration;

metadata = struct();
metadata.name = trajectory_name;
metadata.description = task_description;
metadata.q_start = q_start;
metadata.q_peak = q_peak;
metadata.path_origin = q_start;
metadata.path_slope = path_slope;
metadata.phase = phase;
metadata.progress = progress;
metadata.move_start = 1.0;
metadata.peak_start = 3.5;
metadata.return_start = 4.5;
metadata.final_hold_start = 7.0;
metadata.t_final = 8.0;
end


function [alpha, dalpha, ddalpha, phase] = smooth_hold_move_return(t)
move_start = 1.0;
peak_start = 3.5;
return_start = 4.5;
final_hold_start = 7.0;
move_duration = peak_start - move_start;
return_duration = final_hold_start - return_start;

if t < move_start
    alpha = 0;
    dalpha = 0;
    ddalpha = 0;
    phase = "initial_hold";
elseif t < peak_start
    r = (t-move_start) / move_duration;
    [s, ds, dds] = quintic_blend(r);
    alpha = s;
    dalpha = ds / move_duration;
    ddalpha = dds / move_duration^2;
    phase = "smooth_flexion";
elseif t < return_start
    alpha = 1;
    dalpha = 0;
    ddalpha = 0;
    phase = "peak_hold";
elseif t < final_hold_start
    r = (t-return_start) / return_duration;
    [s, ds, dds] = quintic_blend(r);
    alpha = 1-s;
    dalpha = -ds / return_duration;
    ddalpha = -dds / return_duration^2;
    phase = "smooth_return";
else
    alpha = 0;
    dalpha = 0;
    ddalpha = 0;
    phase = "final_hold";
end
end


function [s, ds, dds] = quintic_blend(r)
s = 10*r^3 - 15*r^4 + 6*r^5;
ds = 30*r^2 - 60*r^3 + 30*r^4;
dds = 60*r - 180*r^2 + 120*r^3;
end
