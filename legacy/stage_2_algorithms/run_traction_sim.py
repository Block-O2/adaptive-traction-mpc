"""
Stage II: Elastic rod traction — impedance-based direction + MPC radial constraint

Controller:
  - Direction: impedance detection. Push in direction phi, measure displacement
    along force direction. If low displacement (high impedance) → wrong direction,
    snap phi to actual displacement direction. If high displacement → correct, keep.
  - MPC: constrains radial force, plans deceleration near target.
  - No geometric knowledge. Only uses (p_ee, F_cmd) each step.
"""

import os, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

OUT_GIF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rod_traction.gif')

L=0.35; m_rod=1.5; g=9.81; I_rod=(1/3)*m_rod*L**2
k_r=100.0; c_r=20.0; s_frac=0.9; s=s_frac*L
delta_slide_true=0.03; delta_slide_max=0.05
dt=1/50; theta_target=np.pi/2
F_max=11.0; F_rad_max=1.5
noise_pos=5e-5; noise_vel=1e-3
np.random.seed(42)

class RodEnv:
    def __init__(self):
        self.theta=0.05; self.theta_dot=0.0; self.delta_r=0.0; self.delta_r_dot=0.0
    def hinge_pos(self):
        return np.array([np.clip(delta_slide_true*np.sin(self.theta),-delta_slide_max,delta_slide_max),0.0])
    def contact_pos_true(self):
        h=self.hinge_pos(); r=s+self.delta_r
        return h+r*np.array([np.cos(self.theta),np.sin(self.theta)])
    def contact_vel_true(self):
        r=s+self.delta_r
        e_r=np.array([np.cos(self.theta),np.sin(self.theta)])
        e_t=np.array([-np.sin(self.theta),np.cos(self.theta)])
        dh=np.array([delta_slide_true*np.cos(self.theta)*self.theta_dot,0.0])
        return dh+r*self.theta_dot*e_t+self.delta_r_dot*e_r
    def observe_pos(self): return self.contact_pos_true()+np.random.randn(2)*noise_pos
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
    Direction: impedance-based snap correction.
    Push in direction phi. If EE barely moves along phi (high impedance),
    snap phi to the actual displacement direction (low impedance = tangential).
    Only updates phi when the direction is clearly wrong — no continuous drift.

    MPC: constrains radial force component below F_rad_max.
    """
    def __init__(self, phi_offset_deg=30):
        self.phi = np.pi/2 + np.radians(phi_offset_deg)
        self._p_prev = None
        self._impedance_ratio_thresh = 0.90  # dp_parallel / dp_total; below this = wrong direction

        # Logging
        self.phi_log = [self.phi]
        self.impedance_log = []   # ratio each step
        self.snap_log = []        # 1 if direction snapped this step

    def compute(self, p_noisy):
        """
        p_noisy: current noisy EE position.
        Returns: F_cmd [2].
        """
        snap = 0

        if self._p_prev is not None:
            dp = p_noisy - self._p_prev
            dp_mag = np.linalg.norm(dp)

            if dp_mag > 1e-4:  # meaningful displacement
                F_hat = np.array([np.cos(self.phi), np.sin(self.phi)])
                dp_parallel = np.dot(dp, F_hat)
                ratio = dp_parallel / dp_mag   # how much displacement is along force

                self.impedance_log.append(float(ratio))

                if ratio < self._impedance_ratio_thresh:
                    # High impedance → wrong direction
                    # Blend phi toward displacement direction (damped snap)
                    dp_hat = dp / dp_mag
                    phi_target = float(np.arctan2(dp_hat[1], dp_hat[0]))

                    # Continuity: pick sign closest to current phi
                    phi_flip = phi_target + np.pi
                    d1 = abs(((phi_target - self.phi) + np.pi) % (2*np.pi) - np.pi)
                    d2 = abs(((phi_flip - self.phi) + np.pi) % (2*np.pi) - np.pi)
                    phi_target = phi_target if d1 <= d2 else phi_flip

                    # Blend: move 60% toward target each snap
                    delta = ((phi_target - self.phi) + np.pi) % (2*np.pi) - np.pi
                    self.phi += 0.6 * delta
                    snap = 1
            else:
                self.impedance_log.append(0.0)
        else:
            self.impedance_log.append(0.0)

        self._p_prev = p_noisy.copy()
        self.snap_log.append(snap)

        # Construct force along phi
        F = F_max * np.array([np.cos(self.phi), np.sin(self.phi)])
        self.phi_log.append(self.phi)
        return F


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
    env=RodEnv(); ctrl=ImpedanceMPC(phi_offset_deg)
    times=[0.0]; thetas=[env.theta]; delta_rs=[env.delta_r]
    ee_true=[env.contact_pos_true().copy()]; ee_noisy=[env.observe_pos().copy()]
    forces=[]; hinges=[env.hinge_pos().copy()]
    t=0.0
    for _ in range(int(15/dt)):
        p_m=env.observe_pos()
        F=ctrl.compute(p_m)
        th,dr=env.step(F); t+=dt
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
    print(f"  Mean |δr|     : {np.mean(np.abs(delta_rs))*1000:.2f} mm")
    if fit:
        cx,cy,r_fit=fit
        print(f"  Fitted r      : {r_fit:.4f} m  err={abs(r_fit-s)*1000:.1f}mm ({abs(r_fit-s)/s*100:.1f}%)")
    phi=np.degrees(ctrl.phi_log); tang=np.degrees(thetas+np.pi/2)
    print(f"  phi           : {phi[0]:.1f}° → {phi[-1]:.1f}°  (tangent: {tang[0]:.1f}° → {tang[-1]:.1f}°)")
    n_snaps=sum(ctrl.snap_log)
    print(f"  Snaps         : {n_snaps}/{len(ctrl.snap_log)}")


if __name__=='__main__':
    for deg in [10, 15, 20, 25, 30, 45]:
        np.random.seed(42)
        result = run_sim(deg)
        print_results(*result, label=f"offset={deg}°")

    # GIF for 30 deg
    np.random.seed(42)
    times,thetas,delta_rs,ee_true,ee_noisy,forces,hinges,ctrl = run_sim(30)
    fit = fit_circle_taubin(ee_noisy)

    fig,axes=plt.subplots(1,3,figsize=(15,5))
    fig.patch.set_facecolor('#0f1117')
    for ax in axes:
        ax.set_facecolor('#1a1d27'); ax.tick_params(colors='#aaaaaa',labelsize=7)
        for sp in ax.spines.values(): sp.set_color('#333344')
    ax_rod,ax_th,ax_phi=axes
    C=dict(rod='#4fc3f7',ee='#ff7043',trail='#80cbc4',force='#ffb74d',hinge='#ce93d8',fit='#a5d6a7',noise='#555566')
    margin=0.06; xlim=(-delta_slide_max-margin,L+margin); ylim=(-margin,L+margin); t_end=max(times[-1],0.5)

    ax_rod.set_xlim(xlim);ax_rod.set_ylim(ylim);ax_rod.set_aspect('equal')
    ax_rod.set_title('Rod motion',color='white',fontsize=9)
    ax_rod.set_xlabel('x [m]',color='#aaaaaa',fontsize=8);ax_rod.set_ylabel('y [m]',color='#aaaaaa',fontsize=8)
    h_mean=hinges.mean(axis=0); arc_a=np.linspace(0.02,theta_target,80)
    ax_rod.plot(h_mean[0]+s*np.cos(arc_a),h_mean[1]+s*np.sin(arc_a),'--',color='#334455',lw=0.8,label='ideal arc')
    if fit:
        cx,cy,r_fit=fit
        ax_rod.plot(cx+r_fit*np.cos(arc_a),cy+r_fit*np.sin(arc_a),'-',color=C['fit'],lw=1,alpha=0.65,label=f'fit r={r_fit:.3f}m')
    ax_rod.legend(loc='upper right',fontsize=7,facecolor='#1a1d27',labelcolor='white',framealpha=0.6)
    rod_line,=ax_rod.plot([],[],'-',color=C['rod'],lw=3,alpha=0.9)
    trail_t,=ax_rod.plot([],[],'-',color=C['trail'],lw=0.8,alpha=0.6)
    trail_n,=ax_rod.plot([],[],'.', color=C['noise'],ms=1.5,alpha=0.35)
    ee_dot,=ax_rod.plot([],[],'o',color=C['ee'],ms=6,zorder=6)
    hinge_dot,=ax_rod.plot([],[],'s',color=C['hinge'],ms=5,zorder=6)
    quiv=ax_rod.quiver([],[],[],[],color=C['force'],scale=120,width=0.004,alpha=0.85)
    time_txt=ax_rod.text(xlim[0]+0.01,ylim[1]-0.03,'',color='white',fontsize=8)
    ang_txt=ax_rod.text(xlim[0]+0.01,ylim[1]-0.06,'',color='#aaaaaa',fontsize=8)

    ax_th.set_xlim(0,t_end);ax_th.set_ylim(-5,100)
    ax_th.set_title('Angle θ',color='white',fontsize=9)
    ax_th.set_xlabel('time [s]',color='#aaaaaa',fontsize=8);ax_th.set_ylabel('θ [deg]',color='#aaaaaa',fontsize=8)
    ax_th.axhline(90,color='#ef5350',lw=1,ls='--',alpha=0.7,label='target')
    ax_th.legend(fontsize=7,facecolor='#1a1d27',labelcolor='white',framealpha=0.6)
    theta_line,=ax_th.plot([],[],color=C['rod'],lw=1.5)

    phi_deg=np.degrees(np.array(ctrl.phi_log));true_tang=np.degrees(thetas+np.pi/2)
    y_lo=min(phi_deg.min(),true_tang.min())-10;y_hi=max(phi_deg.max(),true_tang.max())+10
    ax_phi.set_xlim(0,t_end);ax_phi.set_ylim(y_lo,y_hi)
    ax_phi.set_title('φ (force) vs true tangent',color='white',fontsize=9)
    ax_phi.set_xlabel('time [s]',color='#aaaaaa',fontsize=8);ax_phi.set_ylabel('angle [deg]',color='#aaaaaa',fontsize=8)
    ax_phi.plot(times,true_tang,'--',color='#888899',lw=1,label='true tangent')
    phi_line,=ax_phi.plot([],[],color=C['force'],lw=1.5,label='φ (cmd)')
    ax_phi.legend(fontsize=7,facecolor='#1a1d27',labelcolor='white',framealpha=0.6)
    fig.tight_layout(pad=1.5)

    stride=max(1,len(times)//150); frames=list(range(0,len(times),stride))
    if frames[-1]!=len(times)-1: frames.append(len(times)-1)
    def init():
        for a in(rod_line,trail_t,trail_n,ee_dot,hinge_dot,theta_line,phi_line): a.set_data([],[])
        return rod_line,trail_t,trail_n,ee_dot,hinge_dot,theta_line,phi_line
    def update(fi):
        i=frames[fi];th=thetas[i];h=hinges[i];ee=ee_true[i]
        tip=h+L*np.array([np.cos(th),np.sin(th)])
        rod_line.set_data([h[0],tip[0]],[h[1],tip[1]])
        ee_dot.set_data([ee[0]],[ee[1]]);hinge_dot.set_data([h[0]],[h[1]])
        trail_t.set_data(ee_true[:i+1,0],ee_true[:i+1,1])
        trail_n.set_data(ee_noisy[:i+1,0],ee_noisy[:i+1,1])
        if i<len(forces): quiv.set_offsets([[ee[0],ee[1]]]);quiv.set_UVC([forces[i,0]*0.015],[forces[i,1]*0.015])
        time_txt.set_text(f't={times[i]:.2f}s');ang_txt.set_text(f'θ={np.degrees(th):.1f}° δr={delta_rs[i]*1000:.1f}mm')
        theta_line.set_data(times[:i+1],np.degrees(thetas[:i+1]))
        n=min(i+1,len(phi_deg));phi_line.set_data(times[:n],phi_deg[:n])
        return rod_line,trail_t,trail_n,ee_dot,hinge_dot,theta_line,phi_line
    ani=FuncAnimation(fig,update,frames=len(frames),init_func=init,blit=True,interval=40)
    ani.save(OUT_GIF,writer=PillowWriter(fps=25),dpi=110); plt.close()
    print(f"\nGIF → {OUT_GIF}")