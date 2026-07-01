"""
Stage II Baseline: Impedance-based direction + adaptive force.

v6 changes for MuJoCo robustness:
  - Windowed displacement (5-step) for direction detection
  - Higher displacement threshold (5e-4 vs 1e-5)
  - Softer snap blend (0.3 vs 0.6)
  - Snap cooldown (15 steps between snaps)
"""

import os, numpy as np, matplotlib
matplotlib.use('Agg')

OUT_GIF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rod_traction.gif')

# Python sim parameters (standalone testing)
L=0.35; m_rod=1.5; g=9.81; I_rod=(1/3)*m_rod*L**2
k_r=100.0; c_r=20.0; s_frac=0.9; s=s_frac*L
delta_slide_true=0.03; delta_slide_max=0.05
dt=1/50; theta_target=np.pi/2
noise_pos=5e-5
np.random.seed(42)


class RodEnv:
    """Standalone 2D rod env for testing without MuJoCo."""
    def __init__(self):
        self.theta=0.05; self.theta_dot=0.0; self.delta_r=0.0; self.delta_r_dot=0.0
    def hinge_pos(self):
        return np.array([np.clip(delta_slide_true*np.sin(self.theta),-delta_slide_max,delta_slide_max),0.0])
    def contact_pos_true(self):
        h=self.hinge_pos(); r=s+self.delta_r
        return h+r*np.array([np.cos(self.theta),np.sin(self.theta)])
    def observe_pos(self):
        return self.contact_pos_true()+np.random.randn(2)*noise_pos
    def step(self,F):
        e_r=np.array([np.cos(self.theta),np.sin(self.theta)])
        e_t=np.array([-np.sin(self.theta),np.cos(self.theta)])
        Ft=np.dot(F,e_t); Fr=np.dot(F,e_r)
        tau=Ft*(s+self.delta_r)-m_rod*g*(L/2)*np.cos(self.theta)
        self.theta_dot+=tau/I_rod*dt; self.theta+=self.theta_dot*dt
        self.delta_r_dot+=(Fr-k_r*self.delta_r-c_r*self.delta_r_dot)/m_rod*dt
        self.delta_r+=self.delta_r_dot*dt
        self.theta=float(np.clip(self.theta,0,np.pi))
        if self.theta in(0.0,np.pi): self.theta_dot=0.0
        return self.theta,self.delta_r


class ImpedanceMPC:
    """
    Baseline controller: impedance-based direction + adaptive force.

    Uses windowed displacement for robust direction detection in MuJoCo.
    """
    def __init__(self, phi_offset_deg=30, F_explore=15.0, F_safe=40.0, ramp_rate=0.5):
        self.phi = np.pi/2 + np.radians(phi_offset_deg)
        self._impedance_ratio_thresh = 0.85

        # Windowed displacement: compare current pos vs pos N steps ago
        self._pos_window = []
        self._window_len = 5
        self._dp_threshold = 5e-4   # 0.5mm minimum displacement for detection

        # Snap control
        self._snap_blend = 0.3
        self._snap_cooldown = 15     # minimum steps between snaps
        self._steps_since_snap = 999 # start ready to snap

        # Force adaptation
        self._F_explore = F_explore
        self._F_safe    = F_safe
        self._F_mag     = F_explore
        self._ramp_rate = ramp_rate
        self._confirm_count  = 0
        self._confirm_thresh = 10

        # Logging
        self.phi_log       = [self.phi]
        self.impedance_log = []
        self.snap_log      = []
        self.F_mag_log     = []

    def compute(self, p_noisy):
        self._pos_window.append(p_noisy.copy())
        if len(self._pos_window) > self._window_len + 5:
            self._pos_window = self._pos_window[-(self._window_len + 5):]

        snap = 0
        direction_good = True
        self._steps_since_snap += 1

        # Windowed displacement: current vs N steps ago
        if len(self._pos_window) > self._window_len:
            dp = self._pos_window[-1] - self._pos_window[-self._window_len]
            dp_mag = np.linalg.norm(dp)

            if dp_mag > self._dp_threshold:
                F_hat = np.array([np.cos(self.phi), np.sin(self.phi)])
                ratio = np.dot(dp, F_hat) / dp_mag

                self.impedance_log.append(float(ratio))

                if ratio < self._impedance_ratio_thresh and \
                   self._steps_since_snap >= self._snap_cooldown:
                    direction_good = False
                    dp_hat = dp / dp_mag
                    phi_target = float(np.arctan2(dp_hat[1], dp_hat[0]))
                    # Pick sign closest to current phi
                    phi_flip = phi_target + np.pi
                    d1 = abs(((phi_target - self.phi) + np.pi) % (2*np.pi) - np.pi)
                    d2 = abs(((phi_flip  - self.phi) + np.pi) % (2*np.pi) - np.pi)
                    phi_target = phi_target if d1 <= d2 else phi_flip
                    delta = ((phi_target - self.phi) + np.pi) % (2*np.pi) - np.pi
                    self.phi += self._snap_blend * delta
                    snap = 1
                    self._steps_since_snap = 0
            else:
                self.impedance_log.append(0.0)
        else:
            self.impedance_log.append(0.0)

        self.snap_log.append(snap)

        # Force adaptation
        if direction_good:
            self._confirm_count += 1
            if self._confirm_count >= self._confirm_thresh:
                self._F_mag = min(self._F_mag + self._ramp_rate, self._F_safe)
        else:
            self._confirm_count = 0
            self._F_mag = self._F_explore

        self.F_mag_log.append(self._F_mag)
        self.phi_log.append(self.phi)
        return self._F_mag * np.array([np.cos(self.phi), np.sin(self.phi)])


