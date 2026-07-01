"""
Stage II Proposed: Adaptive MPC with Cubic Trajectory Model

Two-layer architecture:
  Layer 1 (Geometry): cubic polynomial fit to recent EE positions
                      → tangent e_t, normal e_r, curvature κ
  Layer 2 (Dynamics): RLS with forgetting factor, fits Δp̃ = B̃·F̃ + c̃
                      in local {e_t, e_r} frame
  MPC: N-step QP, maximises tangential progress, penalises radial
       displacement and force rate-of-change

Cold start: push [0,1] with F_cold until geo model ready.
No dedicated exploration phase — geometry and dynamics learnt on-the-fly.
"""

import numpy as np

# ── Physical constants (standalone Python sim) ──────────────────────────────
L = 0.35; m_rod = 1.5; g = 9.81; I_rod = (1/3)*m_rod*L**2
k_r = 100.0; c_r = 20.0; s = 0.9*L
delta_slide_true = 0.03; delta_slide_max = 0.05
dt = 1/50; noise_pos = 5e-5


class RodEnv:
    def __init__(self):
        self.theta = 0.05; self.theta_dot = 0.0
        self.delta_r = 0.0; self.delta_r_dot = 0.0
    def hinge_pos(self):
        return np.array([np.clip(delta_slide_true*np.sin(self.theta),
                                 -delta_slide_max, delta_slide_max), 0.0])
    def contact_pos_true(self):
        h = self.hinge_pos(); r = s + self.delta_r
        return h + r*np.array([np.cos(self.theta), np.sin(self.theta)])
    def observe_pos(self):
        return self.contact_pos_true() + np.random.randn(2)*noise_pos
    def step(self, F):
        e_r = np.array([np.cos(self.theta), np.sin(self.theta)])
        e_t = np.array([-np.sin(self.theta), np.cos(self.theta)])
        Ft = np.dot(F, e_t); Fr = np.dot(F, e_r)
        tau = Ft*(s+self.delta_r) - m_rod*g*(L/2)*np.cos(self.theta)
        self.theta_dot += tau/I_rod*dt; self.theta += self.theta_dot*dt
        self.delta_r_dot += (Fr - k_r*self.delta_r - c_r*self.delta_r_dot)/m_rod*dt
        self.delta_r += self.delta_r_dot*dt
        self.theta = float(np.clip(self.theta, 0, np.pi))
        if self.theta in (0.0, np.pi): self.theta_dot = 0.0
        return self.theta, self.delta_r


# ── Layer 1: Cubic Trajectory Model ─────────────────────────────────────────

class CubicTrajectoryModel:
    """
    Fits p(τ) = a0 + a1τ + a2τ² + a3τ³ to last W positions.
    Extracts tangent e_t, normal e_r, curvature κ at τ=1.

    e_t is always constrained to have z ≥ 0 (rod rotates upward only).
    Confidence based on RMS fit residual.
    """
    def __init__(self, W=25, sigma_ref=3e-4):
        self.W = W
        self._sigma_ref = sigma_ref
        self._hist = []

        # Defaults (used before ready)
        self.e_t       = np.array([0.0, 1.0])
        self.e_r       = np.array([1.0, 0.0])
        self.kappa     = 0.0
        self.sigma_fit = np.inf
        self.ready     = False

    def update(self, p):
        self._hist.append(p.copy())
        if len(self._hist) > self.W + 10:
            self._hist = self._hist[-(self.W + 10):]

        n = min(len(self._hist), self.W)
        if n < 6:
            return

        pts = np.array(self._hist[-n:])
        tau = np.linspace(0.0, 1.0, n)
        V   = np.column_stack([np.ones(n), tau, tau**2, tau**3])

        try:
            Ax = np.linalg.lstsq(V, pts[:, 0], rcond=None)[0]
            Az = np.linalg.lstsq(V, pts[:, 1], rcond=None)[0]
        except np.linalg.LinAlgError:
            return

        # First derivative at τ=1
        dp = np.array([Ax[1] + 2*Ax[2] + 3*Ax[3],
                       Az[1] + 2*Az[2] + 3*Az[3]])
        # Second derivative at τ=1
        ddp = np.array([2*Ax[2] + 6*Ax[3],
                        2*Az[2] + 6*Az[3]])

        dp_norm = np.linalg.norm(dp)
        if dp_norm < 1e-8:
            return

        e_t_new = dp / dp_norm

        # Enforce z ≥ 0: rod can only rotate upward
        if e_t_new[1] < 0:
            e_t_new = -e_t_new

        self.e_t   = e_t_new
        self.e_r   = np.array([-e_t_new[1], e_t_new[0]])  # 90° CCW

        cross = abs(dp[0]*ddp[1] - dp[1]*ddp[0])
        self.kappa = cross / (dp_norm**3 + 1e-12)

        p_hat = np.column_stack([V @ Ax, V @ Az])
        self.sigma_fit = float(np.sqrt(np.mean(np.sum((pts - p_hat)**2, axis=1))))
        self.ready = True

    @property
    def confidence(self):
        if not self.ready:
            return 0.0
        return 1.0 / (1.0 + self.sigma_fit / self._sigma_ref)


