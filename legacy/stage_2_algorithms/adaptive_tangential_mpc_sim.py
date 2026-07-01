"""
Stage II: Noise-robust adaptive tangential MPC simulation.

This script keeps the rod/spring model from run_traction_sim.py and replaces
the ESC controller with a single-loop controller that pushes continuously while
updating its force direction from noisy observations.

Output format mirrors run_traction_sim.py:
- terminal summary with target time, radial deformation, fitted radius, phi
- GIF saved next to this script
"""

import os
from collections import deque

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

OUT_GIF = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "rod_traction_adaptive_mpc.gif",
)

# Physical parameters: same model as run_traction_sim.py
L = 0.35
m_rod = 1.5
g = 9.81
I_rod = (1 / 3) * m_rod * L**2

k_r = 100.0
c_r = 20.0

s_frac = 0.9
s = s_frac * L

delta_slide_true = 0.03
delta_slide_max = 0.05

dt = 1 / 50
theta_target = np.pi / 2

# Force and sensor settings
F_MAX = 9.5
F_T_MAX = 9.5
F_R_MAX = 0.8

noise_pos = 5e-4
noise_vel = 1e-3
noise_force = 0.05

np.random.seed(42)


class RodEnv:
    def __init__(self):
        self.theta = 0.05
        self.theta_dot = 0.0
        self.delta_r = 0.0
        self.delta_r_dot = 0.0

    def hinge_pos(self):
        xh = np.clip(
            delta_slide_true * np.sin(self.theta),
            -delta_slide_max,
            delta_slide_max,
        )
        return np.array([xh, 0.0])

    def contact_pos_true(self):
        h = self.hinge_pos()
        r = s + self.delta_r
        return h + r * np.array([np.cos(self.theta), np.sin(self.theta)])

    def contact_vel_true(self):
        r = s + self.delta_r
        e_r = np.array([np.cos(self.theta), np.sin(self.theta)])
        e_t = np.array([-np.sin(self.theta), np.cos(self.theta)])
        dh = np.array([delta_slide_true * np.cos(self.theta) * self.theta_dot, 0.0])
        return dh + r * self.theta_dot * e_t + self.delta_r_dot * e_r

    def observe_pos(self):
        return self.contact_pos_true() + np.random.randn(2) * noise_pos

    def observe_vel(self):
        return self.contact_vel_true() + np.random.randn(2) * noise_vel

    def observe_force(self, F_world):
        return F_world + np.random.randn(2) * noise_force

    def step(self, F_world):
        e_r = np.array([np.cos(self.theta), np.sin(self.theta)])
        e_t = np.array([-np.sin(self.theta), np.cos(self.theta)])

        F_t = np.dot(F_world, e_t)
        F_r = np.dot(F_world, e_r)

        tau_F = F_t * (s + self.delta_r)
        tau_grav = -m_rod * g * (L / 2.0) * np.cos(self.theta)
        theta_ddot = (tau_F + tau_grav) / I_rod
        delta_r_ddot = (F_r - k_r * self.delta_r - c_r * self.delta_r_dot) / m_rod

        self.theta_dot += theta_ddot * dt
        self.theta += self.theta_dot * dt
        self.delta_r_dot += delta_r_ddot * dt
        self.delta_r += self.delta_r_dot * dt

        self.theta = float(np.clip(self.theta, 0.0, np.pi))
        if self.theta in (0.0, np.pi):
            self.theta_dot = 0.0

        return self.theta, self.delta_r


def fit_circle_taubin(points):
    pts = np.array(points)
    if len(pts) < 5:
        return None
    x, y = pts[:, 0], pts[:, 1]
    mx, my = x.mean(), y.mean()
    u, v = x - mx, y - my
    Suu = np.dot(u, u)
    Svv = np.dot(v, v)
    Suv = np.dot(u, v)
    A = np.array([[Suu, Suv], [Suv, Svv]])
    b = np.array(
        [
            0.5 * (np.dot(u * u, u) + np.dot(u, v * v)),
            0.5 * (np.dot(v * v, v) + np.dot(v, u * u)),
        ]
    )
    try:
        uc, vc = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return None
    cx = uc + mx
    cy = vc + my
    r = np.sqrt(uc**2 + vc**2 + (Suu + Svv) / len(x))
    residual = np.std(np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r)
    return cx, cy, r, residual


