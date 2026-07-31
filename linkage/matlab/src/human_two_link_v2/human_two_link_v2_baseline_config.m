function config = human_two_link_v2_baseline_config()
%HUMAN_TWO_LINK_V2_BASELINE_CONFIG Fixed nominal plant-validation settings.

config = struct();
config.trajectory_name = "slow_passive_flexion_v2";
config.dt = 0.002;
config.t_final = 16.0;
config.Kp = diag([180, 140]);
config.Kd = diag([28, 22]);
config.rom_tolerance = 1e-10;
end
