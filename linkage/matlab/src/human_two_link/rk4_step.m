function x_next = rk4_step(rhs, t, x, dt)
%RK4_STEP One deterministic fixed-step classical Runge-Kutta update.

if ~isscalar(dt) || ~isfinite(dt) || dt <= 0
    error('HumanTwoLink:InvalidTimeStep', 'dt must be positive and finite.');
end

k1 = rhs(t, x);
k2 = rhs(t + dt/2, x + dt*k1/2);
k3 = rhs(t + dt/2, x + dt*k2/2);
k4 = rhs(t + dt, x + dt*k3);
x_next = x + dt*(k1 + 2*k2 + 2*k3 + k4)/6;
end
