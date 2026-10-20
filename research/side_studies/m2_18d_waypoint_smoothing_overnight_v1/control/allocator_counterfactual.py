"""Algebraic replay of archived allocation inputs, never step physics.

Two-factor swaps are a model decomposition, not physically executable arms.
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
B=load('B0');E=load('18D');h=B['su']['commissioning']['handoff_belief'];he=E['su']['commissioning']['handoff_belief']
assert h['effective_geometry']==he['effective_geometry'];geo=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in h['effective_geometry'].items()});model=BaseParameterHumanModel(geo,np.asarray(h['beta']));al=CuffAwareSagittalAllocator()
arrays={};maxres=0
for qtag,qz in [('B',B),('E',E)]:
 q=qz['estimated_human_state_rad_rad_s'][:,:2]
 for utag,uz in [('B',B),('E',E)]:
  tau=uz['applied_generalized_action_nm'];w=[]
  for qq,uu in zip(q[:-1],tau[:-1]):
   a=al.allocate(uu,qq,model);w.append(a['wrench_world']);maxres=max(maxres,a['equality_residual_nm'])
  arrays[qtag+utag]=np.vstack([w,np.full(6,np.nan)])
tf=B['tf'];f={k:np.linalg.norm(v[:,:3],axis=1) for k,v in arrays.items()};m={k:np.linalg.norm(v[:,3:],axis=1) for k,v in arrays.items()}
# Shapley average over both orders exactly partitions the norm change.
geom=.5*((f['EB']-f['BB'])+(f['EE']-f['BE']));demand=.5*((f['BE']-f['BB'])+(f['EE']-f['EB']));assert np.nanmax(abs(geom+demand-f['EE']+f['BB']))<1e-10
rows={}
for lo,hi in [(0,19.03),(4,6),(15,16),(15,15.5),(15.5,16)]:
 rows[f'{lo}-{hi}']=dict(pure_allocator_force_integrals={k:integ(tf,v,lo,hi) for k,v in f.items()},pure_allocator_moment_integrals={k:integ(tf,v,lo,hi) for k,v in m.items()},delta_E_minus_B=dict(geometry=integ(tf,geom,lo,hi),generalized_action=integ(tf,demand,lo,hi),pure_allocation_total=integ(tf,f['EE']-f['BB'],lo,hi),measured_force=integ(tf,E['f']-B['f'],lo,hi)),generalized_action_mean={n:z['applied_generalized_action_nm'][(tf>=lo)&(tf<hi)].mean(axis=0) for n,z in [('B',B),('E',E)]})
put('derived/ALLOCATOR_INPUT_SWAP.json',dict(scope='Algebraic fixed-input counterfactual on the frozen default Human-point cuff allocator, using each archived causal estimated q and applied generalized action. No physics, no new qualification, no isolated physical causal effect. Total command also includes feedback and Human/robot reference-point shift. Measured force is a contact result and is not equal to this prediction.',geometry_equal=True,equality_residual_max_Nm=maxres,rows=rows))
np.savez_compressed(P/'series/allocator_input_swap.npz',tf=tf,geometry=geom,demand=demand,**arrays)
fig,axs=plt.subplots(3,1,figsize=(14,10),sharex=True,layout='constrained')
axs[0].plot(tf,B['f']-E['f'],label='Measured B − 18D force',c='#238b45');axs[0].plot(tf,f['BB']-f['EE'],label='Pure allocator model B − 18D',c='#762a83',ls='--');axs[0].legend()
axs[1].plot(tf,-geom,label='Geometry input contribution');axs[1].plot(tf,-demand,label='Generalized-action input contribution');axs[1].axhline(0,c='.5');axs[1].legend()
for z,col,lab in [(B,'#2166ac','B'),(E,'#b2182b','18D')]:
 axs[2].plot(z['t'],np.degrees(z['q'][:,0]-z['q'][:,1]),c=col,label=lab+' hip − knee')
for ax in axs:
 ax.set_xlim(0,19.03);ax.grid(alpha=.2)
 for lo,hi in [(4,6),(15,16)]:ax.axvspan(lo,hi,color='#238b45',alpha=.08)
axs[0].set_ylabel('Force benefit [N]');axs[1].set_ylabel('Model force benefit [N]');axs[2].set_ylabel('Coordination angle [deg]');axs[2].set_xlabel('Task elapsed [s]');axs[2].legend();fig.suptitle('Allocator input swaps | algebraic model decomposition, not new physical interventions')
fig.savefig(P/'figures/04_allocator_input_decomposition.png',dpi=170);fig.savefig(P/'figures/04_allocator_input_decomposition.svg')
print(json.dumps(clean(rows),indent=2))
