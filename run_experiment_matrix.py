"""
实验矩阵脚本 v2 — 基于 v13 架构
4×3×2 factorial design:
  - 材料(ks): 10, 30, 50, 100 N/m
  - 弧角(arc): 30°, 60°, 90°
  - 速度权重(W_TIME): 0.5, 2.0
共 24 组，结果写入 results_v2.csv

v13 核心改动：
- stretch 硬约束加入 MPC（直接约束形变，不依赖 ks 精度）
- force_bounds 恢复干净版本（力约束独立安全网）
- settle 安全检查用位移增量（不依赖 L0_est）
- SETTLE_STEPS 动态适配各 ks
"""
import matplotlib
matplotlib.use('Agg')
import numpy as np
import csv
import warnings
warnings.filterwarnings('ignore')
from scipy.optimize import minimize
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel
from scipy.stats import t as student_t

# ══════════════════════════════════════════════════════
# 固定系统参数
# ══════════════════════════════════════════════════════
dt         = 0.05
b_true     = 0.5
m_true     = 0.05
L0_true    = 0.5
anchor     = np.array([0.0, 0.0, 0.0])
f_max_safe = 3.0
noise_std  = 0.1

W_FORCE  = 30.0
W_INPUT  = 0.0
W_ANGLE  = 10.0
V_MAX    = 0.3
V_MIN    = 0.05
V_RAMP   = 60
MPC_N    = 6
R_TOL        = 0.04
R_REF_UPDATE = 20
ARC_WARMUP_STEPS = 20
V_WARMUP         = 0.02
SETTLE_SPEED     = 0.06
GPR_MIN_DATA     = 20

# 每种 ks 的 settle 参数（STRETCH_MAX 也随 ks 动态设定）
_KS_PARAMS = {
    10:  dict(AMP=0.20, KS_MIN=7.5,  STEPS=130, STRETCH_MAX=0.20),
    30:  dict(AMP=0.07, KS_MIN=22.5, STEPS=130, STRETCH_MAX=0.07),
    50:  dict(AMP=0.05, KS_MIN=37.5, STEPS=130, STRETCH_MAX=0.06),
    100: dict(AMP=0.02, KS_MIN=40.0, STEPS=260, STRETCH_MAX=0.02),
}

# ══════════════════════════════════════════════════════
# 类定义
# ══════════════════════════════════════════════════════
class BOCD:
    def __init__(self, hazard=0.05, mu0=0.0, kappa0=1., alpha0=3., beta0=0.5):
        self.h=hazard; self.mu0=mu0; self.kappa0=kappa0
        self.alpha0=alpha0; self.beta0=beta0
        self.mu=np.array([mu0]); self.kappa=np.array([kappa0])
        self.alpha=np.array([alpha0]); self.beta=np.array([beta0])
        self.R=np.array([1.]); self.prev_mode_r=0
    def update(self, x):
        df=2*self.alpha
        scale=np.maximum(np.sqrt(self.beta*(self.kappa+1)/(self.alpha*self.kappa)),1e-10)
        lp=np.clip(student_t.logpdf(x,df=df,loc=self.mu,scale=scale),-50,50)
        pi=np.exp(lp)
        Rn=np.empty(len(self.R)+1)
        Rn[0]=np.sum(self.R*pi)*self.h; Rn[1:]=self.R*pi*(1-self.h)
        s=Rn.sum(); Rn=Rn/s if s>0 else np.array([1.]+[0.]*len(self.R))
        self.R=Rn
        mode_r=int(np.argmax(Rn))
        sig=max(0, self.prev_mode_r-mode_r)/max(1, self.prev_mode_r)
        self.prev_mode_r=mode_r
        kn=self.kappa+1; mn=(self.kappa*self.mu+x)/kn
        an=self.alpha+0.5; bn=self.beta+self.kappa*(x-self.mu)**2/(2*kn)
        self.mu=np.append([self.mu0],mn); self.kappa=np.append([self.kappa0],kn)
        self.alpha=np.append([self.alpha0],an); self.beta=np.append([self.beta0],bn)
        return sig

