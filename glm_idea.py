"""
Integrated 3D Simulation — 面向下肢康复的充分拉伸牵引架构 v14
核心架构：Local GPR + MPPI (时间-力联合优化) + Bio-CBF (解析式安全屏障)
场景：给定90度弧线轨迹，模拟下肢在不同屈伸角度下的刚度突变
"""
import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel
import warnings
warnings.filterwarnings('ignore')
# ══════════════════════════════════════════════════════
# 1. 真实系统环境（控制器不可见）
# ══════════════════════════════════════════════════════
np.random.seed(42)
dt         = 0.05
b_true     = 1.5     # 真实阻尼 
m_true     = 0.1     # 真实质量
L0_true    = 0.5     # 真实自然长度
anchor     = np.array([0.0, 0.0, 0.0])
f_max_safe = 3.0     # 最大安全力
noise_std  = 0.05    # 传感器噪声
STRETCH_MAX = 0.06   # 允许的最大形变量
def get_true_stiffness(theta_rad):
    """模拟下肢关节活动度极限：角度越大，刚度急剧上升"""
    angle_deg = np.degrees(theta_rad)
    if angle_deg < 45:
        return 50.0
    else:
        # 45度以后模拟遇到关节极限，刚度指数级激增
        return 50.0 + 8.0 * (angle_deg - 45)**2
def true_force_mag(stretch, vel, acc, theta_rad):
    if stretch <= 0: return 0.0
    ks_true = get_true_stiffness(theta_rad)
    return ks_true*stretch + b_true*vel + m_true*acc
def true_force_3d(p, vel=0.0, acc=0.0):
    d = p - anchor; dist = np.linalg.norm(d)
    noise = np.random.normal(0, noise_std, 3)
    if dist < 1e-6: return noise
    theta = np.arctan2(d[1], d[0])
    stretch = max(0.0, dist - L0_true)
    f = max(0.0, true_force_mag(stretch, vel, acc, theta))
    if f < 1e-6: return noise
    return f * d/dist + noise
# ══════════════════════════════════════════════════════
# 2. 轨迹与参数定义
# ══════════════════════════════════════════════════════
theta_start  = np.radians(0)
theta_target = np.radians(90)
R_path       = L0_true + 0.04  # 给定轨迹的半径
# MPPI 参数
N_SAMPLES = 300
HORIZON   = 8
V_MAX     = 0.3
V_MIN     = 0.0
W_TIME    = 1.0
W_FORCE   = 50.0
W_TRACK   = 100.0
# ══════════════════════════════════════════════════════
# 3. 感知与建模层
# ══════════════════════════════════════════════════════
class LocalGPR:
    def __init__(self, max_data=50):
        k = ConstantKernel(1.0, (0.1, 10.0)) * RBF(length_scale=0.1, length_scale_bounds=(0.01, 1.0)) + WhiteKernel(noise_level=0.1)
        self.gpr = GaussianProcessRegressor(kernel=k, n_restarts_optimizer=0, normalize_y=True)
        self.X = []; self.y = []; self.max_data = max_data
        self.fitted = False
    def add_data(self, s, v, a, f):
        self.X.append([s, v, a]); self.y.append(f)
        if len(self.X) > self.max_data:
            self.X.pop(0); self.y.pop(0)
    def fit(self):
        if len(self.X) < 15: return
        self.gpr.fit(np.array(self.X), np.array(self.y))
        self.fitted = True
    def predict(self, s, v, a):
        if not self.fitted: return 0.0, 0.5
        mu, sig = self.gpr.predict(np.array([[s, v, a]]), return_std=True)
        return float(mu[0]), float(sig[0])
    def get_local_stiffness(self, s, v, a):
        if not self.fitted: return 0.0
        delta = 0.001
        mu_plus, _ = self.predict(s + delta, v, a)
        mu_minus, _ = self.predict(max(0, s - delta), v, a)
        return (mu_plus - mu_minus) / (2 * delta)
class RLS:
    def __init__(self, lam=0.95):
        self.lam = lam
        self.theta = np.array([10.0, 0.5, 0.05])
        self.P = np.diag([100., 10., 1.])
    def update(self, phi, y):
        e = y - phi @ self.theta
        d = self.lam + phi @ self.P @ phi
        K = self.P @ phi / d
        self.theta += K * e
        self.P = (1./self.lam) * (np.eye(3) - np.outer(K, phi)) @ self.P
        self.theta = np.clip(self.theta, [0.1, 0., 0.], [2000., 10., 2.])
        return self.theta.copy()
