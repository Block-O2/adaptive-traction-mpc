"""Exact algebraic partition of pure allocator norm difference.

Gravity / elastic / velocity terms follow the frozen regressor. The remainder
is explicitly not labeled as a directly measured acceleration-only term.
"""
from pathlib import Path
import os,sys,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1');sys.path.insert(0,str(P/'code'));sys.path.insert(0,str(P/'control'))
import study_common
from analyze_mechanism import load,put,integ,clean
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry,BaseParameterHumanModel
from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator
import numpy as np
import matplotlib.pyplot as plt
B=load('B0');E=load('18D');h=B['su']['commissioning']['handoff_belief'];geo=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in h['effective_geometry'].items()});model=BaseParameterHumanModel(geo,np.asarray(h['beta']));al=CuffAwareSagittalAllocator()
def components(z):
 q=z['estimated_human_state_rad_rad_s'][:-1,:2];v=z['estimated_human_state_rad_rad_s'][:-1,2:];be=z['beta'][:-1];phi=q[:,0]-q[:,1]
 gravity=np.c_[be[:,3]*np.cos(q[:,0])+be[:,4]*np.cos(phi),-be[:,4]*np.cos(phi)]
 elastic=np.c_[be[:,5]*q[:,0]-be[:,7],be[:,6]*q[:,1]-be[:,8]]
 velocity=np.c_[be[:,2]*np.sin(q[:,1])*(-2*v[:,0]*v[:,1]+v[:,1]**2)+be[:,9]*v[:,0],be[:,2]*np.sin(q[:,1])*v[:,0]**2+be[:,10]*v[:,1]]
 action=z['applied_generalized_action_nm'][:-1]
 return dict(gravity=gravity,elastic=elastic,velocity_terms=velocity,remainder=action-gravity-elastic-velocity)
cb=components(B);ce=components(E);ab=np.array([al._prepare_factors(q,model).action_to_wrench_world for q in B['estimated_human_state_rad_rad_s'][:-1,:2]]);ae=np.array([al._prepare_factors(q,model).action_to_wrench_world for q in E['estimated_human_state_rad_rad_s'][:-1,:2]])
ub=B['applied_generalized_action_nm'][:-1];ue=E['applied_generalized_action_nm'][:-1];wb=np.einsum('nij,nj->ni',ab,ub);we=np.einsum('nij,nj->ni',ae,ue)
normb=np.linalg.norm(wb[:,:3],axis=1);norme=np.linalg.norm(we[:,:3],axis=1);projection=(wb[:,:3]+we[:,:3])/(normb+norme)[:,None]
parts={k:np.einsum('ni,ni->n',projection,np.einsum('nij,nj->ni',.5*(ab+ae),ce[k]-cb[k])[:,:3]) for k in cb}
parts['allocation_geometry']=np.einsum('ni,ni->n',projection,np.einsum('nij,nj->ni',.5*(ae-ab),ue+ub)[:,:3])
closure=np.max(abs(sum(parts.values())-(norme-normb)));assert closure<1e-10
tf=B['tf'];rows={}
for lo,hi in [(0,19.03),(0,9.005),(10.025,19.03),(4,6),(15,16),(15,15.5),(15.5,16)]:
 sel=(tf[:-1]>=lo)&(tf[:-1]<hi)
 rows[f'{lo}-{hi}']=dict(E_minus_B_force_N_s={k:integ(tf,np.r_[v,v[-1]],lo,hi) for k,v in parts.items()},mean_tau_terms={n:{k:v[sel].mean(axis=0) for k,v in c.items()} for n,c in [('B',cb),('18D',ce)]})
put('derived/DEMAND_TERM_DECOMPOSITION.json',dict(rows=rows,closure_N=closure,beta_task_range_B=np.ptp(B['beta'],axis=0),beta_task_range_18D=np.ptp(E['beta'],axis=0),max_paired_beta_delta=np.max(abs(B['beta']-E['beta'])),formula='delta norm = (F_E+F_B)/(norm_E+norm_B) dot delta F. delta W split exactly into mean(A)*delta(tau_terms) + delta(A)*mean(tau). A is original pure allocator mapping. This differs from norm-level two-factor Shapley but both sums close exactly.',term_scope='gravity: beta[3,4] cos terms; elastic: beta[5:9] angle/rest-offset terms; velocity: Coriolis plus beta[9,10] damping; remainder: all remaining requested action including inertia, feedback, soft limit, learned residual and safety correction; not an independently measured causal effect.',model_scope='Frozen commissioned estimated Human model and original allocation geometry. Explains model-demand changes; does not identify independently manipulable physical mediation.'))
fig,axs=plt.subplots(3,1,figsize=(15,11),layout='constrained')
for ax,(lo,hi) in zip(axs,[(0,19.03),(4,6),(15,16)]):
 for k,v in parts.items():ax.plot(tf[:-1],-v,label=k)
 ax.plot(tf[:-1],normb-norme,c='black',ls='--',lw=1,label='pure allocation total');ax.set_xlim(lo,hi);ax.axhline(0,c='.5');ax.grid(alpha=.2);ax.set_ylabel('B − 18D force [N]');ax.set_xlabel('Task elapsed [s]')
axs[0].legend(ncol=3);fig.suptitle('Model-demand decomposition | exact algebraic closure; model terms, not isolated physical effects');fig.savefig(P/'figures/05_demand_term_decomposition.png',dpi=170);fig.savefig(P/'figures/05_demand_term_decomposition.svg')
np.savez_compressed(P/'series/demand_terms.npz',tf=tf[:-1],**parts)
print(json.dumps(clean({k:v['E_minus_B_force_N_s'] for k,v in rows.items()}),indent=2))