class RLS:
    def __init__(self, lam=0.97, lam_settle=0.88):
        self.lam=lam; self.lam_settle=lam_settle; self.lam_cur=lam_settle
        self.theta=np.array([10.0,0.3,0.05]); self.P=np.diag([100.,3.,1.])
    def set_lam(self, lam): self.lam_cur=lam
    def update(self, phi, y, stretch_delta=None):
        if stretch_delta is not None and abs(stretch_delta)<1e-3:
            return self.theta.copy()
        e=y-phi@self.theta; d=self.lam_cur+phi@self.P@phi
        K=self.P@phi/d; self.theta+=K*e
        self.P=(1./self.lam_cur)*(np.eye(3)-np.outer(K,phi))@self.P
        self.theta=np.clip(self.theta,[0.05,0.,0.],[200.,5.,2.])
        return self.theta.copy()
    def force_bounds(self, f_taut):
        return 0.95*f_taut, min(2.5*f_taut, f_max_safe)

class GPRModel:
    def __init__(self, max_data=80):
        k=(ConstantKernel(1.,(0.1,10.))*RBF(length_scale=[0.05,0.05,0.5],
           length_scale_bounds=[(0.005,1.),(0.005,1.),(0.05,5.)])
           +WhiteKernel(0.1,(1e-3,1.)))
        self.gpr=GaussianProcessRegressor(kernel=k,n_restarts_optimizer=0,normalize_y=True)
        self.X=[]; self.y=[]; self.fitted=False
        self.xm=np.zeros(3); self.xs=np.ones(3); self.max_data=max_data
    def add_data(self,s,v,theta,f):
        self.X.append([s,v,theta]); self.y.append(f)
        if len(self.X)>self.max_data: self.X.pop(0); self.y.pop(0)
    def fit(self):
        if len(self.X)<15: return
        X=np.array(self.X); self.xm=X.mean(0); self.xs=X.std(0)+1e-6
        self.gpr.fit((X-self.xm)/self.xs,np.array(self.y)); self.fitted=True
    def predict(self,s,v,theta):
        if not self.fitted: return None,None
        xn=(np.array([[s,v,theta]])-self.xm)/self.xs
        mu,sig=self.gpr.predict(xn,return_std=True)
        return float(mu[0]),float(sig[0])

def retract_velocity(p_cur, anchor_est, speed=0.1):
    d=anchor_est-p_cur; n=np.linalg.norm(d)
    return np.zeros(3) if n<1e-6 else d/n*speed

def run_mpc_3d(p_cur, v_cur, ks_eff, b_rls, m_rls,
               anchor_est, L0_est, theta_cur, theta_target,
               f_taut, f_lower, f_upper, STRETCH_MAX,
               sigma_gpr=0., v_max_cur=0.1, R_ref=None, W_TIME=0.5):
    f_max_eff=max(f_upper-2.0*np.clip(sigma_gpr,0.,0.5), f_taut*1.1)
    if R_ref is None: R_ref=np.linalg.norm(p_cur-anchor_est)

    def pf(p_,v_,a_):
        stretch_=max(0.,np.linalg.norm(p_-anchor_est)-L0_est)
        return max(0.,ks_eff*stretch_+b_rls*np.linalg.norm(v_)+m_rls*np.linalg.norm(a_))
    pf_fast=pf

    def cost(u_flat):
        u_seq=u_flat.reshape(MPC_N,3); p=p_cur.copy(); v=v_cur.copy(); c=0.
        f_mid=0.7*f_lower+0.3*f_max_eff; W_MID=3.0
        for k in range(MPC_N):
            vk=u_seq[k]; ak=(vk-v)/dt; pn=p+dt*vk
            f_pred=pf(pn,vk,ak)
            c+=W_FORCE*max(0,f_lower-f_pred)**2+W_FORCE*max(0,f_pred-f_max_eff)**2
            c+=W_MID*(f_pred-f_mid)**2+W_TIME
            tn=np.arctan2(pn[1]-anchor_est[1],pn[0]-anchor_est[0])
            pg=tn-theta_cur
            if pg<-np.pi: pg+=2*np.pi
            c-=W_ANGLE*np.clip(pg,0.,0.15); p=pn; v=vk
        f_t=pf(p,v,np.zeros(3)); f_mid2=0.7*f_lower+0.3*f_max_eff
        c+=W_FORCE*max(0,f_lower-f_t)**2+W_FORCE*max(0,f_t-f_max_eff)**2
        c+=W_MID*(f_t-f_mid2)**2
        return c

    cons=[]
    for k in range(MPC_N):
        def make_upper(k_=k):
            def fn(u):
                p=p_cur.copy(); v=v_cur.copy()
                for i in range(k_+1): v=u.reshape(MPC_N,3)[i]; p=p+dt*v
                return f_max_eff-pf_fast(p,v,np.zeros(3))
            return fn
        def make_lower(k_=k):
            def fn(u):
                p=p_cur.copy(); v=v_cur.copy()
                for i in range(k_+1): v=u.reshape(MPC_N,3)[i]; p=p+dt*v
                return pf_fast(p,v,np.zeros(3))-f_lower
            return fn
        def make_rad_up(k_=k):
            def fn(u):
                p=p_cur.copy(); v=v_cur.copy()
                for i in range(k_+1): v=u.reshape(MPC_N,3)[i]; p=p+dt*v
                return R_ref+R_TOL-np.linalg.norm(p-anchor_est)
            return fn
        def make_rad_lo(k_=k):
            def fn(u):
                p=p_cur.copy(); v=v_cur.copy()
                for i in range(k_+1): v=u.reshape(MPC_N,3)[i]; p=p+dt*v
                return np.linalg.norm(p-anchor_est)-(R_ref-R_TOL)
            return fn
        def make_stretch_up(k_=k):
            def fn(u):
                p=p_cur.copy(); v=v_cur.copy()
                for i in range(k_+1): v=u.reshape(MPC_N,3)[i]; p=p+dt*v
                return STRETCH_MAX-max(0.,np.linalg.norm(p-anchor_est)-L0_est)
            return fn
        cons.append({'type':'ineq','fun':make_upper(k)})
        cons.append({'type':'ineq','fun':make_lower(k)})
        cons.append({'type':'ineq','fun':make_rad_up(k)})
        cons.append({'type':'ineq','fun':make_rad_lo(k)})
        cons.append({'type':'ineq','fun':make_stretch_up(k)})

    tang=np.array([-np.sin(theta_cur),np.cos(theta_cur),0.])
    u0=np.tile(tang*0.05,MPC_N)
    res=minimize(cost,u0,method='SLSQP',
                 bounds=[(-v_max_cur,v_max_cur)]*(MPC_N*3),
                 constraints=cons,options={'maxiter':40,'ftol':2e-3})
    u_out=res.x.reshape(MPC_N,3)[0]
    return u_out if (res.success or res.fun<1e8) else tang*0.02

