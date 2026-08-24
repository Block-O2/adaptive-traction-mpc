function x_next = human_two_link_v2_rk4_step(rhs, t, x, dt)
%HUMAN_TWO_LINK_V2_RK4_STEP Deterministic fixed-step classical RK4.

if ~isscalar(dt) || ~isfinite(dt) || dt <= 0
    error('HumanTwoLinkV2:InvalidTimeStep', ...
        'dt must be positive and finite.');
end
k1 = rhs(t, x);
k2 = rhs(t+dt/2, x+dt*k1/2);
k3 = rhs(t+dt/2, x+dt*k2/2);
k4 = rhs(t+dt, x+dt*k3);
x_next = x+dt*(k1+2*k2+2*k3+k4)/6;
end