class RLS:
    def __init__(self, theta0, p0=200.0, forgetting=0.992):
        self.theta = np.array(theta0, dtype=float)
        self.P = np.eye(len(theta0)) * p0
        self.lam = forgetting

    def update(self, phi, y):
        phi = np.array(phi, dtype=float)
        denom = self.lam + phi @ self.P @ phi
        if denom < 1e-9:
            return
        K = self.P @ phi / denom
        err = y - phi @ self.theta
        self.theta += K * err
        self.P = (self.P - np.outer(K, phi) @ self.P) / self.lam


class AdaptiveTangentialMPC:
    def __init__(self):
        self.pos_f = None
        self.vel_f = np.zeros(2)
        self.pos_hist = deque(maxlen=28)

        self.center = np.array([0.0, 0.0])
        self.radius = s * 0.9
        self.radius_ref = s * 0.9
        self.conf = 0.0

        self.e_t = np.array([0.0, 1.0])
        self.e_r = np.array([1.0, 0.0])

        self.theta_hat = 0.05
        self.omega_hat = 0.0
        self.delta_hat = 0.0
        self.delta_dot_hat = 0.0

        self.prev_omega = 0.0
        self.prev_delta_dot = 0.0
        self.prev_cmd = np.zeros(2)
        self.prev_force_meas = np.zeros(2)

        # Local models:
        # theta_ddot ~= a_t F_t + b_g - d_t omega
        # delta_ddot ~= a_r F_r - k_eff delta - c_eff delta_dot
        self.rls_t = RLS([4.5, -30.0, 1.0])
        self.rls_r = RLS([0.65, 65.0, 12.0])

        self.phi_log = [np.pi / 2]
        self.ft_log = []
        self.fr_log = []
        self.conf_log = []

    def _regularize_tangent(self, et, er_hint=None):
        et = np.array(et, dtype=float)
        n = np.linalg.norm(et)
        if n < 1e-8:
            return self.e_t, self.e_r
        et = et / n

        # The task is positive lifting in the vertical plane. A valid tangent
        # should point upward and leftward; right-up commands inject radial load.
        if et[1] < 0:
            et = -et
        et[0] = min(et[0], -0.02)
        et = et / max(np.linalg.norm(et), 1e-8)

        er = np.array([et[1], -et[0]])
        if er_hint is not None and np.dot(er, er_hint) < 0:
            er = -er
        return et, er

    def _filter_observation(self, pos_m, vel_m):
        if self.pos_f is None:
            self.pos_f = pos_m.copy()
            self.vel_f = vel_m.copy()
        alpha_p = 0.35
        alpha_v = 0.25
        self.pos_f = alpha_p * pos_m + (1 - alpha_p) * self.pos_f
        self.vel_f = alpha_v * vel_m + (1 - alpha_v) * self.vel_f
        self.pos_hist.append(self.pos_f.copy())

    def _update_geometry(self):
        fit = fit_circle_taubin(self.pos_hist)
        if fit is None:
            return

        cx, cy, r, residual = fit
        pts = np.array(self.pos_hist)
        span = np.linalg.norm(pts[-1] - pts[0])
        residual_score = np.exp(-residual / 0.0025)
        span_score = np.clip((span - 0.01) / 0.05, 0.0, 1.0)
        radius_score = 1.0 if 0.08 < r < 0.8 else 0.0
        conf = float(np.clip(residual_score * span_score * radius_score, 0.0, 1.0))

        alpha = 0.03 + 0.18 * conf
        self.center = (1 - alpha) * self.center + alpha * np.array([cx, cy])
        self.radius = (1 - alpha) * self.radius + alpha * r
        self.conf = conf

        vec = self.pos_f - self.center
        n = np.linalg.norm(vec)
        if n > 1e-6:
            er_arc = vec / n
            et_arc = np.array([-er_arc[1], er_arc[0]])
            et_arc, er_arc = self._regularize_tangent(et_arc, er_arc)

            v_norm = np.linalg.norm(self.vel_f)
            if v_norm > 1e-4:
                et_vel = self.vel_f / v_norm
                et_vel, _ = self._regularize_tangent(et_vel, er_arc)
                gamma = 0.25 + 0.65 * conf
                et = gamma * et_arc + (1 - gamma) * et_vel
                et, er = self._regularize_tangent(et, er_arc)
            else:
                et = et_arc
                er = er_arc

            y_ratio = np.clip(self.pos_f[1] / max(self.radius_ref, 0.08), 0.0, 1.0)
            theta_ground = np.arcsin(y_ratio)
            et_ground = np.array([-np.sin(theta_ground), np.cos(theta_ground)])
            et_ground, _ = self._regularize_tangent(et_ground, er)

            # The hinge is constrained to the ground line in this experiment.
            # This gives a strong tangent cue that is less noisy than local
            # circle fitting when the sliding hinge makes the center nonstatic.
            ground_w = 0.65
            et = ground_w * et_ground + (1.0 - ground_w) * et
            et, er = self._regularize_tangent(et, er)

            self.e_t = et
            self.e_r = er

    def _update_state_estimate(self):
        v_t = float(np.dot(self.vel_f, self.e_t))
        v_r = float(np.dot(self.vel_f, self.e_r))
        r_now = float(np.linalg.norm(self.pos_f - self.center))

        self.omega_hat = v_t / max(self.radius_ref, 0.08)
        if self.omega_hat > -0.25:
            self.theta_hat += self.omega_hat * dt
        self.theta_hat = float(np.clip(self.theta_hat, 0.0, theta_target + 0.2))

        raw_delta = r_now - self.radius_ref
        self.delta_dot_hat = 0.7 * self.delta_dot_hat + 0.3 * v_r
        self.delta_hat = 0.8 * self.delta_hat + 0.2 * raw_delta

        stable_radial = abs(v_r) < 0.01 and abs(self.delta_hat) < 0.015 and self.conf > 0.25
        if stable_radial:
            self.radius_ref = 0.995 * self.radius_ref + 0.005 * r_now

    def _update_models(self, F_meas):
        F_t = float(np.dot(F_meas, self.e_t))
        F_r = float(np.dot(F_meas, self.e_r))
        omega_ddot = (self.omega_hat - self.prev_omega) / dt
        delta_ddot = (self.delta_dot_hat - self.prev_delta_dot) / dt

        if self.conf > 0.18 and abs(F_t) > 1.0 and abs(omega_ddot) < 80.0:
            self.rls_t.update([F_t, 1.0, -self.omega_hat], omega_ddot)

        radial_signal = max(abs(F_r), abs(self.delta_hat) * 100.0, abs(self.delta_dot_hat) * 10.0)
        if self.conf > 0.12 and radial_signal > 0.5 and abs(delta_ddot) < 80.0:
            self.rls_r.update([F_r, -self.delta_hat, -self.delta_dot_hat], delta_ddot)

        self.prev_omega = self.omega_hat
        self.prev_delta_dot = self.delta_dot_hat

    def _predict_cost(self, ft, fr):
        a_t, b_g, d_t = self.rls_t.theta
        a_r, k_eff, c_eff = self.rls_r.theta
        a_t = float(np.clip(a_t, 1.0, 8.0))
        b_g = float(np.clip(b_g, -55.0, 15.0))
        d_t = float(np.clip(d_t, 0.0, 8.0))
        a_r = float(np.clip(a_r, 0.1, 2.0))
        k_eff = float(np.clip(k_eff, 20.0, 180.0))
        c_eff = float(np.clip(c_eff, 2.0, 35.0))

        th = self.theta_hat
        om = self.omega_hat
        dr = self.delta_hat
        vr = self.delta_dot_hat

        cost = 0.0
        horizon = 12
        for _ in range(horizon):
            om += dt * (a_t * ft + b_g - d_t * om)
            th += dt * om
            vr += dt * (a_r * fr - k_eff * dr - c_eff * vr)
            dr += dt * vr

            rem = max(theta_target - th, 0.0)
            cost += 18.0 * rem
            cost += 35000.0 * dr * dr
            cost += 650.0 * vr * vr
            if abs(dr) > 0.010:
                cost += 8e5 * (abs(dr) - 0.010) ** 2

        terminal = max(theta_target - th, 0.0)
        cost += 450.0 * terminal * terminal
        cost += 3.5 * ft * ft + 900.0 * fr * fr

        prev_ft = float(np.dot(self.prev_cmd, self.e_t))
        prev_fr = float(np.dot(self.prev_cmd, self.e_r))
        cost += 10.0 * (ft - prev_ft) ** 2 + 250.0 * (fr - prev_fr) ** 2

        return cost

    def _solve_mpc(self):
        remaining = theta_target - self.theta_hat
        ft_min = 0.0 if remaining > 0.02 else -1.0
        ft_grid = np.linspace(ft_min, F_T_MAX, 21)

        fr_center = -8.0 * self.delta_hat - 2.0 * self.delta_dot_hat
        fr_center = float(np.clip(fr_center, -F_R_MAX, F_R_MAX))
        fr_grid = np.linspace(fr_center - 0.25, fr_center + 0.25, 7)
        fr_grid = np.clip(fr_grid, -F_R_MAX, F_R_MAX)

        best = (np.inf, 0.0, 0.0)
        for ft in ft_grid:
            for fr in fr_grid:
                if np.hypot(ft, fr) > F_MAX:
                    continue
                cost = self._predict_cost(float(ft), float(fr))
                if cost < best[0]:
                    best = (cost, float(ft), float(fr))
        return best[1], best[2]

    def compute(self, pos_m, vel_m, F_prev_meas):
        self._filter_observation(pos_m, vel_m)
        self._update_geometry()
        self._update_state_estimate()
        self._update_models(F_prev_meas)

        ft, fr = self._solve_mpc()
        F_cmd = ft * self.e_t + fr * self.e_r
        norm = np.linalg.norm(F_cmd)
        if norm > F_MAX:
            F_cmd *= F_MAX / norm

        self.prev_cmd = F_cmd.copy()
        self.ft_log.append(ft)
        self.fr_log.append(fr)
        self.conf_log.append(self.conf)
        self.phi_log.append(float(np.arctan2(F_cmd[1], F_cmd[0])))
        return F_cmd