# ══════════════════════════════════════════════════════
# 单次仿真函数
# ══════════════════════════════════════════════════════
def run_sim(ks, arc_deg, w_time, seed=42):
    np.random.seed(seed)
    ks_true_  = ks
    arc_rad   = np.radians(arc_deg)
    p = _KS_PARAMS.get(ks, dict(AMP=min(0.70*f_max_safe/ks,0.20),
                                 KS_MIN=0.75*ks, STEPS=130,
                                 STRETCH_MAX=min(0.70*f_max_safe/ks,0.20)))
    SETTLE_AMP_      = p['AMP']
    KS_MIN_          = p['KS_MIN']
    SETTLE_STEPS_    = p['STEPS']
    STRETCH_MAX_     = p['STRETCH_MAX']

    def true_force_3d_(pos, vel=0.0, acc=0.0):
        d=pos-anchor; dist=np.linalg.norm(d)
        noise=np.random.normal(0,noise_std,3)
        if dist<1e-6: return noise
        stretch=max(0.,dist-L0_true)
        f=max(0.,ks_true_*stretch+b_true*vel+m_true*acc)
        if f<1e-6: return noise
        return f*d/dist+noise

    theta_start=np.radians(-20); theta_target=theta_start+arc_rad
    R_init=L0_true*0.35
    p_cur=anchor+R_init*np.array([np.cos(theta_start),np.sin(theta_start),0.])
    v_cur=np.zeros(3); v_prev=np.zeros(3)
    L0_est=R_init*0.8; anchor_est=anchor.copy()

    bocd=BOCD(); rls=RLS(); gpr=GPRModel()
    phase=0; taut_step=None; arc_step=None
    arc_steps=0; settle_steps_done=0; settle_base_dist=0.
    f_taut=0.2; f_lower=0.1; f_upper=1.0
    sigma_s=0.; R_ref=None; st_prev=0.
    ks_settle_val=None; ks_final_val=None

    hp=[p_cur.copy()]; hf=[]
    f_cur=true_force_3d_(p_cur)

    for t in range(1500):
        fm=np.linalg.norm(f_cur); hf.append(fm)
        sig=bocd.update(fm)
        theta_cur=np.arctan2(p_cur[1]-anchor_est[1],p_cur[0]-anchor_est[0])

        if phase==0 and sig>0.35:
            phase=1; taut_step=t; settle_steps_done=0
            f_taut=max(fm,0.1); f_lower,f_upper=rls.force_bounds(f_taut)
            ks_guess=max(rls.theta[0],1.0)
            L0_est=max(0.05,np.linalg.norm(p_cur-anchor_est)-fm/ks_guess)
            settle_base_dist=np.linalg.norm(p_cur-anchor_est)

        if phase==1:
            ks_conv=rls.theta[0]>KS_MIN_
            s_done=settle_steps_done>=SETTLE_STEPS_
            if ks_conv or s_done:
                phase=2; arc_step=t
                if ks_conv:
                    ks_now=rls.theta[0]; dist_now=np.linalg.norm(p_cur-anchor_est)
                    L0_est=max(0.05,dist_now-fm/ks_now); ks_settle_val=ks_now
                else:
                    ks_settle_val=rls.theta[0]
                rls.set_lam(rls.lam)
                R_ref=np.linalg.norm(p_cur-anchor_est)
                st_prev=max(0.,np.linalg.norm(p_cur-anchor_est)-L0_est)

        if phase==2 and theta_cur>=theta_target-0.03:
            ks_final_val=rls.theta[0]; break

        if fm>=f_max_safe and phase==2:
            u=retract_velocity(p_cur,anchor_est,speed=0.1)
            v_prev=v_cur.copy(); v_cur=u.copy()
            pn=p_cur+dt*u
            f_cur=true_force_3d_(pn,np.linalg.norm(u),np.linalg.norm((u-v_prev)/dt))
            p_cur=pn; hp.append(p_cur.copy()); continue

        if phase==0:
            dist=np.linalg.norm(p_cur-anchor_est); dn=(p_cur-anchor_est)/(dist+1e-6)
            sp=0.15*max(0.3,1.4-dist/(L0_true*1.3)); u=dn*sp
        elif phase==1:
            dist=np.linalg.norm(p_cur-anchor_est); dn=(p_cur-anchor_est)/(dist+1e-6)
            disp_from_base=dist-settle_base_dist
            if disp_from_base>SETTLE_AMP_*0.9 or fm>f_max_safe*0.8:
                target_dist=settle_base_dist
            else:
                half=SETTLE_STEPS_/2
                if settle_steps_done<half:
                    target_dist=settle_base_dist+SETTLE_AMP_*(settle_steps_done/half)
                else:
                    target_dist=settle_base_dist+SETTLE_AMP_*(2-settle_steps_done/half)
            err=target_dist-dist
            u=dn*np.clip(err/dt,-SETTLE_SPEED,SETTLE_SPEED)
            settle_steps_done+=1
            st=max(0.,dist-L0_est); vs=np.linalg.norm(v_cur)
            ac=np.linalg.norm((v_cur-v_prev)/dt)
            phi=np.array([st,vs,ac]); trls=rls.update(phi,fm)
            f_lower,f_upper=rls.force_bounds(f_taut); f_upper=min(f_upper,f_max_safe)
            gpr.add_data(st,vs,theta_cur,fm)
            if len(gpr.X)>=15 and t%5==0: gpr.fit()
        else:
            d=p_cur-anchor_est; dist=np.linalg.norm(d)
            st=max(0.,dist-L0_est); vs=np.linalg.norm(v_cur)
            ac=np.linalg.norm((v_cur-v_prev)/dt)
            phi=np.array([st,vs,ac])
            stretch_delta=st-st_prev
            trls=rls.update(phi,fm,stretch_delta=stretch_delta); st_prev=st
            f_lower,f_upper=rls.force_bounds(f_taut); f_upper=min(f_upper,f_max_safe)
            if trls[0]>KS_MIN_ and fm>f_taut*0.5:
                L0_est_new=max(0.05,dist-fm/trls[0])
                L0_est=0.9*L0_est+0.1*L0_est_new
            if arc_steps%R_REF_UPDATE==0: R_ref=0.8*R_ref+0.2*dist
            gpr.add_data(st,vs,theta_cur,fm)
            if t%15==0: gpr.fit()
            _,sr=gpr.predict(st,vs,theta_cur)
            if sr is None: sr=0.
            sigma_s=0.2*sr+0.8*sigma_s
            b_rls,m_rls=trls[1],trls[2]
            if arc_steps<ARC_WARMUP_STEPS: v_max_cur=V_WARMUP
            else: v_max_cur=min(V_MIN+(V_MAX-V_MIN)*((arc_steps-ARC_WARMUP_STEPS)/V_RAMP),V_MAX)
            arc_steps+=1
            u=run_mpc_3d(p_cur,v_cur,trls[0],b_rls,m_rls,
                         anchor_est,L0_est,theta_cur,theta_target,
                         f_taut,f_lower,f_upper,STRETCH_MAX_,
                         sigma_gpr=sigma_s,v_max_cur=v_max_cur,
                         R_ref=R_ref,W_TIME=w_time)

        v_prev=v_cur.copy(); v_cur=u.copy()
        pn=p_cur+dt*u
        vs2=float(np.linalg.norm(u)); as2=float(np.linalg.norm((u-v_prev)/dt))
        f_cur=true_force_3d_(pn,vs2,as2); p_cur=pn; hp.append(p_cur.copy())

    hp_arr=np.array(hp); hf_arr=np.array(hf)
    if arc_step is None:
        return {'ks':ks,'arc_deg':arc_deg,'w_time':w_time,'status':'FAILED',
                'ks_settle':'N/A','ks_final':'N/A','ks_settle_err':'N/A',
                'ks_final_err':'N/A','rms':'N/A','viol':'N/A',
                'r_mean':'N/A','r_std':'N/A'}
    fc=hf_arr[arc_step:]
    rms=float(np.sqrt(np.mean((fc-f_taut)**2)))
    viol=float(np.mean(fc>f_max_safe)*100)
    pts2d=hp_arr[arc_step+ARC_WARMUP_STEPS:,:2]
    dists=np.linalg.norm(pts2d-anchor[:2],axis=1)
    r_mean=float(np.mean(dists)); r_std=float(np.std(dists))
    ks_se=round(abs(ks_settle_val-ks_true_)/ks_true_*100,1) if ks_settle_val else 'N/A'
    ks_fe=round(abs(ks_final_val-ks_true_)/ks_true_*100,1) if ks_final_val else 'N/A'
    status='OK' if (ks_final_val and ks_final_val<150) else 'KS_OVERFLOW'
    return {'ks':ks,'arc_deg':arc_deg,'w_time':w_time,'status':status,
            'ks_settle':round(ks_settle_val,1) if ks_settle_val else 'N/A',
            'ks_final': round(ks_final_val,1)  if ks_final_val  else 'N/A',
            'ks_settle_err':ks_se,'ks_final_err':ks_fe,
            'rms':round(rms,4),'viol':round(viol,2),
            'r_mean':round(r_mean,4),'r_std':round(r_std,5)}

