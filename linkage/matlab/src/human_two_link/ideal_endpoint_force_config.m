function config = ideal_endpoint_force_config()
%IDEAL_ENDPOINT_FORCE_CONFIG Fixed shared controller and experiment settings.

config = struct();
config.dt = 0.002;
config.t_final = 8.0;

% Acceleration-domain tracking law: ddq_cmd = ddq_ref - Kp*e - Kd*de.
config.accel_Kp = diag([36, 49]);
config.accel_Kd = diag([12, 14]);

% One fixed generalized-torque weighting is used for every task/profile.
config.W_tau = diag([0.55, 1.00]);
config.lambda_u = 2.0e-4;
config.lambda_du = 2.0e-3;

% Ideal bidirectional cuff-force and component slew limits.
config.u_min = [-300; -300];
config.u_max = [ 300;  300];
config.du_max = [2500; 2500];

% Existing oracle controller gains retained from the physical-plant baseline.
config.oracle_Kp = diag([180, 140]);
config.oracle_Kd = diag([28, 22]);

config.limit_tolerance = 1e-10;
config.saturation_tolerance = 1e-8;
end