def fit_circle_taubin(pts):
    pts=np.array(pts)
    if len(pts)<5: return None
    x,y=pts[:,0],pts[:,1]; mx,my=x.mean(),y.mean(); u,v=x-mx,y-my
    Suu=np.dot(u,u);Svv=np.dot(v,v);Suv=np.dot(u,v)
    A=np.array([[Suu,Suv],[Suv,Svv]])
    b=np.array([0.5*(np.dot(u*u,u)+np.dot(u,v*v)),0.5*(np.dot(v*v,v)+np.dot(v,u*u))])
    try: uc,vc=np.linalg.solve(A,b)
    except: return None
    cx=uc+mx;cy=vc+my;r=np.sqrt(uc**2+vc**2+(Suu+Svv)/len(x))
    return cx,cy,r


def run_sim(phi_offset_deg=30):
    env=RodEnv(); ctrl=ImpedanceMPC(phi_offset_deg, F_explore=11.0, F_safe=11.0)
    times=[0.0]; thetas=[env.theta]; delta_rs=[env.delta_r]
    ee_true=[env.contact_pos_true().copy()]; ee_noisy=[env.observe_pos().copy()]
    forces=[]; hinges=[env.hinge_pos().copy()]
    t=0.0
    for _ in range(int(15/dt)):
        p_m=env.observe_pos(); F=ctrl.compute(p_m); th,dr=env.step(F); t+=dt
        times.append(t);thetas.append(th);delta_rs.append(dr)
        ee_true.append(env.contact_pos_true().copy());ee_noisy.append(env.observe_pos().copy())
        forces.append(F.copy());hinges.append(env.hinge_pos().copy())
        if th>=theta_target-0.01: break
    return (np.array(times),np.array(thetas),np.array(delta_rs),np.array(ee_true),
            np.array(ee_noisy),np.array(forces) if forces else np.zeros((1,2)),
            np.array(hinges),ctrl)


def print_results(times,thetas,delta_rs,ee_true,ee_noisy,forces,hinges,ctrl,label=""):
    fit=fit_circle_taubin(ee_noisy)
    if label: print(f"\n── {label} ──")
    print(f"  Target        : {np.degrees(thetas[-1]):.1f}°  in  {times[-1]:.2f} s")
    print(f"  Max |δr|      : {np.max(np.abs(delta_rs))*1000:.2f} mm")
    print(f"  Snaps         : {sum(ctrl.snap_log)}/{len(ctrl.snap_log)}")
    if ctrl.F_mag_log:
        print(f"  F_mag         : {ctrl.F_mag_log[0]:.1f} → {ctrl.F_mag_log[-1]:.1f} N  (peak {max(ctrl.F_mag_log):.1f} N)")


if __name__=='__main__':
    for deg in [10, 15, 20, 25, 30, 45]:
        np.random.seed(42)
        result = run_sim(deg)
        print_results(*result, label=f"offset={deg}°")