# ── Layer 2: RLS Dynamics Model ──────────────────────────────────────────────

class RLSDynamicsModel:
    """
    RLS with forgetting factor λ.
    Fits:  Δp̃ = B̃·F̃ + c̃   in local {e_t, e_r} frame.
    Regressor: φ = [F̃_t, F̃_r, 1]^T
    Parameter: Θ ∈ ℝ^{3×2}  (rows: Ft-input, Fr-input, bias)
    """
    def __init__(self, lam=0.97, P0=1e3, P_ref=50.0):
        self._lam   = lam
        self._P_ref = P_ref

        # Physical prior: tangential compliance >> radial compliance
        sigma_t = 5e-4
        sigma_r = 5e-5
        self.Theta = np.array([
            [sigma_t, 0.0],
            [0.0,     sigma_r],
            [0.0,     0.0],
        ])  # 3×2

        self.P     = P0 * np.eye(3)
        self.ready = False

    def update(self, F, dp, e_t, e_r):
        F_loc  = np.array([F  @ e_t, F  @ e_r])
        dp_loc = np.array([dp @ e_t, dp @ e_r])
        phi    = np.array([F_loc[0], F_loc[1], 1.0])

        Pp    = self.P @ phi
        denom = self._lam + phi @ Pp
        K     = Pp / denom

        for j in range(2):
            err = dp_loc[j] - phi @ self.Theta[:, j]
            self.Theta[:, j] += K * err

        self.P = (self.P - np.outer(K, Pp)) / self._lam
        self.ready = True

    @property
    def B_tilde(self):
        return self.Theta[:2, :].T   # 2×2

    @property
    def c_tilde(self):
        return self.Theta[2, :]      # [2]

    @property
    def confidence(self):
        tr = float(np.trace(self.P))
        return 1.0 / (1.0 + tr / self._P_ref)


# ── Layer 3: MPC (N-step QP) ─────────────────────────────────────────────────

class MPCSolver:
    """
    N-step QP in local {e_t, e_r} frame.

    min  Σ_k [ -w_prog·Δp̃_{t,k}
              + w_rad·(B̃[1,:]·F̃_k + c̃[1])²
              + w_dF·||F̃_k - F̃_{k-1}||² ]

    s.t. ||F̃_k|| ≤ F_max
         ||F̃_k - F̃_{k-1}|| ≤ dF_max
    """
    def __init__(self, N=5, w_prog=5.0, w_rad=500.0, w_dF=2.0,
                 F_safe=40.0, dF_max=3.0):
        self.N      = N
        self.w_prog = w_prog
        self.w_rad  = w_rad
        self.w_dF   = w_dF
        self.F_safe = F_safe
        self.dF_max = dF_max

    def solve(self, B_tilde, c_tilde, F_prev_loc, F_max):
        N = self.N
        n = 2*N

        H = np.zeros((n, n))
        f = np.zeros(n)
        B = B_tilde; c = c_tilde

        for k in range(N):
            i = 2*k

            # Tangential progress (linear)
            f[i]   -= self.w_prog * B[0, 0]
            f[i+1] -= self.w_prog * B[0, 1]

            # Radial penalty (quadratic)
            b_r = B[1, :]
            H[i:i+2, i:i+2] += 2.0 * self.w_rad * np.outer(b_r, b_r)
            f[i:i+2]         += 2.0 * self.w_rad * c[1] * b_r

            # Force rate penalty
            if k == 0:
                H[i:i+2, i:i+2] += 2.0 * self.w_dF * np.eye(2)
                f[i:i+2]         -= 2.0 * self.w_dF * F_prev_loc
            else:
                j = 2*(k-1)
                H[i:i+2, i:i+2] += 2.0 * self.w_dF * np.eye(2)
                H[j:j+2, j:j+2] += 2.0 * self.w_dF * np.eye(2)
                H[i:i+2, j:j+2] -= 2.0 * self.w_dF * np.eye(2)
                H[j:j+2, i:i+2] -= 2.0 * self.w_dF * np.eye(2)

        H = (H + H.T) / 2 + 1e-8 * np.eye(n)

        try:
            x = np.linalg.solve(H, -f)
        except np.linalg.LinAlgError:
            x = np.zeros(n)

        F0 = x[:2]

        # Rate constraint
        dF = F0 - F_prev_loc
        dF_norm = np.linalg.norm(dF)
        if dF_norm > self.dF_max:
            F0 = F_prev_loc + dF * (self.dF_max / dF_norm)

        # Magnitude constraint
        F0_norm = np.linalg.norm(F0)
        if F0_norm > F_max:
            F0 = F0 * (F_max / F0_norm)

        # Hard safety: z component must push upward (F_world_z > 0)
        # enforced after converting back in ProposedMPC

        return F0