# ══════════════════════════════════════════════════════
# 实验矩阵
# ══════════════════════════════════════════════════════
ks_list     = [10, 30, 50, 100]
arc_list    = [30, 60, 90]
w_time_list = [0.5, 2.0]

results=[]; total=len(ks_list)*len(arc_list)*len(w_time_list); count=0
print("="*65)
print(f"实验矩阵 v2：{total}组  v13架构（stretch硬约束）")
print("="*65)

for ks in ks_list:
    for arc_deg in arc_list:
        for w_time in w_time_list:
            count+=1
            print(f"[{count:2d}/{total}] ks={ks:3d}  arc={arc_deg:2d}°  w_time={w_time} ...",
                  end=' ', flush=True)
            r=run_sim(ks,arc_deg,w_time)
            results.append(r)
            print(f"RMS={r['rms']}  viol={r['viol']}%  R_std={r['r_std']}  [{r['status']}]")

fields=['ks','arc_deg','w_time','ks_settle','ks_final','ks_settle_err',
        'ks_final_err','rms','viol','r_mean','r_std','status']
with open('results_v2.csv','w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields)
    writer.writeheader(); writer.writerows(results)

print(f"\n结果已写入 results_v2.csv")
print("="*65)
print("\n[汇总] 按 ks 分组平均 RMS 和 R_std：")
for ks in ks_list:
    grp=[r for r in results if r['ks']==ks and r['status']=='OK']
    if grp:
        avg_rms=np.mean([r['rms'] for r in grp])
        avg_rstd=np.mean([r['r_std'] for r in grp])
        print(f"  ks={ks:3d}: RMS={avg_rms:.4f}N  R_std={avg_rstd:.5f}m  ({len(grp)}组)")