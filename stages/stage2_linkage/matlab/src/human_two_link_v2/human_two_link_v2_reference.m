function [q_ref, dq_ref, ddq_ref, phase, progress, jerk_ref] = ...
        human_two_link_v2_reference(t, trajectory_name)
%HUMAN_TWO_LINK_V2_REFERENCE Slow synchronous minimum-jerk engineering path.

if ~isscalar(t) || ~isfinite(t) || t < 0
    error('HumanTwoLinkV2:InvalidReferenceTime', ...
        'Reference time must be a finite nonnegative scalar.');
end
trajectory_name = string(trajectory_name);
if trajectory_name ~= "slow_passive_flexion_v2"
    error('HumanTwoLinkV2:UnknownTrajectory', ...
        'Unknown V2 trajectory: %s', trajectory_name);
end

q_start = deg2rad([5; 10]);
q_peak = deg2rad([45; 84]);
delta = q_peak-q_start;
[progress, progress_rate, progress_acceleration, ...
    progress_jerk, phase] = progress_profile(t);
q_ref = q_start+delta*progress;
dq_ref = delta*progress_rate;
ddq_ref = delta*progress_acceleration;
jerk_ref = delta*progress_jerk;
end


function [alpha, dalpha, ddalpha, dddalpha, phase] = progress_profile(t)
initial_hold_end = 1.0;
flexion_end = 7.5;
peak_hold_end = 8.5;
return_end = 15.0;
flexion_duration = 6.5;
return_duration = 6.5;

if t < initial_hold_end
    alpha = 0;
    dalpha = 0;
    ddalpha = 0;
    dddalpha = 0;
    phase = "initial_hold";
elseif t < flexion_end
    r = (t-initial_hold_end)/flexion_duration;
    [s, ds, dds, ddds] = quintic_blend(r);
    alpha = s;
    dalpha = ds/flexion_duration;
    ddalpha = dds/flexion_duration^2;
    dddalpha = ddds/flexion_duration^3;
    phase = "flexion";
elseif t < peak_hold_end
    alpha = 1;
    dalpha = 0;
    ddalpha = 0;
    dddalpha = 0;
    phase = "peak_hold";
elseif t < return_end
    r = (t-peak_hold_end)/return_duration;
    [s, ds, dds, ddds] = quintic_blend(r);
    alpha = 1-s;
    dalpha = -ds/return_duration;
    ddalpha = -dds/return_duration^2;
    dddalpha = -ddds/return_duration^3;
    phase = "return";
else
    alpha = 0;
    dalpha = 0;
    ddalpha = 0;
    dddalpha = 0;
    phase = "final_hold";
end
end


function [s, ds, dds, ddds] = quintic_blend(r)
s = 10*r^3-15*r^4+6*r^5;
ds = 30*r^2-60*r^3+30*r^4;
dds = 60*r-180*r^2+120*r^3;
ddds = 60-360*r+360*r^2;
end