# ── Main Controller ───────────────────────────────────────────────────────────

class ProposedMPC:
    """
    Adaptive MPC with cubic trajectory model.
    """
    def __init__(self, phi_offset_deg=0,
                 F_safe=40.0, F_cold=12.0,
                 w_prog=5.0, w_rad=500.0, w_dF=2.0,
                 N_mpc=5, dF_max=3.0,
                 W_traj=25, lam=0.97):

        self._F_safe = F_safe
        self._F_cold = F_cold

        self._geo = CubicTrajectoryModel(W=W_traj)
        self._dyn = RLSDynamicsModel(lam=lam)
        self._mpc = MPCSolver(N=N_mpc, w_prog=w_prog, w_rad=w_rad,
                              w_dF=w_dF, F_safe=F_safe, dF_max=dF_max)

        self._p_prev     = None
        self._F_prev     = np.array([0.0, F_cold])
        self._F_prev_loc = np.array([0.0, 0.0])

        # Logging
        self.phi_log      = []
        self.F_mag_log    = []
        self.mode_log     = []
        self.snap_log     = []
        self.conf_geo_log = []
        self.conf_dyn_log = []

    def compute(self, p_noisy):
        # ── 1. Update geometry ──
        self._geo.update(p_noisy)
        e_t = self._geo.e_t
        e_r = self._geo.e_r
        conf_geo = self._geo.confidence

        # ── 2. Update dynamics (from previous step's force) ──
        if self._p_prev is not None:
            dp = p_noisy - self._p_prev
            self._dyn.update(self._F_prev, dp, e_t, e_r)
        conf_dyn = self._dyn.confidence

        self._p_prev = p_noisy.copy()

        # ── 3. Adaptive force ceiling ──
        # During cold start (geo not ready): use F_cold with prior direction
        # Once geo ready: ceiling scales with both confidences
        if not self._geo.ready:
            F_max = self._F_cold
        else:
            # F_max ramps with dynamics confidence only.
            # Geo confidence controls direction quality, not force ceiling.
            F_max = self._F_cold + (self._F_safe - self._F_cold) * min(conf_dyn, 1.0)
            F_max = float(np.clip(F_max, self._F_cold, self._F_safe))

        # ── 4. Force computation ──
        if self._geo.ready and self._dyn.ready:
            mode = 'mpc'
            F_loc = self._mpc.solve(
                self._dyn.B_tilde,
                self._dyn.c_tilde,
                self._F_prev_loc,
                F_max
            )
            F = F_loc[0] * e_t + F_loc[1] * e_r
            # Safety: world-frame z must be positive (upward only)
            if F[1] < 0:
                F[1] = 0.0
                F_norm = np.linalg.norm(F)
                if F_norm < 1.0:
                    F = np.array([0.0, 5.0])   # fallback
        else:
            mode = 'cold'
            F = np.array([0.0, self._F_cold])
            F_loc = np.array([F @ e_t, F @ e_r])

        # ── 5. Store and log ──
        self._F_prev     = F.copy()
        self._F_prev_loc = np.array([F @ e_t, F @ e_r])

        self.phi_log.append(float(np.arctan2(F[1], F[0])))
        self.F_mag_log.append(float(np.linalg.norm(F)))
        self.mode_log.append(mode)
        self.snap_log.append(0)
        self.conf_geo_log.append(conf_geo)
        self.conf_dyn_log.append(conf_dyn)

        return F