def run_simulation():
    env = RodEnv()
    ctrl = AdaptiveTangentialMPC()

    times = [0.0]
    thetas = [env.theta]
    delta_rs = [env.delta_r]
    ee_true = [env.contact_pos_true().copy()]
    ee_noisy = [env.observe_pos().copy()]
    forces_log = []
    hinges_log = [env.hinge_pos().copy()]

    F_prev_meas = np.zeros(2)
    t = 0.0
    for _ in range(int(15.0 / dt)):
        p_m = env.observe_pos()
        v_m = env.observe_vel()
        F = ctrl.compute(p_m, v_m, F_prev_meas)
        F_prev_meas = env.observe_force(F)

        th, dr = env.step(F)
        t += dt

        times.append(t)
        thetas.append(th)
        delta_rs.append(dr)
        ee_true.append(env.contact_pos_true().copy())
        ee_noisy.append(env.observe_pos().copy())
        forces_log.append(F.copy())
        hinges_log.append(env.hinge_pos().copy())

        if th >= theta_target - 0.01:
            break

    times = np.array(times)
    thetas = np.array(thetas)
    delta_rs = np.array(delta_rs)
    ee_true = np.array(ee_true)
    ee_noisy = np.array(ee_noisy)
    forces_log = np.array(forces_log) if forces_log else np.zeros((1, 2))
    hinges_log = np.array(hinges_log)

    fit_raw = fit_circle_taubin(ee_noisy)
    fit = None if fit_raw is None else fit_raw[:3]
    r_true_vals = np.linalg.norm(ee_true - hinges_log, axis=1)

    print(f"Target reached  : {np.degrees(thetas[-1]):.1f}°  in  {times[-1]:.2f} s")
    print(f"Max |delta_r|   : {np.max(np.abs(delta_rs))*1000:.2f} mm")
    print(f"Mean |delta_r|  : {np.mean(np.abs(delta_rs))*1000:.2f} mm")
    if fit:
        cx, cy, r_fit = fit
        h_mean = hinges_log.mean(axis=0)
        print(f"True r (mean)   : {r_true_vals.mean():.4f} m  (nominal s={s:.4f} m)")
        print(
            f"Fitted r        : {r_fit:.4f} m  "
            f"error={abs(r_fit-s)*1000:.2f} mm ({abs(r_fit-s)/s*100:.2f}%)"
        )
        print(
            f"Fitted center   : ({cx:.4f}, {cy:.4f}) m  "
            f"true hinge mean: ({h_mean[0]:.4f}, {h_mean[1]:.4f}) m"
        )

    phi_log = np.unwrap(np.array(ctrl.phi_log))
    true_tang = np.degrees(thetas + np.pi / 2)
    print(
        f"phi: {np.degrees(phi_log[0]):.1f}° → {np.degrees(phi_log[-1]):.1f}°  "
        f"(true tangent: {true_tang[0]:.1f}° → {true_tang[-1]:.1f}°)"
    )

    return (
        times,
        thetas,
        delta_rs,
        ee_true,
        ee_noisy,
        forces_log,
        hinges_log,
        fit,
        r_true_vals,
        ctrl.phi_log,
    )


