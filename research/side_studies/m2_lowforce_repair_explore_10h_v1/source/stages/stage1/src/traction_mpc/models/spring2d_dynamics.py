"""2D moving-base polar spring-rod dynamics with gravity."""

from __future__ import annotations

from typing import Any

import numpy as np

from traction_mpc.common.types import Spring2DAction, Spring2DState


ArrayLike = np.ndarray | list[float] | tuple[float, ...] | Spring2DState
ActionLike = np.ndarray | list[float] | tuple[float, ...] | Spring2DAction


def _p(params: dict[str, Any], name: str, default: float | None = None) -> float:
    if name in params:
        return float(params[name])
    if default is not None:
        return float(default)
    raise KeyError(f"Missing spring2d parameter: {name}")


def _state_array(state: ArrayLike) -> np.ndarray:
    if isinstance(state, Spring2DState):
        return state.as_array()
    return np.asarray(state, dtype=float)


def _action_array(action: ActionLike) -> np.ndarray:
    if isinstance(action, Spring2DAction):
        return action.as_array()
    return np.asarray(action, dtype=float)


def compute_base_kinematics(theta: float, params: dict[str, Any]) -> dict[str, float]:
    """Compute x_b(theta), dx_b/dtheta, and d2x_b/dtheta2."""

    theta_init = _p(params, "theta_init", 0.0)
    x_base0 = _p(params, "base_x0", 0.0)
    mode = str(params.get("base_mode", "linear_sin"))

    if mode == "linear_sin":
        amp = _p(params, "base_slide_amp", 0.0)
        x_b = x_base0 + amp * (np.sin(theta) - np.sin(theta_init))
        a = amp * np.cos(theta)
        ap = -amp * np.sin(theta)
    elif mode == "tanh_sin":
        x_range = _p(params, "base_x_range", 0.0)
        beta = _p(params, "base_slide_beta", 1.0)
        z = beta * (np.sin(theta) - np.sin(theta_init))
        tanh_z = np.tanh(z)
        sech2 = 1.0 / np.cosh(z) ** 2
        x_b = x_base0 + x_range * tanh_z
        a = x_range * beta * sech2 * np.cos(theta)
        ap = x_range * beta * sech2 * (
            -np.sin(theta) - 2.0 * beta * tanh_z * np.cos(theta) ** 2
        )
    else:
        raise ValueError(f"Unknown base_mode '{mode}'. Use 'linear_sin' or 'tanh_sin'.")

    return {"x_b": float(x_b), "a": float(a), "ap": float(ap)}


def compute_base_position(theta: float, params: dict[str, Any]) -> np.ndarray:
    """Compute moving base position for the current angle."""

    kin = compute_base_kinematics(theta, params)
    y_base0 = _p(params, "base_y0", 0.0)
    return np.array([kin["x_b"], y_base0], dtype=float)


def compute_directions(theta: float) -> tuple[np.ndarray, np.ndarray]:
    """Return radial and tangential unit vectors."""

    e_rad = np.array([np.cos(theta), np.sin(theta)], dtype=float)
    e_tan = np.array([-np.sin(theta), np.cos(theta)], dtype=float)
    return e_rad, e_tan


def compute_positions(state: ArrayLike, params: dict[str, Any]) -> dict[str, np.ndarray]:
    """Compute base, tip, and contact positions in world coordinates."""

    theta, _, r, _ = _state_array(state)
    rho = _p(params, "rho")
    base_pos = compute_base_position(theta, params)
    e_rad, e_tan = compute_directions(theta)
    tip_pos = base_pos + r * e_rad
    contact_pos = base_pos + rho * r * e_rad
    return {
        "base_pos": base_pos,
        "tip_pos": tip_pos,
        "contact_pos": contact_pos,
        "e_rad": e_rad,
        "e_tan": e_tan,
    }


