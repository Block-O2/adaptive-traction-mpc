from pathlib import Path
import os,sys,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1');sys.path.insert(0,str(P/'code'));sys.path.insert(0,str(P/'control'))
import study_common
from postprocess_targeted import load
from analyze_mechanism import put,integ,clean
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry,BaseParameterHumanModel
from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator
import numpy as np
def terms(z):
 q=z['estimated_human_state_rad_rad_s'][:-1,:2];v=z['estimated_human_state_rad_rad_s'][:-1,2:];be=z['beta'][:-1];phi=q[:,0]-q[:,1]
 g=np.c_[be[:,3]*np.cos(q[:,0])+be[:,4]*np.cos(phi),-be[:,4]*np.cos(phi)];e=np.c_[be[:,5]*q[:,0]-be[:,7],be[:,6]*q[:,1]-be[:,8]]
 vel=np.c_[be[:,2]*np.sin(q[:,1])*(-2*v[:,0]*v[:,1]+v[:,1]**2)+be[:,9]*v[:,0],be[:,2]*np.sin(q[:,1])*v[:,0]**2+be[:,10]*v[:,1]]
 return dict(gravity=g,elastic=e,velocity_terms=vel,remainder=z['applied_generalized_action_nm'][:-1]-g-e-vel)
def main():
 B=load('targeted2_B0');h=B['su']['commissioning']['handoff_belief'];geo=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in h['effective_geometry'].items()});model=BaseParameterHumanModel(geo,np.asarray(h['beta']));al=CuffAwareSagittalAllocator();cb=terms(B);ab=np.array([al._prepare_factors(q,model).action_to_wrench_world for q in B['estimated_human_state_rad_rad_s'][:-1,:2]]);ub=B['applied_generalized_action_nm'][:-1];wb=np.einsum('nij,nj->ni',ab,ub);normb=np.linalg.norm(wb[:,:3],axis=1);rows=[]
 candidates=[json.loads(l) for l in (P/'CANDIDATE_RESULTS.jsonl').read_text().splitlines()]
 for r in candidates:
  if r['status']!='COMPLETE' or 'local' not in r or r['candidate']['id'].endswith('zero'):continue
  E=load(r['id']);ce=terms(E);ae=np.array([al._prepare_factors(q,model).action_to_wrench_world for q in E['estimated_human_state_rad_rad_s'][:-1,:2]]);ue=E['applied_generalized_action_nm'][:-1];we=np.einsum('nij,nj->ni',ae,ue);norme=np.linalg.norm(we[:,:3],axis=1);proj=(wb[:,:3]+we[:,:3])/(normb+norme)[:,None]
  parts={k:np.einsum('ni,ni->n',proj,np.einsum('nij,nj->ni',.5*(ab+ae),ce[k]-cb[k])[:,:3]) for k in cb};parts['allocation_geometry']=np.einsum('ni,ni->n',proj,np.einsum('nij,nj->ni',.5*(ae-ab),ue+ub)[:,:3]);assert np.max(abs(sum(parts.values())-(norme-normb)))<1e-10
  lo,hi=r['candidate']['local_window_task_s'];windows={}
  for name,(a,b) in [('support',(lo,hi)),('full',(0,B['tf'][-1]))]:
   windows[name]=dict(delta_force_integral_N_s={k:integ(B['tf'],np.r_[v,v[-1]],a,b) for k,v in parts.items()},pure_allocator_delta=integ(B['tf'],np.r_[norme-normb,0],a,b),measured_delta=integ(B['tf'],E['f']-B['f'],a,b))
  rows.append(dict(id=r['id'],windows=windows))
 put('derived/TARGETED_DEMAND_TERMS.json',dict(rows=rows,scope='Exact algebraic decomposition of original pure allocator applied to stored causal estimated q and requested generalized action. Remainder contains inertia, tracking, soft limit, residual and safety corrections; no isolated smoothness mediation.'))
 print(json.dumps(clean(rows),indent=2))
if __name__=='__main__':main()
