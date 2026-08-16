function residual = dynamic_robust_v1_adaptive_window_residual( ...
        theta, state, nominal, h_hip, config)
%DYNAMIC_ROBUST_V1_ADAPTIVE_WINDOW_RESIDUAL Exact one-step RK4 residual.
%
% Each transition uses only the observed current state, applied robot force,
% and subsequently observed next state. The fixed bed/contact model and known
% hip calibration are part of the existing experiment model. No true case
% parameters, scenario identity, or future state beyond x_{k+1} are inputs.

parameters=dynamic_robust_v1_adaptive_apply_theta(nominal,theta);
count=size(state.x,2);residual=zeros(4*count,1);
for index=1:count
    held_force=state.u(:,index);
    rhs=@(~,x)bed_supported_v1_dynamics( ...
        x,held_force,h_hip,parameters,config);
    prediction=human_two_link_v2_rk4_step( ...
        rhs,0,state.x(:,index),config.dt);
    error=prediction-state.x_next(:,index);
    % Convert position error to an equivalent velocity over one control step
    % so q and dq residual blocks have the same physical unit.
    residual(4*(index-1)+(1:4))=[error(1:2)/config.dt;error(3:4)];
end
end
