function [q_ref, dq_ref, ddq_ref] = reference_trajectory( ...
        t, trajectory_name)
%REFERENCE_TRAJECTORY Deterministic smooth engineering validation references.

trajectory_name = string(trajectory_name);

switch trajectory_name
    case "slow_coordinated"
        omega = 2*pi*0.12;
        q_ref = deg2rad([25; 35]) - ...
            deg2rad([20; 30]) * cos(omega*t);
        dq_ref = deg2rad([20; 30]) * omega * sin(omega*t);
        ddq_ref = deg2rad([20; 30]) * omega^2 * cos(omega*t);

    case "faster_low_amplitude"
        omega = 2*pi*0.25;
        phase = 0.20;
        q_ref = deg2rad([20; 30]) + ...
            deg2rad([12; 15]) .* sin(omega*t + [0; phase]);
        dq_ref = deg2rad([12; 15]) .* omega .* ...
            cos(omega*t + [0; phase]);
        ddq_ref = -deg2rad([12; 15]) .* omega^2 .* ...
            sin(omega*t + [0; phase]);

    case "phase_shifted"
        omega = 2*pi*0.16;
        phases = [0; -pi/3];
        q_ref = deg2rad([25; 35]) + ...
            deg2rad([18; 22]) .* sin(omega*t + phases);
        dq_ref = deg2rad([18; 22]) .* omega .* ...
            cos(omega*t + phases);
        ddq_ref = -deg2rad([18; 22]) .* omega^2 .* ...
            sin(omega*t + phases);

    otherwise
        error('HumanTwoLink:UnknownTrajectory', ...
            'Unknown reference trajectory: %s', trajectory_name);
end
end