# ══════════════════════════════════════════════════════
# 4. 控制层：MPPI
# ══════════════════════════════════════════════════════
def run_mppi(p_cur, v_cur_vec, theta_cur, ks, b, m, L0_est, f_max_eff):
    tang = np.array([-np.sin(theta_cur), np.cos(theta_cur), 0.])
    # 【修复1】提取当前三维速度在切向上的标量投影
    v_cur_scalar = np.dot(v_cur_vec, tang)
    v_nominal = np.full(HORIZON, V_MAX * 0.8)
    noise = np.random.normal(0, 0.1, (N_SAMPLES, HORIZON))
    v_samples = np.clip(v_nominal + noise, V_MIN, V_MAX)
    costs = np.zeros(N_SAMPLES)
    for k in range(HORIZON):
        v_k = v_samples[:, k]  # (N_SAMPLES,)
        p_next = p_cur + dt * v_k[:, None] * tang
        dist = np.linalg.norm(p_next - anchor, axis=1)
        s = np.maximum(0.0, dist - L0_est)
        # 【修复2】使用标量速度计算加速度
        a_k = (v_k - v_cur_scalar) / dt
        f_pred = ks * s + b * v_k + m * a_k
        cost_time = -W_TIME * v_k
        cost_force = W_FORCE * np.maximum(0, f_pred - f_max_eff)**2
        cost_track = W_TRACK * (dist - R_path)**2
        costs += cost_time + cost_force + cost_track
    costs -= np.min(costs)
    weights = np.exp(-costs / 10.0)
    weights /= np.sum(weights)
    v_opt = np.sum(weights * v_samples[:, 0])
    return float(np.clip(v_opt, V_MIN, V_MAX))
# ══════════════════════════════════════════════════════
# 5. 安全层：Bio-CBF
# ══════════════════════════════════════════════════════
def apply_bio_cbf(p_cur, u_cmd, L0_est):
    d = p_cur - anchor
    dist = np.linalg.norm(d)
    if dist < 1e-6: return u_cmd
    radial_dir = d / dist
    tang_dir = np.array([-radial_dir[1], radial_dir[0], 0.])
    v_radial = np.dot(u_cmd, radial_dir)
    v_tang = np.dot(u_cmd, tang_dir)
    stretch_cur = max(0.0, dist - L0_est)
    if stretch_cur > STRETCH_MAX * 0.85:
        v_radial_safe = min(0.0, v_radial)
        if stretch_cur > STRETCH_MAX * 0.95:
            v_radial_safe = -0.02 
        u_safe = v_radial_safe * radial_dir + v_tang * tang_dir
        return u_safe
    return u_cmd
# ══════════════════════════════════════════════════════
# 6. 主仿真循环
# ══════════════════════════════════════════════════════
T_sim = 400
p_cur = anchor + R_path * np.array([np.cos(theta_start), np.sin(theta_start), 0.])
v_cur = np.zeros(3); v_prev = np.zeros(3)
L0_est = L0_true * 0.9 
gpr = LocalGPR(); rls = RLS()
hp = [p_cur.copy()]; hf = []; hv = []; htheta = []; hs = []; hkeff = []
print("="*60)
print("开始仿真: MPPI + Bio-CBF 架构 (修复版)")
print("="*60)
for t in range(T_sim):
    theta_cur = np.arctan2(p_cur[1]-anchor[1], p_cur[0]-anchor[0])
    if theta_cur >= theta_target:
        print(f"  [完成] t={t}: 到达目标角度!")
        break
    f_cur_vec = true_force_3d(p_cur, np.linalg.norm(v_cur), np.linalg.norm((v_cur-v_prev)/dt))
    fm = np.linalg.norm(f_cur_vec)
    dist = np.linalg.norm(p_cur - anchor)
    st = max(0.0, dist - L0_est)
    vs = np.linalg.norm(v_cur)
    ac = np.linalg.norm((v_cur - v_prev) / dt)
    phi = np.array([st, vs, ac])
    rls.update(phi, fm)
    gpr.add_data(st, vs, ac, fm)
    if t % 10 == 0 and len(gpr.X) >= 15:
        gpr.fit()
    mu_gpr, sig_gpr = gpr.predict(st, vs, ac)
    k_eff = gpr.get_local_stiffness(st, vs, ac)
    f_max_eff = f_max_safe - 2.0 * sig_gpr
    if k_eff > 50.0 * 0.8: # 如果刚度估计超过基础值
        f_max_eff = min(f_max_eff, 1.8)
    f_max_eff = max(f_max_eff, 0.5) 
    v_opt = run_mppi(p_cur, v_cur, theta_cur, rls.theta[0], rls.theta[1], rls.theta[2], L0_est, f_max_eff)
    tang = np.array([-np.sin(theta_cur), np.cos(theta_cur), 0.])
    u_cmd = v_opt * tang
    u_safe = apply_bio_cbf(p_cur, u_cmd, L0_est)
    v_prev = v_cur.copy()
    v_cur = u_safe.copy()
    p_cur = p_cur + dt * v_cur
    hp.append(p_cur.copy()); hf.append(fm); hv.append(np.linalg.norm(u_safe))
    htheta.append(np.degrees(theta_cur)); hs.append(st); hkeff.append(k_eff)