# ── Standalone test ───────────────────────────────────────────────────────────

def run_sim(theta_target=np.pi/2, F_safe=11.0):
    env  = RodEnv()
    ctrl = ProposedMPC(F_safe=F_safe, F_cold=10.0,
                       w_prog=5.0, w_rad=500.0, w_dF=2.0)
    times=[0.0]; thetas=[env.theta]; delta_rs=[env.delta_r]
    t = 0.0
    for _ in range(int(15/dt)):
        p = env.observe_pos(); F = ctrl.compute(p)
        th, dr = env.step(F); t += dt
        times.append(t); thetas.append(th); delta_rs.append(dr)
        if th >= theta_target - 0.01:
            break
    return np.array(times), np.array(thetas), np.array(delta_rs), ctrl


def print_results(times, thetas, delta_rs, ctrl, label=""):
    if label: print(f"\n── {label} ──")
    print(f"  Final angle  : {np.degrees(thetas[-1]):.1f}° in {times[-1]:.2f}s")
    print(f"  Max |δr|     : {np.max(np.abs(delta_rs))*1000:.2f} mm")
    print(f"  Mean |δr|    : {np.mean(np.abs(delta_rs))*1000:.2f} mm")
    modes = ctrl.mode_log
    print(f"  Modes        : cold={modes.count('cold')}  mpc={modes.count('mpc')}")
    if ctrl.conf_geo_log:
        print(f"  Conf geo     : final={ctrl.conf_geo_log[-1]:.3f}  "
              f"mean={np.mean(ctrl.conf_geo_log):.3f}")
    if ctrl.conf_dyn_log:
        print(f"  Conf dyn     : final={ctrl.conf_dyn_log[-1]:.3f}  "
              f"mean={np.mean(ctrl.conf_dyn_log):.3f}")
    if ctrl.F_mag_log:
        print(f"  F range      : {min(ctrl.F_mag_log):.1f}–{max(ctrl.F_mag_log):.1f} N")


if __name__ == '__main__':
    for seed in [42, 43, 44]:
        np.random.seed(seed)
        results = run_sim()
        print_results(*results, label=f"seed={seed}")

# ── GIF output ────────────────────────────────────────────────────────────────

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import os

OUT_GIF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rod_traction_proposed.gif')


