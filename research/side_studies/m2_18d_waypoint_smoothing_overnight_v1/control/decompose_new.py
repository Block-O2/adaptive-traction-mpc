"""Original allocator algebra on stored causal signals; MuJoCo stepping forbidden."""
from pathlib import Path
import os,sys,json
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.path[:0]=[str(P/'code'),str(P/'control')]
import study_common
import mujoco
def forbidden(*a,**k):raise RuntimeError('NO_PHYSICS_IN_ALGEBRAIC_AUDIT')
for name in ['mj_step','mj_step1','mj_step2']:setattr(mujoco,name,forbidden)
from postprocess_targeted import load
from analyze_mechanism import put,integ
from targeted_demand_terms import terms
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry,BaseParameterHumanModel
from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator
import numpy as np
rows=json.loads((P/'ALL_ANALYZED_RESULTS.json').read_text())['rows'];cache={};out=[]
def get(ident):
 if ident not in cache:
  z=load(ident);h=z['su']['commissioning']['handoff_belief'];geo=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in h['effective_geometry'].items()});model=BaseParameterHumanModel(geo,np.asarray(h['beta']));al=CuffAwareSagittalAllocator()
  aa=np.array([al._prepare_factors(q,model).action_to_wrench_world for q in z['estimated_human_state_rad_rad_s'][:-1,:2]]);u=z['applied_generalized_action_nm'][:-1];w=np.einsum('nij,nj->ni',aa,u);cache[ident]=(z,terms(z),aa,u,w,np.linalg.norm(w[:,:3],axis=1))
 return cache[ident]
for r in rows:
 if r['status']!='COMPLETE' or not r['candidate'].get('changes') or r['candidate']['id'].endswith('_zero'):continue
 E,ce,ae,ue,we,ne=get(r['id']);B,cb,ab,ub,wb,nb=get(r['matched_baseline'])
 if E['tf'].shape!=B['tf'].shape or np.max(abs(E['tf']-B['tf']))>1e-8:
  out.append(dict(id=r['id'],status='TIME_GRID_MISMATCH_UNDECOMPOSED'));continue
 p=(wb[:,:3]+we[:,:3])/(nb+ne)[:,None]
 parts={k:np.einsum('ni,ni->n',p,np.einsum('nij,nj->ni',.5*(ab+ae),ce[k]-cb[k])[:,:3]) for k in cb}
 parts['allocation_geometry']=np.einsum('ni,ni->n',p,np.einsum('nij,nj->ni',.5*(ae-ab),ue+ub)[:,:3]);closure=float(np.max(abs(sum(parts.values())-(ne-nb))));assert closure<1e-10
 windows={}
 for lo,hi in [(0,float(B['tf'][-1])),(4,6),(15,16)]+[tuple(c['local_window_task_s']) for c in r['candidate']['changes']]:
  mask=(B['tf'][:-1]>=lo)&(B['tf'][:-1]<hi)
  windows[f'{lo:.6f}-{hi:.6f}']=dict(pure_allocator_delta_components_N_s={k:integ(B['tf'],np.r_[v,0],lo,hi) for k,v in parts.items()},pure_allocator_delta_N_s=integ(B['tf'],np.r_[ne-nb,0],lo,hi),measured_delta_N_s=integ(B['tf'],E['f']-B['f'],lo,hi),model_term_mean_delta_Nm={k:(ce[k]-cb[k])[mask].mean(axis=0) for k in cb},actual_q_mean_delta_deg=np.degrees((E['q'][::20][:-1]-B['q'][::20][:-1])[mask].mean(axis=0)),command_torque_component_delta_RMS_Nm={k:np.sqrt(np.mean((E['robot_torque_component_'+k+'_nm'][:-1][mask]-B['robot_torque_component_'+k+'_nm'][:-1][mask])**2,axis=0)) for k in ['base','position','velocity','allocator','clipping']})
 out.append(dict(id=r['id'],status='PASS',closure_N=closure,max_beta_delta=float(np.max(abs(E['beta']-B['beta']))),windows=windows))
put('derived/NEW_DEMAND_DECOMPOSITION.json',dict(rows=out,physics_starts=0,scope='algebraic model-demand accounting, not independent causal mediation; remainder includes inertia/tracking/soft-limit/residual/safety terms',stepping_forbidden=True))
print('ALGEBRAIC_CASES',len(out))
