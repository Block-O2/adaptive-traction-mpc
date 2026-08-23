function q = near_extension_protective_mode_coordinated_posture(q2)
%NEAR_EXTENSION_PROTECTIVE_MODE_COORDINATED_POSTURE Extend taught coordination.
%
% This geometric continuation is used only by the kinematic sanity patch.
% The retained taught trajectory itself is not modified.

q2_start = deg2rad(10); q2_peak = deg2rad(84);
q1_start = deg2rad(5); q1_peak = deg2rad(45);
q1 = q1_start+(q2-q2_start)*(q1_peak-q1_start)/(q2_peak-q2_start);
q = [q1; q2];
end