def make_gif(times, thetas, delta_rs, ctrl, ee_pos=None):
    """
    Three-panel GIF:
      Left:   EE trajectory + current cubic fit
      Center: Rod angle θ over time
      Right:  Radial force |k·δr| over time
    """
    K_R = 100.0
    radial_forces = np.abs(delta_rs) * K_R

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.patch.set_facecolor('#0f1117')
    for ax in axes:
        ax.set_facecolor('#1a1d27')
        ax.tick_params(colors='#aaaaaa', labelsize=7)
        for sp in ax.spines.values():
            sp.set_color('#333344')

    ax_traj, ax_th, ax_fr = axes
    C = dict(trail='#4fc3f7', fit='#a5d6a7', ee='#ff7043',
             theta='#81c784', frad='#ffb74d')

    # ── Left: trajectory ──
    if ee_pos is not None:
        all_x = ee_pos[:, 0]; all_z = ee_pos[:, 1]
    else:
        all_x = np.array([s * np.cos(th) for th in thetas])
        all_z = np.array([s * np.sin(th) for th in thetas])

    margin = 0.05
    xlim = (all_x.min() - margin, all_x.max() + margin)
    zlim = (all_z.min() - margin, all_z.max() + margin)
    ax_traj.set_xlim(xlim); ax_traj.set_ylim(zlim)
    ax_traj.set_aspect('equal')
    ax_traj.set_title('EE trajectory + cubic fit', color='white', fontsize=9)
    ax_traj.set_xlabel('x [m]', color='#aaaaaa', fontsize=8)
    ax_traj.set_ylabel('z [m]', color='#aaaaaa', fontsize=8)

    trail_line, = ax_traj.plot([], [], '-', color=C['trail'], lw=1.2, alpha=0.7)
    fit_line,   = ax_traj.plot([], [], '-', color=C['fit'],   lw=2.0, alpha=0.9)
    ee_dot,     = ax_traj.plot([], [], 'o', color=C['ee'],    ms=6, zorder=5)
    info_txt = ax_traj.text(xlim[0]+0.005, zlim[1]-0.005, '',
                             color='white', fontsize=7.5, va='top',
                             family='monospace')

    # ── Center: angle ──
    t_end = max(float(times[-1]), 0.5)
    ax_th.set_xlim(0, t_end)
    ax_th.set_ylim(-5, max(np.degrees(thetas).max() + 10, 100))
    ax_th.set_title('Rod angle θ', color='white', fontsize=9)
    ax_th.set_xlabel('time [s]', color='#aaaaaa', fontsize=8)
    ax_th.set_ylabel('deg', color='#aaaaaa', fontsize=8)
    ax_th.axhline(90, color='#ef5350', lw=1, ls='--', alpha=0.7, label='target')
    ax_th.legend(fontsize=7, facecolor='#1a1d27', labelcolor='white', framealpha=0.6)
    th_line, = ax_th.plot([], [], color=C['theta'], lw=1.5)

    # ── Right: radial force ──
    fr_max = max(float(radial_forces.max()), 0.1)
    ax_fr.set_xlim(0, t_end)
    ax_fr.set_ylim(0, fr_max * 1.2)
    ax_fr.set_title('Radial force |k·δr|', color='white', fontsize=9)
    ax_fr.set_xlabel('time [s]', color='#aaaaaa', fontsize=8)
    ax_fr.set_ylabel('N', color='#aaaaaa', fontsize=8)
    fr_line, = ax_fr.plot([], [], color=C['frad'], lw=1.5)

    fig.tight_layout(pad=1.5)

    W = 25  # cubic fit window

    def init():
        for a in (trail_line, fit_line, ee_dot, th_line, fr_line):
            a.set_data([], [])
        return trail_line, fit_line, ee_dot, th_line, fr_line

    def update(i):
        # Trajectory trail
        xs = all_x[:i+1]; zs = all_z[:i+1]
        trail_line.set_data(xs, zs)
        ee_dot.set_data([xs[-1]], [zs[-1]])

        # Cubic fit on last W points
        n = min(i+1, W)
        if n >= 6:
            pts = np.column_stack([xs[-n:], zs[-n:]])
            tau = np.linspace(0, 1, n)
            V   = np.column_stack([np.ones(n), tau, tau**2, tau**3])
            try:
                Ax = np.linalg.lstsq(V, pts[:, 0], rcond=None)[0]
                Az = np.linalg.lstsq(V, pts[:, 1], rcond=None)[0]
                tau_fine = np.linspace(0, 1, 60)
                V2 = np.column_stack([np.ones(60), tau_fine,
                                      tau_fine**2, tau_fine**3])
                fit_x = V2 @ Ax; fit_z = V2 @ Az
                fit_line.set_data(fit_x, fit_z)
            except Exception:
                fit_line.set_data([], [])
        else:
            fit_line.set_data([], [])

        # Mode label
        mode = ctrl.mode_log[i] if i < len(ctrl.mode_log) else '?'
        info_txt.set_text(
            f"t={times[i]:.2f}s  θ={np.degrees(thetas[i]):.1f}°\n"
            f"δr={delta_rs[i]*1000:.1f}mm\n"
            f"mode: {mode}")

        # Angle & radial force
        th_line.set_data(times[:i+1], np.degrees(thetas[:i+1]))
        fr_line.set_data(times[:i+1], radial_forces[:i+1])

        return trail_line, fit_line, ee_dot, th_line, fr_line

    stride = max(1, len(times) // 200)
    frames = list(range(0, len(times), stride))
    if frames[-1] != len(times)-1:
        frames.append(len(times)-1)

    ani = FuncAnimation(fig, update, frames=len(frames),
                        init_func=init, blit=True, interval=50,
                        fargs=())

    # Wrap update to use frame index → actual time index
    def update_idx(fi):
        return update(frames[fi])

    ani2 = FuncAnimation(fig, update_idx, frames=len(frames),
                         init_func=init, blit=True, interval=50)

    ani2.save(OUT_GIF, writer=PillowWriter(fps=20), dpi=110)
    plt.close()
    print(f"GIF → {OUT_GIF}")


if __name__ == '__main__':
    for seed in [42, 43, 44]:
        np.random.seed(seed)
        results = run_sim()
        print_results(*results, label=f"seed={seed}")

    # GIF for seed=42
    np.random.seed(42)
    times, thetas, delta_rs, ctrl = run_sim()
    # Build ee_pos from contact position
    ee_pos = np.column_stack([
        s * np.cos(thetas),
        s * np.sin(thetas)
    ])
    make_gif(times, thetas, delta_rs, ctrl, ee_pos=ee_pos)