def compute_moving_base_terms(
    state: ArrayLike,
    action: ActionLike,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Compute M, Q, h and solved accelerations for the moving-base model."""

    theta, omega, r, r_dot = _state_array(state)
    F_tan, F_rad = _action_array(action)

    m = _p(params, "m")
    g = _p(params, "g")
    L0 = _p(params, "L0")
    k = _p(params, "k")
    b_r = _p(params, "b_r")
    b_theta = _p(params, "b_theta")
    rho = _p(params, "rho")

    r_eff = max(float(r), 1e-6)
    kin = compute_base_kinematics(theta, params)
    a = kin["a"]
    ap = kin["ap"]

    M11 = m / 3.0
    M12 = 0.5 * m * a * np.cos(theta)
    M22 = m * (r_eff**2 / 3.0 - a * r_eff * np.sin(theta) + a**2)
    M = np.array([[M11, M12], [M12, M22]], dtype=float)

    Q_r = rho * F_rad
    Q_theta = rho * r_eff * F_tan + a * (F_rad * np.cos(theta) - F_tan * np.sin(theta))
    Q = np.array([Q_r, Q_theta], dtype=float)

    h_r = (
        b_r * r_dot
        + k * (r_eff - L0)
        + 0.5 * m * g * np.sin(theta)
        - (m / 3.0) * r_eff * omega**2
        + 0.5 * m * ap * np.cos(theta) * omega**2
    )
    h_theta = (
        b_theta * omega
        + 0.5 * m * g * r_eff * np.cos(theta)
        + (2.0 / 3.0) * m * r_eff * r_dot * omega
        - m * a * np.sin(theta) * r_dot * omega
        - 0.5 * m * r_eff * a * np.cos(theta) * omega**2
        - 0.5 * m * r_eff * ap * np.sin(theta) * omega**2
        + m * a * ap * omega**2
    )
    h = np.array([h_r, h_theta], dtype=float)

    r_ddot, omega_dot = np.linalg.solve(M, Q - h)
    return {
        "M": M,
        "Q": Q,
        "h": h,
        "r_ddot": float(r_ddot),
        "omega_dot": float(omega_dot),
        "M11": float(M11),
        "M12": float(M12),
        "M22": float(M22),
        "Q_r": float(Q_r),
        "Q_theta": float(Q_theta),
        "h_r": float(h_r),
        "h_theta": float(h_theta),
        "base_x": float(kin["x_b"]),
        "base_a": float(a),
        "base_ap": float(ap),
    }


def compute_derivatives(state: ArrayLike, action: ActionLike, params: dict[str, Any]) -> np.ndarray:
    """Compute [theta_dot, omega_dot, r_dot, r_ddot]."""

    theta, omega, r, r_dot = _state_array(state)
    terms = compute_moving_base_terms(state, action, params)
    return np.array([omega, terms["omega_dot"], r_dot, terms["r_ddot"]], dtype=float)


def step_dynamics(
    state: ArrayLike,
    action: ActionLike,
    dt: float,
    params: dict[str, Any],
) -> np.ndarray:
    """Advance dynamics using RK4 integration."""

    x = _state_array(state)
    u = _action_array(action)
    h = float(dt)

    k1 = compute_derivatives(x, u, params)
    k2 = compute_derivatives(x + 0.5 * h * k1, u, params)
    k3 = compute_derivatives(x + 0.5 * h * k2, u, params)
    k4 = compute_derivatives(x + h * k3, u, params)
    x_next = x + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    x_next[2] = max(x_next[2], 1e-6)
    return x_next


def compute_physical_info(
    state: ArrayLike,
    action: ActionLike,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Return derived physical quantities for logging and visualization."""

    theta, omega, r, r_dot = _state_array(state)
    F_tan, F_rad = _action_array(action)

    m = _p(params, "m")
    g = _p(params, "g")
    L0 = _p(params, "L0")
    k = _p(params, "k")
    rho = _p(params, "rho")
    r_eff = max(float(r), 1e-6)

    terms = compute_moving_base_terms(state, action, params)
    positions = compute_positions(state, params)
    e_rad = positions["e_rad"]
    e_tan = positions["e_tan"]
    force_xy = F_rad * e_rad + F_tan * e_tan

    I = (1.0 / 3.0) * m * r_eff**2
    spring_force = -k * (r_eff - L0)
    gravity_force = -0.5 * m * g * np.sin(theta)
    gravity_torque = -0.5 * m * g * r_eff * np.cos(theta)
    centrifugal_term = (m / 3.0) * r_eff * omega**2

    return {
        "theta": float(theta),
        "omega": float(omega),
        "r": float(r),
        "r_dot": float(r_dot),
        "delta_r": float(r - L0),
        "I": float(I),
        "M_r": float(terms["M11"]),
        "base_x": float(terms["base_x"]),
        "base_a": float(terms["base_a"]),
        "base_ap": float(terms["base_ap"]),
        "M11": float(terms["M11"]),
        "M12": float(terms["M12"]),
        "M22": float(terms["M22"]),
        "Q_r": float(terms["Q_r"]),
        "Q_theta": float(terms["Q_theta"]),
        "h_r": float(terms["h_r"]),
        "h_theta": float(terms["h_theta"]),
        "spring_force": float(spring_force),
        "gravity_force": float(gravity_force),
        "gravity_torque": float(gravity_torque),
        "centrifugal_term": float(centrifugal_term),
        "radial_accel": float(terms["r_ddot"]),
        "angular_accel": float(terms["omega_dot"]),
        "r_ddot": float(terms["r_ddot"]),
        "omega_dot": float(terms["omega_dot"]),
        "base_pos": positions["base_pos"],
        "tip_pos": positions["tip_pos"],
        "contact_pos": positions["contact_pos"],
        "e_rad": e_rad,
        "e_tan": e_tan,
        "force_xy": force_xy,
        "F_tan": float(F_tan),
        "F_rad": float(F_rad),
        "rho": float(rho),
    }
