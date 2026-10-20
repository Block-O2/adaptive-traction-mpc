from pathlib import Path
import os,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1')
a=np.load(P/'motion_series/development_legacy005.npz');b=np.load(P/'motion_series/development_B0.npz');ta=np.load(P/'source/results/development_legacy005/trace.npz');tb=np.load(P/'source/results/development_B0/trace.npz');task=ta['stage']=='TASK';t0=ta['time_s'][task][0];t=a['time_s']-t0;tt=ta['time_s'][task]-t0
plt.rcParams.update({'font.size':8,'figure.dpi':140});fig,axes=plt.subplots(3,2,figsize=(12,8))
for col in range(2):
 axes[0,col].plot(t,np.degrees(b['acceleration_rad_s2'][:,0]),label='B actual hip');axes[0,col].plot(t,np.degrees(a['acceleration_rad_s2'][:,0]),label='+0.05 actual hip');axes[0,col].set_ylabel('Acceleration [deg/s^2]')
 for k in ['base','position','velocity','allocator','clipping']:
  axes[1,col].plot(tt,np.linalg.norm(ta['robot_torque_component_'+k+'_nm'][task]-tb['robot_torque_component_'+k+'_nm'][task],axis=1),label=k)
 axes[1,col].set_ylabel('Torque contribution delta norm [N m]')
 axes[2,col].plot(tt,np.linalg.norm(ta['physical_cuff_force_world_n'][task],axis=1)-np.linalg.norm(tb['physical_cuff_force_world_n'][task],axis=1));axes[2,col].set_ylabel('Cuff force norm - B [N]');axes[2,col].set_xlabel('Task elapsed [s]')
 for ax in axes[:,col]:ax.axvline(5.87,color='k',ls=':',lw=.7);ax.set_xlim((0,19.03) if col==0 else (5.72,6.02))
axes[0,0].legend();axes[1,0].legend();axes[0,0].set_title('Full actual task');axes[0,1].set_title('Downstream anomaly: task 5.87 s = absolute 15.92 s');fig.tight_layout();fig.savefig(P/'figures/downstream_anomaly_torque_components.png');plt.close(fig);print('ANOMALY_FIGURE_SAVED')