# ══════════════════════════════════════════════════════
# 7. 结果可视化
# ══════════════════════════════════════════════════════
fig, axs = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("Lower Limb Rehab: MPPI + Bio-CBF Architecture\n(Time-Force Optimization & Analytical Safety)", fontsize=14, fontweight='bold')
ax = axs[0, 0]
hp_arr = np.array(hp)
ax.plot(hp_arr[:, 0], hp_arr[:, 1], 'b-', lw=2, label='Actual Trajectory')
theta_ideal = np.linspace(theta_start, theta_target, 100)
ax.plot(R_path*np.cos(theta_ideal), R_path*np.sin(theta_ideal), 'g--', label='Reference Arc')
safe_R = L0_true + STRETCH_MAX
ax.plot(safe_R*np.cos(theta_ideal), safe_R*np.sin(theta_ideal), 'r:', label=f'Safety Boundary')
ax.plot(*anchor[:2], 'k+', ms=15, mew=2, label='Joint (Anchor)')
ax.set_aspect('equal'); ax.grid(True, alpha=0.3)
ax.set_title('1. End-Effector Trajectory & CBF Boundary')
ax.set_xlabel('X (m)'); ax.set_ylabel('Y (m)'); ax.legend(fontsize=8)
ax = axs[0, 1]
t_axis = np.arange(len(hf))
ax.plot(t_axis, hf, 'b-', lw=1.5, label='Force Magnitude (N)')
ax.axhline(f_max_safe, color='r', ls='-', lw=1.5, label=f'F_max_safe={f_max_safe}N')
ax.set_ylabel('Force (N)', color='b')
ax.tick_params(axis='y', labelcolor='b')
ax2 = ax.twinx()
ax2.plot(t_axis, hv, 'g-', lw=1.5, label='Tangential Velocity')
ax2.set_ylabel('Velocity (m/s)', color='g')
ax2.tick_params(axis='y', labelcolor='g')
ax.set_title('2. MPPI Time-Force Tradeoff (Speed adapts to Force)')
ax.set_xlabel('Time Step')
ax.grid(True, alpha=0.3)
lines, labels = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines + lines2, labels + labels2, loc='upper right', fontsize=8)
ax = axs[1, 0]
ax.plot(t_axis, htheta, 'm-', lw=2, label='Joint Angle (deg)')
ax.set_ylabel('Angle (deg)', color='m')
ax.tick_params(axis='y', labelcolor='m')
ax2 = ax.twinx()
ax2.plot(t_axis, hs, 'y-', lw=1.5, label='Stretch (m)')
ax2.axhline(STRETCH_MAX, color='r', ls=':', label='Stretch Max')
ax2.set_ylabel('Stretch (m)', color='y')
ax2.tick_params(axis='y', labelcolor='y')
ax.set_title('3. Motion Progression & Deformation Safety')
ax.set_xlabel('Time Step')
ax.grid(True, alpha=0.3)
lines, labels = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines + lines2, labels + labels2, loc='center right', fontsize=8)
ax = axs[1, 1]
ax.plot(t_axis, hkeff, 'c-', lw=2, label='Local GPR k_eff')
# 画出真实的刚度变化曲线作为对比
true_ks_curve = [get_true_stiffness(np.radians(a)) for a in htheta]
ax.plot(t_axis, true_ks_curve, 'k--', label='True Stiffness (Angle-based)')
ax.set_title('4. Nonlinear Stiffness Estimation (Local GPR)')
ax.set_xlabel('Time Step')
ax.set_ylabel('Stiffness (N/m)')
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8)
plt.tight_layout()
out_name = 'mppi_cbf_sim_v14.png'
plt.savefig(out_name, dpi=150, bbox_inches='tight')
print(f"\n[结果] 图像已保存: {out_name}")
viol = np.mean(np.array(hf) > f_max_safe) * 100
print(f"[指标] 力超限比例: {viol:.2f}%")
print(f"[指标] 到达目标时间: {len(hf)*dt:.2f}s")