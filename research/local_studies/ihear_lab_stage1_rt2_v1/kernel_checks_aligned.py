"""Supplementary software characterization; frozen laws, no new physics."""
from env_rt2 import *
from software_aligned import reconstruct
from reactive import *
import time
from types import SimpleNamespace
def main():
    times={k:[] for k in ('I','II','III')};apex={};max_common=0.
    for i,k,path,s,p,d,e in reconstruct():
        if e['phase'].value=='HOLD' or path.duration_s-s<DT-1e-12:continue
        obs=observe(e['belief'].human_model(),e['x'],e['wrench'],e['owned'],e['vmax'],e['amax'],e['span'],e['sign'])
        vel=path.sample(s+DT).dq_rad_s;flags=np.ones(2,dtype=bool);old=np.zeros(2)
        for name,law,args in [('I',Governor(),(obs,vel,DT)),('II',Analytical(),(obs,vel,DT,flags)),('III',QP(),(obs,vel,DT,flags,old))]:
            start=time.monotonic_ns();act=law.action(*args);times[name].append((time.monotonic_ns()-start)/1e6)
            if name=='II':max_common=max(max_common,abs(np.sum(act/obs.span)))
        occupancy=float(np.max(abs(vel)/obs.vmax))
        if not apex or occupancy>apex['fraction']:apex=dict(fraction=occupancy,i=i,k=k)
    # Exact held-axis fixture: one component of q,dq,ddq is identically constant.
    class Affine:
        def sample(self,t):return SimpleNamespace(q_rad=np.array([1.,1.+obs.sign*.10*t]),dq_rad_s=np.array([0.,obs.sign*.1]),ddq_rad_s2=np.zeros(2))
    hcases={}
    for kind in times:
        fun,state=target(kind,obs,Affine(),0.,DT,mobile=np.array([False,True]))
        hcases[kind]=max(max(abs(qq[0]-1.),abs(vv[0]),abs(aa[0])) for qq,vv,aa in (fun(DT*u) for u in np.linspace(0,1,9)))
    save(HERE/'kernel_checks.json',dict(raw_ms=times,max_common_velocity_sum=max_common,held_axis_max_error=hcases,highest_nominal_v_fraction=apex))
if __name__=='__main__':main()