def make_gif(
    times,
    thetas,
    delta_rs,
    ee_true,
    ee_noisy,
    forces_log,
    hinges_log,
    fit,
    r_true_vals,
    phi_log,
):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.patch.set_facecolor("#0f1117")
    for ax in axes:
        ax.set_facecolor("#1a1d27")
        ax.tick_params(colors="#aaaaaa", labelsize=7)
        for sp in ax.spines.values():
            sp.set_color("#333344")

    ax_rod, ax_th, ax_phi = axes
    C = dict(
        rod="#4fc3f7",
        ee="#ff7043",
        trail="#80cbc4",
        force="#ffb74d",
        hinge="#ce93d8",
        fit="#a5d6a7",
        noise="#555566",
    )

    margin = 0.06
    xlim = (-delta_slide_max - margin, L + margin)
    ylim = (-margin, L + margin)
    t_end = max(float(times[-1]), 0.5)

    ax_rod.set_xlim(xlim)
    ax_rod.set_ylim(ylim)
    ax_rod.set_aspect("equal")
    ax_rod.set_title("Rod motion", color="white", fontsize=9)
    ax_rod.set_xlabel("x [m]", color="#aaaaaa", fontsize=8)
    ax_rod.set_ylabel("y [m]", color="#aaaaaa", fontsize=8)
    h_mean = hinges_log.mean(axis=0)
    arc_a = np.linspace(0.02, theta_target, 80)
    ax_rod.plot(
        h_mean[0] + s * np.cos(arc_a),
        h_mean[1] + s * np.sin(arc_a),
        "--",
        color="#334455",
        lw=0.8,
        label="ideal arc",
    )
    if fit:
        cx, cy, r_fit = fit
        ax_rod.plot(
            cx + r_fit * np.cos(arc_a),
            cy + r_fit * np.sin(arc_a),
            "-",
            color=C["fit"],
            lw=1,
            alpha=0.65,
            label=f"fit r={r_fit:.3f}m",
        )
    ax_rod.legend(
        loc="upper right",
        fontsize=7,
        facecolor="#1a1d27",
        labelcolor="white",
        framealpha=0.6,
    )
    rod_line, = ax_rod.plot([], [], "-", color=C["rod"], lw=3, alpha=0.9)
    trail_t, = ax_rod.plot([], [], "-", color=C["trail"], lw=0.8, alpha=0.6)
    trail_n, = ax_rod.plot([], [], ".", color=C["noise"], ms=1.5, alpha=0.35)
    ee_dot, = ax_rod.plot([], [], "o", color=C["ee"], ms=6, zorder=6)
    hinge_dot, = ax_rod.plot([], [], "s", color=C["hinge"], ms=5, zorder=6)
    quiv = ax_rod.quiver([], [], [], [], color=C["force"], scale=120, width=0.004, alpha=0.85)
    time_txt = ax_rod.text(xlim[0] + 0.01, ylim[1] - 0.03, "", color="white", fontsize=8)
    ang_txt = ax_rod.text(xlim[0] + 0.01, ylim[1] - 0.06, "", color="#aaaaaa", fontsize=8)

    ax_th.set_xlim(0, t_end)
    ax_th.set_ylim(-5, 100)
    ax_th.set_title("Angle theta", color="white", fontsize=9)
    ax_th.set_xlabel("time [s]", color="#aaaaaa", fontsize=8)
    ax_th.set_ylabel("theta [deg]", color="#aaaaaa", fontsize=8)
    ax_th.axhline(np.degrees(theta_target), color="#ef5350", lw=1, ls="--", alpha=0.7, label="target")
    ax_th.legend(fontsize=7, facecolor="#1a1d27", labelcolor="white", framealpha=0.6)
    theta_line, = ax_th.plot([], [], color=C["rod"], lw=1.5)

    phi_deg = np.degrees(np.unwrap(np.array(phi_log)))
    true_tang = np.degrees(thetas + np.pi / 2)
    y_lo = min(phi_deg.min(), true_tang.min()) - 10
    y_hi = max(phi_deg.max(), true_tang.max()) + 10
    ax_phi.set_xlim(0, t_end)
    ax_phi.set_ylim(y_lo, y_hi)
    ax_phi.set_title("phi (force dir) vs true tangent", color="white", fontsize=9)
    ax_phi.set_xlabel("time [s]", color="#aaaaaa", fontsize=8)
    ax_phi.set_ylabel("angle [deg]", color="#aaaaaa", fontsize=8)
    ax_phi.plot(times, true_tang, "--", color="#888899", lw=1, label="true tangent")
    phi_line, = ax_phi.plot([], [], color=C["force"], lw=1.2, label="phi (cmd)")
    ax_phi.legend(fontsize=7, facecolor="#1a1d27", labelcolor="white", framealpha=0.6)

    fig.tight_layout(pad=1.5)

    stride = max(1, len(times) // 150)
    frames = list(range(0, len(times), stride))
    if frames[-1] != len(times) - 1:
        frames.append(len(times) - 1)

    def init():
        for a in (rod_line, trail_t, trail_n, ee_dot, hinge_dot, theta_line, phi_line):
            a.set_data([], [])
        return rod_line, trail_t, trail_n, ee_dot, hinge_dot, theta_line, phi_line

    def update(fi):
        i = frames[fi]
        th = thetas[i]
        h = hinges_log[i]
        ee = ee_true[i]

        tip = h + L * np.array([np.cos(th), np.sin(th)])
        rod_line.set_data([h[0], tip[0]], [h[1], tip[1]])
        ee_dot.set_data([ee[0]], [ee[1]])
        hinge_dot.set_data([h[0]], [h[1]])
        trail_t.set_data(ee_true[: i + 1, 0], ee_true[: i + 1, 1])
        trail_n.set_data(ee_noisy[: i + 1, 0], ee_noisy[: i + 1, 1])

        if i < len(forces_log):
            quiv.set_offsets([[ee[0], ee[1]]])
            quiv.set_UVC([forces_log[i, 0] * 0.015], [forces_log[i, 1] * 0.015])

        time_txt.set_text(f"t={times[i]:.2f}s")
        ang_txt.set_text(f"theta={np.degrees(th):.1f} deg  dr={delta_rs[i]*1000:.2f}mm")
        theta_line.set_data(times[: i + 1], np.degrees(thetas[: i + 1]))

        n_phi = min(i + 1, len(phi_deg))
        phi_line.set_data(times[:n_phi], phi_deg[:n_phi])

        return rod_line, trail_t, trail_n, ee_dot, hinge_dot, theta_line, phi_line

    ani = FuncAnimation(fig, update, frames=len(frames), init_func=init, blit=True, interval=40)
    ani.save(OUT_GIF, writer=PillowWriter(fps=25), dpi=110)
    plt.close()
    print(f"GIF → {OUT_GIF}")


if __name__ == "__main__":
    result = run_simulation()
    make_gif(*result)
